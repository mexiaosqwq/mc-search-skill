#!/usr/bin/env python3
"""mc-search MC百科 搜索入口 — 搜索/作者/整合包 API + 并行抓取"""

import re
import time
import urllib.parse
from concurrent import futures as futures_module

from ._http import (
    logger, SearchError,
    curl, _fetch_json,
    _clean_html_text,
    MIN_HTML_LEN, _MCMOD_FILTER_MOD, _MCMOD_FILTER_ITEM,
    _MCMOD_MODPACK_FILTERS, _MCMOD_COMMON_SKIP_PREFIXES,
    _DEFAULT_RESULTS_PER_PLATFORM, _MAX_FETCH_WORKERS,
    _MCMOD_RETRY_CODES,
    _MAX_SEARCH_DESC_CHARS, _MAX_AUTHOR_SECTION,
    _is_mcmod_blocked, _apply_truncation,
)
from ._mcmod_parse import (
    _parse_mcmod_mod_result,
    _parse_mcmod_item_result,
    _parse_mcmod_modpack_result,
    _build_mcmod_fallback_result,
    _extract_mcmod_external_links,
    _extract_mcmod_author_team,
    _extract_mcmod_community_stats,
)


def _parallel_fetch_with_fallback(items: list, fetch_func: callable, max_workers: int,
                                   filter_none: bool = True, timeout: int = 30) -> list:
    """并行抓取，单条超时/失败不影响其他 item。不做串行降级重试。

    timeout: 每条 fetch 的超时秒数（默认 30s）。单条超时记录警告并跳过。
    """
    if not items:
        return []
    results = []
    with futures_module.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(fetch_func, item): i for i, item in enumerate(items)}
        for f in futures_module.as_completed(futs):
            try:
                results.append(f.result(timeout=timeout))
            except (futures_module.TimeoutError, SearchError, OSError, Exception) as e:
                logger.warning(f"Fetch failed for item {futs[f]}: {e}")
                continue

    if filter_none:
        results = [r for r in results if r is not None]
    return results


def _build_mcmod_search_urls(keyword: str, content_type: str) -> list[str]:
    """构建MC百科搜索URL列表"""
    # filter 映射
    filter_map = {"mod": _MCMOD_FILTER_MOD, "item": _MCMOD_FILTER_ITEM}
    if content_type not in filter_map and content_type != "modpack":
        raise ValueError(f"search_mcmod 不支持的 content_type: {content_type}。仅支持 'mod' / 'item' / 'modpack'")

    q = urllib.parse.quote(keyword)

    # 物品用 /item/ URL，模组用 /class/ URL
    if content_type == "item":
        return [f"https://search.mcmod.cn/s?key={q}&filter={_MCMOD_FILTER_ITEM}"]
    else:
        return [f"https://search.mcmod.cn/s?key={q}&filter={_MCMOD_FILTER_MOD}"]


def _extract_mcmod_search_section(html: str, raise_on_empty: bool = True) -> str | None:
    """从 MC 百科搜索结果页提取 search-result-list 区域（不含 pagination）。

    Args:
        html: 完整页面 HTML
        raise_on_empty: 未找到 search-result-list 时是否抛出异常

    Returns:
        提取的 section 内容（已移除 <em> 标签），未找到时返回 None 或抛出异常
    """
    idx = html.find("search-result-list")
    if idx == -1:
        if raise_on_empty:
            raise SearchError("MC 百科 搜索结果页结构变化（无 search-result-list）")
        return None

    end_idx = html.find('class="pagination"', idx)
    if end_idx == -1:
        end_idx = len(html)
    section = html[idx:end_idx]
    return re.sub(r"<em[^>]*>|</em>", "", section)


def _parse_mcmod_search_results(html: str, content_type: str, keyword: str) -> list[tuple[str, str]]:
    """解析MC百科搜索结果页面，提取URL和名称对"""
    section = _extract_mcmod_search_section(html)  # raise_on_empty=True → 结构变化时直接抛异常
    clean = section

    # 物品用 /item/ URL，模组用 /class/ URL，整合包用 /modpack/ URL
    if content_type == "item":
        pairs = re.findall(
            r'href="(https://www\.mcmod\.cn/item/\d+\.html)">([^<]+)</a>',
            clean,
        )
    elif content_type == "modpack":
        pairs = re.findall(
            r'href="(https://www\.mcmod\.cn/modpack/\d+\.html)">([^<]+)</a>',
            clean,
        )
    else:
        pairs = re.findall(
            r'href="(https://www\.mcmod\.cn/class/\d+\.html)">([^<]+)</a>',
            clean,
        )

    if not pairs:
        raise SearchError(f"MC百科 无结果（{content_type}）：{keyword}")

    # 去重
    seen = set()
    all_pairs = []
    for raw_url, name in pairs:
        name = name.strip()
        if name and raw_url not in seen and not name.startswith("www."):
            seen.add(raw_url)
            all_pairs.append((raw_url, name))

    return all_pairs


def _extract_search_result_metadata(html: str) -> dict[str, dict]:
    """从搜索结果页提取每个结果的描述和分类 ID。
    返回 {url: {"description": "...", "category": N}}。
    """
    section = _extract_mcmod_search_section(html, raise_on_empty=False)
    if section is None:
        return {}

    # 按 result-item 分割
    items = section.split('class="result-item"')
    metadata = {}

    for item in items[1:]:  # 跳过第一个空段
        # 提取 URL
        url_m = re.search(
            r'href="(https://www\.mcmod\.cn/(?:class|item|modpack)/\d+\.html)"',
            item
        )
        if not url_m:
            continue
        url = url_m.group(1)

        # 提取描述（body div）
        body_m = re.search(r'<div class="body">(.*?)</div>', item, re.DOTALL)
        if body_m:
            raw = body_m.group(1)
            raw = _clean_html_text(raw)
            metadata.setdefault(url, {})["description"] = raw[:_MAX_SEARCH_DESC_CHARS]

        # 提取分类 ID（class="c_N" 中的 N）
        cat_m = re.search(r'class="c_(\d+)"', item)
        if cat_m:
            try:
                metadata.setdefault(url, {})["category"] = int(cat_m.group(1))
            except ValueError:
                pass

    return metadata


def _rank_by_name_match(pairs: list[tuple[str, str]], keyword: str) -> list[tuple[str, str]]:
    """按名称匹配度排序。精确匹配→前缀→包含→其余，每层内部保持原始顺序。"""
    keyword_lower = keyword.lower().replace(" ", "")

    def _match_tier(pair):
        name_lower = pair[1].lower().replace(" ", "")
        if name_lower == keyword_lower:
            return 0
        if name_lower.startswith(keyword_lower):
            return 1
        if keyword_lower in name_lower:
            return 2
        return 3

    tiers = {0: [], 1: [], 2: [], 3: []}
    for pair in pairs:
        tiers[_match_tier(pair)].append(pair)

    result = []
    for tier in [0, 1, 2]:
        result.extend(tiers[tier])

    # 兜底：如果 tier 0/1/2 全空（极端退化查询），保留 tier 3 前 3 条
    if not result and tiers.get(3):
        result = tiers[3][:3]

    return result


def _fetch_mcmod_details(limited_pairs: list[tuple[str, str]], content_type: str,
                         search_metadata: dict[str, dict] | None = None) -> list[dict]:
    """并行抓取模组详情页。若被 WAF 拦截，回退到搜索数据构建最小结果。"""
    if not limited_pairs:
        return []

    if search_metadata is None:
        search_metadata = {}

    def _fetch_one(args):
        raw_url, name = args
        page_html = curl(raw_url)

        # 检测 WAF 拦截 → 用搜索数据回退
        if _is_mcmod_blocked(page_html):
            meta = search_metadata.get(raw_url, {})
            return _build_mcmod_fallback_result(raw_url, name, meta, content_type)

        if content_type == "item":
            result = _parse_mcmod_item_result(page_html, raw_url, name)
        elif content_type == "modpack":
            result = _parse_mcmod_modpack_result(page_html, raw_url, name)
        else:
            result = _parse_mcmod_mod_result(page_html, raw_url, name)
        return result

    results = _parallel_fetch_with_fallback(
        limited_pairs, _fetch_one,
        max_workers=min(len(limited_pairs), _MAX_FETCH_WORKERS)
    )
    return results


def search_mcmod(keyword: str, max_results: int = 5, content_type: str = "mod") -> list[dict]:
    """
    MC百科 搜索。

    content_type: "mod" | "item" | "modpack"
      - "mod"     → filter=0  → /class/ 页面（综合排序，主模组更靠前）
      - "item"    → filter=3  → /item/  页面（物品/方块）
      - "modpack" → 使用多 filter 策略搜索整合包
    """
    # 整合包使用专用搜索函数（多 filter 策略）
    if content_type == "modpack":
        return search_mcmod_modpack(keyword, max_results)

    # 1. 构建搜索URL
    urls = _build_mcmod_search_urls(keyword, content_type)

    # 2. 执行搜索
    html = curl(urls[0])
    if not html:
        raise SearchError(f"MC百科 (mcmod.cn) 当前无法访问，可能正在维护。建议使用 --platform modrinth 搜索 Modrinth 或稍后重试。")

    # 3. 解析结果
    all_pairs = _parse_mcmod_search_results(html, content_type, keyword)
    search_metadata = _extract_search_result_metadata(html)

    # 4. 按匹配度排序
    reordered = _rank_by_name_match(all_pairs, keyword)

    # 5. 截断到 max_results
    limited_pairs = reordered[:max_results]

    # 6. 抓取详情（WAF 拦截时自动回退到搜索数据）
    results = _fetch_mcmod_details(limited_pairs, content_type, search_metadata)

    # 7. 截断描述（控制 token 消耗）
    for r in results:
        _apply_truncation(r, "description", _MAX_SEARCH_DESC_CHARS)

    return results


def search_mcmod_author(author_name: str, max_mods: int = 20) -> list[dict]:
    """MC百科按作者搜索。返回该作者在 MC百科收录的所有模组列表。

    Args:
        author_name: 作者名（需精确匹配）
        max_mods: 最大返回模组数，默认 20

    Returns:
        模组列表，每项含 name, name_en, name_zh, url, source, source_id, type,
        description, status, source_type, author, categories, tags, supported_versions,
        cover_image, screenshots, relationships, has_changelog, external_links 等字段。
    """
    q = urllib.parse.quote(author_name)
    html = curl(f"https://search.mcmod.cn/s?key={q}&filter=0")
    if not html or len(html) < MIN_HTML_LEN:
        raise SearchError(f"MC百科 作者搜索网络失败：{author_name}")

    idx = html.find("search-result-list")
    if idx == -1:
        raise SearchError(f"MC百科 作者搜索结果页结构变化：{author_name}")

    section = html[idx:idx + _MAX_AUTHOR_SECTION]
    clean = re.sub(r"<em[^>]*>|</em>", "", section)

    # 找 /author/ URL（搜索词精确匹配作者名时会出现）
    author_urls = re.findall(r'href="(https://www\.mcmod\.cn/author/\d+\.html)"', clean)
    if not author_urls:
        raise SearchError(f"MC百科 未找到作者 [{author_name}] 的页面（作者名需精确匹配）")

    author_url = author_urls[0]

    # 解析作者页面，获取所有模组
    page_html = curl(author_url)
    if _is_mcmod_blocked(page_html):
        raise SearchError(f"MC百科 作者页面被防火墙拦截：{author_name}。MC百科当前限制了页面访问，请稍后重试或使用 --platform modrinth。")
    if not page_html or len(page_html) < MIN_HTML_LEN:
        raise SearchError(f"MC百科 作者页面获取失败：{author_name}")

    # 从作者页面提取所有 /class/ 链接
    mod_links = re.findall(r'href="(/class/\d+\.html)"[^>]*>([^<]+)</a>', page_html)
    # 去重
    seen = set()
    unique_mods = []
    for url, name in mod_links:
        if url not in seen and name.strip() and not name.startswith("www."):
            seen.add(url)
            unique_mods.append((url, name.strip()))

    # 并行解析每个模组页面
    def _fetch_mod(args):
        url, name = args
        full_url = f"https://www.mcmod.cn{url}"
        page = curl(full_url)
        if _is_mcmod_blocked(page):
            return _build_mcmod_fallback_result(full_url, name, None, "mod")
        if page and len(page) >= MIN_HTML_LEN:
            return _parse_mcmod_mod_result(page, full_url, name)
        return {"name": name, "url": full_url, "source": "mcmod.cn", "_error": "page_fetch_failed"}

    limited_mods = unique_mods[:max_mods]
    results = _parallel_fetch_with_fallback(
        limited_mods, _fetch_mod,
        max_workers=min(len(limited_mods), _MAX_FETCH_WORKERS)
    )

    return results


def search_mcmod_modpack(keyword: str, max_results: int = 5) -> list[dict]:
    """MC百科整合包搜索。尝试多个filter策略，返回结果列表。"""
    q = urllib.parse.quote(keyword)

    # 多 filter 策略：按优先级尝试不同的 filter 值
    all_pairs = []
    seen = set()
    all_metadata = {}  # 跨 filter 累积搜索元数据

    for filter_val in _MCMOD_MODPACK_FILTERS:
        html = curl(f"https://search.mcmod.cn/s?key={q}&filter={filter_val}")
        if not html:
            continue

        idx = html.find("search-result-list")
        if idx == -1:
            continue

        # 累积搜索元数据（用于 WAF 回退）
        page_meta = _extract_search_result_metadata(html)
        all_metadata.update(page_meta)

        # 找到结果区域的结束位置（分页区域）
        end_idx = html.find('class="pagination"', idx)
        if end_idx == -1:
            end_idx = len(html)
        section = html[idx:end_idx]
        clean = re.sub(r"<em[^>]*>|</em>", "", section)

        # 提取整合包 URL（/modpack/ 路径）
        pairs = re.findall(
            r'href="(https://www\.mcmod\.cn/modpack/\d+\.html)">([^<]+)</a>',
            clean,
        )

        # 去重并添加到结果集
        for raw_url, name in pairs:
            name = name.strip()
            if name and raw_url not in seen and not name.startswith("www."):
                seen.add(raw_url)
                all_pairs.append((raw_url, name))

        # 如果已经找到足够结果，提前结束
        if len(all_pairs) >= max_results:
            break

    if not all_pairs:
        return []

    # 重新排序：名称匹配度优先（复用模组排序逻辑）
    reordered = _rank_by_name_match(all_pairs, keyword)

    # 截断到 max_results
    limited_pairs = reordered[:max_results]

    # 并行抓取详情页（WAF 拦截时自动回退到搜索数据）
    results = _fetch_mcmod_details(limited_pairs, "modpack", all_metadata)

    return results
