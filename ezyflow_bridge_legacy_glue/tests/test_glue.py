# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The glue on a legacy tenant (docs/slices/S26-legacy-glue.md): the legacy
module owns every mirrored value, eligibility and backorders; the bridge's
fields follow it both ways; the connector never learns which world it is in."""
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.ezyflow_bridge.tests.common import EzyflowBridgeCase

from ..hooks import backfill


@tagged("post_install", "-at_install")
class TestLegacyGlue(EzyflowBridgeCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer.idcanal = "WEB"

    def _delivery(self, assign=True):
        picking = self.confirm_order()
        if assign:
            picking.action_assign()
        return picking

    def _connector_write(self, picking, state):
        picking.with_user(self.connector_user).with_context(
            tracking_disable=True, mail_create_nosubscribe=True
        ).write({"ezy_wms_state": state})
        picking.invalidate_recordset()

    # Eligibility is the legacy module's.

    def test_the_bridge_mode_reads_off_on_every_operation_type(self):
        for picking_type in (self.out_type, self.in_type, self.int_type):
            self.assertEqual(picking_type.ezy_logistics_mode, "off")
        self.out_type.write({"ezy_logistics_mode": "auto"})
        self.assertEqual(self.out_type.ezy_logistics_mode, "off", "a write cannot turn it on")

    def test_the_legacy_module_offers_the_assigned_delivery_and_the_bridge_reads_it(self):
        picking = self._delivery()

        self.assertEqual(picking.move_ids.mapped("textual_substate"), ["ready_for_logistics"])
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")

    def test_a_person_cannot_offer_through_the_bridge(self):
        # The Offer button of the bridge is for manual mode; the mode reads off
        # on a glued tenant, so the bridge's guard refuses the action.
        picking = self.confirm_order()
        with self.assertRaises(UserError):
            picking.with_user(self.warehouse_user).action_ezy_offer_to_logistics()

    # The WMS state: one value, the legacy module's, mirrored both ways.

    def test_the_connector_s_state_lands_on_every_move_and_freezes(self):
        picking = self._delivery()
        self._connector_write(picking, "sent_to_logistics")

        self.assertEqual(picking.move_ids.mapped("textual_substate"), ["sent_to_logistics"])
        self.assertEqual(picking.move_ids.mapped("substate_id.name"), ["sent_to_logistics"])
        self.assertEqual(picking.ezy_wms_state, "sent_to_logistics")
        self.assertTrue(picking.ezy_is_frozen)

    def test_a_legacy_write_on_the_moves_surfaces_on_the_transfer(self):
        picking = self._delivery()
        picking.move_ids.write({"textual_substate": "preparation_in_progress"})
        picking.invalidate_recordset()

        self.assertEqual(picking.ezy_wms_state, "preparation_in_progress")

    def test_the_legacy_precedence_refused_then_cancelled_then_first(self):
        # Two assigned moves: the legacy module resolves a substate on an
        # assigned move only.
        picking = self.confirm_order(quantity=2)
        extra = self.env["product.product"].create(
            {
                "name": "Second good",
                "type": "consu",
                **self.storable(),
                "default_code": "GLUE-2",
                "barcode": "GLUE0002",
            }
        )
        self.env["stock.quant"]._update_available_quantity(extra, self.stock_location, 5)
        picking.write(
            {
                "move_ids": [
                    (0, 0, {"name": "/", "product_id": extra.id, "product_uom_qty": 1,
                            "location_id": picking.location_id.id,
                            "location_dest_id": picking.location_dest_id.id})
                ]
            }
        )
        picking.action_assign()
        moves = picking.move_ids
        self.assertEqual(len(moves), 2)
        self.assertEqual(set(moves.mapped("state")), {"assigned"})
        moves.write({"textual_substate": "preparation_in_progress"})
        moves[1].write({"textual_substate": "cancelled_by_logistics"})
        picking.invalidate_recordset()
        self.assertEqual(picking.ezy_wms_state, "cancelled_by_logistics")
        moves[0].write({"textual_substate": "refused_by_logistics"})
        picking.invalidate_recordset()
        self.assertEqual(picking.ezy_wms_state, "refused_by_logistics", "refused wins")

    def test_a_state_write_crosses_both_modules_once(self):
        picking = self._delivery()
        original = type(picking.move_ids)._get_substate_by_text
        calls = []

        def counting(self, *args, **kwargs):
            calls.append(1)
            return original(self, *args, **kwargs)

        with patch.object(type(picking.move_ids), "_get_substate_by_text", counting):
            self._connector_write(picking, "preparation_to_do")

        self.assertEqual(sum(calls), 1, "the legacy inverse resolves each move's substate once")
        self.assertEqual(picking.ezy_wms_state, "preparation_to_do")

    def test_the_legacy_offer_wakes_the_connector(self):
        picking = self.confirm_order()
        with patch.object(type(self.env["ezyflow.wakeup"]), "schedule") as schedule:
            picking.action_assign()
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")
        schedule.assert_called_once_with("stock.picking", picking.id, picking.company_id.id)

    def test_a_connector_write_to_ready_wakes_once_whatever_the_recompute_order(self):
        # The inverse writes the moves, the compute reruns before the write is
        # flushed: the previous value is the one in the cache, not the table's.
        picking = self._delivery()
        self._connector_write(picking, "sent_to_logistics")
        with patch.object(type(self.env["ezyflow.wakeup"]), "schedule") as schedule:
            self._connector_write(picking, "ready_for_logistics")
            picking.move_ids.write({"textual_substate": "ready_for_logistics"})
            picking.flush_recordset()
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")
        schedule.assert_called_once_with("stock.picking", picking.id, picking.company_id.id)

    def test_the_install_backfills_the_mirrors_without_waking(self):
        picking = self._delivery()
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")
        self.customer.idcanal = "PRO"
        # A stale mirror, as a row written before the glue was installed.
        self.env.cr.execute(
            "UPDATE stock_picking SET ezy_wms_state = NULL WHERE id = %s", (picking.id,)
        )
        self.env.cr.execute(
            "UPDATE res_partner SET ezy_channel = NULL WHERE id = %s", (self.customer.id,)
        )
        self.env.invalidate_all()
        with patch.object(type(self.env["ezyflow.wakeup"]), "schedule") as schedule:
            backfill(self.env)
        self.env.invalidate_all()
        self.assertEqual(picking.ezy_wms_state, "ready_for_logistics")
        self.assertEqual(self.customer.ezy_channel, "PRO")
        schedule.assert_not_called()

    def test_a_new_company_starts_with_the_switches_off(self):
        company = self.env["res.company"].create({"name": "Glued second"})
        self.assertFalse(company.ezy_wms_default_code_required)
        self.assertFalse(company.ezy_wms_partner_name_length)

    # The hold and the channel.

    def test_the_hold_mirrors_both_ways(self):
        picking = self._delivery()
        picking.write({"ezy_hold": True})
        self.assertTrue(picking.is_blocked_for_logistics)
        picking.write({"is_blocked_for_logistics": False})
        picking.invalidate_recordset()
        self.assertFalse(picking.ezy_hold)

    def test_the_channel_mirrors_idcanal_on_partner_order_and_transfer(self):
        # The connector creates an order with its channel (S5); the glue
        # writes it on the legacy field and copies it down to the transfer as
        # the legacy screens do.
        self.assertEqual(self.customer.ezy_channel, "WEB")
        picking = self.confirm_order(ezy_channel="PRO")
        self.assertEqual(picking.sale_id.idcanal, "PRO")
        self.assertEqual(picking.sale_id.ezy_channel, "PRO")
        self.assertEqual(picking.idcanal, "PRO", "copied down at creation")
        self.assertEqual(picking.ezy_channel, "PRO")

        picking.write({"ezy_channel": "WEB"})
        self.assertEqual(picking.idcanal, "WEB")

        other = self.confirm_order()
        self.assertEqual(other.idcanal, "WEB", "without an order channel, the partner's")

    def test_a_channel_outside_the_six_is_refused_naming_them(self):
        with self.assertRaises(ValidationError) as refused:
            self.customer.write({"ezy_channel": "B2B"})
        self.assertIn("B2B", str(refused.exception))
        self.assertIn(
            "WEB, PRO, MARKETPLACE, DISTRIBUTEUR, REASSORT, SPECIAL", str(refused.exception)
        )

    # The carrier codes.

    def test_the_carrier_codes_mirror_the_legacy_names(self):
        service = self.env["product.product"].create(
            {"name": "Ship", "type": "service", "sale_ok": False}
        )
        carrier = self.env["delivery.carrier"].create(
            {"name": "Glue carrier", "product_id": service.id}
        )
        carrier.write({"name_l4": "CHRONO", "name_l4_key2": "13H"})
        self.assertEqual((carrier.ezy_service_code, carrier.ezy_carrier_code), ("CHRONO", "13H"))
        carrier.write({"ezy_service_code": "COLISSIMO"})
        self.assertEqual(carrier.name_l4, "COLISSIMO")

    # The write guard, the freeze, the backorders, the constraints, the mails.

    def test_the_connector_holds_the_legacy_group_and_writes_in_the_hand_off(self):
        self.assertTrue(
            self.connector_user.has_group("logistics_improvements.can_change_logistics_states")
        )
        picking = self._delivery()
        self._connector_write(picking, "sent_to_logistics")
        # The legacy guard, asked directly, is silent for the connector, and the
        # connector's hand-off writes go through; a person is the legacy
        # module's and the bridge's business (their own tests).
        picking.move_ids.with_user(self.connector_user)._ckeck_logistics_states_security()
        picking.with_user(self.connector_user).move_ids.write(self.done(1))
        self.assertEqual([self.move_quantity(m) for m in picking.move_ids], [1])
        stock_user = new_test_user(
            self.env, login="ezy_glue_stock", groups="stock.group_stock_user"
        )
        self.assertFalse(
            stock_user.has_group("logistics_improvements.can_change_logistics_states")
        )

    def test_the_freeze_holds_with_both_modules(self):
        picking = self._delivery()
        self._connector_write(picking, "sent_to_logistics")
        picking.do_unreserve()
        picking.invalidate_recordset()
        self.assertEqual(picking.state, "assigned")
        self.assertEqual(sum(self.move_quantity(m) for m in picking.move_ids), 5)

    def test_the_wms_state_survives_a_partial_preparation(self):
        # The OCA mixin resets the substate on every state change; the
        # connector's partial write moves the move to partially available.
        picking = self._delivery()
        self._connector_write(picking, "preparation_to_do")
        picking.with_user(self.connector_user).move_ids.write(self.done(2))
        picking.invalidate_recordset()
        self.assertEqual(picking.move_ids.mapped("textual_substate"), ["preparation_to_do"])
        self.assertEqual(picking.ezy_wms_state, "preparation_to_do")
        self.assertEqual(picking.state, "assigned")

    def test_the_connector_s_cancellation_gives_the_reservation_back(self):
        # The legacy module bypasses the quants' bookkeeping for a move in a
        # logistics substate; the bridge never does (3.8.2).
        picking = self._delivery()
        quant = self.env["stock.quant"].search(
            [("product_id", "=", self.product.id), ("location_id", "=", picking.location_id.id)]
        )
        self.assertEqual(sum(quant.mapped("reserved_quantity")), 5)
        self._connector_write(picking, "preparation_to_do")
        picking.with_user(self.connector_user).action_cancel()
        quant.invalidate_recordset()
        self.assertEqual(picking.state, "cancel")
        self.assertEqual(sum(quant.mapped("reserved_quantity")), 0)

    def test_the_legacy_backorder_strategy_decides_over_the_context_key(self):
        picking = self._delivery()
        picking.write({"backorder_strategy": "never"})
        self._connector_write(picking, "preparation_to_do")
        picking.move_ids.write(self.done(2))

        picking.with_user(self.connector_user).with_context(
            tracking_disable=True, mail_create_nosubscribe=True, skip_backorder=False
        ).button_validate()

        self.assertEqual(picking.state, "done")
        self.assertFalse(
            picking.backorder_ids,
            "never: the legacy module cancels the remainder whatever the context says",
        )

    def test_a_batch_of_products_lands_one_per_call_for_the_legacy_checks(self):
        templates = (
            self.env["product.template"]
            .with_user(self.connector_user)
            .create(
                [
                    {"name": f"Glued {i}", "default_code": f"GLUED-{i}", **self.storable()}
                    for i in range(3)
                ]
            )
        )
        self.assertEqual(len(templates), 3)
        variants = (
            self.env["product.product"]
            .with_user(self.connector_user)
            .create(
                [
                    {"name": f"Glued V{i}", "default_code": f"GLUEDV-{i}", **self.storable()}
                    for i in range(3)
                ]
            )
        )
        self.assertEqual(len(variants), 3)

    def test_the_bridge_constraints_are_off_and_the_legacy_ones_on(self):
        self.assertFalse(self.company.ezy_wms_default_code_required)
        self.assertTrue(self.company.check_product_constraints)

    def test_no_mail_goes_out_without_a_template_on_the_substate(self):
        picking = self._delivery()
        before = self.env["mail.mail"].search_count([])
        self._connector_write(picking, "sent_to_logistics")
        self.assertEqual(self.env["mail.mail"].search_count([]), before)
