# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
{
    "name": "EzyFlow bridge",
    "summary": "Fields and behaviours the EzyFlow connector needs, nothing else",
    # Series-less on purpose (ADR 0015): Odoo prepends its own series when it
    # records the installed version, so one tree serves Odoo 19 and Odoo 20.
    "version": "3.8.1",
    "category": "Supply Chain",
    "author": "Ezytail",
    "website": "https://github.com/Ezytail/ezyflow-odoo",
    "license": "LGPL-3",
    "depends": ["stock", "sale_stock", "stock_delivery", "purchase_stock"],
    "data": [
        "security/ezyflow_security.xml",
        "data/ir_config_parameter.xml",
        "views/stock_picking_views.xml",
        "views/stock_picking_type_views.xml",
        "views/sale_order_views.xml",
        "views/res_partner_views.xml",
        "views/delivery_carrier_views.xml",
        "views/res_config_settings_views.xml",
        "views/product_views.xml",
    ],
    # Odoo 20 only lists a typed module in Apps; a CLI install on an existing
    # database leaves the type empty (hooks.py). The 3.3.1 migration repairs
    # an existing install on -u.
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
