# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .contract import CHANNELS
from .wms_constraints import (
    CITY_LIMIT,
    EMAIL_LIMIT,
    PARTNER_NAME_LIMIT,
    PHONE_LIMIT,
    STREET_LIMIT,
    ZIP_LIMIT,
    binds,
)

# Field: figure, switch. What the WMS accepts for an address (behaviour 8).
PARTNER_LIMITS = {
    "name": (PARTNER_NAME_LIMIT, "ezy_wms_partner_name_length"),
    "street": (STREET_LIMIT, "ezy_wms_street_length"),
    "street2": (STREET_LIMIT, "ezy_wms_street_length"),
    "city": (CITY_LIMIT, "ezy_wms_city_length"),
    "zip": (ZIP_LIMIT, "ezy_wms_zip_length"),
    "phone": (PHONE_LIMIT, "ezy_wms_phone_length"),
    "email": (EMAIL_LIMIT, "ezy_wms_email_length"),
}


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

    # Behaviour 8 (ADR 0017): every partner, customer, vendor or address, as a
    # person writes it; the connector user writes what the shop sent. One
    # constraint per field, so a partner already above a tightened figure is
    # refused only when a person next writes that field.
    @api.constrains("name")
    def _check_ezy_name_length(self):
        self._ezy_check_lengths("name")

    @api.constrains("street")
    def _check_ezy_street_length(self):
        self._ezy_check_lengths("street")

    @api.constrains("street2")
    def _check_ezy_street2_length(self):
        self._ezy_check_lengths("street2")

    @api.constrains("city")
    def _check_ezy_city_length(self):
        self._ezy_check_lengths("city")

    @api.constrains("zip")
    def _check_ezy_zip_length(self):
        self._ezy_check_lengths("zip")

    @api.constrains("phone")
    def _check_ezy_phone_length(self):
        self._ezy_check_lengths("phone")

    @api.constrains("email")
    def _check_ezy_email_length(self):
        self._ezy_check_lengths("email")

    def _ezy_check_lengths(self, field_name):
        limit, switch = PARTNER_LIMITS[field_name]
        for partner in self:
            value = partner[field_name]
            company = partner.company_id or self.env.company
            if value and len(value) > limit and binds(self.env, company, switch):
                raise ValidationError(
                    self.env._(
                        "%(field)s of %(partner)s is longer than %(limit)s characters, "
                        "the most the WMS accepts.",
                        field=partner._fields[field_name].get_description(self.env)["string"],
                        partner=partner.display_name,
                        limit=limit,
                    )
                )
