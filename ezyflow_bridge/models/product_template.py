# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models, release
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

    ezy_rotation_date_type = fields.Selection(
        selection=[
            ("manufacturing_date", "Manufacturing date"),
            ("best_before", "Best-before date (DDM)"),
            ("sell_by", "Sell-by date (DLV)"),
            ("use_by", "Use-by date (DLC)"),
        ],
        string="Rotation date type",
        help="The date the warehouse rotates this product's stock on: it captures that date at "
        "reception and ships the oldest first. Empty: the receipt date, first in first out. "
        "Only a product tracked by lots or by serial numbers can have one. Odoo's own stock "
        "carries no such date; the warehouse keeps it.",
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

    @api.constrains("company_id")
    def _check_ezy_company_default_code(self):
        # A template moved into another company, or shared by every company,
        # re-checks that its variants' SKU is still held by them alone.
        if deferred(self.env):
            return
        for product in self.product_variant_ids:
            product._ezy_check_default_code_unique()

    @api.constrains("sale_ok", "type")
    def _check_ezy_sellable_identity(self):
        # A template that becomes sellable goods re-checks its variants' reference.
        self.product_variant_ids._check_ezy_default_code_required()

    @api.constrains("ezy_rotation_date_type", "tracking")
    def _check_ezy_rotation_date_type(self):
        # ADR 0034: only a traceable product names the date its stock rotates
        # on. Odoo 19 says "none" for an untracked product, Odoo 20 says nothing.
        for template in self:
            if template.ezy_rotation_date_type and template.tracking not in ("lot", "serial"):
                raise ValidationError(
                    self.env._(
                        "%(product)s is not tracked by lots or by serial numbers, so it cannot "
                        "have a %(field)s. Clear the %(field)s before turning tracking off.",
                        product=template.display_name,
                        field=template._fields["ezy_rotation_date_type"].get_description(self.env)[
                            "string"
                        ],
                    )
                )

    # The template fields the product source publishes from the variant's
    # page (S6, ADR 0034): a change bumps the variants' write date on 17 and
    # later; 16 leaves it, so the source would miss the change there.
    _EZY_PUBLISHED_TEMPLATE_FIELDS = frozenset(
        {
            "name",
            "active",
            "sale_ok",
            "detailed_type",
            "tracking",
            "ezy_rotation_date_type",
            "ezy_shop_product_id",
            "hs_code",
            "country_of_origin",
            "list_price",
        }
    )

    def write(self, vals):
        result = super().write(vals)
        if release.version_info[0] < 17 and self._EZY_PUBLISHED_TEMPLATE_FIELDS.intersection(vals):
            variants = self.with_context(active_test=False).product_variant_ids
            if variants:
                self.env.cr.execute(
                    "UPDATE product_product SET write_date = now() AT TIME ZONE 'UTC' "
                    "WHERE id IN %s",
                    (tuple(variants.ids),),
                )
                variants.invalidate_recordset(["write_date"])
        return result

    def _ezy_is_sellable_goods(self):
        self.ensure_one()
        # Goods: "consu" from 17 (storable or not); on 16 the type is "product"
        # for storable goods and "consu" for the others.
        return self.sale_ok and self.type in ("consu", "product")
