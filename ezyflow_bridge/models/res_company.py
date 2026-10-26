# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import fields, models


class ResCompany(models.Model):
    """One switch per WMS constraint (behaviour 8, ADR 0017), on by default.
    Each help names the exact figure; none binds the connector user. And
    Apply stock reports (ADR 0018), off by default, which the connector reads.
    And the proforma report (ADR 0020), read by the render of the company's
    orders."""

    _inherit = "res.company"

    ezy_apply_stock_reports = fields.Boolean(
        string="Apply stock reports",
        default=False,
        help="Apply the figures of a WMS stock report to the quantities on hand. "
        "Off, they are written as pending counts to review and apply from the "
        "physical inventory, and Odoo republishes nothing for the report. WMS "
        "movements are always applied.",
    )

    ezy_proforma_report_id = fields.Many2one(
        "ir.actions.report",
        string="Proforma report",
        domain=[("model", "=", "sale.order")],
        ondelete="set null",
        help="The sales order report the connector renders as the Proforma of this "
        "company's orders and forwards to the WMS for shipment paperwork. Empty, "
        "Odoo's pro forma invoice.",
    )

    ezy_wms_default_code_length = fields.Boolean(
        string="Internal reference: at most 16 characters",
        default=True,
        help="Refuse an internal reference longer than 16 characters, the longest "
        "SKU Reflex stores.",
    )
    ezy_wms_default_code_alphabet = fields.Boolean(
        string="Internal reference: A-Z 0-9 _ . - # only",
        default=True,
        help="Refuse an internal reference with a character other than the capital "
        "letters A to Z, the digits 0 to 9 and _ . - #, the SKU alphabet of Reflex.",
    )
    ezy_wms_default_code_unique = fields.Boolean(
        string="Internal reference: one active product per reference",
        default=True,
        help="Refuse an internal reference another active product of the company, "
        "or a product shared by every company, already holds, compared without "
        "regard to case: Reflex keeps one article per SKU and would merge the two.",
    )
    ezy_wms_default_code_required = fields.Boolean(
        string="Internal reference: required for sellable goods",
        default=True,
        help="Refuse a sellable good (a product that can be sold and is goods) "
        "without internal reference: Reflex identifies products by it.",
    )
    ezy_wms_product_name_length = fields.Boolean(
        string="Product name: at most 30 characters",
        default=True,
        help="Refuse a product name longer than 30 characters.",
    )
    ezy_wms_barcode_alphabet = fields.Boolean(
        string="Barcode: letters and digits only",
        default=True,
        help="Refuse a barcode, when there is one, with a character other than a "
        "letter or a digit.",
    )
    ezy_wms_barcode_length = fields.Boolean(
        string="Barcode: at most 35 characters",
        default=True,
        help="Refuse a barcode longer than 35 characters.",
    )
    ezy_wms_partner_name_length = fields.Boolean(
        string="Partner name: at most 35 characters",
        default=True,
        help="Refuse a contact or address name longer than 35 characters.",
    )
    ezy_wms_street_length = fields.Boolean(
        string="Street and street 2: at most 35 characters each",
        default=True,
        help="Refuse a street or a street 2 longer than 35 characters.",
    )
    ezy_wms_city_length = fields.Boolean(
        string="City: at most 35 characters",
        default=True,
        help="Refuse a city longer than 35 characters.",
    )
    ezy_wms_zip_length = fields.Boolean(
        string="Postcode: at most 9 characters",
        default=True,
        help="Refuse a postcode longer than 9 characters.",
    )
    ezy_wms_phone_length = fields.Boolean(
        string="Phone: at most 20 characters",
        default=True,
        help="Refuse a phone number longer than 20 characters.",
    )
    ezy_wms_email_length = fields.Boolean(
        string="Email: at most 140 characters",
        default=True,
        help="Refuse an email longer than 140 characters.",
    )
    ezy_wms_delivery_contact_required = fields.Boolean(
        string="Delivery address: phone and email required at confirmation",
        default=True,
        help="Refuse to confirm a sales order whose delivery address has no phone "
        "or no email. Quotations, vendors and receipts are never checked.",
    )
    ezy_wms_picking_name = fields.Boolean(
        string="Transfer reference: at most 20 characters of A-Z 0-9 _ - . # / \\",
        default=True,
        help="Refuse to turn on the logistics mode of a receipt or delivery "
        "operation type, or to change its sequence while it is on, when the next "
        "reference its sequence would give is longer than 20 characters or has a "
        "character other than A-Z 0-9 _ - . # / \\.",
    )
