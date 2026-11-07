# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The transfer's mirrors (ADR 0035, glossary "Legacy glue").

The legacy module keeps the WMS state on the moves (a substate each) and
derives the transfer's; the bridge keeps it on the transfer only (ADR 0003).
The glue computes the bridge field from the moves with the legacy rule,
refused wins, then cancelled, then the first move, and writes every move when
the connector writes the transfer: one value, the legacy module's.
"""
from odoo import api, fields, models

from .channel import legacy_channel
from .stock_move import CONNECTOR_GROUP


class StockPicking(models.Model):
    _inherit = "stock.picking"

    ezy_hold = fields.Boolean(related="is_blocked_for_logistics", store=True, readonly=False)
    ezy_wms_state = fields.Selection(
        compute="_compute_ezy_wms_state_from_legacy",
        inverse="_inverse_ezy_wms_state_to_legacy",
        store=True,
        readonly=False,
    )
    ezy_channel = fields.Char(
        compute="_compute_ezy_channel_from_legacy",
        inverse="_inverse_ezy_channel_to_legacy",
        store=True,
        readonly=False,
    )

    def _ezy_glue_previous_states(self):
        """The value each transfer held before this compute: the one in the
        cache when the transaction already read or wrote it (a write of the
        bridge field in this transaction counts, flushed or not), else the
        stored one. So a transfer written ready by the connector and recomputed
        before the flush does not read as entering twice."""
        field = self._fields["ezy_wms_state"]
        cache = self.env.cache
        previous, unread = {}, []
        for picking in self:
            if not picking.id:
                continue
            if cache.contains(picking, field):
                previous[picking.id] = cache.get(picking, field)
            else:
                unread.append(picking.id)
        if unread:
            self.env.cr.execute(
                "SELECT id, ezy_wms_state FROM stock_picking WHERE id = ANY(%s)", (unread,)
            )
            previous.update(self.env.cr.fetchall())
        return previous

    @api.depends("move_ids.textual_substate")
    def _compute_ezy_wms_state_from_legacy(self):
        # The transfers entering ready for logistics through the legacy module
        # wake the connector the way a write of the bridge field does
        # (behaviour 9, ADR 0006); the install's backfill wakes nobody, the
        # activation's first pass reads everything.
        previous = self._ezy_glue_previous_states()
        waking = not self.env.context.get("ezy_glue_backfill")
        known = {key for key, _label in self._fields["ezy_wms_state"].selection}
        entering = self.env["stock.picking"]
        for picking in self:
            # The legacy module's own substates outside the bridge's vocabulary
            # (not_concerned) read as no WMS state.
            states = [
                state
                for state in picking.move_ids.mapped("textual_substate")
                if state and state in known
            ]
            if not states:
                value = False
            elif "refused_by_logistics" in states:
                value = "refused_by_logistics"
            elif "cancelled_by_logistics" in states:
                value = "cancelled_by_logistics"
            else:
                value = states[0]
            picking.ezy_wms_state = value
            if (
                waking
                and value == "ready_for_logistics"
                and picking.id
                and previous.get(picking.id) != "ready_for_logistics"
            ):
                entering |= picking
        if entering:
            entering._ezy_glue_wake_once()

    def _ezy_glue_wake_once(self):
        """One wake-up per transfer per transaction, however many times the
        compute runs before the flush."""
        woken = self.env.cr.cache.setdefault("ezy_glue_woken", set())
        fresh = self.filtered(lambda picking: picking.id not in woken)
        woken.update(fresh.ids)
        if fresh:
            fresh._ezy_schedule_wakeup()

    def _inverse_ezy_wms_state_to_legacy(self):
        for picking in self:
            picking.move_ids.write({"textual_substate": picking.ezy_wms_state or ""})

    @api.model_create_multi
    def create(self, vals_list):
        # The legacy module copies the channel down on its screens (an
        # onchange from the partner); a transfer created by Odoo from a sales
        # order, or by the connector, gets it here from the order, else the
        # partner, so the legacy field and the bridge field read one value.
        for vals in vals_list:
            if not vals.get("idcanal") and not vals.get("ezy_channel"):
                order = self.env["sale.order"].browse(vals.get("sale_id") or [])
                partner = self.env["res.partner"].browse(vals.get("partner_id") or [])
                channel = (order.idcanal if order else False) or (
                    partner.idcanal if partner else False
                )
                if channel:
                    vals["idcanal"] = channel
        return super().create(vals_list)

    @api.depends("idcanal")
    def _compute_ezy_channel_from_legacy(self):
        for picking in self:
            picking.ezy_channel = picking.idcanal or False

    def _inverse_ezy_channel_to_legacy(self):
        for picking in self:
            picking.idcanal = legacy_channel(self.env, picking.ezy_channel)

    def _picking_to_exclude_from_mrp(self):
        # The connector's own assignment and unreserve are the logistics' (see
        # stock_move.py); the bridge's freeze still decides for them.
        if self.env.user.has_group(CONNECTOR_GROUP):
            return self.env["stock.picking"]
        return super()._picking_to_exclude_from_mrp()
