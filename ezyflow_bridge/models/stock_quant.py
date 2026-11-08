# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""An applied count's move carries the connector's reference (behaviour 14).

The connector applies a stock report or a movement through Odoo's own
inventory mode and names the adjustment with its reference in the context
(``inventory_name``): the move Odoo creates is the trace a rerun finds, so a
redelivered report is applied once (ADR 0010, S7 rule 5). Two things on Odoo
18 lose that name: the auto-apply inverse replaces the context with a dict
(``set_inventory_quantity_auto_apply``) before applying, and the move's name
gains the counting user's name as a suffix. Core 19 and 20 keep the context
and add no suffix. The bridge keeps the behaviour the same on every series
(ADR 0015): the context survives the inverse, and the connector's reference
is the move's whole name. The inverse below is core 18's body with its context
merged, applied to the connector's transactions only (ADR 0011); the weekly job
on the floating ``odoo:18`` image is the gate that catches a point release
changing that body.

The same model carries the stock journal's two overrides (behaviour 15, ADR
0041): every change of a quant's quantity or reservation appends a row to
``ezyflow.stock.journal``. Both pass Odoo's own arguments through untouched,
so 16's ``_update_available_quantity``, which lacks ``reserved_quantity``, is
served by the same override as 18, 19 and 20.
"""
from odoo import api, models, release

from .connector import is_connector_transaction


class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.model
    def _update_available_quantity(self, product_id, location_id, *args, **kwargs):
        result = super()._update_available_quantity(product_id, location_id, *args, **kwargs)
        self.env["ezyflow.stock.journal"]._ezy_append(product_id, location_id)
        return result

    @api.model
    def _update_reserved_quantity(self, product_id, location_id, *args, **kwargs):
        result = super()._update_reserved_quantity(product_id, location_id, *args, **kwargs)
        locations = location_id
        # Odoo 16 reserves non-strictly, on the quants of the location's children
        # too, and answers [(quant, quantity)]; 17 and later reserve on the one
        # location through _update_available_quantity and answer nothing.
        if isinstance(result, list):
            for quant, _quantity in result:
                locations |= quant.location_id
        self.env["ezyflow.stock.journal"]._ezy_append(product_id, locations)
        return result

    def user_has_groups(self, groups):
        """Odoo 16 applies a count for stock managers only ("Only a stock
        manager can validate an inventory adjustment", ``_apply_inventory``);
        17 and later let a stock user apply one in inventory mode. The
        connector applies a stock report through the same field on every
        series (ADR 0015), so on 16 that one check answers yes to the
        connector in inventory mode, and nothing else changes: the user, the
        context and the move's name are the connector's (ADR 0013: the one
        right the 16 series grants it beyond the base's, named here)."""
        if (
            release.version_info[0] < 17
            and groups == "stock.group_stock_manager"
            and self.env.context.get("inventory_mode")
            and is_connector_transaction(self.env)
        ):
            return True
        return super().user_has_groups(groups)

    def _set_inventory_quantity(self):
        if (
            release.version_info[0] >= 19
            or not self.env.context.get("inventory_name")
            or not is_connector_transaction(self.env)
        ):
            return super()._set_inventory_quantity()
        # Odoo 18's inverse, with the context merged rather than replaced.
        if not self._is_inventory_mode():
            return None
        quant_to_inventory = self.env["stock.quant"]
        for quant in self:
            if quant.quantity == quant.inventory_quantity_auto_apply:
                continue
            quant.inventory_quantity = quant.inventory_quantity_auto_apply
            quant_to_inventory |= quant
        if release.version_info[0] < 17:
            # Odoo 16's action_apply_inventory answers a confirmation wizard for
            # a tracked product counted without a lot; the connector counts the
            # lot-less cell on purpose (ADR 0023), so its count is applied the way
            # the wizard's confirmation applies it. The application also dates
            # the location's last inventory, an administrator's write on 16 (a
            # stock user's from 17): it runs with the checks lifted, the user,
            # the context and the move's name staying the connector's, once
            # the connector's own right to write these quants (its companies'
            # quants, the stock rules) is checked: the lift covers the
            # application, never the scope (ADR 0013).
            quant_to_inventory.check_access_rule("write")
            quant_to_inventory.sudo()._apply_inventory()
            quant_to_inventory.inventory_quantity_set = False
            return None
        return quant_to_inventory.with_context(
            set_inventory_quantity_auto_apply=True
        ).action_apply_inventory()

    def _get_inventory_move_values(self, qty, location_id, location_dest_id, **kwargs):
        values = super()._get_inventory_move_values(qty, location_id, location_dest_id, **kwargs)
        reference = self.env.context.get("inventory_name")
        # A move has a name below 19 only; 19 and 20 keep the reference in the
        # move's own inventory_name through the context.
        if reference and "name" in values and is_connector_transaction(self.env):
            values["name"] = reference
        return values
