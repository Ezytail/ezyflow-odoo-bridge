# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo.tests import tagged

from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestCompanyPartner(EzyflowBridgeCase):
    """The marker the connector sets on a partner it creates as the company of a
    shop address (CONTEXT.md, "Company partner"): what it meant on every series,
    Odoo 20 computing Is a Company from the VAT number."""

    def _company(self):
        return (
            self.env["res.partner"]
            .with_user(self.connector_user)
            .create(
                {
                    "name": "Recette Ketra SARL",
                    "is_company": True,
                    "ezy_company_partner": True,
                    "street": "10 rue de Rivoli",
                    "child_ids": [
                        (0, 0, {"name": "Alice Martin", "type": "delivery"}),
                    ],
                }
            )
        )

    def test_the_connector_marks_the_company_partner_it_creates(self):
        company = self._company()

        self.assertTrue(company.ezy_company_partner)
        found = self.env["res.partner"].search(
            [
                ("ezy_company_partner", "=", True),
                ("parent_id", "=", False),
                ("name", "=ilike", "recette ketra sarl"),
            ]
        )
        self.assertEqual(found, company)

    def test_its_address_is_not_marked_and_names_it_as_commercial_partner(self):
        child = self._company().child_ids

        self.assertFalse(child.ezy_company_partner)
        self.assertEqual(child.commercial_partner_id, child.parent_id)

    def test_a_partner_is_not_marked_by_default(self):
        self.assertFalse(self.customer.ezy_company_partner)
