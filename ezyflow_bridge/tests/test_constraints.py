# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestConstraints(EzyflowBridgeCase):
    """Behaviour 8: the lengths and identities the WMS accepts, behind the
    company toggles."""

    def new_product(self, **values):
        # Barcodes are unique across products; each call gets its own.
        self.serial = getattr(self, "serial", 0) + 1
        return self.env["product.product"].create(
            {
                "name": "Good",
                "default_code": "GOOD-%d" % self.serial,
                "barcode": "EZY%09d" % self.serial,
                **values,
            }
        )

    def test_a_sellable_good_needs_an_internal_reference_and_a_barcode(self):
        with self.assertRaisesRegex(ValidationError, "internal reference"):
            self.new_product(default_code=False)
        with self.assertRaisesRegex(ValidationError, "barcode"):
            self.new_product(barcode=False)
        self.assertTrue(self.new_product())

    def test_the_company_toggle_lifts_the_product_constraints(self):
        self.company.ezy_check_product_constraints = False

        self.assertTrue(self.new_product(default_code=False, barcode=False, name="x" * 40))

    def test_services_and_goods_not_for_sale_need_no_identity(self):
        self.assertTrue(self.new_product(type="service", default_code=False, barcode=False))
        self.assertTrue(self.new_product(sale_ok=False, default_code=False, barcode=False))

    def test_a_good_that_becomes_sellable_is_checked(self):
        product = self.new_product(sale_ok=False, default_code=False, barcode=False)

        with self.assertRaisesRegex(ValidationError, "internal reference"):
            product.product_tmpl_id.sale_ok = True

    def test_product_name_and_reference_lengths(self):
        with self.assertRaisesRegex(ValidationError, "30 characters"):
            self.new_product(name="x" * 31)
        with self.assertRaisesRegex(ValidationError, "17 characters"):
            self.new_product(default_code="x" * 18)
        self.assertTrue(self.new_product(name="x" * 30, default_code="x" * 17))

    def test_partner_lengths(self):
        Partner = self.env["res.partner"]
        with self.assertRaisesRegex(ValidationError, "50 characters"):
            Partner.create({"name": "x" * 51})
        with self.assertRaisesRegex(ValidationError, "35 characters"):
            Partner.create({"name": "Long street", "street": "x" * 36})
        with self.assertRaisesRegex(ValidationError, "35 characters"):
            Partner.create({"name": "Long street 2", "street2": "x" * 36})
        self.assertTrue(
            Partner.create({"name": "x" * 50, "street": "x" * 35, "street2": "x" * 35})
        )

    def test_the_company_toggle_lifts_the_partner_constraints(self):
        self.company.ezy_check_partner_constraints = False

        self.assertTrue(self.env["res.partner"].create({"name": "x" * 51, "street": "x" * 36}))
