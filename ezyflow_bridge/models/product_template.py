# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models
from odoo.exceptions import ValidationError

PRODUCT_NAME_LIMIT = 30


class ProductTemplate(models.Model):
    _inherit = "product.template"

    ezy_shop_product_id = fields.Char(
        string="Shop product id",
        index="btree_not_null",
        copy=False,
        help="The id this product has in the web shop. The connector uses it to find the "
        "Odoo record before falling back to the internal reference. One shop per Odoo product.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Odoo's template create generates the variants and validates them before
        # it writes the template's default_code and barcode onto its single
        # variant, so the variant half of behaviour 8 would refuse a sellable
        # template created with its whole identity. The check waits for the end
        # of the create and then runs on the variants as they are. Odoo offers no
        # hook between the variant generation and the related write, so an
        # override of create is the only place; the context key covers every
        # variant created inside this call, and the explicit check at the end
        # covers the variants of these templates.
        templates = super(
            ProductTemplate, self.with_context(ezy_defer_wms_identity=True)
        ).create(vals_list)
        templates.with_context(
            ezy_defer_wms_identity=False
        ).product_variant_ids._check_ezy_wms_identity()
        return templates.with_env(self.env)

    @api.constrains("name", "sale_ok", "type")
    def _check_ezy_wms_identity(self):
        # Behaviour 8. The internal reference lives on the variant, so the
        # variant carries that half of the check; a template that becomes
        # sellable goods re-checks its variants.
        for template in self:
            if not template._ezy_checks_products():
                continue
            if template.name and len(template.name) > PRODUCT_NAME_LIMIT:
                raise ValidationError(
                    self.env._(
                        "The name of %(product)s is longer than %(limit)s characters, "
                        "the most the WMS accepts.",
                        product=template.display_name,
                        limit=PRODUCT_NAME_LIMIT,
                    )
                )
            template.product_variant_ids._check_ezy_wms_identity()

    def _ezy_checks_products(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        return company.ezy_check_product_constraints

    def _ezy_is_sellable_goods(self):
        self.ensure_one()
        return self.sale_ok and self.type == "consu"
