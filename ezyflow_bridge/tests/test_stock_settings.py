# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from lxml import etree

from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestStockSettings(EzyflowBridgeCase):
    """Apply stock reports (ADR 0018): a company switch, off until an
    administrator turns it on, that the connector reads with every report."""

    def test_the_switch_is_off_for_every_company_until_turned_on(self):
        self.assertFalse(self.company.ezy_apply_stock_reports)
        other = self.env["res.company"].create({"name": "Second company"})
        self.assertFalse(other.ezy_apply_stock_reports)

    def test_the_setting_saves_the_company_switch_and_reads_it_back(self):
        settings = self.env["res.config.settings"].create({"ezy_apply_stock_reports": True})

        settings.execute()

        self.assertTrue(self.company.ezy_apply_stock_reports)
        self.assertTrue(self.env["res.config.settings"].create({}).ezy_apply_stock_reports)

        self.env["res.config.settings"].create({"ezy_apply_stock_reports": False}).execute()

        self.assertFalse(self.company.ezy_apply_stock_reports)

    def test_the_ezyflow_page_shows_the_setting_in_its_stock_block(self):
        views = self.env["res.config.settings"].get_views([(False, "form")])
        arch = etree.fromstring(views["views"]["form"]["arch"])

        block = arch.xpath("//app[@name='ezyflow_bridge']/block[@name='ezy_stock']")
        self.assertEqual(len(block), 1)
        self.assertEqual(
            [setting.get("id") for setting in block[0].xpath("setting")],
            ["ezy_apply_stock_reports"],
        )
        self.assertEqual(len(block[0].xpath("setting/field[@name='ezy_apply_stock_reports']")), 1)

    def test_the_connector_user_reads_the_switch(self):
        # What the connector reads with every report, once the bridge's
        # contract version says the switch exists.
        self.company.ezy_apply_stock_reports = True
        env = self.env(user=self.connector_user)

        switch = env["res.company"].search_read(
            [("id", "in", [self.company.id])], ["ezy_apply_stock_reports"]
        )

        self.assertEqual(switch, [{"id": self.company.id, "ezy_apply_stock_reports": True}])
