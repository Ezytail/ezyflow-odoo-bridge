# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestRelay(EzyflowBridgeCase):
    """The relay fields the picking source reads (CONTEXT.md, "Relay point",
    "Final recipient", "Relay carrier"): a relay point is a partner with a
    relay code and a carrier, and the final recipient copies down from the
    order to its transfers."""

    def test_the_final_recipient_copies_down_to_the_transfer(self):
        carrier = self.env["delivery.carrier"].create(
            {
                "name": "Relay",
                "product_id": self.env["product.product"]
                .create({"name": "Relay delivery", "type": "service"})
                .id,
                "ezy_service_code": "RELAY_STD",
                "ezy_carrier_code": "RLY",
                "ezy_has_relay_points": True,
            }
        )
        relay = self.env["res.partner"].create(
            {
                "name": "Tabac du Centre",
                "phone": "+33100000002",
                "email": "tabac@example.test",
                "ezy_relay_code": "R123",
                "ezy_relay_carrier_id": carrier.id,
            }
        )
        picking = self.confirm_order(
            partner=relay, ezy_final_recipient_id=self.customer.id
        )

        self.assertEqual(picking.partner_id, relay)
        self.assertEqual(picking.ezy_final_recipient_id, self.customer)
        self.assertEqual(relay.ezy_relay_carrier_id.ezy_carrier_code, "RLY")

    def test_the_final_recipient_follows_a_later_change_on_the_order(self):
        picking = self.confirm_order()
        self.assertFalse(picking.ezy_final_recipient_id)

        picking.sale_id.ezy_final_recipient_id = self.customer

        self.assertEqual(picking.ezy_final_recipient_id, self.customer)
