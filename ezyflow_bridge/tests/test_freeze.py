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

    def assert_reserved(self, expected, message=None):
        """The stock's reservation of the product, as the quants hold it, is the
        open detailed operations' and equals expected."""
        quants = self.env["stock.quant"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "child_of", self.stock_location.id),
            ]
        )
        lines = self.env["stock.move.line"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "child_of", self.stock_location.id),
                ("state", "not in", ("done", "cancel")),
            ]
        )
        self.assertEqual(sum(lines.mapped("quantity_product_uom")), expected, message)
        self.assertEqual(sum(quants.mapped("reserved_quantity")), expected, message)

    def prepare_as_connector(self, picking, quantity):
        """What the fulfilment rounds write on a frozen delivery (S4)."""
        picking.with_user(self.connector_user).write(
            {"move_ids": [(1, picking.move_ids.id, {"quantity": quantity, "picked": True})]}
        )

    def test_a_frozen_delivery_is_not_unreserved(self):
        for state in FROZEN_WMS_STATES:
            picking = self.reserved_delivery()
            self.set_wms_state(picking, state)

            picking.do_unreserve()
            picking.move_ids._do_unreserve()

            self.assertEqual(picking.move_ids.quantity, 5, state)
            self.assertEqual(picking.state, "assigned", state)
        self.assert_reserved(5 * len(FROZEN_WMS_STATES), "the quants keep the reservation")

    def test_a_frozen_delivery_validated_by_the_connector_gives_its_reservation_back(self):
        # The leak found in recette on 2026-10-21: the stock stayed reserved by
        # the quantities the connector validated, so no new delivery reserved.
        open_delivery = self.reserved_delivery()
        for state in FROZEN_WMS_STATES:
            picking = self.reserved_delivery()
            self.set_wms_state(picking, state)
            self.prepare_as_connector(picking, 5)

            picking.with_user(self.connector_user).with_context(
                skip_backorder=True
            ).button_validate()

            self.assertEqual(picking.state, "done", state)
            self.assert_reserved(5, state)
        self.assertEqual(open_delivery.state, "assigned")

    def test_a_partly_prepared_frozen_delivery_gives_its_whole_reservation_back(self):
        picking = self.reserved_delivery()
        self.set_wms_state(picking, "preparation_in_progress")

        self.prepare_as_connector(picking, 2)
        self.assert_reserved(2, "the prepared quantity is the reservation")
        picking.with_user(self.connector_user).with_context(
            skip_backorder=True, picking_ids_not_to_backorder=picking.ids
        ).button_validate()

        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.move_ids.quantity, 2)
        self.assert_reserved(0)

    def test_a_cancelled_frozen_delivery_gives_its_reservation_back(self):
        for state in FROZEN_WMS_STATES:
            by_a_person = self.reserved_delivery()
            self.set_wms_state(by_a_person, state)
            by_a_person.with_user(self.warehouse_user).action_cancel()
            # The Order.Cancelled flow (S5): release, then cancel.
            by_the_connector = self.reserved_delivery()
            self.set_wms_state(by_the_connector, state)
            by_the_connector.with_user(self.connector_user).do_unreserve()
            by_the_connector.with_user(self.connector_user).action_cancel()

            self.assertEqual(by_a_person.state, "cancel", state)
            self.assertEqual(by_the_connector.state, "cancel", state)
            self.assert_reserved(0, state)

    def test_a_frozen_delivery_holding_a_done_move_keeps_its_reservation_when_refused(self):
        # Core refuses to cancel a done move: the release of the open move,
        # made just before core's check, goes back with the refusal.
        other = self.env["product.product"].create(
            {
                "name": "Other good",
                "is_storable": True,
                "default_code": "GOOD-2",
                "barcode": "3000000000024",
            }
        )
        self.env["stock.quant"]._update_available_quantity(other, self.stock_location, 10)
        picking = self.reserved_delivery()
        self.set_wms_state(picking, "preparation_in_progress")
        picking.with_user(self.connector_user).write(
            {
                "move_ids": [
                    Command.create(
                        {
                            "product_id": other.id,
                            "product_uom_qty": 2,
                            "quantity": 2,
                            "picked": True,
                            "location_id": picking.location_id.id,
                            "location_dest_id": picking.location_dest_id.id,
                        }
                    )
                ]
            }
        )
        done_move = picking.move_ids.filtered(lambda move: move.product_id == other)
        # Without cancel_backorder core moves the open move to a backorder.
        done_move._action_done(cancel_backorder=True)
        open_move = picking.move_ids - done_move
        self.assertEqual(done_move.state, "done")

        with self.assertRaises(UserError):
            picking.with_user(self.warehouse_user).action_cancel()

        self.assertEqual(open_move.state, "assigned")
        self.assertEqual(open_move.quantity, 5)
        self.assert_reserved(5)

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

    def test_a_person_cannot_change_the_unit_of_a_frozen_delivery(self):
        # Odoo 19 names the unit product_uom (move) and product_uom_id (line),
        # Odoo 20 uom_id on both (issue #52). Writing the current unit is enough:
        # the guard refuses on the field, before Odoo compares values.
        picking = self.reserved_delivery()
        self.set_wms_state(picking, "sent_to_logistics")
        move = picking.move_ids.with_user(self.warehouse_user)
        line = picking.move_line_ids.with_user(self.warehouse_user)
        move_unit = "uom_id" if "uom_id" in move._fields else "product_uom"
        line_unit = "uom_id" if "uom_id" in line._fields else "product_uom_id"

        with self.assertRaisesRegex(UserError, "Sent to logistics"):
            move.write({move_unit: move[move_unit].id})
        with self.assertRaisesRegex(UserError, "Sent to logistics"):
            line.write({line_unit: line[line_unit].id})

        picking.move_ids.with_user(self.connector_user).write({move_unit: move[move_unit].id})
        picking.move_line_ids.with_user(self.connector_user).write(
            {line_unit: line[line_unit].id}
        )

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
