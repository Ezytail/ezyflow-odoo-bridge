# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
# Bridge 3.5.0 replaces the two company switches of 3.4.0 with one switch per
# WMS constraint (ADR 0017). The new columns are created on (their default)
# for every company; this carries a 3.4.0 switch a company had turned off onto
# the 3.5.0 switches it covered, and leaves every other new switch on. Odoo
# keeps the old columns after their fields are gone; they are read here once.
# The mapping lives here, not in the models: a migration outlives the code it
# migrates from.
from odoo.tools import SQL

# The 3.4.0 switches and the 3.5.0 switches each one covered.
COVERED = {
    "ezy_check_product_constraints": (
        "ezy_wms_default_code_length",
        "ezy_wms_default_code_required",
        "ezy_wms_product_name_length",
    ),
    "ezy_check_partner_constraints": (
        "ezy_wms_partner_name_length",
        "ezy_wms_street_length",
    ),
}


def _has_column(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    for old, new_switches in COVERED.items():
        if not _has_column(cr, "res_company", old):
            continue
        assignments = SQL(", ").join(
            SQL("%s = COALESCE(%s, TRUE)", SQL.identifier(new), SQL.identifier(old))
            for new in new_switches
        )
        cr.execute(SQL("UPDATE res_company SET %s", assignments))
