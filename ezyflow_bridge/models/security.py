# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The one place the bridge branches on the Odoo series (ADR 0015).

Odoo 19 grants rights through ``ir.model.access`` rows and narrows them with
``ir.rule`` records; Odoo 20 merged both into ``ir.access``. No common API
exists, so each series has its own folder under ``security/`` and the
common data file calls :meth:`load_series_security` to load it.
"""
import os

from odoo import api, models, release
from odoo.tools.convert import convert_file

MODULE = "ezyflow_bridge"

# One folder per supported series; a series without a folder cannot install
# the bridge, which is the intended failure (CONTEXT.md, "Odoo series").
SERIES_FILES = {
    19: ("odoo19/ir.model.access.csv", "odoo19/ir_rule.xml"),
    20: ("odoo20/ir.access.csv",),
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
            convert_file(
                self.env, MODULE, os.path.join("security", name), {}, mode="update"
            )
