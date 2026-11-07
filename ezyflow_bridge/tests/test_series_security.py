# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import release
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from ..models.contract import WMS_STATES
from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestSeriesSecurity(EzyflowBridgeCase):
    """S4b (ADR 0015): the per-series access rights load on install and on
    update, under the module's own xml ids, and give the connector group the
    same rights on every supported series."""

    def test_the_series_folder_matches_the_server(self):
        self.assertEqual(
            self.env["ezyflow.bridge.security"].series(), release.version_info[0]
        )

    def test_the_access_rights_are_owned_by_the_module(self):
        for xml_id in (
            "ezyflow_bridge.access_sale_order_line_ezyflow_connector",
            "ezyflow_bridge.rule_sale_order_line_ezyflow_connector",
        ):
            self.assertTrue(self.env.ref(xml_id), xml_id)

    def test_reloading_is_idempotent(self):
        before = self.env.ref("ezyflow_bridge.rule_sale_order_line_ezyflow_connector")
        self.env["ezyflow.bridge.security"].load_series_security()
        after = self.env.ref("ezyflow_bridge.rule_sale_order_line_ezyflow_connector")
        self.assertEqual(before, after)

    def test_the_connector_reads_orders_and_carriers(self):
        as_connector = self.env["sale.order"].with_user(self.connector_user)
        as_connector.search([], limit=1)
        self.env["delivery.carrier"].with_user(self.connector_user).search([], limit=1)
        self.env["purchase.order"].with_user(self.connector_user).search([], limit=1)

    def test_the_16_rules_name_every_wms_state(self):
        """Odoo 16 reads ``!= False`` on a one2many path as true for an order
        without transfers, so its rules list the WMS states instead; the list
        is the field's selection, a state added later cannot fall out of it."""
        if release.version_info[0] >= 17:
            self.skipTest("the rules of 17 and later read the state as set")
        expected = [key for key, _label in WMS_STATES]
        for xml_id in (
            "ezyflow_bridge.rule_sale_order_line_ezyflow_connector",
            "ezyflow_bridge.rule_sale_order_ezyflow_connector",
        ):
            domain = safe_eval(self.env.ref(xml_id).domain_force)
            lists = [
                value
                for leaf in domain
                if isinstance(leaf, (tuple, list))
                and len(leaf) == 3
                for path, operator, value in [leaf]
                if path.endswith("ezy_wms_state") and operator == "in"
            ]
            self.assertEqual(lists, [expected], xml_id)
