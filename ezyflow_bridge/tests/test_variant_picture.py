# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
import base64
import io
import os
from unittest.mock import patch

from PIL import Image

from odoo.tests import tagged
from odoo.tools.image import image_apply_opt

from ..models import picture
from ..models.compat import binary_content
from .common import EzyflowBridgeCase

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"


def _image(output_format, size=(64, 64), color=(200, 30, 30), noise=False, **params):
    image = Image.new("RGB", size, color)
    if noise:
        image = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
    stream = io.BytesIO()
    image.save(stream, format=output_format, **params)
    return stream.getvalue()


def _field(raw):
    return base64.b64encode(raw).decode()


@tagged("post_install", "-at_install")
class TestVariantPicture(EzyflowBridgeCase):
    """The picture the connector publishes for a variant (CONTEXT.md,
    "Variant picture"): the 256-pixel rendition Odoo shows, the variant's own
    image else its template's, as a JPEG or a PNG of at most 256 KB, or
    withheld when Odoo cannot bring it there. The same on every series
    (ADR 0015)."""

    def _template(self, **values):
        return self.env["product.template"].create(
            {"name": "Pictured good", **self.storable(), "sale_ok": False, **values}
        )

    def _published(self, variant):
        variant.invalidate_recordset(["ezy_picture", "ezy_picture_withheld"])
        return binary_content(variant.ezy_picture), variant.ezy_picture_withheld

    def test_a_variant_and_a_template_without_a_picture_publish_an_empty_one(self):
        content, withheld = self._published(self._template().product_variant_id)

        self.assertEqual(content, b"")
        self.assertFalse(withheld, "no picture is stated as none, not withheld")

    def test_the_template_picture_is_published_when_the_variant_has_none(self):
        variant = self._template(image_1920=_field(_image("PNG"))).product_variant_id

        content, withheld = self._published(variant)

        self.assertTrue(content.startswith(_PNG))
        self.assertFalse(withheld)
        self.assertEqual(content, binary_content(variant.product_tmpl_id.image_256))

    def test_the_variant_own_picture_wins_over_the_template(self):
        template = self._template(image_1920=_field(_image("PNG")))
        variant = template.product_variant_id
        variant.write({"image_variant_1920": _field(_image("JPEG", color=(10, 10, 200)))})

        content, withheld = self._published(variant)

        self.assertTrue(content.startswith(_JPEG), "the variant's JPEG, not the template's PNG")
        self.assertFalse(withheld)

    def test_a_webp_is_published_as_a_png_or_a_jpeg_within_256_pixels(self):
        variant = self._template(
            image_1920=_field(_image("WEBP", size=(600, 400)))
        ).product_variant_id

        content, withheld = self._published(variant)

        self.assertFalse(withheld)
        self.assertTrue(content.startswith((_PNG, _JPEG)))
        self.assertLessEqual(max(Image.open(io.BytesIO(content)).size), 256)

    def test_a_gif_is_published_as_a_png_or_a_jpeg(self):
        variant = self._template(image_1920=_field(_image("GIF"))).product_variant_id

        content, withheld = self._published(variant)

        self.assertFalse(withheld)
        self.assertTrue(content.startswith((_PNG, _JPEG)))

    def test_a_picture_odoo_cannot_read_is_withheld(self):
        content, withheld = picture.publishable_picture(
            b'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"/>'
        )

        self.assertEqual(content, b"")
        self.assertTrue(withheld, "withheld, never stated as no picture")

    def test_a_picture_that_stays_above_the_limit_is_withheld(self):
        raw = _image("WEBP", size=(256, 256), noise=True, lossless=True)
        with patch.object(picture, "PICTURE_LIMIT", 1024):
            content, withheld = picture.publishable_picture(raw)

        self.assertEqual(content, b"")
        self.assertTrue(withheld)

    def test_a_picture_above_odoos_resolution_limit_is_withheld_without_decoding(self):
        raw = _image("WEBP", size=(64, 64))
        with patch.object(picture, "IMAGE_MAX_RESOLUTION", 64 * 64 - 1):
            content, withheld = picture.publishable_picture(raw)

        self.assertEqual(content, b"")
        self.assertTrue(withheld)

    def test_the_fields_are_read_by_the_connector_group_only(self):
        for name in ("ezy_picture", "ezy_picture_withheld"):
            with self.subTest(field=name):
                self.assertEqual(
                    self.env["product.product"]._fields[name].groups,
                    "ezyflow_bridge.group_ezyflow_connector",
                )

    def test_a_png_above_the_limit_is_brought_under_it_as_a_jpeg(self):
        raw = _image("PNG", size=(256, 256), noise=True)
        # Noise compresses poorly as a PNG and well enough as a JPEG.
        limit = len(image_apply_opt(Image.open(io.BytesIO(raw)), "JPEG", quality=85))
        with patch.object(picture, "PICTURE_LIMIT", limit):
            content, withheld = picture.publishable_picture(raw)

        self.assertFalse(withheld)
        self.assertTrue(content.startswith(_JPEG))
        self.assertLessEqual(len(content), limit)

    def test_a_template_picture_change_moves_the_variant_write_date(self):
        # The product source pages the variants on their write date: 17 and
        # later move it from the template's, the bridge does on 16.
        template = self._template()
        variant = template.product_variant_id
        self.env.cr.execute(
            "UPDATE product_product SET write_date = '2000-01-01' WHERE id = %s", (variant.id,)
        )
        variant.invalidate_recordset(["write_date"])

        template.write({"image_1920": _field(_image("PNG"))})
        self.env.flush_all()
        variant.invalidate_recordset(["write_date"])

        self.assertGreater(variant.write_date.year, 2000)

    def test_a_variant_picture_change_moves_the_variant_write_date(self):
        template = self._template()
        variant = template.product_variant_id
        self.env.cr.execute(
            "UPDATE product_product SET write_date = '2000-01-01' WHERE id = %s", (variant.id,)
        )
        variant.invalidate_recordset(["write_date"])

        variant.write({"image_variant_1920": _field(_image("PNG"))})
        self.env.flush_all()
        variant.invalidate_recordset(["write_date"])

        self.assertGreater(variant.write_date.year, 2000)
