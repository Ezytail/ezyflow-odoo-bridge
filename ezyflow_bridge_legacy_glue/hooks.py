# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""At install, the legacy module keeps the WMS constraints (ADR 0035): the
bridge's own switches (ADR 0017) go off on every company, so a person meets
one refusal per figure, the one they met before the bridge arrived; and the
mirrors are computed once for the rows that exist, without waking the
connector (the activation's first pass reads everything)."""

MIRRORS = {
    "stock.picking": ["ezy_wms_state", "ezy_hold", "ezy_channel"],
    "sale.order": ["ezy_channel"],
    "res.partner": ["ezy_channel"],
    "delivery.carrier": ["ezy_service_code", "ezy_carrier_code"],
    "stock.picking.type": ["ezy_logistics_mode"],
}


def switches_off(companies):
    """Every bridge WMS constraint switch off on these companies. A later
    bridge minor that adds a switch defaults it on; the glue's README tells
    the administrator to switch it off on a glued database."""
    switches = [
        name
        for name, field in companies._fields.items()
        if name.startswith("ezy_wms_") and field.type == "boolean"
    ]
    companies.write({name: False for name in switches})


def backfill(env):
    """The mirrors recomputed for the rows that exist at install, from the
    legacy values, with the wake-up off."""
    env = env(context=dict(env.context, ezy_glue_backfill=True, active_test=False))
    for model, names in MIRRORS.items():
        records = env[model].sudo().search([])
        for name in names:
            field = records._fields.get(name)
            if field is not None and field.compute:
                env.add_to_compute(field, records)
    env.flush_all()


def post_init_hook(env_or_cr, registry=None):
    # Odoo 16 calls the hook with (cr, registry); 17 and later with the environment.
    env = env_or_cr
    if registry is not None:
        from odoo import SUPERUSER_ID, api  # noqa: PLC0415

        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    switches_off(env["res.company"].sudo().search([]))
    backfill(env)
