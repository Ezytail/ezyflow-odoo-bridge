# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestDeliveryStatus(EzyflowBridgeCase):
    """Behaviour 7: the sales order's delivery status shows the WMS values."""

    def two_pickings(self):
        """An order with two transfers: its delivery and a second one linked to
        it by hand, the way a transfer created outside the order is attached
        through the Sales Order field (a backorder is the everyday case)."""
        first = self.confirm_order()
        order = first.sale_id
        second = self.create_picking(
            self.out_type, self.stock_location, first.location_dest_id, quantity=1
        )
        second.sale_id = order
        self.assertEqual(len(order.picking_ids), 2)
        return first, second, order

    def test_without_wms_state_odoo_s_own_value_stands(self):
        _pick, _ship, order = self.two_pickings()

        self.assertEqual(order.delivery_status, "pending")

    def test_refused_wins_over_preparation_to_do(self):
        pick, ship, order = self.two_pickings()

        self.set_wms_state(ship, "preparation_to_do")
        self.set_wms_state(pick, "refused_by_logistics")
        self.assertEqual(order.delivery_status, "refused_by_logistics")

        self.set_wms_state(pick, "cancelled_by_logistics")
        self.assertEqual(order.delivery_status, "cancelled_by_logistics")

    def test_otherwise_the_transfer_touched_last_speaks(self):
        pick, ship, order = self.two_pickings()

        self.set_wms_state(pick, "shipped")
        self.assertEqual(order.delivery_status, "shipped")

        self.set_wms_state(ship, "sent_to_logistics")
        self.assertEqual(order.delivery_status, "sent_to_logistics")

        self.set_wms_state(ship, "shipped")
        self.assertEqual(order.delivery_status, "shipped")
