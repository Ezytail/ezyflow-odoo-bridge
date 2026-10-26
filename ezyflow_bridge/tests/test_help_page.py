# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import ast

import lxml.html
from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import html_sanitize
from odoo.tools.misc import file_path

from .common import EzyflowBridgeCase

MODULE = "ezyflow_bridge"
PAGE = "ezyflow_bridge/static/description/index.html"
ACTION = "ezyflow_bridge.action_ezyflow_bridge_help"
VIEW = "ezyflow_bridge.ir_module_module_view_form_ezyflow_help"


@tagged("post_install", "-at_install")
class TestHelpPage(EzyflowBridgeCase):
    """The bridge help page (ADR 0030): Odoo renders the page shipped in the
    module as its description; the Help block of the EzyFlow settings page
    opens the module record in a dialog on a form view of the bridge's own
    showing that description alone. Reached by administrators, as the
    settings page is; the page's content is reviewed, never tested (ADR 0030)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = cls.env["ir.module.module"].search([("name", "=", MODULE)])
        cls.action = cls.env.ref(ACTION)
        cls.view = cls.env.ref(VIEW)

    def settings_arch(self):
        views = self.env["res.config.settings"].get_views([(False, "form")])
        return etree.fromstring(views["views"]["form"]["arch"])

    def test_the_description_is_rendered_from_the_shipped_page(self):
        # The mechanism, not the content (ADR 0030: the review is the gate):
        # what Odoo shows is the shipped file, read through html_sanitize.
        self.assertEqual(len(self.module), 1)
        with open(file_path(PAGE), encoding="utf-8") as page:
            shipped = lxml.html.document_fromstring(page.read())
        expected = html_sanitize(lxml.html.tostring(shipped, encoding="unicode"))

        self.assertTrue(expected)
        self.assertEqual(self.module.description_html, expected)

    def test_the_help_block_is_first_in_the_ezyflow_app_and_opens_the_action(self):
        [app] = self.settings_arch().xpath("//app[@name='ezyflow_bridge']")

        blocks = app.xpath("block")
        self.assertEqual(blocks[0].get("name"), "ezy_help")
        self.assertEqual(blocks[0].get("title"), "Help")
        self.assertEqual(blocks[1].get("name"), "ezy_connector")
        [button] = blocks[0].xpath("setting[@id='ezy_help']//button")
        self.assertEqual(button.get("type"), "action")
        self.assertEqual(button.get("name"), str(self.action.id))
        self.assertEqual(button.get("string"), "Open the EzyFlow bridge help")
        self.assertFalse(blocks[0].xpath(".//field"), "the Help block adds no setting (ADR 0020)")

    def test_the_action_opens_the_bridge_module_alone_in_a_dialog_on_its_own_view(self):
        self.assertEqual(self.action.res_model, "ir.module.module")
        self.assertEqual(self.action.res_id, self.module.id)
        self.assertEqual(self.module.search(ast.literal_eval(self.action.domain)), self.module)
        self.assertEqual(self.action.target, "new")
        self.assertEqual(self.action.view_mode, "form")
        self.assertEqual(self.action.view_id, self.view)

    def test_the_view_shows_the_description_and_nothing_else(self):
        arch = etree.fromstring(self.view.arch)

        self.assertEqual(self.view.model, "ir.module.module")
        self.assertEqual(
            [field.get("name") for field in arch.xpath("//field")], ["description_html"]
        )
        self.assertEqual(arch.get("create"), "0")
        self.assertEqual(arch.get("edit"), "0")
        for tag in ("header", "button", "notebook"):
            self.assertFalse(arch.xpath(f"//{tag}"), tag)

    def test_an_administrator_reads_the_module_and_the_view_through_the_action(self):
        action = self.action.with_user(self.admin_user).read(["res_id", "view_id"])[0]
        module = self.env["ir.module.module"].with_user(self.admin_user).browse(action["res_id"])
        views = module.get_views([(action["view_id"][0], "form")])

        self.assertTrue(module.description_html)
        arch = etree.fromstring(views["views"]["form"]["arch"])
        self.assertEqual(
            [field.get("name") for field in arch.xpath("//field")], ["description_html"]
        )

    def test_the_connector_user_does_not_reach_the_action(self):
        # The connector reads the module row for its contract version and
        # nothing else of this: the action and the view, like the settings
        # page, are the administrator's.
        with self.assertRaises(AccessError):
            self.action.with_user(self.connector_user).read(["res_id"])
        with self.assertRaises(AccessError):
            self.view.with_user(self.connector_user).read(["arch"])
