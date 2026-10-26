# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import release
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestFulfilmentRights(EzyflowBridgeCase):
    """S4: the connector user validates a delivery the warehouse prepared,
    including a product the order did not name. Core sale_stock then adds the
    line to the sales order, so the connector group carries write and create
    on sales order lines (and no sales group, which would scope its view of
    orders to its own documents)."""

    def test_the_connector_validates_a_delivery_with_an_extra_product(self):
        picking = self.confirm_order()
        picking.action_assign()
        # A delivery the WMS is preparing: the only one whose lines the connector
        # may add to the order (the S4 record rule).
        self.set_wms_state(picking, "preparation_to_do")
        extra = self.env["product.product"].create(
            {
                "name": "Extra",
                "is_storable": True,
                "default_code": "EXTRA",
                "barcode": "EZYEXTRA",
            }
        )
        self.env["stock.quant"]._update_available_quantity(
            extra, self.stock_location, 3
        )
        as_connector = picking.with_user(self.connector_user)
        as_connector.write(
            {
                "move_ids": [
                    (1, picking.move_ids.id, {"quantity": 5, "picked": True}),
                    (
                        0,
                        0,
                        {
                            "product_id": extra.id,
                            "product_uom_qty": 2,
                            "quantity": 2,
                            "picked": True,
                            "additional": True,
                            "location_id": picking.location_id.id,
                            "location_dest_id": picking.location_dest_id.id,
                        },
                    ),
                ]
            }
        )

        as_connector.with_context(skip_backorder=True).button_validate()

        self.assertEqual(picking.state, "done")
        lines = picking.sale_id.order_line.filtered(lambda line: line.product_id == extra)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.qty_delivered, 2)

    def test_the_connector_cannot_touch_lines_of_an_order_outside_the_hand_off(self):
        picking = self.confirm_order()
        line = picking.sale_id.order_line[0]
        self.assertFalse(picking.ezy_wms_state)

        with self.assertRaises(AccessError):
            self.env["sale.order.line"].with_user(self.connector_user).create(
                {
                    "order_id": picking.sale_id.id,
                    "product_id": self.product.id,
                    "product_uom_qty": 1,
                }
            )
        if release.version_info[0] == 19:
            # Odoo 20's sale_stock grants every stock user the update of any
            # sales order line (ir.access "ru" without domain); Odoo 19 grants
            # the read only, so the bridge's rule is what narrows the write there.
            with self.assertRaises(AccessError):
                line.with_user(self.connector_user).write({"price_unit": 1.0})

        # Once the transfer is in the hand-off, the line is the connector's to
        # complete: the right follows the transfer, not the order.
        self.set_wms_state(picking, "ready_for_logistics")
        line.with_user(self.connector_user).write({"name": line.name})
