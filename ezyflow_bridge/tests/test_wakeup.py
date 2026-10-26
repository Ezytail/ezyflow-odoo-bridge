# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import hashlib
import hmac
import json
from unittest.mock import patch

from odoo.tests import tagged

from ..models import wakeup
from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestWakeup(EzyflowBridgeCase):
    """Behaviour 9 (ADR 0006): a transfer entering ready for logistics posts a
    signed wake-up once the transaction commits."""

    def set_param(self, key, value):
        # Through the record, the API both series share (ADR 0015).
        params = self.env["ir.config_parameter"].sudo()
        record = params.search([("key", "=", key)], limit=1)
        if record:
            record.value = value
        else:
            params.create({"key": key, "value": value})

    def setUp(self):
        super().setUp()
        self.set_param("ezyflow.activity", "acme")
        self.set_param("ezyflow.wakeup_url", "http://connector.test/wake-up")
        self.set_param("ezyflow.wakeup_secret", "s3cret")
        self.out_type.ezy_logistics_mode = "auto"

    def _run_postcommit(self):
        """TransactionCase never commits: run what the transaction registered."""
        self.env.cr.postcommit.run()

    def test_entering_ready_posts_a_signed_wakeup_after_commit(self):
        picking = self.confirm_order()
        with patch.object(wakeup.requests, "post") as post:
            post.return_value.status_code = 202
            picking.action_assign()
            self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")
            post.assert_not_called()

            self._run_postcommit()

        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://connector.test/wake-up")
        self.assertEqual(kwargs["timeout"], wakeup.WAKEUP_TIMEOUT)
        body = json.loads(kwargs["data"])
        self.assertEqual(
            body,
            {
                "activity": "acme",
                "company_id": picking.company_id.id,
                "model": "stock.picking",
                "id": picking.id,
            },
        )
        expected = hmac.new(b"s3cret", kwargs["data"], hashlib.sha256).hexdigest()
        self.assertEqual(kwargs["headers"][wakeup.SIGNATURE_HEADER], expected)

    def test_a_manual_offer_by_a_person_wakes_the_connector_too(self):
        self.out_type.ezy_logistics_mode = "manual"
        picking = self.confirm_order()
        picking.action_assign()
        with patch.object(wakeup.requests, "post") as post:
            post.return_value.status_code = 202
            picking.with_user(self.warehouse_user).action_ezy_offer_to_logistics()
            self._run_postcommit()

        post.assert_called_once()

    def test_a_later_state_does_not_wake(self):
        picking = self.confirm_order()
        picking.action_assign()
        self._run_postcommit()
        with patch.object(wakeup.requests, "post") as post:
            self.set_wms_state(picking, "sent_to_logistics")
            self._run_postcommit()

        post.assert_not_called()

    def test_no_url_no_wakeup(self):
        self.set_param("ezyflow.wakeup_url", "")
        picking = self.confirm_order()
        with patch.object(wakeup.requests, "post") as post:
            picking.action_assign()
            self._run_postcommit()

        post.assert_not_called()

    def test_a_failing_connector_never_breaks_odoo(self):
        picking = self.confirm_order()
        with patch.object(
            wakeup.requests, "post", side_effect=wakeup.requests.ConnectionError("down")
        ):
            picking.action_assign()
            self._run_postcommit()

        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")
