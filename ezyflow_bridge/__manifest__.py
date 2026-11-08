# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
{
    "name": "EzyFlow bridge",
    "summary": "Fields and behaviours the EzyFlow connector needs, nothing else",
    # Series-less on purpose (ADR 0015): Odoo prepends its own series when it
    # records the installed version, so one tree serves Odoo 16, 18, 19 and 20.
    "version": "3.17.0",
    "category": "Supply Chain",
    "author": "Ezytail",
    "website": "https://github.com/Ezytail/ezyflow-odoo-bridge",
    "license": "LGPL-3",
    # delivery carries the carrier on every series; 17 and later split the
    # transfer's carrier fields into stock_delivery, which Odoo installs on its
    # own next to sale_stock and delivery (auto_install), so one list serves
    # 16, 18, 19 and 20 (ADR 0035).
    "depends": ["stock", "sale_stock", "delivery", "purchase_stock"],
    # The views are loaded by the series loader (views/series_views.xml, last):
    # the shared tree on 17 and later, its views/odoo16/ twin on 16 (ADR 0015).
    "data": [
        # Before the security file: the 16 folder it loads adjusts the cron.
        "data/ir_cron.xml",
        "security/ezyflow_security.xml",
        "data/ir_config_parameter.xml",
        "views/series_views.xml",
    ],
    # Odoo 20 only lists a typed module in Apps; a CLI install on an existing
    # database leaves the type empty (hooks.py). The 3.3.1 migration repairs
    # an existing install on -u.
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
