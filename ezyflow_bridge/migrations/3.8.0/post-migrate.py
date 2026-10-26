# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
# Bridge 3.8.0 moves the proforma report from the system parameter
# ezyflow.proforma_report to a field of the company (ADR 0020). This copies
# the parameter onto every company whose field is empty, so a re-run never
# overwrites a company's choice, then deletes the parameter: its seed record
# was noupdate, so the upgrade neither recreates nor deletes the row on its
# own. A value that resolves to no sales order report is dropped with a
# warning and leaves the field empty: the render then uses Odoo's pro forma.
# The key lives here, not in the models: a migration outlives the code it
# migrates from.
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

PARAM = "ezyflow.proforma_report"


def resolve(env, value):
    """The sales order report a parameter value names, or an empty recordset.
    Resolved in the order the render of 3.7 did through _render_qweb_pdf, a
    report name first, then an xml id; the name is looked up among sales order
    reports only, so another model's report sharing it never hides one."""
    reports = env["ir.actions.report"]
    value = (value or "").strip()
    if not value:
        return reports
    report = reports.search(
        [("report_name", "=", value), ("model", "=", "sale.order")], limit=1
    )
    if not report:
        record = env.ref(value, raise_if_not_found=False) if "." in value else None
        if record is not None and record._name == "ir.actions.report":
            report = record
    if report.model != "sale.order":
        return reports
    return report


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    param = env["ir.config_parameter"].search([("key", "=", PARAM)])
    if not param:
        return
    value = param.value
    report = resolve(env, value)
    if report:
        companies = env["res.company"].with_context(active_test=False).search(
            [("ezy_proforma_report_id", "=", False)]
        )
        companies.write({"ezy_proforma_report_id": report.id})
    elif (value or "").strip():
        _logger.warning(
            "EzyFlow: %s names %r, which is no sale.order report; dropped, every "
            "company without a proforma report renders Odoo's pro forma",
            PARAM,
            value,
        )
    # Through the ORM: its xml id goes with it.
    param.unlink()
