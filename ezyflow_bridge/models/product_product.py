# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models
from odoo.exceptions import ValidationError

DEFAULT_CODE_LIMIT = 17


class ProductProduct(models.Model):
    _inherit = "product.product"

    ezy_shop_variant_id = fields.Char(
        string="Shop variant id",
        index="btree_not_null",
        copy=False,
        help="The id this variant has in the web shop. The connector uses it to find the "
        "Odoo record before falling back to the internal reference. One shop per Odoo product.",
    )

    # name and product_tmpl_id are always in the creation values, so the check
    # runs for a variant created without a reference at all.
    @api.constrains("name", "product_tmpl_id", "default_code", "sale_ok", "type")
    def _check_ezy_wms_identity(self):
        # Behaviour 8: the WMS identifies a product by its internal reference and
        # stores at most 17 characters of it. The barcode is optional (3.4.0): a
        # product without one is sold and shipped by its reference.
        # A template being created checks its variants once it is complete; the
        # connector asks for the same deferral when it adds attribute values to a
        # template (Odoo generates the new variant without identity in that
        # write) and writes the identity in its next call, which runs the check.
        if self.env.context.get("ezy_defer_wms_identity"):
            return
        for product in self:
            template = product.product_tmpl_id
            if not template._ezy_checks_products():
                continue
            if product.default_code and len(product.default_code) > DEFAULT_CODE_LIMIT:
                raise ValidationError(
                    self.env._(
                        "The internal reference of %(product)s is longer than %(limit)s "
                        "characters, the most the WMS accepts.",
                        product=product.display_name,
                        limit=DEFAULT_CODE_LIMIT,
                    )
                )
            if not template._ezy_is_sellable_goods():
                continue
            if not product.default_code:
                raise ValidationError(
                    self.env._(
                        "%(product)s is sold as goods and has no internal reference; "
                        "the WMS identifies products by it.",
                        product=product.display_name,
                    )
                )
