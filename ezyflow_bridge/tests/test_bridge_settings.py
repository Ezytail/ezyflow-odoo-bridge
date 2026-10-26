# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import importlib.util

from lxml import etree

from odoo.tests import tagged
from odoo.tools.misc import file_path

from .common import EzyflowBridgeCase

MIGRATION = "ezyflow_bridge/migrations/3.8.0/post-migrate.py"
WAKEUP_KEYS = {
    "ezy_activity": "ezyflow.activity",
    "ezy_wakeup_url": "ezyflow.wakeup_url",
    "ezy_wakeup_secret": "ezyflow.wakeup_secret",
}


@tagged("post_install", "-at_install")
class TestBridgeSettings(EzyflowBridgeCase):
    """Every bridge setting lives on the EzyFlow settings page (ADR 0020): the
    Connector block shows the three wake-up keys, the proforma report is the
    company's, and the 3.8.0 migration moves ezyflow.proforma_report onto it."""

    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("ezy_post_migrate_380", file_path(MIGRATION))
        self.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.migration)
        self.second = self.env["res.company"].create({"name": "Second company"})

    def param(self, key):
        return self.env["ezyflow.wakeup"]._param(key)

    def set_param(self, key, value):
        # Through the record, the API both series share (ADR 0015).
        params = self.env["ir.config_parameter"].sudo()
        record = params.search([("key", "=", key)], limit=1)
        if record:
            record.value = value
        else:
            params.create({"key": key, "value": value})

    def save_page(self, values):
        """What the administrator's Save does: the form opens on the stored
        values, the edited ones replace them, the page is executed."""
        settings = self.env["res.config.settings"].with_user(self.admin_user)
        settings.create(values).execute()

    def page_arch(self):
        views = self.env["res.config.settings"].get_views([(False, "form")])
        return etree.fromstring(views["views"]["form"]["arch"])

    def test_the_page_shows_a_connector_block_and_the_proforma_report(self):
        [app] = self.page_arch().xpath("//app[@name='ezyflow_bridge']")

        [connector] = app.xpath("block[@name='ezy_connector']")
        self.assertEqual(connector.get("title"), "Connector")
        self.assertEqual(
            [setting.get("id") for setting in connector.xpath("setting")], list(WAKEUP_KEYS)
        )
        [secret] = connector.xpath("setting/field[@name='ezy_wakeup_secret']")
        self.assertEqual(secret.get("password"), "True")
        self.assertEqual(len(app.xpath("block/setting/field[@name='ezy_proforma_report_id']")), 1)

    def test_the_page_fields_are_the_system_parameters(self):
        settings = self.env["res.config.settings"]
        for name, key in WAKEUP_KEYS.items():
            self.assertEqual(settings._fields[name].config_parameter, key)

    def test_saving_the_page_writes_the_three_system_parameters(self):
        self.save_page(
            {
                "ezy_activity": "acme",
                "ezy_wakeup_url": "https://connector.test/wake-up",
                "ezy_wakeup_secret": "s3cret",
            }
        )

        self.assertEqual(self.param("ezyflow.activity"), "acme")
        self.assertEqual(self.param("ezyflow.wakeup_url"), "https://connector.test/wake-up")
        self.assertEqual(self.param("ezyflow.wakeup_secret"), "s3cret")

    def test_the_page_opens_on_the_three_system_parameters(self):
        self.set_param("ezyflow.activity", "acme")
        self.set_param("ezyflow.wakeup_url", "https://connector.test/wake-up")
        self.set_param("ezyflow.wakeup_secret", "s3cret")

        page = self.env["res.config.settings"].with_user(self.admin_user).create({})

        self.assertEqual(page.ezy_activity, "acme")
        self.assertEqual(page.ezy_wakeup_url, "https://connector.test/wake-up")
        self.assertEqual(page.ezy_wakeup_secret, "s3cret")

    def test_saving_the_page_untouched_keeps_the_secret(self):
        self.set_param("ezyflow.activity", "acme")
        self.set_param("ezyflow.wakeup_secret", "s3cret")

        self.save_page({"ezy_wms_zip_length": False})

        self.assertEqual(self.param("ezyflow.wakeup_secret"), "s3cret")
        self.assertEqual(self.param("ezyflow.activity"), "acme")
        self.assertFalse(self.company.ezy_wms_zip_length)

    def test_clearing_the_secret_on_the_page_clears_the_parameter(self):
        self.set_param("ezyflow.wakeup_secret", "s3cret")

        self.save_page({"ezy_wakeup_secret": False})

        self.assertEqual(self.param("ezyflow.wakeup_secret"), "")

    def test_the_page_saves_the_proforma_report_of_the_current_company(self):
        quotation = self.env.ref("sale.action_report_saleorder")

        self.save_page({"ezy_proforma_report_id": quotation.id})

        self.assertEqual(self.company.ezy_proforma_report_id, quotation)
        self.assertFalse(self.second.ezy_proforma_report_id)

    def test_the_proforma_report_field_offers_sales_order_reports_only(self):
        field = self.env["res.company"]._fields["ezy_proforma_report_id"]
        self.assertEqual(field.comodel_name, "ir.actions.report")
        self.assertEqual(field.ondelete, "set null")
        self.assertEqual(field.domain, [("model", "=", "sale.order")])

    def test_the_bridge_ships_no_proforma_parameter(self):
        self.assertFalse(
            self.env.ref("ezyflow_bridge.param_ezyflow_proforma_report", raise_if_not_found=False)
        )

    # The 3.8.0 migration.

    def run_migration(self):
        self.env.flush_all()
        self.migration.migrate(self.env.cr, "3.7.1")
        self.env.invalidate_all()

    def assert_no_parameter(self):
        params = self.env["ir.config_parameter"].sudo()
        self.assertFalse(params.search([("key", "=", self.migration.PARAM)]))

    def test_the_migration_copies_a_sales_order_report_onto_every_company(self):
        quotation = self.env.ref("sale.action_report_saleorder")
        self.set_param(self.migration.PARAM, "sale.action_report_saleorder")

        self.run_migration()

        self.assertEqual(self.company.ezy_proforma_report_id, quotation)
        self.assertEqual(self.second.ezy_proforma_report_id, quotation)
        self.assert_no_parameter()

    def test_the_migration_resolves_the_shipped_value_by_report_name(self):
        self.set_param(self.migration.PARAM, "sale.report_saleorder_pro_forma")

        self.run_migration()

        pro_forma = self.env.ref("sale.action_report_pro_forma_invoice")
        self.assertEqual(self.company.ezy_proforma_report_id, pro_forma)
        self.assert_no_parameter()

    def test_the_migration_skips_another_model_s_report_sharing_the_name(self):
        quotation = self.env.ref("sale.action_report_saleorder")
        other = self.env["ir.actions.report"].search([("model", "!=", "sale.order")], limit=1)
        self.assertTrue(other)
        # Ordered first by name: the lookup by report name alone would find it.
        other.copy({"name": "A shadow", "report_name": quotation.report_name})
        self.set_param(self.migration.PARAM, quotation.report_name)

        self.run_migration()

        self.assertEqual(self.company.ezy_proforma_report_id, quotation)
        self.assert_no_parameter()

    def test_the_migration_leaves_a_company_that_chose_alone(self):
        quotation = self.env.ref("sale.action_report_saleorder")
        pro_forma = self.env.ref("sale.action_report_pro_forma_invoice")
        self.company.ezy_proforma_report_id = quotation
        self.set_param(self.migration.PARAM, "sale.action_report_pro_forma_invoice")

        self.run_migration()

        self.assertEqual(self.company.ezy_proforma_report_id, quotation)
        self.assertEqual(self.second.ezy_proforma_report_id, pro_forma)
        self.assert_no_parameter()

    def test_the_migration_drops_a_value_that_names_no_sales_order_report(self):
        other = self.env["ir.actions.report"].search([("model", "!=", "sale.order")], limit=1)
        self.assertTrue(other)
        for value in (other.report_name, "sale.report_saleorder_document", "nowhere"):
            self.set_param(self.migration.PARAM, value)

            with self.assertLogs(self.migration._logger, "WARNING"):
                self.run_migration()

            self.assertFalse(self.company.ezy_proforma_report_id, value)
            self.assertFalse(self.second.ezy_proforma_report_id, value)
            self.assert_no_parameter()

    def test_the_migration_reruns_without_the_parameter(self):
        quotation = self.env.ref("sale.action_report_saleorder")
        self.set_param(self.migration.PARAM, "sale.action_report_saleorder")
        self.run_migration()
        self.company.ezy_proforma_report_id = False

        self.run_migration()

        self.assertFalse(self.company.ezy_proforma_report_id)
        self.assertEqual(self.second.ezy_proforma_report_id, quotation)
