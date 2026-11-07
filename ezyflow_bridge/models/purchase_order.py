# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # The incoterm's code for the connector: Odoo 16 shows an incoterm by its
    # name where 17 and later show its code (ADR 0015, the 16 delta reads this).
    ezy_incoterm_code = fields.Char(related="incoterm_id.code", string="Incoterm code")
