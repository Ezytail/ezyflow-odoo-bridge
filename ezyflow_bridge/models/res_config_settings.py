# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ezy_check_product_constraints = fields.Boolean(
        related="company_id.ezy_check_product_constraints", readonly=False
    )
    ezy_check_partner_constraints = fields.Boolean(
        related="company_id.ezy_check_partner_constraints", readonly=False
    )
