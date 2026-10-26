# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestTemplateIdentity(EzyflowBridgeCase):
    """Behaviour 8 on a template create: Odoo validates the generated variant
    before it writes the template's internal reference and barcode onto it,
    so the bridge checks the variants once the create is complete. A sellable
    template created with its whole identity is accepted, and so is one
    without barcode; one without internal reference is refused."""

    def new_template(self, env, code, barcode):
        return env["product.template"].create(
            {
                "name": "Mug",
                "type": "consu",
                "is_storable": True,
                "sale_ok": True,
                "default_code": code,
                "barcode": barcode,
            }
        )

    def test_a_sellable_template_with_its_identity_is_created_by_a_person(self):
        template = self.new_template(self.env, "MUG-ADMIN", "3000000000901")

        self.assertEqual(template.product_variant_ids.default_code, "MUG-ADMIN")
        self.assertEqual(template.product_variant_ids.barcode, "3000000000901")

    def test_a_sellable_template_with_its_identity_is_created_by_the_connector(self):
        template = self.new_template(
            self.env(user=self.connector_user), "MUG-CONN", "3000000000918"
        )

        self.assertEqual(template.product_variant_ids.default_code, "MUG-CONN")

    def test_a_sellable_template_without_barcode_is_accepted(self):
        template = self.new_template(self.env, "MUG-NOBC", False)

        self.assertEqual(template.product_variant_ids.default_code, "MUG-NOBC")
        self.assertFalse(template.product_variant_ids.barcode)

    def test_a_sellable_template_without_internal_reference_is_refused(self):
        with self.assertRaisesRegex(ValidationError, "internal reference"):
            self.new_template(self.env, False, "3000000000949")

    def test_the_connector_adds_a_value_under_the_deferral_and_then_the_identity(self):
        # Adding a value generates a variant without identity inside the write;
        # the connector defers the check for that write and the identity write
        # that follows runs it. Without the deferral the write is refused.
        colour = self.env["product.attribute"].create(
            {"name": "Colour", "value_ids": [(0, 0, {"name": "Red"}), (0, 0, {"name": "Blue"})]}
        )
        red, blue = colour.value_ids
        template = self.env["product.template"].create(
            {
                "name": "Tee",
                "type": "consu",
                "is_storable": True,
                "sale_ok": True,
                "default_code": "TEE-RED",
                "barcode": "3000000000925",
                "attribute_line_ids": [
                    (0, 0, {"attribute_id": colour.id, "value_ids": [(6, 0, [red.id])]})
                ],
            }
        )
        line = template.attribute_line_ids
        connector = template.with_env(self.env(user=self.connector_user))

        with self.assertRaisesRegex(ValidationError, "internal reference"):
            connector.write({"attribute_line_ids": [(1, line.id, {"value_ids": [(4, blue.id)]})]})

        connector.with_context(ezy_defer_wms_identity=True).write(
            {"attribute_line_ids": [(1, line.id, {"value_ids": [(4, blue.id)]})]}
        )
        generated = template.product_variant_ids.filtered(lambda v: not v.default_code)
        self.assertEqual(len(generated), 1)
        self.assertTrue(template.sale_ok)
        generated.with_env(self.env(user=self.connector_user)).write(
            {"default_code": "TEE-BLUE", "barcode": "3000000000932"}
        )
        self.assertEqual(generated.barcode, "3000000000932")
