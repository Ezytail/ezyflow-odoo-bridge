# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestShippedSerials(EzyflowBridgeCase):
    """Behaviour 17: the shipped serial numbers of a transfer line, written by
    the connector on an open or a done delivery, refused to a person, gathered
    per sales order line from its done deliveries, never copied. The same on
    every series (ADR 0015)."""

    def _ship(self, picking):
        """What the connector does with a shipped report: the done quantity
        on the move, then the validation, both as the connector user."""
        picking.action_assign()
        self.set_wms_state(picking, "preparation_to_do")
        as_connector = picking.with_user(self.connector_user)
        as_connector.write({"move_ids": [(1, picking.move_ids.id, self.done(5))]})
        as_connector.with_context(skip_backorder=True).button_validate()
        self.assertEqual(picking.state, "done")

    def test_the_connector_writes_the_serials_on_a_done_delivery_move(self):
        picking = self.confirm_order()
        self._ship(picking)

        picking.move_ids.with_user(self.connector_user).write(
            {"ezy_shipped_serials": "SN-1\nSN-2"}
        )

        self.assertEqual(picking.move_ids.ezy_shipped_serials, "SN-1\nSN-2")

    def test_a_person_may_not_write_the_serials_and_an_administrator_may(self):
        picking = self.confirm_order()
        self._ship(picking)

        with self.assertRaises(AccessError):
            picking.move_ids.with_user(self.warehouse_user).write({"ezy_shipped_serials": "SN-9"})
        self.assertFalse(picking.move_ids.ezy_shipped_serials)

        picking.move_ids.with_user(self.admin_user).write({"ezy_shipped_serials": "SN-3"})
        self.assertEqual(picking.move_ids.ezy_shipped_serials, "SN-3")

    def test_the_order_line_gathers_the_serials_of_its_done_deliveries(self):
        picking = self.confirm_order()
        line = picking.sale_id.order_line
        # Written on the open delivery: nothing shows on the line before it is done.
        picking.move_ids.with_user(self.connector_user).write(
            {"ezy_shipped_serials": " SN-2\nSN-1\n\nSN-1"}
        )
        self.assertFalse(line.ezy_shipped_serials)

        self._ship(picking)

        self.assertEqual(line.ezy_shipped_serials, "SN-1\nSN-2")
        # Read as the connector too, who reads the line through its own rights.
        self.assertEqual(line.with_user(self.connector_user).ezy_shipped_serials, "SN-1\nSN-2")

    def test_the_order_line_splits_on_carriage_return_and_line_feed_only(self):
        picking = self.confirm_order()
        line = picking.sale_id.order_line
        # A form feed or a Unicode line separator inside a serial is not a
        # line break: the connector splits on \r and \n only.
        picking.move_ids.with_user(self.connector_user).write(
            {"ezy_shipped_serials": "SN\x0c1\r\nSN\u20282\rSN-3\n"}
        )

        self._ship(picking)

        self.assertEqual(line.ezy_shipped_serials, "SN\x0c1\nSN-3\nSN\u20282")

    def test_a_copy_of_the_transfer_does_not_carry_the_serials(self):
        picking = self.confirm_order()
        picking.move_ids.with_user(self.connector_user).write({"ezy_shipped_serials": "SN-1"})

        # A person duplicates the transfer (the connector never does).
        copy = picking.with_user(self.admin_user).copy()

        self.assertTrue(copy.move_ids)
        self.assertFalse(copy.move_ids.ezy_shipped_serials)

    def test_a_person_may_not_create_a_move_carrying_the_serials(self):
        picking = self.confirm_order()
        move = picking.move_ids

        # The create path of the guard: a duplicate that names the field.
        with self.assertRaises(AccessError):
            move.with_user(self.warehouse_user).copy({"ezy_shipped_serials": "SN-9"})

        copy = move.with_user(self.admin_user).copy({"ezy_shipped_serials": "SN-3"})
        self.assertEqual(copy.ezy_shipped_serials, "SN-3")
