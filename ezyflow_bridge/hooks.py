# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""Keep the bridge visible on the Apps screen of Odoo 20.

Odoo 20 (base_import_module) lists a module in Apps only under one of two
panel entries, "Official Apps" (``module_type = official``, the default for
every module found on the addons path) or "Industries" (store downloads);
the "All" entry is hidden. A command-line install on an existing database
(``odoo -i ezyflow_bridge``) registers the module right after ``base`` is
loaded, before that field is in the registry, so the row is created without
a type and the module never shows in Apps although it is installed and
working. The Apps screen's own "Update Apps List" does not repair it.

The post-install hook sets the value a UI install would have given; the
3.3.1 migration does the same for an already installed bridge on ``-u``.
Odoo 19 has no such field, and the hook is a no-op there.
"""

MODULE = "ezyflow_bridge"


def make_visible_in_apps(env):
    """Give the bridge's own module row the type Odoo 20 expects (idempotent)."""
    modules = env["ir.module.module"].sudo()
    if "module_type" not in modules._fields:
        return
    row = modules.search([("name", "=", MODULE), ("module_type", "=", False)])
    row.write({"module_type": "official"})


def post_init_hook(env_or_cr, registry=None):
    # Odoo 16 calls the hook with (cr, registry); 17 and later with the environment.
    if registry is not None:
        from odoo import SUPERUSER_ID, api  # noqa: PLC0415

        env_or_cr = api.Environment(env_or_cr, SUPERUSER_ID, {})
    make_visible_in_apps(env_or_cr)
