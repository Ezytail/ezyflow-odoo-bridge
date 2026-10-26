# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import base64
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .contract import WMS_STATES, check_channel_codes
from .wms_constraints import binds

_logger = logging.getLogger(__name__)

DEFAULT_PROFORMA_REPORT = "sale.report_saleorder_pro_forma"


class SaleOrder(models.Model):
    """Channel copy-down (behaviour 3), the WMS values on the delivery status
    (behaviour 7), the delivery contact WMS constraint (behaviour 8), the
    proforma rendering and the removed lines (S8), the shop total and its
    warning (behaviour 12)."""

    _inherit = "sale.order"

    ezy_channel = fields.Char(
        string="Channel",
        compute="_compute_ezy_channel",
        store=True,
        readonly=False,
        precompute=True,
        help="The sales channel, a code such as WEB, PRO or B2B, copied from the "
        "delivery address when the order is created; copied down to the order's "
        "transfers.",
    )
    ezy_final_recipient_id = fields.Many2one(
        "res.partner",
        string="Final recipient",
        ondelete="set null",
        help="The customer who collects the parcel when the delivery address is a "
        "relay point; copied down to the order's transfers.",
    )
    ezy_removed_lines = fields.Json(
        string="Removed lines",
        default=list,
        copy=False,
        help="The product lines deleted from this order while it was a quotation, "
        "one entry each (line, product, SKU, quantity, time of removal), so the "
        "connector's order source can surface the removal.",
    )
    delivery_status = fields.Selection(
        selection_add=WMS_STATES,
        ondelete={key: "set null" for key, _label in WMS_STATES},
    )
    ezy_shop_total = fields.Monetary(
        string="Shop total",
        currency_field="currency_id",
        copy=False,
        help="What the customer paid the shop for this order, in the order's "
        "currency, written by the connector when the order is created. A "
        "difference with the order total is shown on the form; the order is "
        "never refused for it. A total of zero reads as not set, so a fully "
        "discounted order never warns.",
    )
    ezy_total_differs = fields.Boolean(
        string="Shop total differs",
        compute="_compute_ezy_total_differs",
        store=True,
        help="The shop total is set and differs from the order total beyond the "
        "currency's rounding: a tax or a fiscal position to check.",
    )

    @api.depends("ezy_shop_total", "amount_total", "currency_id")
    def _compute_ezy_total_differs(self):
        # Behaviour 12 (ADR 0028): a gap between what the shop collected and
        # what Odoo computes is shown to a person, never refused. An unset
        # total reads as zero on a Monetary field, so zero means "not set".
        for order in self:
            order.ezy_total_differs = bool(order.ezy_shop_total) and (
                order.currency_id.compare_amounts(order.ezy_shop_total, order.amount_total) != 0
                if order.currency_id
                else order.ezy_shop_total != order.amount_total
            )

    @api.constrains("ezy_channel")
    def _check_ezy_channel(self):
        for record in self.filtered("ezy_channel"):
            check_channel_codes(self.env, [record.ezy_channel], record.display_name)

    @api.depends("partner_shipping_id.ezy_channel")
    def _compute_ezy_channel(self):
        for order in self:
            order.ezy_channel = order.partner_shipping_id.ezy_channel or order.ezy_channel

    @api.depends("picking_ids.ezy_wms_state", "picking_ids.write_date")
    def _compute_delivery_status(self):
        # Once a transfer is in the hand-off, the order shows the WMS value:
        # refused wins, then cancelled, then the transfer touched last.
        result = super()._compute_delivery_status()
        for order in self:
            in_hand_off = order.picking_ids.filtered("ezy_wms_state")
            if not in_hand_off:
                continue
            states = set(in_hand_off.mapped("ezy_wms_state"))
            if "refused_by_logistics" in states:
                order.delivery_status = "refused_by_logistics"
            elif "cancelled_by_logistics" in states:
                order.delivery_status = "cancelled_by_logistics"
            else:
                latest = max(in_hand_off, key=lambda picking: (picking.write_date, picking.id))
                order.delivery_status = latest.ezy_wms_state
        return result

    def action_confirm(self):
        # Behaviour 8 (ADR 0017): the WMS needs a phone and an email on the
        # delivery address of a confirmed order. Checked here, on the person's
        # confirmation, and never on res.partner: a quotation, a vendor or a
        # receipt needs neither. Core offers no switch for it (ADR 0011).
        for order in self:
            if order.state in ("draft", "sent"):
                order._ezy_check_delivery_contact()
        return super().action_confirm()

    def _ezy_check_delivery_contact(self):
        self.ensure_one()
        if not binds(self.env, self.company_id, "ezy_wms_delivery_contact_required"):
            return
        address = self.partner_shipping_id
        missing = [name for name in ("phone", "email") if not address[name]]
        if missing:
            raise ValidationError(
                self.env._(
                    "%(order)s cannot be confirmed: its delivery address %(partner)s "
                    "has no %(field)s, and the WMS requires a phone and an email on "
                    "the delivery address.",
                    order=self.display_name,
                    field=", ".join(
                        address._fields[name].get_description(self.env)["string"]
                        for name in missing
                    ),
                    partner=address.display_name,
                )
            )

    def ezy_render_proforma(self):
        """The Proforma: the PDF the connector fetches for a validated order and
        forwards to the WMS for shipment paperwork. Rendered by this public method
        because report rendering is private in Odoo 19.

        The report is the proforma report of the order's company
        (``ezy_proforma_report_id``, ADR 0020), Odoo's pro forma invoice when it
        is empty. The order is read as the caller, so an order the caller cannot
        read raises AccessError; the rendering itself runs as superuser, since
        the connector user holds no sales group: any internal user who can read
        the order gets the priced document. Returns the PDF in base64, or an
        empty string when nothing was rendered."""
        self.ensure_one()
        self.check_access("read")
        report = self.sudo().company_id.ezy_proforma_report_id
        report_ref = report or DEFAULT_PROFORMA_REPORT
        # The form offers sales order reports only, but RPC or an import writes
        # past the field's domain: rendering runs as superuser, and another
        # model's report would render its records by colliding id.
        if report and report.model != "sale.order":
            _logger.warning(
                "EzyFlow: the proforma report of %s is %s, a %s report, not a "
                "sale.order report; rendering %s",
                self.company_id.display_name,
                report.display_name,
                report.model,
                DEFAULT_PROFORMA_REPORT,
            )
            report_ref = DEFAULT_PROFORMA_REPORT
        pdf, report_type = (
            self.env["ir.actions.report"].sudo()._render_qweb_pdf(report_ref, res_ids=self.ids)
        )
        if report_type != "pdf" or not pdf:
            return ""
        return base64.b64encode(pdf).decode()
