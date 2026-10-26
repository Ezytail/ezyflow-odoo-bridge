# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The bridge help page in the person's language (ADR 0031).

Odoo renders a module's description from ``static/description/index.html``,
one fixed path with no language lookup (both series). For the bridge's own
module row, and no other, the description is read from the sibling file named
after the base language of the person's language when it exists
(``index.fr.html`` for fr_FR, fr_BE, fr_CH, fr_CA), through the same
sanitiser; every other case, including English, is Odoo's own compute.
"""

import lxml.html

from odoo import fields, models, tools

MODULE = "ezyflow_bridge"
PAGES = "static/description"


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    # Odoo's field carries no context dependency: the first language rendered
    # would be served to every later one from the cache.
    description_html = fields.Html(depends_context=("lang",))

    def _get_desc(self):
        page = self._ezy_help_page_path(self.env.lang)
        served = self.browse()
        if page is not None:
            served = self.filtered(lambda module: module.name == MODULE)
            with tools.file_open(page, "rb") as file:
                document = lxml.html.document_fromstring(file.read().decode())
            # The page carries no image (ADR 0030), so Odoo's image rewrite is
            # not replicated; the sanitiser is the same one Odoo applies.
            served.description_html = tools.html_sanitize(
                lxml.html.tostring(document, encoding="unicode")
            )
        return super(IrModuleModule, self - served)._get_desc()

    @staticmethod
    def _ezy_help_page_path(lang):
        """The translated page for ``lang``, or None when English is the page."""
        base = (lang or "en_US").split("_", 1)[0].lower()
        if base == "en":
            return None
        try:
            return tools.file_path(f"{MODULE}/{PAGES}/index.{base}.html")
        except FileNotFoundError:
            return None
