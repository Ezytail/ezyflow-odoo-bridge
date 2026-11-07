# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models

from .channel import legacy_channel


class ResPartner(models.Model):
    _inherit = "res.partner"

    # The legacy module owns the value (ADR 0035): the bridge field mirrors idcanal.
    ezy_channel = fields.Char(
        compute="_compute_ezy_channel_from_legacy",
        inverse="_inverse_ezy_channel_to_legacy",
        store=True,
        readonly=False,
    )

    @api.depends("idcanal")
    def _compute_ezy_channel_from_legacy(self):
        for partner in self:
            partner.ezy_channel = partner.idcanal or False

    def _inverse_ezy_channel_to_legacy(self):
        for partner in self:
            partner.idcanal = legacy_channel(self.env, partner.ezy_channel)
