# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The picture the connector publishes for a variant (CONTEXT.md, "Variant
picture"): Odoo's 256-pixel rendition brought to a JPEG or a PNG of at most
256 KB with Odoo's own image tools. Odoo's rendition is not always one: it
keeps an SVG as uploaded, a GIF as a GIF and, from 18, a WEBP as uploaded at
its full size. Each is converted here, never in the connector."""
import logging

# Odoo registers only the Pillow formats it processes; WEBP, which Odoo keeps
# as uploaded, is Pillow's own plugin and is registered here to be read.
from PIL import WebPImagePlugin  # noqa: F401 pylint: disable=unused-import

from odoo.tools.image import IMAGE_MAX_RESOLUTION, binary_to_image, image_apply_opt

_logger = logging.getLogger(__name__)

# The most decoded bytes a published picture carries (canonical ADR 0007).
PICTURE_LIMIT = 256 * 1024

# The edge of Odoo's rendition the connector publishes.
PICTURE_SIZE = 256

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"

# The modes Pillow writes as a PNG; any other is converted to RGBA first.
_PNG_MODES = ("1", "L", "LA", "P", "RGB", "RGBA")


def publishable_picture(raw):
    """``(content, withheld)`` for the raw bytes of a picture.

    No picture: ``(b"", False)``, the connector states that the variant has
    none. A JPEG or a PNG within the limit: itself. Anything else Odoo can
    read: fitted in 256 pixels, then a PNG, else a JPEG, whichever is first
    within the limit. Nothing Odoo can read, more pixels than Odoo accepts on
    upload, or nothing within the limit: ``(b"", True)``, the connector
    states nothing.
    """
    if not raw:
        return b"", False
    if raw.startswith((_PNG, _JPEG)) and len(raw) <= PICTURE_LIMIT:
        return raw, False
    try:
        # Opened lazily: the size is known before the bitmap is decoded. Odoo
        # refuses above this on upload but keeps a WEBP unchecked from 18; a
        # larger one is withheld rather than decoded whole on every read.
        image = binary_to_image(raw)
        if image.size[0] * image.size[1] > IMAGE_MAX_RESOLUTION:
            _logger.info("a variant picture above %s pixels is withheld", IMAGE_MAX_RESOLUTION)
            return b"", True
        image.thumbnail((PICTURE_SIZE, PICTURE_SIZE))
        if image.mode not in _PNG_MODES:
            image = image.convert("RGBA")
        for output_format, params in (("PNG", {"optimize": True}), ("JPEG", {"quality": 85})):
            content = image_apply_opt(image, output_format, **params)
            if len(content) <= PICTURE_LIMIT:
                return content, False
    except Exception:  # noqa: BLE001 — Pillow raises many kinds; unreadable is withheld
        _logger.info("a variant picture could not be converted to a JPEG or a PNG")
    return b"", True
