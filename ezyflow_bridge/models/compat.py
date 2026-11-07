# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
"""The Python APIs that differ below Odoo 17 (ADR 0015, ADR 0035), in one
place so the models are written to the 17-and-later API on every series:

- ``env._`` (the translation call) exists from 17. On 16 this module gives
  the environment the same method, built on 16's own code translations and
  the caller's module, so a model's ``self.env._(...)`` reads the same and
  Odoo's term extraction sees the same calls on every series.
- ``has_access`` and ``check_access`` exist from 18; below, the two checks
  of 16 and 17 answer (``has_read_access``, ``check_read_access``).
"""
import inspect

from odoo import api, modules
from odoo.exceptions import AccessError
from odoo.tools import translate as odoo_translate


def _env_translate(env, source, *args, **kwargs):
    """Odoo 16's ``_`` with the language of the environment and the module of
    the calling file, formatted like 17's ``env._``."""
    lang = env.lang or env.user.lang
    text = source
    if lang and lang != "en_US":
        try:
            caller = inspect.currentframe().f_back
            path_info = modules.get_resource_from_path(inspect.getfile(caller))
            module = path_info[0] if path_info else "base"
            text = odoo_translate.code_translations.get_python_translations(module, lang).get(
                source, source
            )
        except Exception:  # noqa: BLE001 — a failed lookup reads in English, as core's does
            text = source
    if args:
        return text % args
    if kwargs:
        return text % kwargs
    return text


if not hasattr(api.Environment, "_"):
    api.Environment._ = _env_translate


def has_read_access(records):
    """``has_access("read")`` from 18. Below, the model's right, then what a
    search answers: on 16 a variant carries no record rule of its own (the
    company rule sits on its template), so ``check_access_rule`` passes
    where a search, which applies the template's rule, finds nothing."""
    if hasattr(records, "has_access"):
        return records.has_access("read")
    try:
        records.check_access_rights("read")
        records.check_access_rule("read")
    except AccessError:
        return False
    return len(records.search([("id", "in", records.ids)])) == len(records)


def check_read_access(records):
    """``check_access("read")`` from 18; the two checks of 16 and 17 (each raises)."""
    if hasattr(records, "check_access"):
        records.check_access("read")
        return
    records.check_access_rights("read")
    records.check_access_rule("read")
