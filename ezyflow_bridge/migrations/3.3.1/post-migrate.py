# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
# A bridge installed from the command line on an existing Odoo 20 database
# before 3.3.1 has no module type and is hidden in Apps (hooks.py); `-u` on
# the way to 3.3.1 repairs it, as the post-install hook does for new installs.
from odoo import SUPERUSER_ID, api

from odoo.addons.ezyflow_bridge.hooks import make_visible_in_apps


def migrate(cr, version):
    make_visible_in_apps(api.Environment(cr, SUPERUSER_ID, {}))
