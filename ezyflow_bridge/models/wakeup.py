# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The wake-up (ADR 0006): a small signed POST telling the connector to poll now.

Posted from a post-commit hook, so a rolled-back transaction wakes nobody and
the connector never reads a record the database has not committed. Carries
the activity, the company, the model and the id, and an HMAC-SHA256 of the
body in a header; the connector treats it only as "poll this publication now".
"""
import hashlib
import hmac
import json
import logging

import requests

from odoo import api, models

_logger = logging.getLogger(__name__)

WAKEUP_TIMEOUT = 2
SIGNATURE_HEADER = "X-EzyFlow-Signature"


class EzyflowWakeup(models.AbstractModel):
    _name = "ezyflow.wakeup"
    _description = "EzyFlow wake-up"

    @api.model
    def _param(self, key):
        """A system parameter's value, through the ORM: Odoo 19 reads them with
        get_param and Odoo 20 with get_str, the record is the common API
        (ADR 0015). The bridge ships the three records, empty."""
        record = self.env["ir.config_parameter"].sudo().search([("key", "=", key)], limit=1)
        return record.value or ""

    @api.model
    def schedule(self, model, res_id, company_id):
        """Registers the wake-up on the transaction's post-commit hooks. Nothing
        is sent when the wake-up URL or the activity is not configured."""
        url = self._param("ezyflow.wakeup_url").strip()
        activity = self._param("ezyflow.activity").strip()
        secret = self._param("ezyflow.wakeup_secret")
        if not url or not activity:
            return
        body = {"activity": activity, "company_id": company_id, "model": model, "id": res_id}
        self.env.cr.postcommit.add(lambda: self._post(url, secret, body))

    @api.model
    def sign(self, secret, payload):
        return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    @api.model
    def _post(self, url, secret, body):
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: self.sign(secret, payload),
        }
        try:
            response = requests.post(url, data=payload, headers=headers, timeout=WAKEUP_TIMEOUT)
        except requests.RequestException as error:
            # A lost wake-up costs latency, never data: the poll is the ledger.
            _logger.warning("EzyFlow wake-up to %s failed: %s", url, error)
            return
        if response.status_code >= 300:
            _logger.warning(
                "EzyFlow wake-up to %s answered %s", url, response.status_code
            )
