# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.tests import TransactionCase, tagged

from .. import hooks


@tagged("post_install", "-at_install")
class TestAppsVisibility(TransactionCase):
    """A command-line install on an existing Odoo 20 database leaves the
    bridge's module row without a type, which hides it in Apps (hooks.py).
    The post-install hook and the 3.3.1 migration give it the type a UI
    install would have; on a series without the field they do nothing."""

    def setUp(self):
        super().setUp()
        self.module = self.env["ir.module.module"].search([("name", "=", hooks.MODULE)])
        self.assertEqual(len(self.module), 1)

    def test_hook_sets_the_type_odoo_20_lists_in_apps(self):
        if "module_type" not in self.module._fields:
            self.skipTest("this series has no module_type (Odoo 19)")
        # The row as a command-line install on an existing database leaves it.
        self.module.write({"module_type": False})
        hooks.post_init_hook(self.env)
        self.assertEqual(self.module.module_type, "official")

    def test_hook_leaves_a_typed_row_alone(self):
        if "module_type" not in self.module._fields:
            self.skipTest("this series has no module_type (Odoo 19)")
        self.module.write({"module_type": "industries"})
        hooks.post_init_hook(self.env)
        self.assertEqual(self.module.module_type, "industries")

    def test_hook_is_a_no_op_without_the_field(self):
        if "module_type" in self.module._fields:
            self.skipTest("this series has module_type (Odoo 20)")
        before = self.module.read()[0]
        hooks.post_init_hook(self.env)
        self.assertEqual(self.module.read()[0], before)
