# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import fields, models


class SaleOrderLine(models.Model):
    """Removed lines (S8): a product line deleted from a quotation is recorded on
    its order, whose write date then moves, so the connector's order source sees
    the removal. Odoo refuses to delete a line of a confirmed order, so this only
    ever records quotation lines."""

    _inherit = "sale.order.line"

    def unlink(self):
        removed_at = fields.Datetime.now().isoformat()
        entries = {}
        for line in self:
            # Goods lines only: a carrier line re-chosen on a quotation or a down
            # payment is not a line the shop placed.
            if (
                line.display_type
                or not line.product_id
                or line.is_delivery
                or line.is_downpayment
            ):
                continue
            entries.setdefault(line.order_id, []).append(
                {
                    "line_id": line.id,
                    "product_id": line.product_id.id,
                    "sku": line.product_id.default_code or None,
                    "quantity": float(line.product_uom_qty),
                    "removed_at": removed_at,
                }
            )
        # Recorded once the deletion went through: Odoo's refusal for a confirmed
        # order raises inside super() and leaves the order untouched. An order
        # deleted itself takes its lines by database cascade, which never comes
        # here; exists() covers an order gone in the same transaction. The write
        # is sudo so whoever may delete a quotation line still can.
        result = super().unlink()
        for order, order_entries in entries.items():
            order = order.sudo().exists()
            if not order:
                continue
            recorded = order.ezy_removed_lines or []
            known = {entry.get("line_id") for entry in recorded}
            fresh = [entry for entry in order_entries if entry["line_id"] not in known]
            if fresh:
                order.ezy_removed_lines = recorded + fresh
        return result
