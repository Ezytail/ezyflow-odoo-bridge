# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .contract import CHANNELS

# Field, limit: what the WMS accepts for an address (behaviour 8).
PARTNER_LIMITS = (("name", 50), ("street", 35), ("street2", 35))


class ResPartner(models.Model):
    _inherit = "res.partner"

    ezy_channel = fields.Selection(
        CHANNELS,
        string="Channel",
        help="The sales channel this partner buys through; copied to its sales "
        "orders and their transfers.",
    )
    ezy_relay_code = fields.Char(
        string="Relay code",
        index="btree_not_null",
        help="Set when this partner is a relay point: the code the carrier knows "
        "it by. A relay point is the shipping address of a relay order.",
    )
    ezy_relay_carrier_id = fields.Many2one(
        "delivery.carrier",
        string="Relay carrier",
        ondelete="set null",
        help="The carrier this relay point belongs to.",
    )

    @api.constrains("name", "street", "street2")
    def _check_ezy_lengths(self):
        for partner in self:
            company = partner.company_id or self.env.company
            if not company.ezy_check_partner_constraints:
                continue
            for field_name, limit in PARTNER_LIMITS:
                value = partner[field_name]
                if value and len(value) > limit:
                    raise ValidationError(
                        self.env._(
                            "%(field)s of %(partner)s is longer than %(limit)s characters, "
                            "the most the WMS accepts.",
                            field=partner._fields[field_name].get_description(self.env)["string"],
                            partner=partner.display_name,
                            limit=limit,
                        )
                    )
