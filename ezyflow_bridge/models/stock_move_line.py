# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, models

# See GUARDED_MOVE_FIELDS: the line content the WMS owns on a frozen transfer,
# the unit under both series' names (product_uom_id on 19, uom_id on 20).
GUARDED_LINE_FIELDS = frozenset(
    {
        "quantity",
        "product_id",
        "product_uom_id",
        "uom_id",
        "lot_id",
        "lot_name",
        "package_id",
        "result_package_id",
        "location_id",
        "location_dest_id",
        "move_id",
        "picking_id",
    }
)


class StockMoveLine(models.Model):
    """The write guard (behaviour 6) on the detailed operations."""

    _inherit = "stock.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        picking_ids = {vals["picking_id"] for vals in vals_list if vals.get("picking_id")}
        move_ids = {vals["move_id"] for vals in vals_list if vals.get("move_id")}
        pickings = self.env["stock.picking"].browse(picking_ids)
        pickings |= self.env["stock.move"].browse(move_ids).picking_id
        pickings._ezy_check_lines_may_change()
        return super().create(vals_list)

    def write(self, vals):
        if GUARDED_LINE_FIELDS.intersection(vals):
            (self.picking_id | self.move_id.picking_id)._ezy_check_lines_may_change()
        return super().write(vals)

    def unlink(self):
        (self.picking_id | self.move_id.picking_id)._ezy_check_lines_may_change()
        return super().unlink()
