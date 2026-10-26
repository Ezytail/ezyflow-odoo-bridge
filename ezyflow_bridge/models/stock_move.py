# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, models

# The line content the WMS owns while a transfer is frozen (behaviour 6).
# Housekeeping Odoo writes on behalf of a person working the transfer header
# (dates, partner, state, picked) stays allowed: cancelling a transfer must
# still reach the WMS as a cancellation (S2, S8).
# The unit is product_uom on Odoo 19 and uom_id on Odoo 20 (ADR 0015): both
# names are listed, a series never sends the other one.
GUARDED_MOVE_FIELDS = frozenset(
    {
        "product_uom_qty",
        "quantity",
        "product_id",
        "product_uom",
        "uom_id",
        "move_line_ids",
        "lot_ids",
    }
)


class StockMove(models.Model):
    """The reservation freeze (behaviour 5) and the offer on assignment
    (behaviour 1), both read through the move's picking (ADR 0003).

    The freeze stops the decisions to reserve or unreserve, never the quants'
    bookkeeping: a frozen move does not bypass reservation, so the quants give
    back what its lines reserved when they are validated, resized or unlinked
    (3.8.2: bypassing it left the validated quantities reserved)."""

    _inherit = "stock.move"

    def _action_assign(self, force_qty=False):
        movable = self._ezy_not_frozen()
        result = super(StockMove, movable)._action_assign(force_qty=force_qty)
        reserved = movable.filtered(lambda move: move.state in ("assigned", "partially_available"))
        reserved.picking_id._ezy_offer_on_assignment()
        return result

    def _action_cancel(self):
        # A cancelled move gives its reservation back, frozen or not: nobody
        # works on it any more. Core releases it through _do_unreserve, which
        # the freeze skips, and offers no switch for it (ADR 0011), so the
        # frozen moves' lines go here, all of them as core's would, before core
        # marks the moves cancelled (a cancelled line cannot be unlinked) and as
        # the superuser, so that the write guard (behaviour 6) leaves a person's
        # cancellation alone. When core refuses the cancellation (a done move),
        # the release goes back with it.
        cancelling = self._ezy_frozen().filtered(lambda move: move.state not in ("done", "cancel"))
        cancelling.move_line_ids.sudo().unlink()
        return super()._action_cancel()

    def _do_unreserve(self):
        return super(StockMove, self._ezy_not_frozen())._do_unreserve()

    def _trigger_assign(self):
        return super(StockMove, self._ezy_not_frozen())._trigger_assign()

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

    def _ezy_frozen(self):
        return self.filtered(lambda move: move.picking_id.ezy_is_frozen)

    def _ezy_not_frozen(self):
        return self - self._ezy_frozen()
