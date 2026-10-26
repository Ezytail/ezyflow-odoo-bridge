# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """The EzyFlow page of the Settings: one setting per WMS constraint."""

    _inherit = "res.config.settings"

    ezy_wms_default_code_length = fields.Boolean(
        related="company_id.ezy_wms_default_code_length", readonly=False
    )
    ezy_wms_default_code_alphabet = fields.Boolean(
        related="company_id.ezy_wms_default_code_alphabet", readonly=False
    )
    ezy_wms_default_code_required = fields.Boolean(
        related="company_id.ezy_wms_default_code_required", readonly=False
    )
    ezy_wms_product_name_length = fields.Boolean(
        related="company_id.ezy_wms_product_name_length", readonly=False
    )
    ezy_wms_barcode_alphabet = fields.Boolean(
        related="company_id.ezy_wms_barcode_alphabet", readonly=False
    )
    ezy_wms_barcode_length = fields.Boolean(
        related="company_id.ezy_wms_barcode_length", readonly=False
    )
    ezy_wms_partner_name_length = fields.Boolean(
        related="company_id.ezy_wms_partner_name_length", readonly=False
    )
    ezy_wms_street_length = fields.Boolean(
        related="company_id.ezy_wms_street_length", readonly=False
    )
    ezy_wms_city_length = fields.Boolean(related="company_id.ezy_wms_city_length", readonly=False)
    ezy_wms_zip_length = fields.Boolean(related="company_id.ezy_wms_zip_length", readonly=False)
    ezy_wms_phone_length = fields.Boolean(
        related="company_id.ezy_wms_phone_length", readonly=False
    )
    ezy_wms_email_length = fields.Boolean(
        related="company_id.ezy_wms_email_length", readonly=False
    )
    ezy_wms_delivery_contact_required = fields.Boolean(
        related="company_id.ezy_wms_delivery_contact_required", readonly=False
    )
    ezy_wms_picking_name = fields.Boolean(
        related="company_id.ezy_wms_picking_name", readonly=False
    )
