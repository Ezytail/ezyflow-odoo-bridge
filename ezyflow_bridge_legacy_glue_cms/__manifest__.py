# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
{
    "name": "EzyFlow bridge: legacy glue, shop ids",
    "summary": "Mirrors the bridge's shop ids onto the CMS ids of the EzyFlow NG CMS bridge",
    "version": "3.16.0",
    "category": "Supply Chain",
    "author": "Ezytail",
    "website": "https://github.com/Ezytail/ezyflow-odoo-bridge",
    "license": "LGPL-3",
    "depends": ["ezyflow_bridge_legacy_glue", "ezyflowng_cms_bridge"],
    "auto_install": True,
    "installable": True,
    "application": False,
}
