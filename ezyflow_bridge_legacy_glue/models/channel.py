# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The legacy module's channel is a closed selection; the bridge's is a free
code (ADR 0029). A value outside the six is refused by the glue, naming them,
and the connector Rejects the order as it does for a code outside the rule."""
from odoo.exceptions import ValidationError

LEGACY_CHANNELS = ("WEB", "PRO", "MARKETPLACE", "DISTRIBUTEUR", "REASSORT", "SPECIAL")


def legacy_channel(env, value):
    value = value or False
    if value and value not in LEGACY_CHANNELS:
        raise ValidationError(
            env._(
                "Channel %(value)s is not one of the legacy logistics module's channels "
                "(%(channels)s).",
                value=value,
                channels=", ".join(LEGACY_CHANNELS),
            )
        )
    return value
