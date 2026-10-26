# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """The EzyFlow page of the Settings, the one place an administrator
    configures the bridge (ADR 0020): one setting per WMS constraint, Apply
    stock reports (ADR 0018) and the proforma report, all of the current
    company, and the three wake-up keys (ADR 0006), database-wide system
    parameters."""

    _inherit = "res.config.settings"

    # config_parameter is the settings form's own: Odoo 19 stores it through
    # set_param and Odoo 20 through set_str, the bridge declares it once
    # (ADR 0015). The bridge reads the rows back in ezyflow.wakeup._param.
    ezy_activity = fields.Char(
        string="Activity",
        config_parameter="ezyflow.activity",
        help="The activity this Odoo belongs to on the EzyFlow platform.",
    )
    ezy_wakeup_url = fields.Char(
        string="Wake-up URL",
        config_parameter="ezyflow.wakeup_url",
        help="The connector's wake-up endpoint, https://<connector>/wake-up.",
    )
    ezy_wakeup_secret = fields.Char(
        string="Wake-up secret",
        config_parameter="ezyflow.wakeup_secret",
        help="The secret the wake-ups are signed with, the value the publication's "
        "odoo_wakeup_secret points to.",
    )

    ezy_proforma_report_id = fields.Many2one(
        related="company_id.ezy_proforma_report_id", readonly=False
    )

    ezy_apply_stock_reports = fields.Boolean(
        related="company_id.ezy_apply_stock_reports", readonly=False
    )

    ezy_wms_default_code_length = fields.Boolean(
        related="company_id.ezy_wms_default_code_length", readonly=False
    )
    ezy_wms_default_code_alphabet = fields.Boolean(
        related="company_id.ezy_wms_default_code_alphabet", readonly=False
    )
    ezy_wms_default_code_unique = fields.Boolean(
        related="company_id.ezy_wms_default_code_unique", readonly=False
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
