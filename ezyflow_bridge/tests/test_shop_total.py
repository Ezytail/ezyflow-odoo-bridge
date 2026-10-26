# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import Command
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestShopTotal(EzyflowBridgeCase):
    """Behaviour 12 (ADR 0028): the shop total the connector writes at create
    and the flag that shows a gap with Odoo's total; a gap never refuses the
    order. The same on every series (ADR 0015)."""

    def _order(self, **values):
        # As the connector creates orders: the connector user, no taxes on the
        # line so Odoo's total is the line's price (10 x 2 = 20).
        return (
            self.env["sale.order"]
            .with_user(self.connector_user)
            .with_context(default_quotation_document_ids=[])
            .create(
                {
                    "partner_id": self.customer.id,
                    "origin": "SHOP-TOTAL",
                    "order_line": [
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 2,
                                "price_unit": 10.0,
                                "tax_ids": [Command.clear()],
                            }
                        )
                    ],
                    **values,
                }
            )
        )

    def test_the_connector_writes_the_shop_total_at_create(self):
        order = self._order(ezy_shop_total=20.0)

        self.assertEqual(order.ezy_shop_total, 20.0)
        self.assertEqual(order.amount_total, 20.0)
        self.assertFalse(order.ezy_total_differs)
        # Read as the connector too: the flag is a readable stored field.
        self.assertFalse(order.with_user(self.connector_user).ezy_total_differs)

    def test_a_total_beyond_the_rounding_sets_the_flag_and_keeps_the_order(self):
        order = self._order(ezy_shop_total=24.2)

        self.assertTrue(order.ezy_total_differs)
        self.assertEqual(order.state, "draft")
        order.with_user(self.connector_user).action_confirm()
        self.assertEqual(order.state, "sale")

    def test_a_total_within_the_rounding_does_not_set_the_flag(self):
        order = self._order(ezy_shop_total=20.004)

        self.assertFalse(order.ezy_total_differs)

    def test_without_a_shop_total_the_flag_stays_off(self):
        order = self._order()

        self.assertFalse(order.ezy_shop_total)
        self.assertFalse(order.ezy_total_differs)

    def test_the_flag_follows_a_later_change_of_the_order_total(self):
        order = self._order(ezy_shop_total=20.0)
        self.assertFalse(order.ezy_total_differs)

        # A person changes the line; the price is written with the quantity,
        # since Odoo recomputes a line's price when its quantity changes.
        order.sudo().order_line.write({"product_uom_qty": 3, "price_unit": 10.0})

        self.assertEqual(order.amount_total, 30.0)
        self.assertTrue(order.ezy_total_differs)

    def test_a_copy_does_not_carry_the_shop_total(self):
        order = self._order(ezy_shop_total=24.2)

        # A person duplicates the order (the connector never does).
        copy = order.with_user(self.admin_user).copy()

        self.assertFalse(copy.ezy_shop_total)
        self.assertFalse(copy.ezy_total_differs)
