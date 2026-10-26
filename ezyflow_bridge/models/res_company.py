# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import fields, models


class ResCompany(models.Model):
    """The toggles behind the length constraints (behaviour 8), on by default."""

    _inherit = "res.company"

    ezy_check_product_constraints = fields.Boolean(
        string="Check product constraints for the WMS",
        default=True,
        help="Refuse a product name longer than 30 characters, an internal reference "
        "longer than 17, and a sellable good without internal reference: "
        "the limits the WMS accepts.",
    )
    ezy_check_partner_constraints = fields.Boolean(
        string="Check partner constraints for the WMS",
        default=True,
        help="Refuse a partner name longer than 50 characters and a street or street 2 "
        "longer than 35: the limits the WMS accepts.",
    )
