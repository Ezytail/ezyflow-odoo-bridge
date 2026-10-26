# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .contract import CHANNELS, LOGISTICS_MODES
from .wms_constraints import (
    PICKING_NAME_ALPHABET,
    PICKING_NAME_LIMIT,
    PICKING_NAME_PATTERN,
    binds,
)

# The operation types whose transfers reach the WMS under their own name.
OFFERED_CODES = ("incoming", "outgoing")

# The fields of an operation type that decide whether, and under which name, its
# next transfer reaches the WMS.
PICKING_NAME_FIELDS = frozenset(
    ("ezy_logistics_mode", "code", "sequence_id", "sequence_code", "company_id")
)


class StockPickingType(models.Model):
    """The per-warehouse switch (ADR 0002): whether an operation type offers its
    pickings to the WMS, and for which channels."""

    _inherit = "stock.picking.type"

    ezy_logistics_mode = fields.Selection(
        LOGISTICS_MODES,
        string="Logistics mode",
        default="off",
        required=True,
        help="Whether the transfers of this operation type are offered to the WMS: "
        "never, as soon as they are reserved, or only when a person marks them "
        "ready for logistics. Internal transfers are never offered.",
    )
    ezy_channels = fields.Char(
        string="Channel allow-list",
        help="Comma-separated channel codes (WEB, PRO, MARKETPLACE, DISTRIBUTEUR, "
        "REASSORT, SPECIAL) this operation type may offer to the WMS. Empty: every "
        "channel. A transfer whose channel is not listed stays in Odoo.",
    )

    @api.constrains("ezy_channels")
    def _check_ezy_channels(self):
        known = {code for code, _label in CHANNELS}
        for picking_type in self:
            allow_list = picking_type._ezy_channel_allow_list()
            unknown = [code for code in allow_list if code not in known]
            if unknown:
                raise ValidationError(
                    self.env._(
                        "Unknown channel %(codes)s in the allow-list of %(name)s. "
                        "Known channels: %(known)s.",
                        codes=", ".join(unknown),
                        name=picking_type.display_name,
                        known=", ".join(code for code, _label in CHANNELS),
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        picking_types = super().create(vals_list)
        picking_types._check_ezy_picking_name()
        return picking_types

    def write(self, vals):
        # Behaviour 8 (ADR 0017): checked when a field that decides the next
        # reference is written, like every other figure. Core stock rewrites the
        # sequence prefix inside its own write when the sequence code changes, so
        # the check runs once the whole write is done; a prefix edited on the
        # sequence itself is checked by ir.sequence.
        result = super().write(vals)
        if PICKING_NAME_FIELDS.intersection(vals):
            self._check_ezy_picking_name()
        return result

    def _check_ezy_picking_name(self):
        """Refuse a receipt or delivery type in logistics mode whose sequence would
        give the next transfer a name Reflex refuses: longer than 20 characters
        or outside its alphabet. The example in the message is that next name."""
        for picking_type in self:
            if (
                picking_type.ezy_logistics_mode == "off"
                or picking_type.code not in OFFERED_CODES
                or not picking_type.sequence_id
                or not binds(self.env, picking_type.company_id, "ezy_wms_picking_name")
            ):
                continue
            example = picking_type._ezy_next_picking_name()
            if len(example) > PICKING_NAME_LIMIT or not PICKING_NAME_PATTERN.fullmatch(example):
                raise ValidationError(
                    self.env._(
                        "%(field)s of %(name)s would give its next transfer the reference "
                        "%(example)s; the WMS accepts at most %(limit)s characters of "
                        "%(alphabet)s. Shorten the sequence prefix or turn the logistics "
                        "mode off.",
                        field=picking_type._fields["sequence_id"].get_description(self.env)[
                            "string"
                        ],
                        name=picking_type.display_name,
                        example=example,
                        limit=PICKING_NAME_LIMIT,
                        alphabet=PICKING_NAME_ALPHABET,
                    )
                )

    def _ezy_next_picking_name(self):
        """The name the sequence would give the next transfer, without drawing it."""
        self.ensure_one()
        sequence = self.sequence_id.sudo()
        return sequence.get_next_char(sequence.number_next_actual)

    def _ezy_channel_allow_list(self):
        """The allow-list as a list of codes; empty when every channel is allowed."""
        self.ensure_one()
        codes = (self.ezy_channels or "").split(",")
        return [code.strip().upper() for code in codes if code.strip()]

    def _ezy_offers_channel(self, channel):
        """Whether a transfer of this channel may be offered (behaviour 1)."""
        self.ensure_one()
        allowed = self._ezy_channel_allow_list()
        return not allowed or channel in allowed
