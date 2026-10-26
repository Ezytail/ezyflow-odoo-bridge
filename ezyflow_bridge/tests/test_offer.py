# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestOffer(EzyflowBridgeCase):
    """Behaviours 1 (offer on assignment), 2 (hold) and the manual offer of 7."""

    def test_auto_mode_offers_the_delivery_once_reserved(self):
        self.out_type.ezy_logistics_mode = "auto"
        picking = self.confirm_order()
        self.assertFalse(picking.ezy_wms_state, "confirmed but not reserved: nothing offered")

        picking.action_assign()

        self.assertEqual(picking.state, "assigned")
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")

    def test_partial_availability_is_enough_to_offer(self):
        self.out_type.ezy_logistics_mode = "auto"
        picking = self.confirm_order(quantity=150)

        picking.action_assign()

        self.assertEqual(picking.move_ids.state, "partially_available")
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")

    def test_off_mode_never_offers(self):
        self.out_type.ezy_logistics_mode = "off"
        picking = self.confirm_order()

        picking.action_assign()

        self.assertEqual(picking.state, "assigned")
        self.assertFalse(picking.ezy_wms_state)

    def test_manual_mode_waits_for_a_person(self):
        self.out_type.ezy_logistics_mode = "manual"
        picking = self.confirm_order()
        picking.action_assign()
        self.assertFalse(picking.ezy_wms_state)

        picking.with_user(self.warehouse_user).write({"ezy_wms_state": "ready_for_logistics"})

        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")

    def test_the_form_button_offers_a_manual_delivery(self):
        self.out_type.ezy_logistics_mode = "manual"
        picking = self.confirm_order()
        picking.action_assign()

        picking.with_user(self.warehouse_user).action_ezy_offer_to_logistics()

        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")

    def test_a_person_may_not_offer_on_an_auto_or_off_type(self):
        for mode in ("auto", "off"):
            self.out_type.ezy_logistics_mode = mode
            picking = self.confirm_order()
            with self.assertRaises(UserError, msg=mode):
                picking.with_user(self.warehouse_user).write(
                    {"ezy_wms_state": "ready_for_logistics"}
                )

    def test_a_person_may_not_write_any_other_state(self):
        self.out_type.ezy_logistics_mode = "manual"
        picking = self.confirm_order()
        picking.action_assign()

        with self.assertRaises(UserError):
            picking.with_user(self.warehouse_user).write({"ezy_wms_state": "sent_to_logistics"})
        picking.with_user(self.warehouse_user).write({"ezy_wms_state": "ready_for_logistics"})
        with self.assertRaises(UserError):
            picking.with_user(self.warehouse_user).write({"ezy_wms_state": False})

        # The connector and an administrator drive the hand-off.
        self.set_wms_state(picking, "sent_to_logistics")
        self.assertEqual(picking.ezy_wms_state, "sent_to_logistics")
        picking.with_user(self.admin_user).write({"ezy_wms_state": "refused_by_logistics"})
        self.assertEqual(picking.ezy_wms_state, "refused_by_logistics")

    def test_allow_list_filters_on_the_channel(self):
        self.out_type.write({"ezy_logistics_mode": "auto", "ezy_channels": "PRO"})
        picking = self.confirm_order()
        picking.action_assign()
        self.assertFalse(picking.ezy_wms_state, "WEB is not in [PRO]")

        self.out_type.ezy_channels = "WEB, PRO"
        picking = self.confirm_order()
        picking.action_assign()
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")

    def test_a_picking_without_channel_is_offered_only_by_an_empty_allow_list(self):
        self.out_type.write({"ezy_logistics_mode": "auto", "ezy_channels": "WEB"})
        anonymous = self.env["res.partner"].create(
            {"name": "No channel", "phone": "+33100000001", "email": "anonymous@example.test"}
        )
        picking = self.confirm_order(partner=anonymous)
        picking.action_assign()
        self.assertFalse(picking.ezy_wms_state)

        self.out_type.ezy_channels = False
        picking = self.confirm_order(partner=anonymous)
        picking.action_assign()
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")

    def test_a_malformed_channel_code_is_refused(self):
        for allow_list in ("WEB,shop", "A,B C", "WEB," + "A" * 33):
            with self.subTest(allow_list=allow_list), self.assertRaises(ValidationError):
                self.out_type.ezy_channels = allow_list

    def test_a_well_formed_channel_code_is_accepted_though_unlisted(self):
        self.out_type.ezy_channels = "WEB, B2B,SHOP-FR"
        self.assertEqual(self.out_type.ezy_channels, "WEB, B2B,SHOP-FR")

        self.customer.ezy_channel = "SHOP-FR"
        self.assertEqual(self.customer.ezy_channel, "SHOP-FR")

    def test_a_held_delivery_is_not_offered_until_the_hold_is_cleared(self):
        self.out_type.ezy_logistics_mode = "auto"
        picking = self.confirm_order()
        picking.ezy_hold = True

        picking.action_assign()
        self.assertEqual(picking.state, "assigned")
        self.assertFalse(picking.ezy_wms_state)

        picking.ezy_hold = False
        picking.do_unreserve()
        picking.action_assign()
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")

    def test_a_held_delivery_cannot_be_offered_by_hand_either(self):
        self.out_type.ezy_logistics_mode = "manual"
        picking = self.confirm_order()
        picking.ezy_hold = True

        with self.assertRaises(UserError):
            picking.with_user(self.warehouse_user).write({"ezy_wms_state": "ready_for_logistics"})

    def test_an_internal_transfer_is_never_offered(self):
        for mode in ("auto", "manual", "off"):
            self.int_type.ezy_logistics_mode = mode
            picking = self.create_picking(self.int_type, self.stock_location, self.shelf)
            picking.action_assign()
            self.assertEqual(picking.state, "assigned", mode)
            self.assertFalse(picking.ezy_wms_state, mode)
            with self.assertRaises(UserError, msg=mode):
                picking.with_user(self.warehouse_user).write(
                    {"ezy_wms_state": "ready_for_logistics"}
                )

    def test_a_receipt_on_auto_is_offered_when_assigned(self):
        self.in_type.ezy_logistics_mode = "auto"

        picking = self.create_picking(self.in_type, self.supplier_location, self.stock_location)

        self.assertEqual(picking.state, "assigned", "a receipt is assigned at confirmation")
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")

    def test_a_delivery_already_in_the_hand_off_is_not_re_offered(self):
        self.out_type.ezy_logistics_mode = "auto"
        picking = self.confirm_order()
        picking.action_assign()
        self.set_wms_state(picking, "refused_by_logistics")

        picking.action_assign()

        self.assertEqual(picking.ezy_wms_state, "refused_by_logistics")
