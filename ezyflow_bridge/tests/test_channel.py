# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestChannel(EzyflowBridgeCase):
    """Behaviour 3: the channel is copied down partner, order, transfer."""

    def test_channel_copies_down_from_the_delivery_address(self):
        picking = self.confirm_order()

        self.assertEqual(picking.sale_id.ezy_channel, "WEB")
        self.assertEqual(picking.ezy_channel, "WEB")

    def test_an_explicit_channel_on_the_order_wins_over_the_partner(self):
        picking = self.confirm_order(ezy_channel="PRO")

        self.assertEqual(picking.sale_id.ezy_channel, "PRO")
        self.assertEqual(picking.ezy_channel, "PRO")

    def test_a_partner_without_channel_leaves_the_order_channel_alone(self):
        anonymous = self.env["res.partner"].create(
            {"name": "No channel", "phone": "+33100000001", "email": "anonymous@example.test"}
        )

        self.assertFalse(self.confirm_order(partner=anonymous).ezy_channel)
        explicit = self.confirm_order(partner=anonymous, ezy_channel="SPECIAL")
        self.assertEqual(explicit.ezy_channel, "SPECIAL")

    def test_changing_the_order_channel_follows_to_the_transfer(self):
        picking = self.confirm_order()

        picking.sale_id.ezy_channel = "MARKETPLACE"

        self.assertEqual(picking.ezy_channel, "MARKETPLACE")
