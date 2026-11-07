# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import api, models

from ..hooks import switches_off


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model_create_multi
    def create(self, vals_list):
        # A company created on a glued database starts with the bridge's WMS
        # constraint switches off, as the install left the others (hooks.py).
        companies = super().create(vals_list)
        switches_off(companies.sudo())
        return companies
