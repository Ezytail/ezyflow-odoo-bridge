# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The move under the legacy module (ADR 0035, glossary "Legacy glue").

Two legacy rules meet the bridge's on the move:

- the substate follows the state: a state change resets the substate to the
  first one of the new state (the OCA mixin), so a transfer in preparation
  whose move the connector resizes (a partial preparation, S3) fell back to
  ready for logistics. The glue keeps the substate's name across the change
  where the legacy vocabulary has it for the new state (preparation to do
  exists for assigned and partially available moves); where it does not (a
  done move, a cancelled one), the legacy default applies.
- the legacy module keeps Odoo's reservation engine away from the moves in a
  logistics substate: no assignment, no unreserve, and no quant bookkeeping
  (bypass). The bridge's freeze (behaviour 5, 3.8.2) stops the decisions and
  never the bookkeeping. Under the glue, the connector's own calls are the
  logistics' and go through, and the bookkeeping always does: a validated,
  resized or unlinked line gives its reservation back to the quants.
"""
from collections import defaultdict

from odoo import models

CONNECTOR_GROUP = "ezyflow_bridge.group_ezyflow_connector"


class StockMove(models.Model):
    _inherit = "stock.move"

    def write(self, values):
        if not values.get("state") or values.get("substate_id"):
            return super().write(values)
        by_substate = defaultdict(lambda: self.env["stock.move"])
        for move in self:
            by_substate[move.textual_substate or ""] |= move
        result = True
        for name, moves in by_substate.items():
            kept = dict(values)
            if name:
                same = moves._get_substate_by_text(state_val=values["state"], substate_name=name)
                if same:
                    kept["substate_id"] = same.id
            result = super(StockMove, moves).write(kept) and result
        return result

    def _moves_to_exclude_from_mrp(self):
        if self.env.user.has_group(CONNECTOR_GROUP):
            return self.env["stock.move"]
        return super()._moves_to_exclude_from_mrp()

    def _should_bypass_reservation(self, forced_location=False):
        # For every user, not the connector alone: the legacy module answers
        # True (skip the quants' bookkeeping) for a move in a logistics
        # substate, and the bridge's rule is that the bookkeeping never skips
        # (3.8.2). The context key tells the legacy module to leave its
        # exclusion aside, so core's own answer comes back.
        return super(
            StockMove, self.with_context(bypass_logistics_states=True)
        )._should_bypass_reservation(forced_location=forced_location)
