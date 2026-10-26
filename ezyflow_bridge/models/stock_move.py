# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, models

# The line content the WMS owns while a transfer is frozen (behaviour 6).
# Housekeeping Odoo writes on behalf of a person working the transfer header
# (dates, partner, state, picked) stays allowed: cancelling a transfer must
# still reach the WMS as a cancellation (S2, S8).
GUARDED_MOVE_FIELDS = frozenset(
    {"product_uom_qty", "quantity", "product_id", "product_uom", "move_line_ids", "lot_ids"}
)


class StockMove(models.Model):
    """The reservation freeze (behaviour 5) and the offer on assignment
    (behaviour 1), both read through the move's picking (ADR 0003)."""

    _inherit = "stock.move"

    def _action_assign(self, force_qty=False):
        movable = self._ezy_not_frozen()
        result = super(StockMove, movable)._action_assign(force_qty=force_qty)
        reserved = movable.filtered(lambda move: move.state in ("assigned", "partially_available"))
        reserved.picking_id._ezy_offer_on_assignment()
        return result

    def _do_unreserve(self):
        return super(StockMove, self._ezy_not_frozen())._do_unreserve()

    def _trigger_assign(self):
        return super(StockMove, self._ezy_not_frozen())._trigger_assign()

    def _should_bypass_reservation(self, forced_location=False):
        self.ensure_one()
        if self.picking_id.ezy_is_frozen:
            return True
        return super()._should_bypass_reservation(forced_location=forced_location)

    @api.model_create_multi
    def create(self, vals_list):
        picking_ids = {vals["picking_id"] for vals in vals_list if vals.get("picking_id")}
        self.env["stock.picking"].browse(picking_ids)._ezy_check_lines_may_change()
        return super().create(vals_list)

    def write(self, vals):
        if GUARDED_MOVE_FIELDS.intersection(vals):
            self.picking_id._ezy_check_lines_may_change()
        return super().write(vals)

    def unlink(self):
        self.picking_id._ezy_check_lines_may_change()
        return super().unlink()

    def _ezy_not_frozen(self):
        return self.filtered(lambda move: not move.picking_id.ezy_is_frozen)
