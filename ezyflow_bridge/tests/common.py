# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import unittest

from lxml import etree

from odoo import Command, release
from odoo.tests import TransactionCase, new_test_user


def bridge_owned(reason, module="ezyflow_bridge_legacy_glue"):
    """Skips a test class on a database where ``module`` is installed (the
    legacy glue by default): the behaviour it asserts is the legacy module's
    there (ADR 0035), and the glue's own tests say what holds instead."""

    def decorate(cls):
        original = cls.setUpClass.__func__

        @classmethod
        def setUpClass(klass):
            original(klass)
            installed = klass.env["ir.module.module"].search_count(
                [("name", "=", module), ("state", "=", "installed")]
            )
            if installed:
                raise unittest.SkipTest(f"{module} installed: {reason}")

        cls.setUpClass = setUpClass
        return cls

    return decorate


MODULE = "ezyflow_bridge"


class SettingsPage:
    """One reading of the EzyFlow settings app on both markups: a block has a
    name and a title, a setting an id, each holds its fields and buttons."""

    def __init__(self, arch):
        self.arch = arch
        self.modern = release.version_info[0] >= 17
        self.apps = (
            arch.xpath("//app[@name='ezyflow_bridge']")
            if self.modern
            else arch.xpath("//div[@data-key='ezyflow_bridge']")
        )

    @property
    def app(self):
        [app] = self.apps
        return app

    def blocks(self):
        """[(name, title, element)] in page order."""
        if self.modern:
            return [(b.get("name"), b.get("title"), b) for b in self.app.xpath("block")]
        return [
            (b.get("name"), b.getprevious().text, b)
            for b in self.app.xpath("div[contains(@class, 'o_settings_container')]")
        ]

    def block(self, name):
        [found] = [b for n, _t, b in self.blocks() if n == name]
        return found

    def settings(self, block):
        """[(id, element)] of a block."""
        if self.modern:
            return [(s.get("id"), s) for s in block.xpath("setting")]
        return [(s.get("id"), s) for s in block.xpath("div[contains(@class, 'o_setting_box')]")]


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
                **cls.storable(),
                "default_code": "GOOD-1",
                "barcode": "3000000000017",
            }
        )
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.stock_location, 100)
        # A phone and an email: a person confirms the test orders, and the WMS
        # constraints require both on the delivery address (behaviour 8).
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Web customer",
                "ezy_channel": "WEB",
                "phone": "+33100000000",
                "email": "web.customer@example.test",
            }
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

    def move_name(self):
        """A move's name is required below Odoo 19 and absent from 19 on (ADR 0015)."""
        return {"name": "/"} if release.version_info[0] < 19 else {}

    @staticmethod
    def storable():
        """Storable goods: ``is_storable`` from 18, ``detailed_type`` on 16, whose
        ``type`` follows it (ADR 0035)."""
        if release.version_info[0] >= 18:
            return {"is_storable": True}
        return {"detailed_type": "product", "type": "product"}

    def validate(self, picking):
        """A person's Validate of a transfer with nothing prepared: 17 and
        later validate the reserved quantities, 16 opens its immediate-transfer
        wizard unless the done quantities are written first."""
        if release.version_info[0] < 17:
            for move in picking.move_ids:
                if not move.quantity_done:
                    move.quantity_done = move.product_uom_qty
        return picking.button_validate()

    def count_by(self, model, domain, field):
        """{value: count} of a grouping: ``_read_group`` from 17, ``read_group`` on 16."""
        if release.version_info[0] >= 17:
            return dict(self.env[model]._read_group(domain, [field], ["__count"]))
        return {
            row[field]: row[f"{field}_count"]
            for row in self.env[model].read_group(domain, [field], [field])
        }

    def skip_below_seventeen(self, reason):
        """A test of what 16 does not have (ADR 0035)."""
        if release.version_info[0] < 17:
            self.skipTest(f"Odoo {release.version_info[0]}: {reason}")

    @staticmethod
    def move_quantity_field():
        """The move's quantity field a person or the connector writes: one from
        17, the done one on 16."""
        return "quantity" if release.version_info[0] >= 17 else "quantity_done"

    @staticmethod
    def line_quantity_field():
        return "quantity" if release.version_info[0] >= 17 else "qty_done"

    @staticmethod
    def line_reserved_field():
        """What a move line reserved: ``quantity_product_uom`` from 17,
        ``reserved_uom_qty`` on 16."""
        return "quantity_product_uom" if release.version_info[0] >= 17 else "reserved_uom_qty"

    def settings_page(self, user=None):
        """The EzyFlow app of the Settings form, read the way the series writes
        it (ADR 0015): <app>, <block> and <setting> from 17, the div markup on 16."""
        settings = self.env["res.config.settings"]
        if user is not None:
            settings = settings.with_user(user)
        views = settings.get_views([(False, "form")])
        return SettingsPage(etree.fromstring(views["views"]["form"]["arch"]))

    @staticmethod
    def done(quantity):
        """A done quantity on a move: one figure and the picked flag from 17,
        ``quantity_done`` on 16 (the 16 delta)."""
        if release.version_info[0] >= 17:
            return {"quantity": quantity, "picked": True}
        return {"quantity_done": quantity}

    @staticmethod
    def move_quantity(moves):
        """The moves' quantity as the connector reads it, summed: one figure
        from 17; on 16 the done one once something is done, the reserved one
        before (a remainder 16 split into a cancelled move counts nothing)."""
        if release.version_info[0] >= 17:
            return sum(moves.mapped("quantity"))
        return sum(move.quantity_done or move.reserved_availability for move in moves)

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
                            **self.move_name(),
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
