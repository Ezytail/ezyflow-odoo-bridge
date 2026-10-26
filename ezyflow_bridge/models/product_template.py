# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .wms_constraints import DEFER_KEY, PRODUCT_NAME_LIMIT, binds, deferred


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
        # template created with its whole identity. The checks wait for the end
        # of the create and then run on the templates and their variants as they
        # are. Odoo offers no hook between the variant generation and the related
        # write, so an override of create is the only place; the context key
        # covers every record created inside this call, and the explicit checks
        # at the end cover these templates and their variants.
        templates = super(ProductTemplate, self.with_context(**{DEFER_KEY: True})).create(
            vals_list
        )
        checked = templates.with_context(**{DEFER_KEY: False})
        checked._check_ezy_name()
        checked.product_variant_ids._ezy_check_identity()
        return templates.with_env(self.env)

    @api.constrains("name")
    def _check_ezy_name(self):
        # Behaviour 8 (ADR 0017). The internal reference and the barcode live on
        # the variant, which carries that half of the checks.
        if deferred(self.env):
            return
        for template in self:
            company = template.company_id or self.env.company
            if (
                template.name
                and len(template.name) > PRODUCT_NAME_LIMIT
                and binds(self.env, company, "ezy_wms_product_name_length")
            ):
                raise ValidationError(
                    self.env._(
                        "%(field)s of %(product)s is longer than %(limit)s characters, "
                        "the most the WMS accepts.",
                        field=template._fields["name"].get_description(self.env)["string"],
                        product=template.display_name,
                        limit=PRODUCT_NAME_LIMIT,
                    )
                )

    @api.constrains("sale_ok", "type")
    def _check_ezy_sellable_identity(self):
        # A template that becomes sellable goods re-checks its variants' reference.
        self.product_variant_ids._check_ezy_default_code_required()

    def _ezy_is_sellable_goods(self):
        self.ensure_one()
        return self.sale_ok and self.type == "consu"
