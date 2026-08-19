"""Minimal i18n: plain-dict string catalogs selected at runtime.

No gettext/.mo compilation here on purpose - this project stays
stdlib-only with no build step (see CLAUDE.md), and gettext's usual
workflow needs an external `msgfmt` binary to compile .po -> .mo. A
catalog is just a `STRINGS: dict[str, str]` module under
`aws_sso_sync/i18n/catalog/`; `t(key, **kwargs)` looks up `key` in the
active language, falls back to `DEFAULT_LANGUAGE`, and finally falls back
to the key itself so a missing translation degrades to something visible
rather than crashing.

To add a language, see CONTRIBUTING.md's "Adding a language" section.
"""

from __future__ import annotations

import logging

from .catalog import en, es

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "en"

CATALOGS: dict[str, dict[str, str]] = {
    "en": en.STRINGS,
    "es": es.STRINGS,
}

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Español",
}

_current_language = DEFAULT_LANGUAGE


def available_languages() -> list[str]:
    return list(CATALOGS)


def set_language(lang: str) -> None:
    global _current_language
    if lang not in CATALOGS:
        logger.debug("Idioma desconocido %r, usando %r", lang, DEFAULT_LANGUAGE)
        lang = DEFAULT_LANGUAGE
    _current_language = lang


def get_language() -> str:
    return _current_language


def t(key: str, **kwargs: object) -> str:
    template = CATALOGS[_current_language].get(key)
    if template is None:
        template = CATALOGS[DEFAULT_LANGUAGE].get(key)
        logger.debug("Falta la clave i18n %r en %r, usando %r", key, _current_language, DEFAULT_LANGUAGE)
    if template is None:
        logger.debug("Falta la clave i18n %r en todos los catálogos", key)
        template = key
    return template.format(**kwargs) if kwargs else template
