# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The WMS constraints (behaviour 8, ADR 0017): Reflex's figures, one switch each.

The figures are Reflex's own (ezyflow-reflex's declared rules and the widths of
the Reflex REST API) and fixed per bridge release; a tenant on another WMS
turns off the switches it does not need instead of changing a figure. Every
constraint binds people only: the connector user writes what a shop sent and
Reflex judges it on the way to the warehouse. Administrators and code run as
superuser stay bound.
"""
import re

CONNECTOR_GROUP = "ezyflow_bridge.group_ezyflow_connector"

# The context key that defers the product constraints of a write in which Odoo
# generates a variant without identity (a template create, attribute values
# added); they run on the write that follows. Read by the product checks only:
# it never lifts a partner, order or operation type constraint.
DEFER_KEY = "ezy_defer_wms_identity"

DEFAULT_CODE_LIMIT = 16
DEFAULT_CODE_ALPHABET = "A-Z 0-9 _ . - #"
DEFAULT_CODE_PATTERN = re.compile(r"[A-Z0-9_.\-#]+")
PRODUCT_NAME_LIMIT = 30
BARCODE_LIMIT = 35
BARCODE_PATTERN = re.compile(r"[A-Za-z0-9]+")
PARTNER_NAME_LIMIT = 35
STREET_LIMIT = 35
CITY_LIMIT = 35
ZIP_LIMIT = 9
PHONE_LIMIT = 20
EMAIL_LIMIT = 140
PICKING_NAME_LIMIT = 20
PICKING_NAME_ALPHABET = "A-Z 0-9 _ - . # / \\"
PICKING_NAME_PATTERN = re.compile(r"[A-Z0-9_\-.#/\\]+")

# The company switches, in the order of the EzyFlow settings page. Each one is
# a boolean on res.company, on by default, and a related setting.
SWITCHES = (
    "ezy_wms_default_code_length",
    "ezy_wms_default_code_alphabet",
    "ezy_wms_default_code_required",
    "ezy_wms_product_name_length",
    "ezy_wms_barcode_alphabet",
    "ezy_wms_barcode_length",
    "ezy_wms_partner_name_length",
    "ezy_wms_street_length",
    "ezy_wms_city_length",
    "ezy_wms_zip_length",
    "ezy_wms_phone_length",
    "ezy_wms_email_length",
    "ezy_wms_delivery_contact_required",
    "ezy_wms_picking_name",
)


def is_connector_user(env):
    """Whether the user behind ``env`` is a member of the EzyFlow connector group,
    read through Odoo's cached ``has_group``."""
    user = env.user
    return bool(user) and user.has_group(CONNECTOR_GROUP)


def binds(env, company, switch):
    """Whether the WMS constraint behind ``switch`` binds a write in ``env`` on a
    record of ``company``: its switch is on and the writer is not the connector
    user."""
    if not company[switch]:
        return False
    return not is_connector_user(env)


def deferred(env):
    """Whether the product constraints of this write wait for the next one."""
    return bool(env.context.get(DEFER_KEY))
