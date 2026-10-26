# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models
from odoo.exceptions import UserError

from .contract import CHANNELS, FROZEN_WMS_STATES, WMS_STATES


class StockPicking(models.Model):
    """The WMS state lives on the picking (ADR 0003); the picking decides
    whether it is offered (behaviours 1 and 2), whether it is frozen
    (behaviour 5) and who may touch its lines (behaviour 6)."""

    _inherit = "stock.picking"

    ezy_wms_state = fields.Selection(
        WMS_STATES,
        string="WMS state",
        copy=False,
        index=True,
        help="Where this transfer stands in the hand-off with the WMS. Odoo sets "
        "'Ready for logistics' when the operation type offers the transfer; the "
        "EzyFlow connector writes every later value.",
    )
    ezy_hold = fields.Boolean(
        string="Hold",
        copy=False,
        help="Keeps this transfer out of the WMS whatever its operation type says.",
    )
    ezy_channel = fields.Selection(
        CHANNELS,
        string="Channel",
        compute="_compute_ezy_channel",
        store=True,
        readonly=False,
        help="The sales channel, copied down from the sales order.",
    )
    ezy_final_recipient_id = fields.Many2one(
        "res.partner",
        string="Final recipient",
        compute="_compute_ezy_final_recipient",
        store=True,
        readonly=False,
        help="The customer who collects the parcel when the delivery address is a "
        "relay point; copied down from the sales order.",
    )
    ezy_logistics_mode = fields.Selection(related="picking_type_id.ezy_logistics_mode")
    ezy_is_frozen = fields.Boolean(
        string="Frozen for the WMS",
        compute="_compute_ezy_is_frozen",
        help="Odoo neither reserves nor unreserves a frozen transfer, and only the "
        "EzyFlow connector may change its lines.",
    )

    @api.depends("sale_id.ezy_channel")
    def _compute_ezy_channel(self):
        # Behaviour 3: copied down from the sales order when moves join the
        # transfer (sale_id follows the moves) and when the order's channel changes.
        for picking in self:
            picking.ezy_channel = picking.sale_id.ezy_channel or picking.ezy_channel

    @api.depends("sale_id.ezy_final_recipient_id")
    def _compute_ezy_final_recipient(self):
        for picking in self:
            picking.ezy_final_recipient_id = (
                picking.sale_id.ezy_final_recipient_id or picking.ezy_final_recipient_id
            )

    @api.depends("ezy_wms_state")
    def _compute_ezy_is_frozen(self):
        for picking in self:
            picking.ezy_is_frozen = picking.ezy_wms_state in FROZEN_WMS_STATES

    @api.model_create_multi
    def create(self, vals_list):
        if not self._ezy_user_drives_wms():
            for vals in vals_list:
                if vals.get("ezy_wms_state"):
                    raise UserError(self._ezy_state_error_message())
        return super().create(vals_list)

    def write(self, vals):
        if "ezy_wms_state" in vals and not self._ezy_user_drives_wms():
            self._ezy_check_person_may_set(vals["ezy_wms_state"])
        entering_ready = (
            vals.get("ezy_wms_state") == "ready_for_logistics"
            and self.filtered(lambda picking: picking.ezy_wms_state != "ready_for_logistics")
        )
        result = super().write(vals)
        if entering_ready:
            # Behaviour 9 (ADR 0006): a transfer entering ready for logistics wakes
            # the connector once the transaction commits; a rolled-back write wakes
            # nobody.
            entering_ready._ezy_schedule_wakeup()
        return result

    def _ezy_schedule_wakeup(self):
        wakeup = self.env["ezyflow.wakeup"]
        for picking in self:
            wakeup.schedule("stock.picking", picking.id, picking.company_id.id)

    def action_assign(self):
        # Behaviour 5: a frozen transfer is neither reserved nor unreserved.
        movable = self.filtered(lambda picking: not picking.ezy_is_frozen)
        if not movable:
            return True
        return super(StockPicking, movable).action_assign()

    def do_unreserve(self):
        movable = self.filtered(lambda picking: not picking.ezy_is_frozen)
        if not movable:
            return True
        return super(StockPicking, movable).do_unreserve()

    def action_ezy_offer_to_logistics(self):
        """The form button of behaviour 7: a person offers a transfer of a manual
        operation type. Goes through the same write guard as any other write."""
        self.write({"ezy_wms_state": "ready_for_logistics"})

    def _ezy_offer_on_assignment(self):
        """Behaviours 1 and 2: offer the transfers whose operation type is in auto
        mode and allows their channel, unless held, internal, or already in the
        hand-off. Called by the moves once they are reserved."""
        offered = self.filtered(lambda picking: picking._ezy_is_offered_on_assignment())
        if offered:
            # The bridge itself sets the state, not the person who happened to
            # trigger the reservation; the person guard does not apply.
            offered.sudo().write({"ezy_wms_state": "ready_for_logistics"})

    def _ezy_is_offered_on_assignment(self):
        self.ensure_one()
        picking_type = self.picking_type_id
        return (
            not self.ezy_wms_state
            and not self.ezy_hold
            and picking_type.code != "internal"
            and picking_type.ezy_logistics_mode == "auto"
            and picking_type._ezy_offers_channel(self.ezy_channel)
        )

    @api.model
    def _ezy_user_drives_wms(self):
        """The connector user and administrators drive the WMS state and the
        lines of a frozen transfer; everyone else is a person the guards apply to."""
        user = self.env.user
        return (
            self.env.su
            or user.has_group("ezyflow_bridge.group_ezyflow_connector")
            or user.has_group("base.group_system")
        )

    def _ezy_check_person_may_set(self, state):
        """Behaviour 7: the one transition a person may make is empty to ready for
        logistics on a manual operation type, on a transfer that is neither held
        nor internal."""
        for picking in self:
            picking_type = picking.picking_type_id
            allowed = (
                state == "ready_for_logistics"
                and not picking.ezy_wms_state
                and not picking.ezy_hold
                and picking_type.code != "internal"
                and picking_type.ezy_logistics_mode == "manual"
            )
            if not allowed:
                raise UserError(self._ezy_state_error_message())

    @api.model
    def _ezy_state_error_message(self):
        return self.env._(
            "The WMS state is written by the EzyFlow connector. A person may only "
            "mark a transfer ready for logistics when its operation type is in "
            "manual mode, it is not held, and it is not an internal transfer."
        )

    def _ezy_check_lines_may_change(self):
        """Behaviour 6: a person cannot change the lines of a frozen transfer;
        the connector user and administrators can. The error names the state."""
        if self._ezy_user_drives_wms():
            return
        frozen = self.filtered("ezy_is_frozen")
        if not frozen:
            return
        picking = frozen[0]
        raise UserError(
            self.env._(
                "%(picking)s is frozen: its WMS state is '%(state)s', so its lines "
                "belong to the WMS. Only the EzyFlow connector or an administrator "
                "may change them.",
                picking=picking.display_name,
                state=picking._fields["ezy_wms_state"].convert_to_export(
                    picking.ezy_wms_state, picking
                ),
            )
        )
