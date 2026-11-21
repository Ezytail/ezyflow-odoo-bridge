# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.tests import Form, new_test_user, tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestWarehouseSerials(EzyflowBridgeCase):
    """Serial numbers captured by the warehouse: a checkbox on a product Odoo
    does not track, off by default, shown on the product form to a person
    without Lots & Serial Numbers and hidden once Odoo tracks the product;
    Odoo's tracking is never refused because of it. The same on every series
    (ADR 0015)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Odoo 19 says "none" for an untracked product, Odoo 20 says nothing.
        selection = cls.env["product.template"]._fields["tracking"].get_values(cls.env)
        cls.untracked = "none" if "none" in selection else False
        cls.stock_manager = new_test_user(
            cls.env,
            login="ezy_serials_stock_manager",
            name="Stock manager without lots",
            groups="stock.group_stock_manager",
        )
        cls.lot_manager = new_test_user(
            cls.env,
            login="ezy_serials_lot_manager",
            name="Stock manager with lots",
            groups="stock.group_stock_manager,stock.group_production_lot",
        )

    def _template(self, **values):
        return self.env["product.template"].create(
            {"name": "Serialised good", **self.storable(), "sale_ok": False, **values}
        )

    def _hidden(self, template, user):
        return Form(template.with_user(user))._get_modifier("ezy_warehouse_serials", "invisible")

    def test_it_is_off_by_default(self):
        self.assertFalse(self._template(tracking=self.untracked).ezy_warehouse_serials)

    def test_an_untracked_product_may_have_it_checked(self):
        template = self._template(tracking=self.untracked)

        template.write({"ezy_warehouse_serials": True})

        self.assertTrue(template.ezy_warehouse_serials)

    def test_turning_tracking_on_afterwards_is_not_refused_and_keeps_the_value(self):
        template = self._template(tracking=self.untracked, ezy_warehouse_serials=True)

        template.write({"tracking": "serial"})
        self.assertTrue(template.ezy_warehouse_serials)
        template.write({"tracking": "lot"})
        self.assertTrue(template.ezy_warehouse_serials)

    def test_the_form_shows_it_on_an_untracked_product(self):
        template = self._template(tracking=self.untracked)

        self.assertFalse(
            self._hidden(template, self.stock_manager),
            "shown to a person without Lots & Serial Numbers",
        )
        self.assertFalse(self._hidden(template, self.lot_manager), "and to one with them")

    def test_the_form_hides_it_on_a_product_tracked_by_lots_or_serial_numbers(self):
        for tracking in ("lot", "serial"):
            with self.subTest(tracking=tracking):
                template = self._template(tracking=tracking)
                self.assertTrue(self._hidden(template, self.lot_manager))

    def test_a_change_moves_the_variant_write_date(self):
        # The product source pages the variants on their write date; Odoo 16
        # leaves it when a template field changes, the bridge moves it.
        template = self._template(tracking=self.untracked)
        variant = template.product_variant_id
        self.env.cr.execute(
            "UPDATE product_product SET write_date = '2000-01-01' WHERE id = %s", (variant.id,)
        )
        variant.invalidate_recordset(["write_date"])

        template.write({"ezy_warehouse_serials": True})
        variant.invalidate_recordset(["write_date"])

        self.assertGreater(variant.write_date.year, 2000)
