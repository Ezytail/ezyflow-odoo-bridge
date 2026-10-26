# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import fields, models


class DeliveryCarrier(models.Model):
    """The WMS-facing identity of a delivery method (CONTEXT.md, "Carrier
    service code") and whether it delivers to relay points."""

    _inherit = "delivery.carrier"

    ezy_service_code = fields.Char(
        string="WMS service code",
        help="The name the WMS knows this delivery method by; the key the EzyFlow "
        "connector resolves a shop's shipping choice against.",
    )
    ezy_carrier_code = fields.Char(
        string="WMS carrier code",
        help="The code the WMS knows the carrier by.",
    )
    ezy_has_relay_points = fields.Boolean(
        string="Delivers to relay points",
        help="This carrier drops parcels at relay points for the customer to "
        "collect; the shipping address of its orders is the relay point and the "
        "final recipient is kept on the order.",
    )
