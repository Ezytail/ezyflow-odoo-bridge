# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from unittest.mock import patch

from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestSmsWarning(EzyflowBridgeCase):
    """Behaviour 11 (ADR 0019): stock_sms answers the first validation of a
    delivery to a customer with a phone with a one-time window, until someone
    acknowledges it for the company. The connector validates past it, as a
    person who chose to send the SMS would; people still see the window.

    stock_sms skips the window under test (modules.module.current_test), so
    these tests lift that flag and stub the SMS sending it would then do."""

    def setUp(self):
        super().setUp()
        self.assertIn(
            "has_received_warning_stock_sms",
            self.env["res.company"]._fields,
            "stock_sms is installed with stock and sms on every supported series",
        )
        self.company.write(
            {"stock_text_confirmation": True, "has_received_warning_stock_sms": False}
        )
        self.startPatcher(patch("odoo.modules.module.current_test", None))
        self.sent = self.startPatcher(
            patch.object(type(self.env["stock.picking"]), "_message_sms_with_template")
        )

    def prepared_delivery(self, wms_state=None, partner=None):
        picking = self.confirm_order(partner=partner)
        picking.action_assign()
        if wms_state:
            self.set_wms_state(picking, wms_state)
        picking.move_ids.write({"quantity": 5, "picked": True})
        return picking

    def validate_as_connector(self, picking):
        return (
            picking.with_user(self.connector_user)
            .with_context(skip_backorder=True)
            .button_validate()
        )

    def test_the_connector_validates_past_the_window_and_the_sms_goes_out(self):
        picking = self.prepared_delivery("preparation_to_do")

        self.assertIs(self.validate_as_connector(picking), True)

        self.assertEqual(picking.state, "done")
        self.assertTrue(self.company.has_received_warning_stock_sms)
        self.assertTrue(self.company.stock_text_confirmation, "the company's choice stays")
        self.sent.assert_called_once()

    def test_a_person_still_gets_the_window(self):
        picking = self.prepared_delivery()

        action = picking.with_user(self.warehouse_user).with_context(
            skip_backorder=True
        ).button_validate()

        self.assertEqual(action["res_model"], "confirm.stock.sms")
        self.assertNotEqual(picking.state, "done")
        self.assertFalse(self.company.has_received_warning_stock_sms)

    def test_no_window_to_acknowledge_when_the_company_sends_no_sms(self):
        self.company.stock_text_confirmation = False
        picking = self.prepared_delivery("preparation_to_do")

        self.validate_as_connector(picking)

        self.assertEqual(picking.state, "done")
        self.assertFalse(self.company.has_received_warning_stock_sms)
        self.sent.assert_not_called()

    def test_no_window_to_acknowledge_for_a_customer_without_phone(self):
        # Created by the administrator: the WMS constraints bind the person who
        # confirms an order, and a delivery address without phone is the shop's case.
        customer = self.env["res.partner"].create(
            {"name": "No phone", "ezy_channel": "WEB", "email": "no.phone@example.test"}
        )
        self.company.ezy_wms_delivery_contact_required = False
        picking = self.prepared_delivery("preparation_to_do", partner=customer)

        self.validate_as_connector(picking)

        self.assertEqual(picking.state, "done")
        self.assertFalse(self.company.has_received_warning_stock_sms)

    def test_a_receipt_leaves_the_flag_alone(self):
        receipt = self.create_picking(self.in_type, self.supplier_location, self.stock_location)
        receipt.move_ids.write({"quantity": 5, "picked": True})

        receipt.with_user(self.connector_user).button_validate()

        self.assertEqual(receipt.state, "done")
        self.assertFalse(self.company.has_received_warning_stock_sms)
