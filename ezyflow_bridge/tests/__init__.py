# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
#
# Bridge tests are tagged post_install and run inside the Odoo container of
# every supported series started by the connector's integration test job. A
# module not imported here never runs.
from . import (
    test_apps_visibility,
    test_bridge_settings,
    test_channel,
    test_constraints,
    test_delivery_status,
    test_freeze,
    test_fulfilment_rights,
    test_group_by,
    test_help_page,
    test_i18n,
    test_offer,
    test_order_rights,
    test_product_rights,
    test_proforma,
    test_relay,
    test_series_security,
    test_shop_identity,
    test_shop_total,
    test_sms_warning,
    test_stock_settings,
    test_template_identity,
    test_wakeup,
    test_wms_settings,
    test_wms_state,
)
