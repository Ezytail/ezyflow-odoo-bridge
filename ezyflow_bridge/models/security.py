# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The one place the bridge branches on the Odoo series (ADR 0015).

Odoo 16, 18 and 19 grant rights through ``ir.model.access`` rows and narrow
them with ``ir.rule`` records; Odoo 20 merged both into ``ir.access``. Odoo 19
and 20 hang a group on a privilege, 16 and 18 on a module category; a key
carries an expiry from 17. No common API exists, so each series has its own
folder under ``security/`` and the common data file calls
:meth:`load_series_security` to load it. The views are loaded here too, the
shared tree or its 16 twin (:meth:`load_series_views`).
"""
import os

from odoo import api, models, release
from odoo.tools.convert import convert_file

MODULE = "ezyflow_bridge"

# One folder per supported series; a series without a folder cannot install
# the bridge, which is the intended failure (CONTEXT.md, "Odoo series"). The
# 16 folder also keeps the stock journal's purge repeating (a 16 cron runs
# once by default); the cron itself is data/ir_cron.xml, loaded before.
SERIES_FILES = {
    16: (
        "odoo16/res_groups.xml",
        "odoo16/ir.model.access.csv",
        "odoo16/ir_rule.xml",
        "odoo16/ir_cron.xml",
    ),
    18: ("odoo18/res_groups.xml", "odoo18/ir.model.access.csv", "odoo18/ir_rule.xml"),
    19: ("odoo19/res_groups.xml", "odoo19/ir.model.access.csv", "odoo19/ir_rule.xml"),
    20: ("odoo20/res_groups.xml", "odoo20/ir.access.csv"),
}

# The views (ADR 0015, ADR 0035): one shared tree for 17 and later, written
# in the direct-modifier syntax, and its twin for 16 under views/odoo16/, the
# same files and the same xml ids in the attrs syntax (the twin test keeps the
# two in step). After the tree, the views a series places differently: Odoo
# 18 hides the product form's Traceability group, so the rotation date type
# moves next to the tracking choice there.
SHARED_VIEWS = (
    "stock_picking_views.xml",
    "stock_picking_type_views.xml",
    "sale_order_views.xml",
    "res_partner_views.xml",
    "delivery_carrier_views.xml",
    "ir_module_module_views.xml",
    "res_config_settings_views.xml",
    "product_views.xml",
)
TWIN_SERIES = 16
SERIES_VIEWS = {
    16: (),
    18: ("odoo18/product_views.xml",),
    19: (),
    20: (),
}


class EzyflowBridgeSecurity(models.AbstractModel):
    _name = "ezyflow.bridge.security"
    _description = "EzyFlow bridge: per-series access rights"

    @api.model
    def series(self):
        return release.version_info[0]

    @api.model
    def load_series_security(self):
        """Load the access rights of the running series, on install and on
        every update: ``convert_file`` registers the xml ids as loaded, so
        the module's end-of-load cleanup keeps them."""
        series = self.series()
        try:
            files = SERIES_FILES[series]
        except KeyError as error:
            raise ValueError(
                f"{MODULE} has no access rights for Odoo {series}; "
                f"supported series: {sorted(SERIES_FILES)}"
            ) from error
        for name in files:
            self._convert(MODULE, os.path.join("security", name))

    @api.model
    def _convert(self, module, path):
        """``convert_file`` takes the cursor below 17, the environment from 17."""
        target = self.env if self.series() >= 17 else self.env.cr
        convert_file(target, module, path, {}, mode="update")

    @api.model
    def views_of(self, series, shared, twins):
        """The view files a series loads: the twin tree for the twin series,
        the shared one for every other, each file under its folder."""
        if series == TWIN_SERIES:
            return [os.path.join(f"odoo{series}", name) for name in twins]
        return list(shared)

    @api.model
    def load_module_views(self, module, shared, twins, series_views=None):
        """Load a module's views for the running series: its shared tree or
        its 16 twin (``views_of``), then what the series places differently
        (``series_views``, by series). The glue calls this for its own tree."""
        series = self.series()
        for name in self.views_of(series, shared, twins) + list(
            (series_views or {}).get(series, ())
        ):
            self._convert(module, os.path.join("views", name))

    @api.model
    def load_series_views(self):
        """Load the bridge's views for the running series; called from the
        last data file of the manifest."""
        self.load_module_views(MODULE, SHARED_VIEWS, SHARED_VIEWS, SERIES_VIEWS)
