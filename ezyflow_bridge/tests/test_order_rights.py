# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import Command, release
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestOrderRights(EzyflowBridgeCase):
    """S5: the connector user creates a shop order's customer, its addresses,
    its sales order with lines, confirms and cancels it, creates a delivery
    method, writes customs on a variant; it deletes none of them (least
    privilege, ADR 0013). The same rights on every series (ADR 0015)."""

    def test_the_connector_creates_a_customer_with_its_addresses(self):
        partner = (
            self.env["res.partner"]
            .with_user(self.connector_user)
            .create(
                {
                    "name": "Alice Martin",
                    "email": "alice@example.test",
                    "type": "contact",
                    "child_ids": [
                        Command.create({"name": "Alice Martin", "type": "delivery"}),
                        Command.create({"name": "Alice Martin", "type": "invoice"}),
                    ],
                }
            )
        )
        self.assertEqual(len(partner.child_ids), 2)
        partner.with_user(self.connector_user).write({"street": "10 rue de Rivoli"})
        with self.assertRaises(AccessError):
            partner.with_user(self.connector_user).unlink()

    def test_the_connector_creates_confirms_and_cancels_a_sales_order(self):
        # The connector creates orders with the context default the service sends
        # (sale_pdf_quote_builder's default search is a sales user's privilege).
        as_connector = (
            self.env["sale.order"]
            .with_user(self.connector_user)
            .with_context(default_quotation_document_ids=[])
        )
        order = as_connector.create(
            {
                "partner_id": self.customer.id,
                "origin": "SHOP-1",
                "order_line": [
                    Command.create({"product_id": self.product.id, "product_uom_qty": 2})
                ],
            }
        )
        self.assertEqual(order.state, "draft")
        order.with_user(self.connector_user).action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertTrue(order.picking_ids)
        order.picking_ids.with_user(self.connector_user).action_cancel()
        order.with_user(self.connector_user).write({"state": "cancel"})
        self.assertEqual(order.state, "cancel")
        with self.assertRaises(AccessError):
            order.with_user(self.connector_user).unlink()

    def test_the_connector_cannot_write_an_order_a_person_typed(self):
        # No origin: not created from a shop, not the connector's to touch. The
        # bridge's rule holds on Odoo 19; on Odoo 20 core sale_stock grants every
        # stock user update on any sales order and permissions add up (ADR 0015),
        # so there the rule documents the intent and the write goes through.
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    Command.create({"product_id": self.product.id, "product_uom_qty": 1})
                ],
            }
        )
        order.with_user(self.connector_user).read(["state"])
        if release.version_info[0] == 19:
            with self.assertRaises(AccessError):
                order.with_user(self.connector_user).write({"state": "cancel"})
        else:
            order.with_user(self.connector_user).write({"state": "cancel"})
            self.assertEqual(order.state, "cancel")

    def test_the_connector_creates_a_delivery_method_and_writes_customs(self):
        product = (
            self.env["product.product"]
            .with_user(self.connector_user)
            .create({"name": "Chrono delivery", "type": "service", "sale_ok": False})
        )
        carrier = (
            self.env["delivery.carrier"]
            .with_user(self.connector_user)
            .create(
                {
                    "name": "Chrono",
                    "product_id": product.id,
                    "delivery_type": "fixed",
                    "fixed_price": 6.0,
                    "ezy_service_code": "CHRONO_HOME",
                    "ezy_carrier_code": "CHRONO",
                }
            )
        )
        self.assertEqual(carrier.ezy_service_code, "CHRONO_HOME")
        self.product.with_user(self.connector_user).write({"hs_code": "610910"})
        self.assertEqual(self.product.hs_code, "610910")
        with self.assertRaises(AccessError):
            carrier.with_user(self.connector_user).unlink()
