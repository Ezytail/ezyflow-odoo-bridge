# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import release
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import EzyflowBridgeCase

# Where the count's name lands: the move's own name below 19, a field of its
# own from 19 (the connector's 18 delta reads the same field).
REFERENCE_FIELD = "name" if release.version_info[0] < 19 else "inventory_name"


@tagged("post_install", "-at_install")
class TestInventoryName(EzyflowBridgeCase):
    """Behaviour 14: the move of a count the connector applies is named with
    the connector's reference, on every series, so a rerun finds its trace."""

    def _apply(self, user, reference, quantity, location=None):
        quant = (
            self.env["stock.quant"]
            .with_user(user)
            .with_context(inventory_mode=True, inventory_name=reference)
            .create(
                {
                    "product_id": self.product.id,
                    "location_id": (location or self.stock_location).id,
                    "inventory_quantity_auto_apply": quantity,
                }
            )
        )
        return self.env["stock.move"].search(
            [("product_id", "=", self.product.id), ("is_inventory", "=", True)]
        ), quant

    def test_the_connector_s_count_names_its_move_with_the_reference(self):
        moves, quant = self._apply(self.connector_user, "ST-TEST-1", 7)

        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[REFERENCE_FIELD], "ST-TEST-1")
        self.assertEqual(quant.quantity, 7)

    def test_a_second_count_with_the_same_reference_is_the_rerun_trace(self):
        self._apply(self.connector_user, "ST-TEST-2", 7)
        moves, _quant = self._apply(self.connector_user, "ST-TEST-2", 9)

        self.assertEqual(moves.mapped(REFERENCE_FIELD), ["ST-TEST-2", "ST-TEST-2"])

    def test_another_company_s_cell_is_not_counted_by_the_connector(self):
        """The connector counts a cell it read by writing the count on its
        quant (inventory mode, auto-apply). On 16 the application then runs
        with the checks lifted for the connector (``_apply_inventory`` is a
        stock manager's there); the lift never widens the scope: a quant of a
        company the connector is not in is refused, on 16 as on every series,
        and its stock stays (ADR 0013)."""
        other = self.env["res.company"].create({"name": "Second company"})
        other_stock = self.env["stock.warehouse"].search(
            [("company_id", "=", other.id)], limit=1
        ).lot_stock_id
        self.assertTrue(other_stock)
        self.product.company_id = False
        self.env["stock.quant"]._update_available_quantity(self.product, other_stock, 5)
        quant = self.env["stock.quant"].search(
            [("product_id", "=", self.product.id), ("location_id", "=", other_stock.id)]
        )
        self.assertEqual(len(quant), 1)

        with self.assertRaises(AccessError):
            quant.with_user(self.connector_user).with_context(
                inventory_mode=True, inventory_name="ST-OTHER"
            ).write({"inventory_quantity_auto_apply": 3})

        self.assertEqual(quant.quantity, 5)
