# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import Command
from odoo.tests import TransactionCase, new_test_user


class EzyflowBridgeCase(TransactionCase):
    """One warehouse in the company, a connector user, a warehouse user, a
    sellable good in stock and a WEB customer. Every test configures the
    operation types it needs; the transaction rolls it all back."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.out_type = cls.warehouse.out_type_id
        cls.in_type = cls.warehouse.in_type_id
        cls.int_type = cls.warehouse.int_type_id
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.shelf = cls.env["stock.location"].create(
            {"name": "Shelf", "usage": "internal", "location_id": cls.stock_location.id}
        )
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        # Reservation on demand: a confirmed delivery stays unreserved until a
        # test reserves it, so the moment of the offer is the test's to choose.
        cls.out_type.reservation_method = "manual"

        cls.connector_user = new_test_user(
            cls.env,
            login="ezy_connector",
            name="EzyFlow connector",
            groups="ezyflow_bridge.group_ezyflow_connector",
        )
        cls.warehouse_user = new_test_user(
            cls.env,
            login="ezy_warehouse",
            name="Warehouse person",
            groups="stock.group_stock_user,sales_team.group_sale_salesman",
        )
        cls.admin_user = cls.env.ref("base.user_admin")

        cls.product = cls.env["product.product"].create(
            {
                "name": "Sellable good",
                "is_storable": True,
                "default_code": "GOOD-1",
                "barcode": "3000000000017",
            }
        )
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.stock_location, 100)
        cls.customer = cls.env["res.partner"].create(
            {"name": "Web customer", "ezy_channel": "WEB"}
        )

    def confirm_order(self, partner=None, product=None, quantity=5, **values):
        """A confirmed sales order on the warehouse; returns its delivery."""
        order = self.env["sale.order"].create(
            {
                "partner_id": (partner or self.customer).id,
                "warehouse_id": self.warehouse.id,
                "order_line": [
                    Command.create(
                        {"product_id": (product or self.product).id, "product_uom_qty": quantity}
                    )
                ],
                **values,
            }
        )
        order.action_confirm()
        return order.picking_ids

    def create_picking(self, picking_type, location, location_dest, quantity=5):
        """A confirmed transfer of one move, outside any sales order."""
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": location.id,
                "location_dest_id": location_dest.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": quantity,
                            "location_id": location.id,
                            "location_dest_id": location_dest.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        return picking

    def set_wms_state(self, picking, state):
        """What the connector does: writes the state as the connector user."""
        picking.with_user(self.connector_user).write({"ezy_wms_state": state})
