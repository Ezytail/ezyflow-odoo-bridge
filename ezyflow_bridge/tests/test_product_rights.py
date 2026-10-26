# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestProductRights(EzyflowBridgeCase):
    """S6: the connector user creates attributes and a product with variants,
    writes a variant's reference and barcode, writes variant-level price list
    items and archives a variant; it deletes none of them (least privilege,
    ADR 0013). The same rights on every series (ADR 0015)."""

    def test_the_connector_creates_variants_and_prices_them(self):
        as_connector = self.env(user=self.connector_user)
        attribute = as_connector["product.attribute"].create(
            {
                "name": "Size",
                "value_ids": [Command.create({"name": "S"}), Command.create({"name": "M"})],
            }
        )
        self.assertEqual(len(attribute.value_ids), 2)
        template = as_connector["product.template"].create(
            {
                "name": "Shirt",
                "type": "consu",
                "is_storable": True,
                # Off sale while the generated variants have no identity (behaviour 8).
                "sale_ok": False,
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": attribute.id,
                            "value_ids": [Command.set(attribute.value_ids.ids)],
                        }
                    )
                ],
            }
        )
        variants = template.product_variant_ids
        self.assertEqual(len(variants), 2)
        variant, other = variants[0], variants[1]
        variant.write({"default_code": "SHIRT-S", "barcode": "3000000000123"})
        other.write({"default_code": "SHIRT-M", "barcode": "3000000000130"})
        self.assertEqual(variant.default_code, "SHIRT-S")
        self.assertEqual(variant.barcode, "3000000000123")
        template.write({"sale_ok": True})
        self.assertTrue(template.sale_ok)

        pricelist = self.env["product.pricelist"].search(
            [("company_id", "in", [False, self.company.id])], limit=1
        ) or self.env["product.pricelist"].create({"name": "Default"})
        item = as_connector["product.pricelist.item"].create(
            {
                "pricelist_id": pricelist.id,
                "applied_on": "0_product_variant",
                "product_id": variant.id,
                "compute_price": "fixed",
                "fixed_price": 12.5,
            }
        )
        self.assertEqual(item.fixed_price, 12.5)
        item.write({"fixed_price": 13.0})
        self.assertEqual(item.fixed_price, 13.0)

        other.write({"active": False})
        self.assertFalse(other.active)
        self.assertEqual(template.product_variant_ids, variant)

    def test_the_connector_does_not_unlink_a_price_list_item(self):
        pricelist = self.env["product.pricelist"].create({"name": "Retail"})
        item = self.env["product.pricelist.item"].create(
            {
                "pricelist_id": pricelist.id,
                "applied_on": "0_product_variant",
                "product_id": self.product.id,
                "compute_price": "fixed",
                "fixed_price": 9.0,
            }
        )
        with self.assertRaises(AccessError):
            item.with_user(self.connector_user).unlink()
