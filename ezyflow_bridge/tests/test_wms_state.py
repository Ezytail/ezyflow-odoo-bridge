# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import EzyflowBridgeCase

HAND_OFF_ORDER = [
    "ready_for_logistics",
    "sent_to_logistics",
    "preparation_to_do",
    "preparation_in_progress",
    "preparation_done",
    "refused_by_logistics",
    "cancelled_by_logistics",
    "shipped",
]


@tagged("post_install", "-at_install")
class TestWmsState(EzyflowBridgeCase):
    """Behaviour 4: one selection field on the transfer, eight values in
    hand-off order; Odoo sets ready, the connector writes the rest."""

    def delivery(self):
        return self.create_picking(
            self.out_type, self.stock_location, self.env.ref("stock.stock_location_customers")
        )

    def test_the_transfer_carries_the_eight_states_in_hand_off_order(self):
        field = self.env["stock.picking"]._fields["ezy_wms_state"]

        self.assertEqual(field.type, "selection")
        self.assertTrue(field.store)
        self.assertEqual(field.get_values(self.env), HAND_OFF_ORDER)

    def test_a_new_transfer_has_no_state(self):
        self.assertFalse(self.delivery().ezy_wms_state)

    def test_a_copy_does_not_carry_the_state(self):
        picking = self.delivery()
        self.set_wms_state(picking, "sent_to_logistics")

        self.assertFalse(picking.copy().ezy_wms_state)

    def test_the_connector_writes_every_state(self):
        picking = self.delivery()
        for state in HAND_OFF_ORDER:
            self.set_wms_state(picking, state)
            self.assertEqual(picking.ezy_wms_state, state)

    def test_a_person_may_not_create_a_transfer_with_a_state(self):
        customers = self.env.ref("stock.stock_location_customers")
        with self.assertRaises(UserError):
            self.env["stock.picking"].with_user(self.warehouse_user).create(
                {
                    "picking_type_id": self.out_type.id,
                    "location_id": self.stock_location.id,
                    "location_dest_id": customers.id,
                    "ezy_wms_state": "sent_to_logistics",
                }
            )
