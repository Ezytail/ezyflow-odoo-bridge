# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from datetime import timedelta

from odoo import fields, release
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import EzyflowBridgeCase

JOURNAL = "ezyflow.stock.journal"


@tagged("post_install", "-at_install")
class TestStockJournal(EzyflowBridgeCase):
    """Behaviour 15 (ADR 0041): every change of a quant's quantity or
    reservation leaves a row naming the product and the location, one per
    cell and transaction, written by the transaction's pre-commit, on every
    series; the connector reads its companies' rows, nobody else writes
    them, and the daily cron purges the rows older than seven days."""

    def _commit(self):
        """What a commit runs before it commits: the ORM flush, then the
        pre-commit hooks, the journal's among them."""
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _last_id(self):
        self._commit()
        return self.env[JOURNAL].search([], order="id desc", limit=1).id or 0

    def _rows_after(self, last_id, product=None):
        self._commit()
        return self.env[JOURNAL].search(
            [("id", ">", last_id), ("product_id", "=", (product or self.product).id)]
        )

    def test_a_quant_write_appends_a_row(self):
        before = self._last_id()

        self.env["stock.quant"]._update_available_quantity(self.product, self.stock_location, 4)

        rows = self._rows_after(before)
        self.assertEqual(rows.location_id, self.stock_location)
        self.assertTrue(all(row.instant for row in rows))

    def test_a_transaction_writes_one_row_per_cell_and_nothing_before_its_commit(self):
        before = self._last_id()
        quants = self.env["stock.quant"]

        for _ in range(3):
            quants._update_available_quantity(self.product, self.stock_location, 1)
        quants._update_available_quantity(self.product, self.shelf, 1)
        self.env.flush_all()

        self.assertFalse(
            self.env[JOURNAL].search([("id", ">", before)]),
            "the rows wait for the transaction's pre-commit",
        )
        rows = self._rows_after(before)
        self.assertEqual(
            sorted(rows.location_id.ids),
            sorted((self.stock_location | self.shelf).ids),
            "one row per cell, whatever the number of calls",
        )

    def test_a_reservation_and_an_unreservation_append_rows(self):
        before = self._last_id()
        delivery = self.confirm_order(quantity=5)
        delivery.action_assign()
        self.assertEqual(delivery.state, "assigned")

        reserved = self._rows_after(before)
        self.assertIn(self.stock_location, reserved.location_id)

        after_reservation = self._last_id()
        delivery.do_unreserve()

        unreserved = self._rows_after(after_reservation)
        self.assertTrue(unreserved, "an unreservation leaves a row where it leaves no move line")
        self.assertIn(self.stock_location, unreserved.location_id)

    def test_a_quant_zeroed_and_deleted_appends_a_row(self):
        product = self.env["product.product"].create(
            {"name": "Journal good", "default_code": "JOURNAL-1", **self.storable()}
        )
        quants = self.env["stock.quant"]
        quants._update_available_quantity(product, self.stock_location, 3)
        before = self._last_id()

        quants._update_available_quantity(product, self.stock_location, -3)
        # Odoo's cleanup is SQL: the zero must reach the table first.
        quants.flush_model()
        quants._unlink_zero_quants()
        quants.invalidate_model()

        self.assertFalse(
            quants.search(
                [("product_id", "=", product.id), ("location_id", "=", self.stock_location.id)]
            ),
            "Odoo deleted the quant at zero",
        )
        self.assertEqual(self._rows_after(before, product).location_id, self.stock_location)

    def test_the_purge_deletes_old_rows_only(self):
        journal = self.env[JOURNAL]
        old = journal.create(
            {"product_id": self.product.id, "location_id": self.stock_location.id}
        )
        old.instant = fields.Datetime.now() - timedelta(days=8)
        recent = journal.create(
            {"product_id": self.product.id, "location_id": self.stock_location.id}
        )
        recent.instant = fields.Datetime.now() - timedelta(days=6)

        journal._ezy_purge()

        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    def test_the_connector_reads_the_journal_and_writes_nothing(self):
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock_location, 1)
        self._commit()
        journal = self.env[JOURNAL].with_user(self.connector_user)

        self.assertTrue(journal.search([("product_id", "=", self.product.id)]))
        with self.assertRaises(AccessError):
            journal.create({"product_id": self.product.id, "location_id": self.stock_location.id})
        with self.assertRaises(AccessError):
            journal.search([], limit=1).unlink()

    def test_the_connector_reads_the_journal_of_its_companies_only(self):
        """ADR 0014: a row at another company's location is not the
        connector's, whatever the location's quant carries."""
        other = self.env["res.company"].create({"name": "Journal company"})
        warehouses = self.env["stock.warehouse"]
        other_stock = warehouses.search([("company_id", "=", other.id)], limit=1).lot_stock_id
        self.product.company_id = False
        before = self._last_id()
        self.env["stock.quant"]._update_available_quantity(self.product, other_stock, 2)
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock_location, 2)
        self._commit()

        rows = (
            self.env[JOURNAL]
            .with_user(self.connector_user)
            .search([("id", ">", before), ("product_id", "=", self.product.id)])
        )

        self.assertEqual(rows.location_id, self.stock_location)

    def test_a_non_strict_reservation_on_16_names_the_child_location_it_reserved_on(self):
        """Odoo 16 reserves at a location and its children and answers the
        quants it reserved on; the row names the child too."""
        if release.version_info[0] >= 17:
            self.skipTest("17 and later reserve on the one location they are given")
        product = self.env["product.product"].create(
            {"name": "Shelved good", "default_code": "JOURNAL-2", **self.storable()}
        )
        quants = self.env["stock.quant"]
        quants._update_available_quantity(product, self.shelf, 4)
        before = self._last_id()

        quants._update_reserved_quantity(product, self.stock_location, 2, strict=False)

        rows = self._rows_after(before, product)
        self.assertIn(self.shelf, rows.location_id)
        self.assertIn(self.stock_location, rows.location_id)

    def test_the_purge_runs_every_day(self):
        cron = self.env.ref("ezyflow_bridge.ir_cron_ezyflow_stock_journal_purge")

        self.assertTrue(cron.active)
        self.assertEqual((cron.interval_number, cron.interval_type), (1, "days"))
        if release.version_info[0] < 18:
            self.assertEqual(cron.numbercall, -1, "a 16 cron runs once unless told otherwise")
