# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from lxml import etree

from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestGroupBy(EzyflowBridgeCase):
    """Behaviour 7: the Group By menus offer the WMS state and the delivery
    status, and grouping by them sorts the refused ones apart."""

    def group_by_filter(self, model, search_view, name):
        """The predefined group-by filter of that name in the search view a
        person gets, or None."""
        views = self.env[model].get_views([(self.env.ref(search_view).id, "search")])
        arch = etree.fromstring(views["views"]["search"]["arch"])
        return next(iter(arch.xpath(f"//filter[@name='{name}']")), None)

    def test_transfers_group_by_offers_the_wms_state(self):
        found = self.group_by_filter(
            "stock.picking", "stock.view_picking_internal_search", "ezy_wms_state"
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.get("context"), "{'group_by': 'ezy_wms_state'}")

    def test_orders_group_by_offers_the_delivery_status(self):
        found = self.group_by_filter(
            "sale.order", "sale.view_sales_order_filter", "ezy_delivery_status"
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.get("context"), "{'group_by': 'delivery_status'}")

    def test_grouping_sorts_the_refused_apart(self):
        refused = self.confirm_order()
        offered = self.confirm_order()
        self.set_wms_state(refused, "refused_by_logistics")
        self.set_wms_state(offered, "sent_to_logistics")

        transfers = self.env["stock.picking"]._read_group(
            [("id", "in", (refused + offered).ids)], ["ezy_wms_state"], ["__count"]
        )
        self.assertEqual(
            dict(transfers), {"refused_by_logistics": 1, "sent_to_logistics": 1}
        )
        orders = self.env["sale.order"]._read_group(
            [("id", "in", (refused.sale_id + offered.sale_id).ids)],
            ["delivery_status"],
            ["__count"],
        )
        self.assertEqual(dict(orders), {"refused_by_logistics": 1, "sent_to_logistics": 1})
