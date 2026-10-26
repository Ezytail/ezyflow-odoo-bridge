# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The closed sets the connector and the bridge share (CONTEXT.md).

The connector maps these keys to its own enums; a key added here is a contract
change and moves the bridge minor version together with the service.
"""

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
# "Channel"). The keys are the codes the platform uses, verbatim.
CHANNELS = [
    ("WEB", "WEB"),
    ("PRO", "PRO"),
    ("MARKETPLACE", "MARKETPLACE"),
    ("DISTRIBUTEUR", "DISTRIBUTEUR"),
    ("REASSORT", "REASSORT"),
    ("SPECIAL", "SPECIAL"),
]

# Whether an operation type offers its pickings to the WMS (CONTEXT.md,
# "Logistics mode"; ADR 0002).
LOGISTICS_MODES = [
    ("off", "Off: never offered"),
    ("auto", "Auto: offered when reserved"),
    ("manual", "Manual: offered when a person says so"),
]
