# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import base64
import logging

from odoo import api, fields, models

from .contract import CHANNELS, WMS_STATES

_logger = logging.getLogger(__name__)

PROFORMA_REPORT_PARAM = "ezyflow.proforma_report"
DEFAULT_PROFORMA_REPORT = "sale.report_saleorder_pro_forma"


class SaleOrder(models.Model):
    """Channel copy-down (behaviour 3), the WMS values on the delivery status
    (behaviour 7), the proforma rendering and the removed lines (S8)."""

    _inherit = "sale.order"

    ezy_channel = fields.Selection(
        CHANNELS,
        string="Channel",
        compute="_compute_ezy_channel",
        store=True,
        readonly=False,
        precompute=True,
        help="The sales channel, copied from the delivery address when the order is "
        "created; copied down to the order's transfers.",
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

    def ezy_render_proforma(self):
        """The Proforma: the PDF the connector fetches for a validated order and
        forwards to the WMS for shipment paperwork. Rendered by this public method
        because report rendering is private in Odoo 19.

        The report comes from the system parameter ``ezyflow.proforma_report``
        (``sale.report_saleorder_pro_forma`` when empty). The order is read as
        the caller, so an order the caller cannot read raises AccessError; the
        rendering itself runs as superuser, since the connector user holds no
        sales group: any internal user who can read the order gets the priced
        document. Returns the PDF in base64, or an empty string when nothing
        was rendered."""
        self.ensure_one()
        self.check_access("read")
        # Read through the record, the API both series share (ADR 0015).
        report_ref = (
            self.env["ezyflow.wakeup"]._param(PROFORMA_REPORT_PARAM).strip()
            or DEFAULT_PROFORMA_REPORT
        )
        # The parameter may only name a sales order report: rendering runs as
        # superuser, and another model's report would render its records by
        # colliding id.
        report = self.env.ref(report_ref, raise_if_not_found=False)
        if not report or report._name != "ir.actions.report" or report.model != "sale.order":
            _logger.warning(
                "EzyFlow: %s names %r, which is not a sale.order report; rendering %s",
                PROFORMA_REPORT_PARAM,
                report_ref,
                DEFAULT_PROFORMA_REPORT,
            )
            report_ref = DEFAULT_PROFORMA_REPORT
        pdf, report_type = (
            self.env["ir.actions.report"].sudo()._render_qweb_pdf(report_ref, res_ids=self.ids)
        )
        if report_type != "pdf" or not pdf:
            return ""
        return base64.b64encode(pdf).decode()
