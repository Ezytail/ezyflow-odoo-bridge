# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestChatterSilence(EzyflowBridgeCase):
    """Behaviour 10 (ADR 0012, S9): nothing the connector user does leaves a
    tracking line, the recompute of a tracked stored field included. A person
    doing the same is tracked as Odoo always did: the test can tell."""

    def _tracking_lines(self, picking):
        """Odoo 19 hangs tracking values on the message, Odoo 20 makes a tracking
        line its own message type; the field tells which (ADR 0015)."""
        self.env.flush_all()
        self.env.cr.precommit.run()
        messages = self.env["mail.message"]
        tracked = (
            ("tracking_value_ids", "!=", False)
            if "tracking_value_ids" in messages._fields
            else ("message_type", "=", "tracking")
        )
        return messages.search(
            [("model", "=", "stock.picking"), ("res_id", "=", picking.id), tracked]
        )

    def _add_move(self, picking, user):
        # A move created on a reserved transfer puts it back to draft and
        # confirming it brings it back to ready: the transfer's state, a tracked
        # stored computed field, changes twice without being written by name.
        move = (
            self.env["stock.move"]
            .with_user(user)
            .with_context(tracking_disable=True)
            .create(
                {
                    "picking_id": picking.id,
                    "product_id": self.product.id,
                    "product_uom_qty": 1,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                }
            )
        )
        move.with_user(user).with_context(tracking_disable=True)._action_confirm()
        move.with_user(user).with_context(tracking_disable=True)._action_assign()

    def test_the_connector_user_leaves_no_tracking_line_on_a_recomputed_state(self):
        picking = self.confirm_order()
        picking.action_assign()
        self.env.flush_all()
        self.env.cr.precommit.run()
        before = self._tracking_lines(picking)

        self._add_move(picking, self.connector_user)

        self.assertEqual(self._tracking_lines(picking), before)

    def test_a_person_is_still_tracked(self):
        picking = self.confirm_order()
        picking.action_assign()
        self.env.flush_all()
        self.env.cr.precommit.run()
        before = self._tracking_lines(picking)

        # A tracked field written by name, as a person does from the form.
        scheduled = picking.scheduled_date
        picking.with_user(self.admin_user).write(
            {"scheduled_date": scheduled.replace(year=scheduled.year + 1)}
        )

        self.assertGreater(len(self._tracking_lines(picking)), len(before))
