# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""Whether the running transaction is the connector's: one answer for every
behaviour that treats the connector user apart (ADR 0012, ADR 0013)."""

CONNECTOR_GROUP = "ezyflow_bridge.group_ezyflow_connector"


def is_connector_transaction(env):
    user = env.user
    return bool(user) and user.has_group(CONNECTOR_GROUP)
