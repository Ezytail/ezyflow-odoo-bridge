# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The views are one tree for 17 and later and its twin for 16 (ADR 0015,
ADR 0035): the two declare the same views, and the running series has every
one of them installed. The drift gate of a view change made on one side."""
import os
import re

from odoo import release
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from ..models.security import SHARED_VIEWS, TWIN_SERIES
from .common import MODULE, EzyflowBridgeCase

RECORD_ID = re.compile(r'<record\s+id="([^"]+)"\s+model="(ir\.ui\.view|ir\.actions\.act_window)"')


def xml_ids(folder, names):
    found = {}
    for name in names:
        path = os.path.join(get_module_path(MODULE), "views", folder, name)
        with open(path, encoding="utf-8") as f:
            found[name] = set(RECORD_ID.findall(f.read()))
    return found


@tagged("post_install", "-at_install")
class TestSeriesViews(EzyflowBridgeCase):
    def test_the_16_twin_declares_the_same_views_as_the_shared_tree(self):
        shared = xml_ids("", SHARED_VIEWS)
        twin = xml_ids(f"odoo{TWIN_SERIES}", SHARED_VIEWS)
        for name in SHARED_VIEWS:
            self.assertEqual(
                shared[name],
                twin[name],
                f"views/{name} and views/odoo{TWIN_SERIES}/{name} declare different xml ids",
            )
            self.assertTrue(shared[name], f"views/{name} declares no view")

    def test_the_running_series_has_every_view_of_its_tree(self):
        loader = self.env["ezyflow.bridge.security"]
        names = loader.views_of(release.version_info[0], SHARED_VIEWS, SHARED_VIEWS)
        folder = os.path.dirname(names[0])
        for name, ids in xml_ids(folder, [os.path.basename(n) for n in names]).items():
            for xml_id, model in ids:
                record = self.env.ref(f"{MODULE}.{xml_id}", raise_if_not_found=False)
                self.assertTrue(record, f"{xml_id} of {name} is not loaded")
                self.assertEqual(record._name, model)
