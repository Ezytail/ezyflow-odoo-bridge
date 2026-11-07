# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
{
    "name": "EzyFlow bridge: legacy glue",
    "summary": "Mirrors the EzyFlow bridge's fields onto the legacy logistics module's fields",
    # The bridge's version, bumped with it (ADR 0033, ADR 0035).
    "version": "3.16.0",
    "category": "Supply Chain",
    "author": "Ezytail",
    "website": "https://github.com/Ezytail/ezyflow-odoo-bridge",
    "license": "LGPL-3",
    "depends": ["ezyflow_bridge", "logistics_improvements"],
    "data": [
        "security/res_groups.xml",
        # The mirrors on a carrier write its legacy names through the ORM's
        # write, which the connector's create right alone does not cover.
        "security/ir.model.access.csv",
        # The settings notice, loaded by the bridge's series loader: the shared
        # file on 17 and later, its views/odoo16/ twin on 16 (ADR 0015).
        "views/series_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    # Present with both modules, installed with neither asked for (ADR 0004).
    "auto_install": True,
    "installable": True,
    "application": False,
}
