"""Internationalization module for Kharkiv Metro."""

from collections.abc import Callable
from functools import lru_cache
from importlib import resources

import toml

from .data_loader import load_metro_data

Language = str

DEFAULT_LANGUAGE: Language = "ua"

_TRANSLATIONS_CACHE: dict[Language, dict[str, str]] = {}


@lru_cache(maxsize=1)
def get_available_languages() -> list[Language]:
    languages: set[Language] = set()
    try:
        package = resources.files("kharkiv_metro_core.translations")
    except (ModuleNotFoundError, FileNotFoundError):
        package = None

    if package is not None:
        for entry in package.iterdir():
            name = entry.name
            if name.endswith(".toml"):
                languages.add(name.removesuffix(".toml"))

    languages.add(DEFAULT_LANGUAGE)
    return sorted(languages)


def _load_translations(lang: Language) -> dict[str, str]:
    if lang in _TRANSLATIONS_CACHE:
        return _TRANSLATIONS_CACHE[lang]

    try:
        path = resources.files("kharkiv_metro_core.translations").joinpath(f"{lang}.toml")
        data = path.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        _TRANSLATIONS_CACHE[lang] = {}
        return _TRANSLATIONS_CACHE[lang]

    translations = toml.loads(data)
    _TRANSLATIONS_CACHE[lang] = translations
    return translations


def _get_line_meta_value(line_meta: dict[str, str], lang: Language, field: str) -> str:
    value = line_meta.get(f"{field}_{lang}")
    if value:
        return value
    fallback = line_meta.get(f"{field}_{DEFAULT_LANGUAGE}")
    if fallback:
        return fallback
    return line_meta.get(field, "")


LINE_META: dict[str, dict[str, str]] = load_metro_data().line_meta
INTERNAL_LINE_NAME_TO_KEY: dict[str, str] = {meta["name_ua"]: key for key, meta in LINE_META.items()}


def get_text(key: str, lang: Language = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Get translated text by key.

    Args:
        key: Translation key
        lang: Language code
        **kwargs: Format string arguments

    Returns:
        Translated text
    """
    text = _load_translations(lang).get(key)
    if text is None and lang != DEFAULT_LANGUAGE:
        text = _load_translations(DEFAULT_LANGUAGE).get(key)
    if text is None:
        text = key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def get_line_display_name(line_key: str, lang: Language = DEFAULT_LANGUAGE) -> str:
    """Get display name for a line.

    Args:
        line_key: Internal line key (e.g., 'kholodnohirsko_zavodska')
        lang: Language code

    Returns:
        Display name with emoji
    """
    line_meta = LINE_META.get(line_key)
    if not line_meta:
        return line_key
    display_name = _get_line_meta_value(line_meta, lang, "display")
    return display_name or line_key


def get_line_short_name(line_key: str, lang: Language = DEFAULT_LANGUAGE) -> str:
    """Get short name for a line (without emoji).

    Args:
        line_key: Internal line key
        lang: Language code

    Returns:
        Short display name
    """
    line_meta = LINE_META.get(line_key)
    if not line_meta:
        return line_key
    name = _get_line_meta_value(line_meta, lang, "name")
    return name or line_key


def get_line_display_by_internal(internal_name: str, lang: Language = DEFAULT_LANGUAGE) -> str:
    """Get display name for a line by its internal (Ukrainian) name.

    Args:
        internal_name: Internal line name (e.g., 'Холодногірсько-заводська')
        lang: Language code

    Returns:
        Display name with emoji (e.g., '🔴 Kholodnohirsko-Zavodska')
    """
    line_key = INTERNAL_LINE_NAME_TO_KEY.get(internal_name)
    if not line_key:
        return internal_name
    return get_line_display_name(line_key, lang)


def _build_line_display_to_internal(lang: Language) -> dict[str, str]:
    return {get_line_display_name(line_key, lang): line_key for line_key in LINE_META}


from collections.abc import Callable


def _build_display_maps(
    build_for_lang: Callable[[Language], dict[str, str]],
) -> tuple[dict[Language, dict[str, str]], dict[str, str]]:
    i18n_maps = {lang: build_for_lang(lang) for lang in get_available_languages()}
    combined = {display: internal for mapping in i18n_maps.values() for display, internal in mapping.items()}
    return i18n_maps, combined


@lru_cache(maxsize=1)
def _get_line_display_maps() -> tuple[dict[Language, dict[str, str]], dict[str, str]]:
    return _build_display_maps(_build_line_display_to_internal)


def parse_line_display_name(display_name: str, lang: Language = DEFAULT_LANGUAGE) -> str | None:
    """Parse display line name to internal line name or line key.

    Args:
        display_name: Display name with emoji (e.g., "🔴 Холодногірсько-Заводська")
        lang: Language code

    Returns:
        Internal line name or line key, or None if not found
    """
    i18n_maps, combined = _get_line_display_maps()
    internal_name = i18n_maps.get(lang, {}).get(display_name)
    if internal_name:
        return internal_name
    if lang != DEFAULT_LANGUAGE:
        internal_name = i18n_maps.get(DEFAULT_LANGUAGE, {}).get(display_name)
    if internal_name:
        return internal_name
    line_key = INTERNAL_LINE_NAME_TO_KEY.get(display_name)
    return line_key or combined.get(display_name)


# Day type reverse mapping
DAY_TYPE_META: dict[str, dict[str, str]] = load_metro_data().day_types


def _build_day_type_display_to_internal(lang: Language) -> dict[str, str]:
    lang_map: dict[str, str] = {}
    for key, meta in DAY_TYPE_META.items():
        name = meta.get(f"name_{lang}") or meta.get(f"name_{DEFAULT_LANGUAGE}") or meta.get("name")
        if not name:
            continue
        lang_map[f"{meta['emoji']} {name}"] = key
    return lang_map


@lru_cache(maxsize=1)
def _get_day_type_display_maps() -> tuple[dict[Language, dict[str, str]], dict[str, str]]:
    return _build_display_maps(_build_day_type_display_to_internal)


def parse_day_type_display(display_name: str, lang: Language = DEFAULT_LANGUAGE) -> str | None:
    """Parse display day type to internal value.

    Args:
        display_name: Display day type (e.g., "📅 Будні")
        lang: Language code

    Returns:
        Internal day type ("weekday" or "weekend") or None
    """
    i18n_maps, combined = _get_day_type_display_maps()
    value = i18n_maps.get(lang, {}).get(display_name)
    if value:
        return value
    if lang != DEFAULT_LANGUAGE:
        value = i18n_maps.get(DEFAULT_LANGUAGE, {}).get(display_name)
        if value:
            return value
    return combined.get(display_name)


def get_line_display_to_internal(lang: Language | None = None) -> dict[str, str]:
    i18n_maps, combined = _get_line_display_maps()
    if lang is None:
        return combined
    return dict(i18n_maps.get(lang, {}))


def get_day_type_display_to_internal(lang: Language | None = None) -> dict[str, str]:
    i18n_maps, combined = _get_day_type_display_maps()
    if lang is None:
        return combined
    return dict(i18n_maps.get(lang, {}))


def get_translations(lang: Language | None = None) -> dict[Language, dict[str, str]] | dict[str, str]:
    if lang is None:
        return {language: _load_translations(language) for language in get_available_languages()}
    return dict(_load_translations(lang))
