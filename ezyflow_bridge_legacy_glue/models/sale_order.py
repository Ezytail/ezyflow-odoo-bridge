# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models

from .channel import legacy_channel


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # The legacy module owns the order's channel and copies it down to the
    # transfer from the partner (ADR 0035): the bridge's order-wins rule
    # (ADR 0029) does not apply on a glued tenant.
    ezy_channel = fields.Char(
        compute="_compute_ezy_channel_from_legacy",
        inverse="_inverse_ezy_channel_to_legacy",
        store=True,
        readonly=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        # The legacy module copies the partner's channel on its screens (an
        # onchange from the delivery address); an order created through the
        # API without a channel gets it here, so the legacy field and the
        # bridge field read one value whichever way the order was made.
        for vals in vals_list:
            if not vals.get("idcanal") and not vals.get("ezy_channel"):
                partner = self.env["res.partner"].browse(
                    vals.get("partner_shipping_id") or vals.get("partner_id") or []
                )
                if partner and partner.idcanal:
                    vals["idcanal"] = partner.idcanal
        return super().create(vals_list)

    @api.depends("idcanal")
    def _compute_ezy_channel_from_legacy(self):
        for order in self:
            order.ezy_channel = order.idcanal or False

    def _inverse_ezy_channel_to_legacy(self):
        for order in self:
            channel = legacy_channel(self.env, order.ezy_channel)
            order.idcanal = channel
            # The legacy module copies the order's channel to its transfers on
            # its screens; the same copy, for a channel written through the API.
            order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel")).write(
                {"idcanal": channel}
            )
