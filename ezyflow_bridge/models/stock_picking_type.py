# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .contract import CHANNELS, LOGISTICS_MODES


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
