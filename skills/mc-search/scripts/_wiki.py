#!/usr/bin/env python3
"""mc-search Wiki 模块 — Minecraft Wiki (EN/ZH) 搜索/阅读/Infobox 解析"""

import re
import urllib.parse

from ._http import (
    logger, SearchError,
    curl,
    _clean_html_text, _html_to_text,
    _build_truncated_meta, _apply_truncation,
    _DEFAULT_RESULTS_PER_PLATFORM,
)

_MAX_SEARCH_DESC_CHARS = 500  # 搜索结果描述最大字符数


def _add_variant_param(url: str) -> str:
    """为中文 wiki URL 添加 variant=zh-hans 参数。"""
    url = re.sub(r"[&?](?:amp;)?variant=zh-[a-z]+", "", url)
    separator = "&" if "?" in url else "?"
    return url + separator + "variant=zh-hans"


def _build_wiki_result(name, url, source, source_id, snippet, sections,
                       title_field="", main_image=None):
    """构造 wiki 搜索结果 dict。title_field 决定哪个 name 字段填入标题。"""
    result = {
        "name": name,
        "name_en": name if title_field == "name_en" else "",
        "name_zh": name if title_field == "name_zh" else "",
        "url": url,
        "source": source,
        "source_id": source_id,
        "type": "wiki",
        "sections": sections,
        "snippet": snippet,
    }
    if main_image:
        result["main_image"] = main_image
    return result


_DISAMBIG_PREFIXES = ('本条目介绍的是', '本條目介紹的是', '關於其他用法', '关于其他用法',
                      '消歧義', '消歧义', '本頁面是', '本页面是')


def _wiki_api_generator_search(
    keyword: str,
    base_url: str,
    source: str,
    title_field: str,
    add_variant: bool,
    max_results: int,
) -> list[dict]:
    """银弹查询：单次 generator=search 替代 go=Go + list=search。

    组合 prop=extracts|pageprops|pageimages，一次 RTT 拿齐所有搜索所需数据。
    redirects=1 确保重定向页返回目标页面数据而非干瘪的 "Redirect to X"。
    """
    results = []
    q = urllib.parse.quote(keyword)
    api_url = (
        f"{base_url}/api.php?action=query&generator=search&gsrsearch={q}"
        f"&gsrlimit={max_results}&prop=extracts|pageprops|pageimages"
        f"&exintro=1&explaintext=1&pithumbsize=200&redirects=1&format=json"
    )
    raw = curl(api_url)
    if not raw:
        return results

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"Wiki generator search JSON parse failed for {keyword}: {e}")
        return results

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return results

    # 按 page.index 排序（generator=search 排序依据，无独立 query.search 数组）
    sorted_pages = sorted(
        pages.items(),
        key=lambda kv: kv[1].get("index", 9999),
    )

    for _, page in sorted_pages:

        title = page.get("title", "")
        pageid = page.get("pageid", 0)
        extract = page.get("extract", "")
        pageprops = page.get("pageprops", {})
        thumbnail = page.get("thumbnail", {})

        # snippet：截断 extract 并保留 _truncated 元信息
        snippet = extract[:_MAX_SEARCH_DESC_CHARS] if extract else ""
        if len(extract) > _MAX_SEARCH_DESC_CHARS:
            is_truncated = True
        else:
            is_truncated = False

        # 消歧义检测：pageprops 为主，中文前缀为回退
        is_disambig = "disambiguation" in pageprops

        # 中文消歧义前缀回退
        if not is_disambig and snippet:
            prefix80 = snippet[:80]
            if any(prefix80.startswith(p) for p in _DISAMBIG_PREFIXES):
                is_disambig = True

        # 客户端精确匹配判定
        direct_match = _is_direct_match(keyword, title)

        # URL
        article_url = f"{base_url}/w/{urllib.parse.quote(title.replace(' ', '_'))}"
        if add_variant:
            article_url = _add_variant_param(article_url)

        # 主图
        main_image = thumbnail.get("source") if thumbnail else None

        result = _build_wiki_result(
            name=title,
            url=article_url,
            source=source,
            source_id=str(pageid),
            snippet=snippet,
            sections=[],
            title_field=title_field,
            main_image=main_image,
        )
        if direct_match:
            result["_direct_match"] = True
        if is_disambig:
            result["is_disambiguation"] = True
        if is_truncated:
            result.setdefault("_truncated", {})["description"] = {
                "returned": _MAX_SEARCH_DESC_CHARS,
                "total": len(extract),
            }

        results.append(result)

    return results


def _search_wiki_impl(
    keyword: str,
    base_url: str,
    cache_prefix: str,
    source: str,
    title_field: str,
    add_variant: bool,
    max_results: int = 5,
) -> list[dict]:
    """minecraft.wiki 搜索通用实现。单次 generator=search API 调用。"""
    return _wiki_api_generator_search(
        keyword=keyword,
        base_url=base_url,
        source=source,
        title_field=title_field,
        add_variant=add_variant,
        max_results=max_results,
    )


def search_wiki(keyword: str, max_results: int = 5) -> list[dict]:
    """minecraft.wiki 英文 wiki 搜索。

    Args:
        keyword: 搜索关键词
        max_results: 最大返回结果数，默认 5

    Returns:
        结果列表，每项含 name, name_en, url, source, source_id, type, snippet, sections
    """
    return _search_wiki_impl(
        keyword=keyword,
        base_url="https://minecraft.wiki",
        cache_prefix="wiki",
        source="minecraft.wiki",
        title_field="name_en",
        add_variant=False,
        max_results=max_results,
    )


def search_wiki_zh(keyword: str, max_results: int = 5) -> list[dict]:
    """minecraft.wiki/zh 中文 wiki 搜索。

    Args:
        keyword: 搜索关键词
        max_results: 最大返回结果数，默认 5

    Returns:
        结果列表，每项含 name, name_en, url, source, source_id, type, snippet, sections
    """
    return _search_wiki_impl(
        keyword=keyword,
        base_url="https://zh.minecraft.wiki",
        cache_prefix="wiki_zh",
        source="minecraft.wiki/zh",
        title_field="name_zh",
        add_variant=True,
        max_results=max_results,
    )


def _is_direct_match(query: str, title: str) -> bool:
    """客户端精确标题匹配判定。替代 go=Go 的 getNearMatch() 行为。

    Args:
        query: 用户搜索关键词
        title: API 返回的页面标题

    Returns:
        True 当 query 和 title 归一化后精确匹配
    """
    q = query.strip().lower().replace(' ', '_')
    t = title.strip().lower().replace(' ', '_')
    if q == t:
        return True
    # CJK：尝试 Unicode 规范化（NFKC 折叠全角/半角、繁简部分等效）
    import unicodedata
    q_norm = unicodedata.normalize('NFKC', q)
    t_norm = unicodedata.normalize('NFKC', t)
    return q_norm == t_norm


def _extract_infobox_from_wikitext(wikitext: str) -> dict:
    """从 wikitext 提取 Infobox 模板键值对。单路径带大括号深度状态机。

    仅在模板嵌套深度归零时把 | 识别为参数分隔符，正确跳过嵌套 {{...}} 内的 = 和 |。
    清洗 wikitext 残留：[[links]]、'''bold'''、''italic''、HTML 标签。
    """
    # 匹配 Infobox/Block/Item/Entity/Biome 模板开头
    m = re.search(r'\{\{(?:Infobox[_\s]\w+|Block|Item|Entity|Biome)\s*[\|\n]', wikitext)
    if not m:
        return {}

    # 从 {{ 开始跟踪大括号深度，找到闭合 }}
    start = m.start()
    depth = 0
    end = start
    while end < len(wikitext):
        if wikitext[end:end+2] == '{{':
            depth += 1
            end += 2
        elif wikitext[end:end+2] == '}}':
            depth -= 1
            if depth == 0:
                break
            end += 2
        else:
            end += 1

    if depth != 0:
        return {}  # 未闭合，放弃

    # 提取模板名之后、闭合 }} 之前的参数块
    # 找到第一个 | 或 \n（模板名结束）
    name_end = start + len(m.group())
    params_block = wikitext[name_end:end]

    # 按 | 切分参数——仅在双括号深度为 0 时切（同时跟踪 {{}} 和 [[]]）
    data = {}
    current = ""
    brace_depth = 0  # {{ }} 嵌套深度
    link_depth = 0   # [[ ]] 嵌套深度

    def _at_depth_zero():
        return brace_depth == 0 and link_depth == 0

    i = 0
    while i < len(params_block):
        ch = params_block[i]
        # 检测 {{ 或 }}
        if ch == '{' and i+1 < len(params_block) and params_block[i+1] == '{':
            brace_depth += 1
            current += '{{'
            i += 2
            continue
        elif ch == '}' and i+1 < len(params_block) and params_block[i+1] == '}':
            brace_depth = max(0, brace_depth - 1)
            current += '}}'
            i += 2
            continue
        # 检测 [[ 或 ]]
        elif ch == '[' and i+1 < len(params_block) and params_block[i+1] == '[':
            link_depth += 1
            current += '[['
            i += 2
            continue
        elif ch == ']' and i+1 < len(params_block) and params_block[i+1] == ']':
            link_depth = max(0, link_depth - 1)
            current += ']]'
            i += 2
            continue
        elif ch == '|' and _at_depth_zero():
            # 参数分隔符
            current = current.strip()
            if '=' in current:
                key, _, value = current.partition('=')
                key = key.strip()
                if key and not key.startswith('{'):
                    data[key.lower()] = _clean_wikitext_value(value.strip())
            elif current:
                # 位置参数（如 |image= 的变体），取有效 key
                pass
            current = ""
            i += 1
            continue
        current += ch
        i += 1

    # 最后一个参数
    current = current.strip()
    if current and '=' in current:
        key, _, value = current.partition('=')
        key = key.strip()
        if key and not key.startswith('{'):
            data[key.lower()] = _clean_wikitext_value(value.strip())

    return data


def _clean_wikitext_value(value: str) -> str:
    """清洗 wikitext 值中的格式标记。"""
    # [[link|text]] → text, [[link]] → link
    value = re.sub(r'\[\[(?:[^\]|]+)\|([^\]]+)\]\]', r'\1', value)
    value = re.sub(r'\[\[([^\]]+)\]\]', r'\1', value)
    # '''bold''', ''italic''
    value = re.sub(r"'''([^']+)'''", r'\1', value)
    value = re.sub(r"''([^']+)''", r'\1', value)
    # HTML 标签残留
    value = re.sub(r'<[^>]+>', '', value)
    # 多余空白
    value = re.sub(r'\s+', ' ', value).strip()
    return value


def _api_fetch_page_data(page_title: str, base_url: str) -> dict:
    """并发获取 wiki 页面数据：extracts（纯文本）+ parse（sections + wikitext）。

    返回 {"extract": str, "sections": list, "wikitext": str, "title": str}
    任一请求失败时对应字段为空/默认值。
    """
    result = {"extract": "", "sections": [], "wikitext": "", "title": page_title}
    q = urllib.parse.quote(page_title)

    extracts_url = (f"{base_url}/api.php?action=query&prop=extracts"
                    f"&explaintext=1&titles={q}&format=json")
    parse_url = (f"{base_url}/api.php?action=parse&prop=sections|wikitext"
                 f"&page={q}&format=json")

    raw_extracts = curl(extracts_url)
    raw_parse = curl(parse_url)

    # 解析 extracts
    if raw_extracts:
        try:
            data = json.loads(raw_extracts)
            pages = data.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                if int(pid) > 0:  # 跳过负数（无效页面）
                    result["extract"] = page.get("extract", "")
                    result["title"] = page.get("title", page_title)
        except json.JSONDecodeError:
            pass

    # 解析 parse（sections + wikitext）
    if raw_parse:
        try:
            data = json.loads(raw_parse)
            parse_data = data.get("parse", {})
            result["sections"] = parse_data.get("sections", [])
            result["wikitext"] = parse_data.get("wikitext", {})
            if not result["title"] or result["title"] == page_title:
                result["title"] = parse_data.get("title", page_title)
            # wikitext 可能是 dict(encoding, content) 或直接是字符串
            if isinstance(result["wikitext"], dict):
                result["wikitext"] = result["wikitext"].get("*", "")
        except json.JSONDecodeError:
            pass

    return result


def _extract_page_title_from_url(url: str) -> str:
    """从 wiki URL 提取页面标题。"""
    from urllib.parse import unquote
    path = url.split("/w/")[-1] if "/w/" in url else url.split("/wiki/")[-1]
    title = path.split("?")[0].split("#")[0]
    return unquote(title.replace("_", " "))


def _extract_base_url_from_url(url: str) -> str:
    """从 wiki 页面 URL 提取 base_url。"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _read_wiki_impl(url: str, max_paragraphs: int,
                    para_skip_prefixes: tuple[str, ...],
                    heading_skip_ids: set[str],
                    source: str,
                    include_infobox: bool = True) -> dict:
    """读取 wiki 页面正文（英文 / 中文共用实现）。

    使用 action=query prop=extracts（纯文本）+ action=parse（sections + wikitext）
    替代 HTML 直连 + 正则刮削。Infox 从 wikitext 模板解析。
    """
    page_title = _extract_page_title_from_url(url)
    base_url = _extract_base_url_from_url(url)

    data = _api_fetch_page_data(page_title, base_url)
    extract = data["extract"]
    sections_raw = data["sections"]
    wikitext = data["wikitext"]
    title = data["title"] or page_title

    if not extract:
        return {"_error": "no_content"}

    # 提取 infobox 结构化数据（从 wikitext）
    infobox_data = {}
    if wikitext:
        infobox_data = _extract_infobox_from_wikitext(wikitext)

    # 将 extract 按 \n\n 拆分为段落，应用过滤
    paragraphs = []
    para_count = 0
    for para in extract.split('\n\n'):
        para = para.strip()
        if not para:
            continue
        if max_paragraphs > 0 and para_count >= max_paragraphs:
            break
        # 跳过前缀匹配的段落
        if para_skip_prefixes and any(para.startswith(p) for p in para_skip_prefixes):
            continue
        paragraphs.append(para)
        para_count += 1

    # 构建 _sections（从 parse.sections，应用 heading_skip_ids）
    sections_output = []
    for sec in sections_raw:
        anchor = sec.get("anchor", "")
        if heading_skip_ids and anchor in heading_skip_ids:
            continue
        sections_output.append({
            "heading": sec.get("line", ""),
            "level": sec.get("toclevel", 1),
            "anchor": anchor,
        })

    result = {
        "name": title,
        "url": url,
        "source": source,
        "language": "zh" if "minecraft.wiki/zh" in source or "zh.minecraft.wiki" in source else "en",
        "content": paragraphs,
        "_sections": sections_output,
    }

    if infobox_data and include_infobox:
        result["infobox"] = infobox_data

    return result


# Wiki heading 跳过 ID（章节过滤，用于 read_wiki）
_WIKI_HEADING_SKIP_IDS = {
    "mw-toc-heading", "References", "Navigation", "Videos", "Trivia",
    "p-personal-label", "p-navigation-label", "p-tb-label",
}
_WIKI_ZH_HEADING_SKIP_IDS = {
    "参考资料", "参考", "导航", "视频", "琐事",
    "p-interaction-label", "p-print-label", "p-toolbox-label",
} | _WIKI_HEADING_SKIP_IDS


def read_wiki(url: str, max_paragraphs: int = -1, include_infobox: bool = True) -> dict:
    """读取minecraft.wiki英文页面正文。"""
    return _read_wiki_impl(
        url, max_paragraphs,
        para_skip_prefixes=("History of", "v ", "[edit"),
        heading_skip_ids=_WIKI_HEADING_SKIP_IDS,
        source="minecraft.wiki",
        include_infobox=include_infobox,
    )


def read_wiki_zh(url: str, max_paragraphs: int = -1, include_infobox: bool = True) -> dict:
    """读取minecraft.wiki/zh中文wiki页面正文。"""
    url = _add_variant_param(url)  # 确保返回简体中文
    return _read_wiki_impl(
        url, max_paragraphs,
        para_skip_prefixes=("历史", "编辑", "请帮助", "History of", "v ", "[edit"),
        heading_skip_ids=_WIKI_ZH_HEADING_SKIP_IDS,
        source="minecraft.wiki/zh",
        include_infobox=include_infobox,
    )
