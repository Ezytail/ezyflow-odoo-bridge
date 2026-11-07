# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    # The legacy module's two carrier names for the WMS, mirrored (ADR 0035).
    ezy_service_code = fields.Char(related="name_l4", store=True, readonly=False)
    ezy_carrier_code = fields.Char(related="name_l4_key2", store=True, readonly=False)
