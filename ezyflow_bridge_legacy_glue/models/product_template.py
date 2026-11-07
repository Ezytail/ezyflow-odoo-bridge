# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The legacy module's product checks read the new records as one (the
template's description checks, the variant's barcode check), so a batch of
products, the connector's way of creating a catalogue, fails on the second
record. One record per call keeps the legacy module's assumption; the
connector never learns."""
from odoo import api, models


def _one_per_call(model, create, vals_list):
    if len(vals_list) <= 1:
        return create(vals_list)
    records = model.browse()
    for vals in vals_list:
        records |= create([vals])
    return records


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        return _one_per_call(self, super().create, vals_list)


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model_create_multi
    def create(self, vals_list):
        return _one_per_call(self, super().create, vals_list)
