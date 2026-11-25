# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import base64

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .compat import binary_content, has_read_access
from .picture import publishable_picture
from .wms_constraints import (
    BARCODE_LIMIT,
    BARCODE_PATTERN,
    DEFAULT_CODE_ALPHABET,
    DEFAULT_CODE_LIMIT,
    DEFAULT_CODE_PATTERN,
    binds,
    deferred,
    sku_key,
)


class ProductProduct(models.Model):
    """The variant half of the product WMS constraints (behaviour 8, ADR 0017):
    Reflex identifies a product by its internal reference, at most 16
    characters of its SKU alphabet held by one active product, and scans the
    barcode when there is one (Odoo itself keeps a barcode to one product).
    Each figure is checked when its own field is written, so a record already
    above a tightened figure is refused only when a person next writes that
    field. A template being created checks its variants once it is complete;
    the deferral key skips the checks of a write in which Odoo generates a
    variant without identity, and the next write runs them."""

    _inherit = "product.product"

    ezy_shop_variant_id = fields.Char(
        string="Shop variant id",
        index="btree_not_null",
        copy=False,
        help="The id this variant has in the web shop. The connector uses it to find the "
        "Odoo record before falling back to the internal reference. One shop per Odoo product.",
    )
    # What two SKUs are compared by (CONTEXT.md, "SKU"): the duplicate check
    # below and the connector's SKU lookups match on it exactly, through the
    # index, instead of scanning the table with ILIKE.
    ezy_sku_key = fields.Char(
        string="SKU key",
        compute="_compute_ezy_sku_key",
        store=True,
        index="btree_not_null",
        help="The internal reference trimmed, its letters a-z upper-cased: what the WMS "
        "and the connector compare SKUs by.",
    )

    # The picture the connector publishes for the variant (CONTEXT.md, "Variant
    # picture"): computed on each read, never stored, so it follows the images
    # Odoo holds without a copy of its own. The connector group alone reads it:
    # a read of every field by anyone else (an export, another integration)
    # does not run the conversion.
    ezy_picture = fields.Binary(
        string="Published picture",
        compute="_compute_ezy_picture",
        attachment=False,
        groups="ezyflow_bridge.group_ezyflow_connector",
        help="The picture the connector publishes for this variant: its own image, else its "
        "product's, at 256 pixels, as a JPEG or a PNG of at most 256 KB.",
    )
    ezy_picture_withheld = fields.Boolean(
        string="Picture withheld",
        compute="_compute_ezy_picture",
        groups="ezyflow_bridge.group_ezyflow_connector",
        help="This variant has a picture the connector cannot publish: Odoo cannot convert it "
        "to a JPEG or a PNG of at most 256 KB. The warehouse and the shops keep the picture they "
        "last received.",
    )

    @api.depends("default_code")
    def _compute_ezy_sku_key(self):
        for product in self:
            product.ezy_sku_key = sku_key(product.default_code)

    @api.depends("image_variant_256", "product_tmpl_id.image_256")
    def _compute_ezy_picture(self):
        # image_256 is Odoo's rendition: the variant's own image, else its
        # template's, on every series. bin_size would give its size instead.
        for product in self:
            content, withheld = publishable_picture(
                binary_content(product.with_context(bin_size=False).image_256)
            )
            product.ezy_picture = base64.b64encode(content).decode() if content else False
            product.ezy_picture_withheld = withheld

    # The shape of a reference is judged before whether another product holds it.
    @api.constrains("default_code")
    def _check_ezy_default_code(self):
        if deferred(self.env):
            return
        for product in self:
            product._ezy_check_default_code()
            product._ezy_check_default_code_unique()

    # An unarchived product takes its reference back. The template's company is
    # checked from the template: a variant write of company_id lands there
    # through the delegation.
    @api.constrains("active")
    def _check_ezy_active_default_code(self):
        if deferred(self.env):
            return
        for product in self:
            product._ezy_check_default_code_unique()

    # name and product_tmpl_id are always in the creation values, so the check
    # runs for a variant created without a reference at all.
    @api.constrains("name", "product_tmpl_id", "default_code", "sale_ok", "type")
    def _check_ezy_default_code_required(self):
        if deferred(self.env):
            return
        for product in self:
            product._ezy_check_default_code_required()

    @api.constrains("barcode")
    def _check_ezy_barcode(self):
        if deferred(self.env):
            return
        for product in self:
            product._ezy_check_barcode()

    def _ezy_check_identity(self):
        """Every variant constraint at once: the end of a template create."""
        for product in self:
            product._ezy_check_default_code()
            product._ezy_check_default_code_unique()
            product._ezy_check_default_code_required()
            product._ezy_check_barcode()

    def _ezy_company(self):
        return self.product_tmpl_id.company_id or self.env.company

    def _ezy_check_default_code(self):
        self.ensure_one()
        code = self.default_code
        if not code:
            return
        company = self._ezy_company()
        if len(code) > DEFAULT_CODE_LIMIT and binds(
            self.env, company, "ezy_wms_default_code_length"
        ):
            raise ValidationError(self._ezy_too_long("default_code", DEFAULT_CODE_LIMIT))
        if not DEFAULT_CODE_PATTERN.fullmatch(code) and binds(
            self.env, company, "ezy_wms_default_code_alphabet"
        ):
            raise ValidationError(
                self.env._(
                    "%(field)s of %(product)s, %(value)s, has a character the WMS "
                    "refuses: only %(alphabet)s are accepted.",
                    field=self._ezy_label("default_code"),
                    product=self.display_name,
                    value=code,
                    alphabet=DEFAULT_CODE_ALPHABET,
                )
            )

    def _ezy_check_default_code_unique(self):
        """One active product per SKU within the company and the products it
        shares with every company, compared without regard to case: Reflex
        keeps one article per SKU and merges what it is sent twice. Archived
        products do not count, so a replacement can take an archived SKU."""
        self.ensure_one()
        code = self.default_code
        key = sku_key(code)
        if not key or not self.active:
            return
        if not binds(self.env, self._ezy_company(), "ezy_wms_default_code_unique"):
            return
        domain = [
            ("ezy_sku_key", "=", key),
            ("id", "!=", self.id),
            ("active", "=", True),
        ]
        if self.product_tmpl_id.company_id:
            domain.append(("company_id", "in", (False, self.product_tmpl_id.company_id.id)))
        holder = self.sudo().search(domain, order="id", limit=1)
        if not holder:
            return
        # The search sees every company; the message names the holder only to
        # a writer allowed to read it (a product shared by every company is
        # checked against the products of each company). Odoo may run the
        # constraint as superuser, so the writer's rights are asked for.
        if has_read_access(holder.with_user(self.env.user)):
            holder_name = holder.display_name
        else:
            holder_name = self.env._("a product of another company")
        raise ValidationError(
            self.env._(
                "%(field)s %(value)s of %(product)s is already used by %(holder)s; "
                "the WMS keeps one product per reference.",
                field=self._ezy_label("default_code"),
                value=code,
                product=self.display_name,
                holder=holder_name,
            )
        )

    def _ezy_check_default_code_required(self):
        self.ensure_one()
        if (
            not self.default_code
            and self.product_tmpl_id._ezy_is_sellable_goods()
            and binds(self.env, self._ezy_company(), "ezy_wms_default_code_required")
        ):
            raise ValidationError(
                self.env._(
                    "%(product)s is sold as goods and has no internal reference; "
                    "the WMS identifies products by it (%(field)s is required).",
                    product=self.display_name,
                    field=self._ezy_label("default_code"),
                )
            )

    def _ezy_check_barcode(self):
        self.ensure_one()
        barcode = self.barcode
        if not barcode:
            return
        company = self._ezy_company()
        if len(barcode) > BARCODE_LIMIT and binds(self.env, company, "ezy_wms_barcode_length"):
            raise ValidationError(self._ezy_too_long("barcode", BARCODE_LIMIT))
        if not BARCODE_PATTERN.fullmatch(barcode) and binds(
            self.env, company, "ezy_wms_barcode_alphabet"
        ):
            raise ValidationError(
                self.env._(
                    "%(field)s of %(product)s, %(value)s, has a character the WMS "
                    "refuses: only letters and digits are accepted.",
                    field=self._ezy_label("barcode"),
                    product=self.display_name,
                    value=barcode,
                )
            )

    def _ezy_label(self, field_name):
        return self._fields[field_name].get_description(self.env)["string"]

    def _ezy_too_long(self, field_name, limit):
        self.ensure_one()
        return self.env._(
            "%(field)s of %(product)s is longer than %(limit)s characters, "
            "the most the WMS accepts.",
            field=self._ezy_label(field_name),
            product=self.display_name,
            limit=limit,
        )
