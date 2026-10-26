# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""Chatter silence for the connector user (ADR 0012, behaviour 10).

The connector sends ``tracking_disable`` on every call, which keeps Odoo from
tracking the fields a write names. A tracked field that is *computed and
stored* (a transfer's state) is prepared for tracking when it is recomputed,
and the recompute runs in whichever environment flushes the transaction, which
is not always the one carrying the connector's context: the S9 chatter audit
found the connector's additional move on a transfer leaving a "Draft -> Ready"
tracking line, and a shop cancellation a "Waiting -> Cancelled" one. Core Odoo
offers no switch that reaches that environment, so the bridge overrides (ADR
0011), on ``mail.thread`` itself: a mixin on the bridge's own model classes
was tried and sits after ``mail.thread`` in the method order, so it missed the
cancellation path. The gate is the connector group, read through Odoo's own
``has_group``, cached per user and group; a person's recompute pays one cached
lookup and is tracked as Odoo always did.
"""
from odoo import models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _ezy_is_connector_transaction(self):
        user = self.env.user
        return bool(user) and user.has_group("ezyflow_bridge.group_ezyflow_connector")

    def _compute_field_value(self, field):
        if not self.env.context.get("tracking_disable") and self._ezy_is_connector_transaction():
            records = self.with_context(tracking_disable=True)
            return super(MailThread, records)._compute_field_value(field)
        return super()._compute_field_value(field)
