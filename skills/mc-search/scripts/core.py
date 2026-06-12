#!/usr/bin/env python3
"""mc-search facade — 保持向后兼容，所有实现已迁移到子模块"""

from pathlib import Path

from scripts._http import (
    SearchError,
    curl,
    _clean_html_text,
    MIN_HTML_LEN,
    MIN_HTML_LEN_ITEM,
    _DEFAULT_RESULTS_PER_PLATFORM,
    FUZZY_MATCH_THRESHOLD,
    FUZZY_MIN_LEN,
    logger,
    set_platform_enabled,
)
from scripts._mcmod_parse import _parse_mcmod_mod_result
from scripts._mcmod_search import (
    search_mcmod,
    search_mcmod_author,
    search_mcmod_modpack,
    _extract_search_result_metadata,
    _parse_mcmod_search_results,
)
from scripts._modrinth import (
    search_modrinth,
    search_modrinth_author,
    fetch_mod_info,
    get_mod_dependencies,
)
from scripts._wiki import search_wiki, search_wiki_zh, read_wiki, read_wiki_zh
from scripts._fuse import search_all

__all__ = [
    "search_all",
    "search_mcmod",
    "search_mcmod_author",
    "search_mcmod_modpack",
    "search_modrinth",
    "search_modrinth_author",
    "search_wiki",
    "search_wiki_zh",
    "read_wiki",
    "read_wiki_zh",
    "fetch_mod_info",
    "get_mod_dependencies",
    "set_platform_enabled",
    "SearchError",
    "curl",
    "_clean_html_text",
    "MIN_HTML_LEN",
    "MIN_HTML_LEN_ITEM",
    "_DEFAULT_RESULTS_PER_PLATFORM",
    "FUZZY_MATCH_THRESHOLD",
    "FUZZY_MIN_LEN",
    "logger",
    "Path",
    "_parse_mcmod_mod_result",
    "_extract_search_result_metadata",
    "_parse_mcmod_search_results",
]
