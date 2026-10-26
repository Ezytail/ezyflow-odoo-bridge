# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The closed sets and the code shapes the connector and the bridge share
(CONTEXT.md).

The connector maps these keys to its own enums; a key added here is a contract
change and moves the bridge minor version together with the service.
"""

import re

from odoo.exceptions import ValidationError

# The WMS state, one field on the picking (ADR 0003), in hand-off order.
WMS_STATES = [
    ("ready_for_logistics", "Ready for logistics"),
    ("sent_to_logistics", "Sent to logistics"),
    ("preparation_to_do", "Preparation to do"),
    ("preparation_in_progress", "Preparation in progress"),
    ("preparation_done", "Preparation done"),
    ("refused_by_logistics", "Refused by logistics"),
    ("cancelled_by_logistics", "Cancelled by logistics"),
    ("shipped", "Shipped"),
]

# A frozen picking (CONTEXT.md): Odoo neither reserves nor unreserves its
# stock, and only the connector user may change its lines. Ready for logistics
# is still Odoo's to reserve; shipped is done with the WMS.
FROZEN_WMS_STATES = (
    "sent_to_logistics",
    "preparation_to_do",
    "preparation_in_progress",
    "preparation_done",
    "refused_by_logistics",
    "cancelled_by_logistics",
)

# The sales channel a partner, an order and a picking carry (CONTEXT.md,
# "Channel"): a free code the platform uses verbatim, such as WEB, PRO or B2B.
# Capital letters, digits, hyphens and underscores; no comma, because the
# allow-list of an operation type is comma-separated. The bridge refuses a code
# outside this shape and never rewrites what a person typed.
# The channel fields carry no size: Odoo 19 cuts a Char to its size before a
# constraint sees it, so the length is this pattern's.
CHANNEL_CODE = re.compile(r"^[A-Z0-9_-]{1,32}$")


def check_channel_codes(env, codes, owner):
    """Refuse the codes that are not channel codes, naming them and their owner."""
    malformed = [code for code in codes if not CHANNEL_CODE.fullmatch(code)]
    if malformed:
        raise ValidationError(
            env._(
                "Not a channel code on %(owner)s: %(codes)s. A channel code is 1 to "
                "32 capital letters, digits, hyphens or underscores, such as WEB, "
                "PRO or B2B.",
                codes=", ".join(malformed),
                owner=owner,
            )
        )


# Whether an operation type offers its pickings to the WMS (CONTEXT.md,
# "Logistics mode"; ADR 0002).
LOGISTICS_MODES = [
    ("off", "Off: never offered"),
    ("auto", "Auto: offered when reserved"),
    ("manual", "Manual: offered when a person says so"),
]
