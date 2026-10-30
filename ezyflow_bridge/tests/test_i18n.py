# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import lxml.html

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import html_sanitize
from odoo.tools.misc import file_path
from odoo.tools.translate import PoFileReader, TranslationModuleReader

from .common import EzyflowBridgeCase

MODULE = "ezyflow_bridge"
PO = "ezyflow_bridge/i18n/fr.po"
PAGE_EN = "ezyflow_bridge/static/description/index.html"
PAGE_FR = "ezyflow_bridge/static/description/index.fr.html"


def page_shape(path):
    """The sequence of heading levels and the row count of every table: what
    the two pages must share (ADR 0031); what the words say is the review's."""
    document = lxml.html.parse(file_path(path)).getroot()
    headings = [e.tag for e in document.iter() if e.tag in ("h1", "h2", "h3", "h4")]
    tables = [len(table.xpath(".//tr")) for table in document.iter("table")]
    return headings, tables


def rendered(path):
    with open(file_path(path), encoding="utf-8") as page:
        document = lxml.html.document_fromstring(page.read())
    return html_sanitize(lxml.html.tostring(document, encoding="unicode"))


@tagged("post_install", "-at_install")
class TestI18n(EzyflowBridgeCase):
    """English and French (ADR 0031): every term the module has is in fr.po,
    the screens and the refusals follow the person's language, the help page
    is served in French to a French person and keeps the English page's shape."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = cls.env["ir.module.module"].search([("name", "=", MODULE)])
        for code in ("fr_FR", "fr_BE"):
            cls.env["res.lang"]._activate_lang(code)
        cls.env["ir.module.module"]._load_module_terms([MODULE], ["fr_FR", "fr_BE"])

    # --- completeness: the drift gate ---------------------------------------

    # The module's description is the README, a developer document kept in
    # English (ADR 0031); its short description is the module name, never
    # translated. Odoo 20 alone extracts both.
    ENGLISH_BY_DESIGN = ("ir.module.module,description", "ir.module.module,shortdesc")
    # Terms Odoo owns and renames between series (a core model's name, the
    # module metadata): one series extracts them and the other does not, so a
    # French line for one of them is never stale.
    SERIES_OWNED = ("ir.model,", "ir.module.module,", "res.groups.privilege,")

    def test_every_term_of_the_module_has_a_french_translation(self):
        terms = {
            source
            for _module, _ttype, name, _res_id, source, _value, _comments in (
                TranslationModuleReader(self.env.cr, modules=[MODULE])
            )
            if source and name not in self.ENGLISH_BY_DESIGN
        }
        # The reader merges the pot next to fr.po, so a term left out of fr.po
        # on purpose comes back as an empty entry: skip it by name here too.
        entries = [
            entry
            for entry in PoFileReader(file_path(PO))
            if entry["name"] not in self.ENGLISH_BY_DESIGN
        ]
        translated = {entry["src"] for entry in entries if entry["value"]}
        untranslated = {entry["src"] for entry in entries} - translated

        missing = sorted(terms - translated)
        self.assertFalse(
            missing,
            "terms without a French line in i18n/fr.po (re-export the pot and add them):\n  "
            + "\n  ".join(repr(term) for term in missing),
        )
        self.assertFalse(
            sorted(untranslated),
            "empty translations in i18n/fr.po:\n  "
            + "\n  ".join(repr(term) for term in sorted(untranslated)),
        )
        stale = sorted(
            {
                entry["src"]
                for entry in entries
                if entry["src"] not in terms
                and not entry["name"].startswith(self.SERIES_OWNED)
            }
        )
        self.assertFalse(
            stale,
            "translations in i18n/fr.po for terms the module no longer has:\n  "
            + "\n  ".join(repr(term) for term in stale),
        )

    # --- mechanism -----------------------------------------------------------

    def test_a_french_person_reads_french_labels_and_values(self):
        picking = self.env["stock.picking"]
        fields = picking.with_context(lang="fr_FR").fields_get(["ezy_wms_state"])
        self.assertEqual(fields["ezy_wms_state"]["string"], "État WMS")
        self.assertIn(
            ("ready_for_logistics", "Prêt pour la logistique"),
            fields["ezy_wms_state"]["selection"],
        )

        fields = picking.with_context(lang="en_US").fields_get(["ezy_wms_state"])
        self.assertEqual(fields["ezy_wms_state"]["string"], "WMS state")

    def test_a_refusal_is_raised_in_the_language_of_the_person(self):
        too_long = {"name": "Long reference", "default_code": "REFERENCE-TOO-LONG-1"}
        with self.assertRaises(ValidationError) as french:
            self.env["product.product"].with_user(self.admin_user).with_context(
                lang="fr_FR"
            ).create(too_long)
        self.assertIn("dépasse 16 caractères", str(french.exception))

        with self.assertRaises(ValidationError) as english:
            self.env["product.product"].with_user(self.admin_user).with_context(
                lang="en_US"
            ).create(too_long)
        self.assertIn("is longer than 16 characters", str(english.exception))

    def test_the_rotation_date_type_refusal_is_raised_in_the_language_of_the_person(self):
        selection = self.env["product.template"]._fields["tracking"].get_values(self.env)
        template = self.env["product.template"].create(
            {
                "name": "Untracked good",
                "is_storable": True,
                "sale_ok": False,
                "tracking": "none" if "none" in selection else False,
            }
        )
        for lang, expected in (
            ("fr_FR", "Untracked good n'est suivi ni par lots ni par numéros de série"),
            ("en_US", "Untracked good is not tracked by lots or by serial numbers"),
        ):
            with self.assertRaises(ValidationError) as refused:
                template.with_user(self.admin_user).with_context(lang=lang).write(
                    {"ezy_rotation_date_type": "use_by"}
                )
            self.assertIn(expected, str(refused.exception))

    def test_the_help_page_follows_the_language_for_the_bridge_row_only(self):
        self.assertEqual(len(self.module), 1)
        module = self.module

        self.assertEqual(module.with_context(lang="en_US").description_html, rendered(PAGE_EN))
        self.assertEqual(module.with_context(lang="fr_FR").description_html, rendered(PAGE_FR))
        # Every French variant reads the French page (Odoo's base-language fallback).
        self.assertEqual(module.with_context(lang="fr_BE").description_html, rendered(PAGE_FR))
        self.assertNotEqual(rendered(PAGE_EN), rendered(PAGE_FR))

        stock = self.env["ir.module.module"].search([("name", "=", "stock")])
        self.assertEqual(
            stock.with_context(lang="fr_FR").description_html,
            stock.with_context(lang="en_US").description_html,
        )

    # --- parity: the second drift gate ---------------------------------------

    def test_the_two_help_pages_have_the_same_shape(self):
        headings_en, tables_en = page_shape(PAGE_EN)
        headings_fr, tables_fr = page_shape(PAGE_FR)
        self.assertTrue(headings_en)
        self.assertEqual(headings_fr, headings_en)
        self.assertEqual(tables_fr, tables_en)
