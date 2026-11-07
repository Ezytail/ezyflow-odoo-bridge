# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The shop ids (ADR 0035): the EzyFlow NG CMS bridge of the 18 tenants keeps
them as tmp_cms_id and variant_cms_id; the bridge's fields mirror them."""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    ezy_shop_product_id = fields.Char(related="tmp_cms_id", store=True, readonly=False)


class ProductProduct(models.Model):
    _inherit = "product.product"

    ezy_shop_variant_id = fields.Char(related="variant_cms_id", store=True, readonly=False)
