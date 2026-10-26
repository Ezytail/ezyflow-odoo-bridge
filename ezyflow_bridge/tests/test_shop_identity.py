# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestShopIdentity(EzyflowBridgeCase):
    """The shop ids the connector finds a product by before falling back to the SKU."""

    def _product(self, **values):
        return self.env["product.product"].create(
            {"name": "Shop item", "default_code": "SHOP-1", "barcode": "5412345000013", **values}
        )

    def test_the_shop_product_id_is_stored_and_searchable(self):
        product = self._product(ezy_shop_product_id="gid://shop/Product/42")

        found = self.env["product.template"].search(
            [("ezy_shop_product_id", "=", "gid://shop/Product/42")]
        )

        self.assertEqual(found, product.product_tmpl_id)

    def test_the_shop_variant_id_is_stored_and_searchable(self):
        product = self._product(ezy_shop_variant_id="gid://shop/Variant/7")

        found = self.env["product.product"].search(
            [("ezy_shop_variant_id", "=", "gid://shop/Variant/7")]
        )

        self.assertEqual(found, product)

    def test_a_copy_does_not_carry_the_shop_ids(self):
        # Not sellable, so the copy is not asked for a reference and a barcode.
        product = self._product(
            sale_ok=False, ezy_shop_product_id="P-1", ezy_shop_variant_id="V-1"
        )

        copy = product.copy()

        self.assertFalse(copy.ezy_shop_product_id)
        self.assertFalse(copy.ezy_shop_variant_id)
        self.assertEqual(product.ezy_shop_product_id, "P-1")
