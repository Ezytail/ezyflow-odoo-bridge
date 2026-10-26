# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.ezyflow_bridge.models.contract import FROZEN_WMS_STATES

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestFreeze(EzyflowBridgeCase):
    """Behaviour 5 (reservation freeze) and 6 (write guard)."""

    def setUp(self):
        super().setUp()
        self.out_type.ezy_logistics_mode = "auto"

    def reserved_delivery(self):
        picking = self.confirm_order()
        picking.action_assign()
        self.assertEqual(picking.move_ids.quantity, 5)
        return picking

    def test_a_frozen_delivery_is_not_unreserved(self):
        for state in FROZEN_WMS_STATES:
            picking = self.reserved_delivery()
            self.set_wms_state(picking, state)

            picking.do_unreserve()
            picking.move_ids._do_unreserve()

            self.assertEqual(picking.move_ids.quantity, 5, state)
            self.assertEqual(picking.state, "assigned", state)
            self.assertTrue(picking.move_ids._should_bypass_reservation(), state)

    def test_a_frozen_delivery_is_not_reserved(self):
        for state in FROZEN_WMS_STATES:
            picking = self.confirm_order()
            self.set_wms_state(picking, state)

            picking.action_assign()
            picking.move_ids._action_assign()

            self.assertEqual(picking.move_ids.quantity, 0, state)
            self.assertEqual(picking.state, "confirmed", state)

    def test_a_frozen_delivery_is_not_reserved_by_incoming_stock(self):
        picking = self.confirm_order(quantity=150)
        self.set_wms_state(picking, "preparation_to_do")

        receipt = self.create_picking(
            self.in_type, self.supplier_location, self.stock_location, 100
        )
        receipt.button_validate()

        self.assertEqual(receipt.state, "done")
        self.assertEqual(picking.move_ids.quantity, 0, "a done receipt reserves elsewhere only")

    def test_ready_and_shipped_are_not_frozen(self):
        for state in ("ready_for_logistics", "shipped"):
            picking = self.reserved_delivery()
            self.set_wms_state(picking, state)
            self.assertFalse(picking.ezy_is_frozen, state)

            picking.do_unreserve()
            self.assertEqual(picking.move_ids.quantity, 0, state)

            picking.action_assign()
            self.assertEqual(picking.move_ids.quantity, 5, state)

    def test_a_person_cannot_change_the_lines_of_a_frozen_delivery(self):
        picking = self.reserved_delivery()
        self.set_wms_state(picking, "sent_to_logistics")
        move = picking.move_ids.with_user(self.warehouse_user)
        line = picking.move_line_ids.with_user(self.warehouse_user)

        with self.assertRaisesRegex(UserError, "Sent to logistics"):
            move.write({"product_uom_qty": 3})
        with self.assertRaisesRegex(UserError, "Sent to logistics"):
            move.write({"quantity": 3})
        with self.assertRaisesRegex(UserError, "Sent to logistics"):
            line.write({"quantity": 3})
        with self.assertRaisesRegex(UserError, "Sent to logistics"):
            line.unlink()
        with self.assertRaisesRegex(UserError, "Sent to logistics"):
            self.env["stock.move.line"].with_user(self.warehouse_user).create(
                {
                    "move_id": picking.move_ids.id,
                    "product_id": self.product.id,
                    "location_id": self.stock_location.id,
                    "location_dest_id": picking.location_dest_id.id,
                    "quantity": 1,
                }
            )
        with self.assertRaisesRegex(UserError, "Sent to logistics"):
            picking.with_user(self.warehouse_user).write(
                {
                    "move_ids": [
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 1,
                                "location_id": picking.location_id.id,
                                "location_dest_id": picking.location_dest_id.id,
                            }
                        )
                    ]
                }
            )
        self.assertEqual(picking.move_ids.product_uom_qty, 5)

    def test_the_connector_and_an_administrator_can_change_the_lines(self):
        picking = self.reserved_delivery()
        self.set_wms_state(picking, "preparation_done")

        picking.move_ids.with_user(self.connector_user).write({"quantity": 3})
        self.assertEqual(picking.move_ids.quantity, 3)

        picking.move_ids.with_user(self.admin_user).write({"product_uom_qty": 4})
        self.assertEqual(picking.move_ids.product_uom_qty, 4)

    def test_the_header_of_a_frozen_delivery_still_belongs_to_people(self):
        # Cancelling must reach the WMS as a cancellation (S2): the guard covers
        # the lines, not the housekeeping Odoo writes for a person.
        picking = self.reserved_delivery()
        self.set_wms_state(picking, "sent_to_logistics")

        picking.with_user(self.warehouse_user).write({"origin": "changed by hand"})
        picking.with_user(self.warehouse_user).action_cancel()

        self.assertEqual(picking.state, "cancel")
        self.assertEqual(picking.ezy_wms_state, "sent_to_logistics")
