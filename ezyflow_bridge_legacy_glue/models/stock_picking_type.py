# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    # Eligibility is the legacy module's (ADR 0035): the bridge never offers a
    # transfer on a glued tenant, and the mode reads off everywhere.
    ezy_logistics_mode = fields.Selection(
        compute="_compute_ezy_logistics_mode_off",
        inverse="_inverse_ezy_logistics_mode_off",
        store=True,
        readonly=True,
    )

    @api.depends("code")
    def _compute_ezy_logistics_mode_off(self):
        for picking_type in self:
            picking_type.ezy_logistics_mode = "off"

    def _inverse_ezy_logistics_mode_off(self):
        # A write of another value lands as off.
        self._compute_ezy_logistics_mode_off()
