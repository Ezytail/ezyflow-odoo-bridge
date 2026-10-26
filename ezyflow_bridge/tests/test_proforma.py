# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import base64

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestProforma(EzyflowBridgeCase):
    """S8: the connector renders a validated order's Proforma through the bridge's
    public method, and a product line deleted from a quotation is recorded on its
    order for the order source."""

    def set_param(self, key, value):
        # Through the record, the API both series share (ADR 0015).
        params = self.env["ir.config_parameter"].sudo()
        record = params.search([("key", "=", key)], limit=1)
        if record:
            record.value = value
        else:
            params.create({"key": key, "value": value})

    def setUp(self):
        super().setUp()
        # wkhtmltopdf fetches the report assets over HTTP, and the test run's
        # HTTP server does not answer while the post_install tests hold it, so
        # the render would wait forever. An address that refuses at once lets
        # wkhtmltopdf lay the document out without the stylesheets.
        self.set_param("report.url", "http://127.0.0.1:9")
        self.set_param("report.print_delay", "0")

    def render_as_connector(self, order):
        # Under the test runner Odoo renders reports as HTML unless asked for
        # the real thing; the serving process renders PDF without the flag.
        return (
            order.with_user(self.connector_user)
            .with_context(force_report_rendering=True)
            .ezy_render_proforma()
        )

    def test_the_connector_renders_the_proforma(self):
        order = self.confirm_order().sale_id
        rendered = self.render_as_connector(order)
        self.assertIsInstance(rendered, str)
        self.assertTrue(rendered)
        pdf = base64.b64decode(rendered)
        self.assertTrue(pdf.startswith(b"%PDF"))
        reference, report_type = (
            self.env["ir.actions.report"]
            .with_context(force_report_rendering=True)
            ._render_qweb_pdf("sale.report_saleorder_pro_forma", res_ids=order.ids)
        )
        self.assertEqual(report_type, "pdf")
        # Same report, same record: the same document. The PDF carries its
        # creation time, so two renders are compared by length, not bytes.
        self.assertEqual(len(pdf), len(reference))

    def test_the_report_name_comes_from_the_system_parameter(self):
        self.set_param("ezyflow.proforma_report", "sale.report_saleorder")
        order = self.confirm_order().sale_id
        pdf = base64.b64decode(self.render_as_connector(order))
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_a_replaced_quotation_line_is_a_removal_and_a_new_line(self):
        # "Removed" means deleted, a replacement included: the line Odoo unlinks
        # under a (2, id) command is gone with its id, and the line created in
        # its place is a new line the order source names by its own id.
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "warehouse_id": self.warehouse.id,
                "order_line": [
                    Command.create({"product_id": self.product.id, "product_uom_qty": 2}),
                ],
            }
        )
        old_id = order.order_line.id

        order.write(
            {
                "order_line": [
                    Command.delete(old_id),
                    Command.create({"product_id": self.product.id, "product_uom_qty": 5}),
                ]
            }
        )

        self.assertEqual([e["line_id"] for e in order.ezy_removed_lines], [old_id])
        self.assertEqual(len(order.order_line), 1)
        self.assertNotEqual(order.order_line.id, old_id)
        self.assertEqual(order.order_line.product_uom_qty, 5)

    def test_a_carrier_line_removed_from_a_quotation_is_not_recorded(self):
        carrier_product = self.env["product.product"].create(
            {"name": "Shipping", "type": "service"}
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "warehouse_id": self.warehouse.id,
                "order_line": [
                    Command.create({"product_id": self.product.id, "product_uom_qty": 2}),
                    Command.create(
                        {
                            "product_id": carrier_product.id,
                            "product_uom_qty": 1,
                            "is_delivery": True,
                        }
                    ),
                ],
            }
        )
        shipping = order.order_line.filtered("is_delivery")

        shipping.unlink()

        self.assertFalse(order.ezy_removed_lines)

    def test_a_removed_quotation_line_is_recorded_on_the_order(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "warehouse_id": self.warehouse.id,
                "order_line": [
                    Command.create({"product_id": self.product.id, "product_uom_qty": 2}),
                    Command.create({"product_id": self.product.id, "product_uom_qty": 3}),
                    Command.create({"product_id": self.product.id, "product_uom_qty": 4}),
                ],
            }
        )
        first, second, kept = order.order_line
        first_id, second_id = first.id, second.id
        # Odoo stores an empty Json as NULL: a fresh order reads False.
        self.assertFalse(order.ezy_removed_lines)

        first.unlink()
        self.assertEqual(len(order.ezy_removed_lines), 1)
        entry = order.ezy_removed_lines[0]
        self.assertEqual(entry["line_id"], first_id)
        self.assertEqual(entry["product_id"], self.product.id)
        self.assertEqual(entry["sku"], "GOOD-1")
        self.assertEqual(entry["quantity"], 2.0)
        self.assertTrue(entry["removed_at"])

        second.unlink()
        self.assertEqual(
            [(e["line_id"], e["quantity"]) for e in order.ezy_removed_lines],
            [(first_id, 2.0), (second_id, 3.0)],
        )

        order.action_confirm()
        with self.assertRaises(UserError):
            kept.unlink()
        self.assertEqual(
            [e["line_id"] for e in order.ezy_removed_lines], [first_id, second_id]
        )
        self.assertTrue(kept.exists())
