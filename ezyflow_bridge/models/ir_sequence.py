# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import models

# The sequence fields that shape the next name it produces.
NAME_FIELDS = {"prefix", "suffix", "padding", "number_next", "number_next_actual"}


class IrSequence(models.Model):
    """The transfer reference WMS constraint (behaviour 8, ADR 0017) seen from
    the sequence: core stock rewrites a picking type's sequence directly (a
    warehouse's short code renamed), and a person can edit it under Technical
    settings, without the operation type being saved. Either way the operation
    types in logistics mode that draw from it are checked again."""

    _inherit = "ir.sequence"

    def write(self, vals):
        result = super().write(vals)
        if NAME_FIELDS.intersection(vals):
            picking_types = (
                self.env["stock.picking.type"]
                .sudo()
                .with_context(active_test=False)
                .search([("sequence_id", "in", self.ids), ("ezy_logistics_mode", "!=", "off")])
            )
            # sudo for the search only: the check binds the user who wrote.
            picking_types.with_env(self.env)._check_ezy_picking_name()
        return result
