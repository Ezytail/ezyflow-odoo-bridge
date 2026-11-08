# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The stock journal (behaviour 15, ADR 0041): a row per quant cell a transaction changed.

Every change of a quant's quantity or reservation passes through two methods
of ``stock.quant`` on 16, 18, 19 and 20 (``_update_available_quantity`` and
``_update_reserved_quantity``, overridden in ``stock_quant.py``). Each call
names the product and the location it changed; the cells a transaction
names are kept on the cursor and written once, in one statement, by a
pre-commit hook (``cr.precommit``, on every series): one row per (product,
location) per transaction, its id and instant taken at commit time, so ids
follow the commit order and a rolled-back change leaves no row. The
connector's stock level source reads the rows by id and republishes the
cell from them. A row survives what a cursor on the quants or on the move
lines cannot see: a quant Odoo deletes at zero, an unreservation that
deletes its move line. Append-only, written as the superuser, read by the
connector group, purged after seven days by a daily cron.
"""
from datetime import timedelta

from odoo import api, fields, models

RETENTION_DAYS = 7

# The cells a transaction changed, kept on the cursor until its pre-commit.
PENDING = "ezyflow_bridge.stock_journal"


class EzyflowStockJournal(models.Model):
    _name = "ezyflow.stock.journal"
    _description = "EzyFlow stock journal"
    _order = "id"
    # Append-only and written on every quant change: no audit columns.
    _log_access = False

    product_id = fields.Many2one(
        "product.product", required=True, index=True, ondelete="cascade", readonly=True
    )
    location_id = fields.Many2one(
        "stock.location", required=True, index=True, ondelete="cascade", readonly=True
    )
    instant = fields.Datetime(
        required=True, index=True, readonly=True, default=fields.Datetime.now
    )

    @api.model
    def _ezy_append(self, product, locations):
        """Remember the cells a call changed; the transaction's pre-commit writes them."""
        if not product or not locations:
            return
        cr = self.env.cr
        pending = cr.precommit.data.get(PENDING)
        if pending is None:
            pending = cr.precommit.data[PENDING] = set()
            cr.precommit.add(lambda: self._ezy_write(cr))
        pending.update((product.id, location.id) for location in locations)

    @api.model
    def _ezy_write(self, cr):
        """One INSERT for every cell of the transaction, at the commit's clock."""
        cells = sorted(cr.precommit.data.pop(PENDING, ()))
        if not cells:
            return
        # A cell named inside a savepoint that was rolled back may name a
        # product or a location that no longer exists: it is dropped, never
        # allowed to fail the commit it rides on.
        cr.execute(
            """
            INSERT INTO ezyflow_stock_journal (product_id, location_id, instant)
            SELECT cell.product, cell.location, clock_timestamp() AT TIME ZONE 'UTC'
              FROM unnest(%s::int[], %s::int[]) AS cell(product, location)
              JOIN product_product ON product_product.id = cell.product
              JOIN stock_location ON stock_location.id = cell.location
             ORDER BY cell.product, cell.location
            """,
            ([product for product, _ in cells], [location for _, location in cells]),
        )

    @api.model
    def _ezy_purge(self, days=RETENTION_DAYS):
        """The daily cron: the rows older than ``days`` days go, the rest stay."""
        before = fields.Datetime.now() - timedelta(days=days)
        self.sudo().search([("instant", "<", before)]).unlink()
