# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import base64
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from ..models import sale_order
from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestProforma(EzyflowBridgeCase):
    """S8: the connector renders a validated order's Proforma through the bridge's
    public method, with the proforma report of the order's company (ADR 0020),
    and a product line deleted from a quotation is recorded on its order for the
    order source."""

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

    def report_rendered_for(self, order, user=None, **context):
        """The report the render hands to Odoo, resolved as Odoo resolves it;
        nothing is laid out."""
        refs = []

        def render(_reports, report_ref, res_ids=None, data=None):
            refs.append(report_ref)
            return b"%PDF-1.7 stub", "pdf"

        reports = self.env["ir.actions.report"]
        with patch.object(type(reports), "_render_qweb_pdf", render):
            order.with_user(user or self.connector_user).with_context(
                **context
            ).ezy_render_proforma()
        self.assertEqual(len(refs), 1)
        return reports._get_report(refs[0])

    def default_report(self):
        return self.env["ir.actions.report"]._get_report(sale_order.DEFAULT_PROFORMA_REPORT)

    def test_an_empty_field_renders_odoo_s_pro_forma(self):
        self.assertFalse(self.company.ezy_proforma_report_id)
        order = self.confirm_order().sale_id

        with self.assertNoLogs(sale_order._logger.name, "WARNING"):
            report = self.report_rendered_for(order)

        self.assertEqual(report, self.env.ref("sale.action_report_pro_forma_invoice"))
        self.assertEqual(report, self.default_report())

    def test_the_render_uses_the_report_of_the_order_s_company(self):
        quotation = self.env.ref("sale.action_report_saleorder")
        pro_forma = self.env.ref("sale.action_report_pro_forma_invoice")
        second = self.env["res.company"].create({"name": "Second company"})
        self.company.ezy_proforma_report_id = quotation
        second.ezy_proforma_report_id = pro_forma
        self.connector_user.company_ids = [Command.link(second.id)]
        first_order = self.confirm_order().sale_id
        second_order = (
            self.env["sale.order"]
            .with_company(second)
            .create({"partner_id": self.customer.id, "company_id": second.id})
        )
        # The connector's current company is the first one: the report follows
        # the order, never the user's company.
        both = [self.company.id, second.id]

        self.assertEqual(
            self.report_rendered_for(first_order, allowed_company_ids=both), quotation
        )
        self.assertEqual(
            self.report_rendered_for(second_order, allowed_company_ids=both), pro_forma
        )

    def test_a_report_of_another_model_renders_the_default_with_a_warning(self):
        # The form offers sales order reports only; RPC writes past the domain.
        other = self.env["ir.actions.report"].search([("model", "!=", "sale.order")], limit=1)
        self.assertTrue(other)
        self.company.with_user(self.admin_user).write({"ezy_proforma_report_id": other.id})
        self.assertEqual(self.company.ezy_proforma_report_id, other)
        order = self.confirm_order().sale_id

        with self.assertLogs(sale_order._logger.name, "WARNING") as logs:
            report = self.report_rendered_for(order)

        self.assertEqual(report, self.default_report())
        self.assertIn("not a sale.order report", logs.output[0])

    def test_deleting_the_chosen_report_empties_the_field(self):
        chosen = self.env.ref("sale.action_report_saleorder").copy({"name": "House proforma"})
        self.company.ezy_proforma_report_id = chosen

        chosen.unlink()

        self.assertFalse(self.company.ezy_proforma_report_id)
        order = self.confirm_order().sale_id
        self.assertEqual(self.report_rendered_for(order), self.default_report())

    def test_the_connector_reads_the_company_report_and_renders_it(self):
        quotation = self.env.ref("sale.action_report_saleorder")
        self.company.ezy_proforma_report_id = quotation
        order = self.confirm_order().sale_id

        [values] = self.company.with_user(self.connector_user).read(["ezy_proforma_report_id"])
        self.assertEqual(values["ezy_proforma_report_id"][0], quotation.id)
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
