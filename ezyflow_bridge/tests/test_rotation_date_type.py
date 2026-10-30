# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.exceptions import ValidationError
from odoo.tests import Form, new_test_user, tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestRotationDateType(EzyflowBridgeCase):
    """The rotation date type (ADR 0034): only a product tracked by lots or by
    serial numbers names the date its stock rotates on, and the product form
    shows the field only then."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Odoo 19 says "none" for an untracked product, Odoo 20 says nothing.
        selection = cls.env["product.template"]._fields["tracking"].get_values(cls.env)
        cls.untracked = "none" if "none" in selection else False
        cls.lot_manager = new_test_user(
            cls.env,
            login="ezy_lot_manager",
            name="Lot manager",
            groups="stock.group_stock_manager,stock.group_production_lot",
        )

    def _template(self, **values):
        return self.env["product.template"].create(
            {"name": "Rotating good", "is_storable": True, "sale_ok": False, **values}
        )

    def test_a_traceable_product_holds_a_rotation_date_type(self):
        template = self._template(tracking="lot", ezy_rotation_date_type="best_before")
        self.assertEqual(template.ezy_rotation_date_type, "best_before")

        template.write({"tracking": "serial", "ezy_rotation_date_type": "use_by"})
        self.assertEqual(template.ezy_rotation_date_type, "use_by")

    def test_a_traceable_product_may_leave_it_empty(self):
        self.assertFalse(self._template(tracking="lot").ezy_rotation_date_type)

    def test_an_untracked_product_cannot_hold_one(self):
        template = self._template(tracking=self.untracked)

        with self.assertRaises(ValidationError) as refused:
            template.write({"ezy_rotation_date_type": "use_by"})

        self.assertIn("Rotating good is not tracked by lots", str(refused.exception))
        self.assertIn("Rotation date type", str(refused.exception))

    def test_turning_tracking_off_on_a_product_that_holds_one_is_refused(self):
        template = self._template(tracking="serial", ezy_rotation_date_type="sell_by")

        with self.assertRaises(ValidationError) as refused:
            template.write({"tracking": self.untracked})

        self.assertIn("Rotating good is not tracked by lots", str(refused.exception))

    def test_clearing_it_first_lets_tracking_be_turned_off(self):
        template = self._template(tracking="lot", ezy_rotation_date_type="manufacturing_date")

        template.write({"ezy_rotation_date_type": False, "tracking": self.untracked})

        self.assertNotIn(template.tracking, ("lot", "serial"))

    def test_the_form_shows_the_field_on_a_traceable_product_only(self):
        traceable = self._template(tracking="lot").with_user(self.lot_manager)
        untracked = self._template(tracking=self.untracked).with_user(self.lot_manager)

        self.assertFalse(
            Form(traceable)._get_modifier("ezy_rotation_date_type", "invisible"),
            "a product tracked by lots shows its rotation date type",
        )
        self.assertTrue(
            Form(untracked)._get_modifier("ezy_rotation_date_type", "invisible"),
            "an untracked product hides it",
        )
