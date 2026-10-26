# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import importlib.util

from lxml import etree

from odoo.tests import tagged
from odoo.tools.misc import file_path

from ..models.wms_constraints import SWITCHES
from .common import EzyflowBridgeCase

MIGRATION = "ezyflow_bridge/migrations/3.5.0/post-migrate.py"


@tagged("post_install", "-at_install")
class TestWmsSettings(EzyflowBridgeCase):
    """The EzyFlow page of the Settings and the 3.5.0 migration (ADR 0017)."""

    def settings_arch(self):
        views = self.env["res.config.settings"].get_views([(False, "form")])
        return etree.fromstring(views["views"]["form"]["arch"])

    def test_the_settings_show_an_ezyflow_app_with_one_setting_per_switch(self):
        arch = self.settings_arch()

        apps = arch.xpath("//app[@name='ezyflow_bridge']")
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].get("string"), "EzyFlow")
        block = apps[0].xpath("block[@name='ezy_wms_constraints']")
        self.assertEqual(len(block), 1)
        self.assertEqual(block[0].get("title"), "WMS constraints")
        self.assertEqual(
            [setting.get("id") for setting in block[0].xpath("setting")], list(SWITCHES)
        )
        for switch in SWITCHES:
            self.assertEqual(len(block[0].xpath(f"setting/field[@name='{switch}']")), 1, switch)

    def test_the_inventory_settings_carry_no_ezyflow_block(self):
        arch = self.settings_arch()

        self.assertFalse(arch.xpath("//block[@name='ezyflow_setting_container']"))

    def test_a_setting_saves_the_company_switch(self):
        self.assertTrue(self.company.ezy_wms_zip_length)
        settings = self.env["res.config.settings"].create({"ezy_wms_zip_length": False})

        settings.execute()

        self.assertFalse(self.company.ezy_wms_zip_length)
        self.assertTrue(self.company.ezy_wms_city_length)

    def test_the_app_icon_ships(self):
        self.assertTrue(file_path("ezyflow_bridge/static/description/icon.png"))

    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("ezy_post_migrate_350", file_path(MIGRATION))
        self.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.migration)

    def run_migration(self):
        self.env.flush_all()
        self.migration.migrate(self.env.cr, "3.4.0")
        self.env.invalidate_all()

    def test_the_migration_covers_only_switches_of_3_5_0(self):
        covered = {new for news in self.migration.COVERED.values() for new in news}
        self.assertLessEqual(covered, set(SWITCHES))

    def test_the_migration_carries_the_old_switches_onto_the_ones_they_cover(self):
        # A 3.4.0 database: the two old columns, the product one turned off.
        cr = self.env.cr
        for old in self.migration.COVERED:
            cr.execute(f"ALTER TABLE res_company ADD COLUMN IF NOT EXISTS {old} boolean")
        cr.execute(
            "UPDATE res_company SET ezy_check_product_constraints = FALSE, "
            "ezy_check_partner_constraints = TRUE WHERE id = %s",
            (self.company.id,),
        )

        self.run_migration()

        off = set(self.migration.COVERED["ezy_check_product_constraints"])
        self.assertEqual({switch for switch in SWITCHES if not self.company[switch]}, off)

    def test_the_migration_leaves_every_switch_on_when_the_old_ones_were_on(self):
        cr = self.env.cr
        for old in self.migration.COVERED:
            cr.execute(f"ALTER TABLE res_company ADD COLUMN IF NOT EXISTS {old} boolean")
            cr.execute(f"UPDATE res_company SET {old} = TRUE")

        self.run_migration()

        self.assertEqual([switch for switch in SWITCHES if not self.company[switch]], [])

    def test_the_migration_runs_on_a_database_without_the_old_columns(self):
        cr = self.env.cr
        for old in self.migration.COVERED:
            cr.execute(f"ALTER TABLE res_company DROP COLUMN IF EXISTS {old}")

        self.run_migration()

        self.assertEqual([switch for switch in SWITCHES if not self.company[switch]], [])
