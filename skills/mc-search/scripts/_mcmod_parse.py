#!/usr/bin/env python3
"""mc-search MC百科 HTML 解析层 — 正则提取 mod/item/modpack 详情"""

import re
import urllib.parse

from ._http import (
    logger, SearchError,
    _clean_html_text, _clean_mcmod_html,
    _build_truncated_meta, _apply_truncation,
    _build_mcmod_fallback_result,
    _url_tail_key, _extract_mcmod_id,
    _is_modrinth_link, _is_wiki_link, _is_discord_link,
    _is_jenkins_link, _is_mcbbs_link, _is_mcmod_blocked,
    _MCMOD_COMMON_SKIP_PREFIXES,
    _MAX_INFO_TABLE_SECTION, _MAX_SEARCH_SEGMENT,
    _MAX_DESCRIPTION_SEGMENT, _MAX_SEARCH_DESC_CHARS,
    _MAX_TAG_SECTION_LEN, _MAX_TAG_TEXT_LEN,
    _MAX_VERSION_SECTION_LEN, _MAX_AUTHOR_SECTION,
    _MIN_DESCRIPTION_LINE_LEN, _MIN_SECTION_MARKER_DISTANCE,
    _SKIP_MCMOD_ORG_NAMES, _MAX_MCMOD_AUTHORS,
    _EXTERNAL_LINK_EXCLUDE_DOMAINS, _SIMPLE_LINK_RULES,
    _MOD_META_PAT,
)
import base64


def _parse_mcmod_item_result(html: str, url: str, name: str) -> dict:
    """从 MC百科 item 页面解析。物品页面结构与 class 页面完全不同。"""
    if _is_mcmod_blocked(html):
        return _build_mcmod_fallback_result(url, name, None, "item")

    m = re.search(r"<title>([^<]+)</title>", html)
    raw_title = m.group(1).strip() if m else name

    name_zh, name_en = _parse_mcmod_title(raw_title)

    # 封面图 + 截图（复用通用提取函数）
    cover_image, screenshots = _extract_mcmod_cover(html)

    # 资料分类 / 最大耐久 / 最大堆叠（从 item-info-table 提取）
    category = ""
    max_durability = None
    max_stack = None
    mod_name = ""
    mod_url = ""

    info_idx = html.find('item-info-table"')
    if info_idx >= 0:
        info_section = html[info_idx:info_idx + _MAX_INFO_TABLE_SECTION]
        # 资料分类
        cat_m = re.search(r'资料分类：</td><td[^>]*>(?:<a[^>]*?>)?([^<]+)', info_section)
        if cat_m:
            category = cat_m.group(1).strip()
        # 最大耐久
        dur_m = re.search(r'最大耐久：</td><td[^>]*>([\d,]+)', info_section)
        if dur_m:
            max_durability = int(dur_m.group(1).replace(",", ""))
        # 最大堆叠
        stack_m = re.search(r'最大堆叠：</td><td[^>]*>([\d,]+)', info_section)
        if stack_m:
            max_stack = int(stack_m.group(1).replace(",", ""))
        # 所属模组
        mod_links = re.findall(r'href="(/class/\d+\.html)"[^>]*>([^<]+)<', html)
        if mod_links:
            mod_url = "https://www.mcmod.cn" + mod_links[0][0]
            mod_name = mod_links[0][1].strip()

    # 物品介绍（item-content common-text font14 div）
    # 使用 regex 匹配完整 <div> 标签，然后用 depth 计数找闭合标签
    description = ""
    tag_m = re.search(r'<div[^>]*class="[^"]*item-content[^"]*font14[^"]*"[^>]*>', html)
    if tag_m:
        tag_end = tag_m.end()  # position of '>' in opening tag
        search = html[tag_end:tag_end + _MAX_SEARCH_SEGMENT]
        depth = 1  # already inside the div
        for i in range(len(search)):
            if search[i:i+4] == '<div':
                depth += 1
            elif search[i:i+6] == '</div>':
                depth -= 1
                if depth == 0:
                    segment = search[:i]
                    segment = re.sub(r"<br\s*/?>", "\n", segment)
                    segment = re.sub(r"</p>", "\n", segment)
                    text = _clean_html_text(segment, preserve_nl=True)
                    skip_prefixes = list(_MCMOD_COMMON_SKIP_PREFIXES) + [
                        "暂无简介，欢迎协助完善",
                        "MCmod does not have a description with this game data yet",
                        "This page still working because",
                        "player can edit description, instead of navigation",
                        "for navigation",
                        "<!--", "-->",
                    ]
                    lines = []
                    for line in text.split("\n"):
                        line = line.strip()
                        if len(line) < _MIN_DESCRIPTION_LINE_LEN:
                            continue
                        if any(line.startswith(p) for p in skip_prefixes):
                            continue
                        if any(p in line for p in ("MCmod does not have a description", "for navigation", "player can edit description")):
                            continue
                        lines.append(line)
                    description = "\n".join(lines)  # 不限制段落数
                    break

    # 截图截断信息
    result = {
        "name": name_zh or raw_title or name,
        "name_en": name_en,
        "name_zh": name_zh or raw_title or name,
        "url": url,
        "source": "mcmod.cn",
        "source_id": re.search(r"/item/(\d+)", url).group(1) if url else "",
        "type": "item",
        "cover_image": cover_image,
        "screenshots": [],
        "category": category,
        "max_durability": max_durability,
        "max_stack": max_stack,
        "source_mod_name": mod_name,
        "source_mod_url": mod_url,
        "description": description[:_MAX_SEARCH_DESC_CHARS] if description else "",
        "has_recipe": "recipe" in html.lower() or "合成" in html,
    }

    # 截断元信息
    truncated = _build_truncated_meta(description, _MAX_SEARCH_DESC_CHARS)
    if truncated:
        result["_truncated"] = truncated

    return result


def _extract_mcmod_cover(html: str) -> tuple[str, list[str]]:
    """提取封面图。返回 (cover_image, [])。"""
    cover_m = re.search(r'class="class-cover-image"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
    cover_image = cover_m.group(1) if cover_m else ""
    return cover_image, []


def _extract_mcmod_modpack_metadata(html: str) -> tuple[str, str, str, str, list[str]]:
    """提取整合包元数据。返回 (name_zh, name_en, author, status, categories)。"""
    # 标题解析
    m = re.search(r"<title>([^<]+)</title>", html)
    raw_title = m.group(1).strip() if m else ""

    name_zh, name_en = _parse_mcmod_title(raw_title)

    # 使用通用函数提取作者和状态
    author = _extract_mcmod_field(html, "作者")
    status = _extract_mcmod_field(html, "状态")

    # 分类
    categories = re.findall(r'href="/modpack/category/[^"]*"[^>]*>([^<]+)</a>', html)

    return name_zh, name_en, author, status, categories


def _extract_mcmod_modpack_description(html: str) -> str:
    """提取整合包描述文本。"""
    intro_idx = html.find("整合包介绍")
    if intro_idx < 0:
        return ""

    segment = html[intro_idx:intro_idx + _MAX_DESCRIPTION_SEGMENT]
    section_markers = ["整合包下载", "版本列表", "包含模组", "相关链接"]
    end = len(segment)
    for marker in section_markers:
        idx = segment.find(marker)
        if idx > _MIN_SECTION_MARKER_DISTANCE:
            end = min(end, idx)

    content = _clean_mcmod_html(segment[:end])
    text = _clean_html_text(content, preserve_nl=True)

    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if len(line) < _MIN_DESCRIPTION_LINE_LEN:
            continue
        lines.append(line)

    return "\n".join(lines)


def _extract_mcmod_modpack_versions(html: str) -> list[str]:
    """提取整合包支持的游戏版本列表。"""
    supported_versions = []
    version_section_idx = html.find("版本列表")
    if version_section_idx >= 0:
        version_section = html[version_section_idx:version_section_idx + _MAX_VERSION_SECTION_LEN]
        versions = re.findall(r'(?:Minecraft\s+)?(\d+\.\d+(?:\.\d+)?)', version_section)
        supported_versions = list(set(versions))

    return supported_versions


def _parse_mcmod_modpack_result(html: str, url: str, name: str) -> dict:
    """从 MC百科整合包页面解析。整合包页面结构与 class 页面类似但有差异。"""
    if _is_mcmod_blocked(html):
        return _build_mcmod_fallback_result(url, name, None, "modpack")

    # 提取元数据
    name_zh, name_en, author, status, categories = _extract_mcmod_modpack_metadata(html)

    # 封面图和截图
    cover_image, screenshots = _extract_mcmod_cover(html)

    # 描述
    description = _extract_mcmod_modpack_description(html)

    # 统计信息（仅版本列表）
    supported_versions = _extract_mcmod_modpack_versions(html)

    # 整合包类型判定（是否为 MC百科官方收录的整合包）
    is_official_modpack = bool(re.search(r'/modpack/\d+\.html', url))

    result = {
        "name": name_zh or name,
        "name_en": name_en,
        "name_zh": name_zh or name,
        "url": url,
        "source": "mcmod.cn",
        "source_id": re.search(r"/modpack/(\d+)", url).group(1) if url else "",
        "type": "modpack",
        "is_official": is_official_modpack,
        "cover_image": cover_image,
        "screenshots": [],
        "supported_versions": supported_versions,
        "categories": categories,
        "author": author,
        "status": status,
        "description": description[:_MAX_SEARCH_DESC_CHARS] if description else "",
        "snippet": description[:_MAX_SEARCH_DESC_CHARS] if description else "",  # 与 search 接口保持一致
        "downloads": 0,  # MC百科整合包通常不提供下载量统计
    }

    # 截断元信息
    truncated = _build_truncated_meta(description, _MAX_SEARCH_DESC_CHARS)
    if truncated:
        result["_truncated"] = truncated

    return result


def _extract_mcmod_versions(html: str) -> list[str]:
    """从版本检索区提取支持的游戏版本列表。"""
    ver_idx = html.find("版本检索")
    ver_section = html[ver_idx:ver_idx + _MAX_VERSION_SECTION_LEN] if ver_idx >= 0 else ""
    return list(set(re.findall(r'mcver=(\d+\.\d+(?:\.\d+)?)', ver_section)))


def _is_valid_tag_text(text: str) -> bool:
    """判断文本是否为有效标签（过滤过长文本和冒号结尾的标签名）。"""
    t = text.strip()
    return bool(t and len(t) < _MAX_TAG_TEXT_LEN and not t.endswith(':'))


def _extract_mcmod_categories(html: str) -> tuple[list[str], list[str]]:
    """提取分类（面包屑）和模组标签。返回 (categories, tags)。"""
    categories = re.findall(r'href="/class/category/\d+-1\.html"[^>]*>([^<]+)</a>', html)
    tags_idx = html.find("模组标签:")
    tags = []
    if tags_idx >= 0:
        tag_section = html[tags_idx:tags_idx + _MAX_TAG_SECTION_LEN]
        # 查找标签容器内的链接文本
        tags = re.findall(r'<a[^>]*class="[^"]*tag[^"]*"[^>]*>([^<]+)</a>', tag_section, re.IGNORECASE)
        if not tags:
            # 备用：提取尖括号内的文本，过滤掉非标签内容
            tags = [t.strip() for t in re.findall(r'>([^<]+)<', tag_section) if _is_valid_tag_text(t)]
    return categories, tags


def _extract_mcmod_description(html: str) -> str:
    """提取 Mod 介绍正文描述。"""
    intro_idx = html.find("Mod介绍")
    if intro_idx < 0:
        return ""
    segment = html[intro_idx:intro_idx + _MAX_DESCRIPTION_SEGMENT]
    section_markers = ["配方", "Mod关系", "Mod前置", "Mod联动",
                       "更新日志", "常见问题", "排行榜", "相关链接",
                       "text-area-post", "class-post-list"]
    end = len(segment)
    for marker in section_markers:
        idx = segment.find(marker)
        if idx > _MIN_SECTION_MARKER_DISTANCE:
            end = min(end, idx)
    content = _clean_mcmod_html(segment[:end])
    content = re.sub(r"</li>", "\n", content)  # 列表项单独一行
    text = _clean_html_text(content, preserve_nl=True)
    prefix_pat = r"^(?:Mod(?:介绍|教程|下载|讨论|特性|关系)|模组介绍|配方|前置Mod|联动Mod|更新日志|介绍)\s*"
    prev = None
    for _ in range(10):  # 安全上限，防止无限循环
        if prev == text:
            break
        prev = text
        text = re.sub(prefix_pat, "", text).strip()
    skip_fragments = list(_MCMOD_COMMON_SKIP_PREFIXES) + [
        "关于百科", "百科帮助", "开发日志", "捐赠百科",
        "联系百科", "意见反馈", "©Copyright MC百科",
        "mcmod.cn | ", "鄂ICP备", "鄂公网安备",
    ]
    # contains 过滤：这些字符串可能出现在行中任何位置（非仅行首）
    skip_contains = ["©Copyright MC百科", "鄂ICP备", "鄂公网安备", "mcmod.cn | ", "百科帮助", "开发日志"]
    para_title_pat = r"^(?:概述|简介|正文)\s*"
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        line = re.sub(para_title_pat, "", line).strip()
        line = re.sub(r"[。！？]\s*概述(?=[^\s])", lambda m: m.group(0)[0], line)
        if len(line) < _MIN_DESCRIPTION_LINE_LEN:
            continue
        if any(line.startswith(p) for p in skip_fragments):
            continue
        if _MOD_META_PAT.match(line):
            continue
        if re.search(r"MC百科\s*\(mcmod\.cn\)\s*的?目标是", line):
            line = re.sub(r"MC百科\s*\(mcmod\.cn\)\s*的?目标是.*", "", line).strip()
        if len(line) < _MIN_DESCRIPTION_LINE_LEN:
            continue
        if any(p in line for p in skip_contains):
            continue
        # 过滤 HTML 残留（如 <li data-id=...）
        if re.search(r"<[a-z]+[\s>]", line, re.IGNORECASE):
            continue
        lines.append(line)
    # 不限制段落数，返回完整描述（JSON 模式下用户可自行处理）
    return "\n".join(lines)


def _extract_mcmod_relationships(html: str) -> dict:
    """提取前置Mod和联动Mod关系。返回 {"requires": [], "integrates": [], "_parse_attempted": bool}。"""
    relationships = {"requires": [], "integrates": []}
    parse_attempted = False
    seen_requires = set()
    seen_integrates = set()
    for m in re.finditer(r'(前置Mod|联动的Mod):</span><ul>(.*?)</ul>', html, re.DOTALL):
        parse_attempted = True
        label = m.group(1)
        ul = m.group(2)
        links = re.findall(r'href="(/class/(\d+)\.html)"[^>]*>([^<]+)</a>', ul)
        for _, cid, raw in links:
            if label == "前置Mod":
                if cid in seen_requires:
                    continue
                seen_requires.add(cid)
            else:
                if cid in seen_integrates:
                    continue
                seen_integrates.add(cid)
            raw = raw.strip()
            parts = re.match(r'(.+?)\s*\(([^)]+)\)\s*$', raw)
            if parts:
                zh, en = parts.group(1).strip(), parts.group(2).strip()
            else:
                zh, en = raw, ''
            entry = {"id": cid, "name_zh": zh, "name_en": en, "url": f"https://www.mcmod.cn/class/{cid}.html"}
            if label == "前置Mod":
                relationships["requires"].append(entry)
            else:
                relationships["integrates"].append(entry)
    relationships["_parse_attempted"] = parse_attempted
    return relationships


def _extract_mcmod_author_status(html: str) -> tuple[str | None, str | None, str | None, bool]:
    """提取作者、状态、开源属性。返回 (author, status, source_type)。"""
    # 使用通用函数提取作者
    author = _extract_mcmod_field(html, "Mod作者/开发团队") or _extract_mcmod_field(html, "作者")

    # 提取状态：新版MC百科使用 <div class="class-status"> 结构
    status = None
    status_match = re.search(r'class="class-status[^"]*">([^<]+)', html)
    if status_match:
        status = status_match.group(1).strip()
    else:
        # 降级：尝试旧版表格结构
        status = _extract_mcmod_field(html, "状态")
        if not status:
            status = None

    # 如果作者字段为空，尝试从 title 属性提取
    if not author:
        author_idx = html.find("Mod作者/开发团队")
        if author_idx >= 0:
            auth_section = html[author_idx:author_idx + _MAX_TAG_SECTION_LEN]
            author_m = re.search(r'title="([^"-]+)', auth_section)
            if author_m:
                author = author_m.group(1).strip()

    log_idx = html.find("更新日志")
    has_changelog = False
    if log_idx >= 0:
        has_changelog = "暂无日志" not in html[log_idx:log_idx + _MAX_TAG_SECTION_LEN]

    source_type = None
    src_m = re.search(r'class="class-source[^"]*"[^>]*>([^<]+)<', html)
    if src_m:
        st = src_m.group(1).strip()
        source_type = "open_source" if ("开源" in st or "open" in st.lower()) else "closed_source"

    return author if author else None, status if status else None, source_type, has_changelog


def _parse_mcmod_title(raw_title: str) -> tuple[str, str]:
    """从 MC百科 <title> 解析中文名和英文名。返回 (name_zh, name_en)。"""
    name_zh = raw_title
    name_en = ""
    title_match = re.match(r"^(.+?)\s*(?:\(([^)]+)\))?\s*-", raw_title)
    if title_match:
        name_zh = title_match.group(1).strip()
        name_en = title_match.group(2).strip() if title_match.group(2) else ""
    return name_zh, name_en


def _extract_mcmod_author_team(html: str) -> list[dict]:
    """从MC百科HTML提取作者团队信息。返回 [{"name": "...", "roles": ["..."]}]，最多10人。"""
    authors = []
    author_idx = html.find("Mod作者/开发团队")
    if author_idx < 0:
        return authors

    # 提取作者区域（在 li 标签内）
    auth_section_start = author_idx
    # 找到 ul/列表区域的结束
    auth_section_end = html.find("</ul>", auth_section_start)
    if auth_section_end < 0:
        auth_section_end = auth_section_start + _MAX_AUTHOR_SECTION
    auth_section = html[auth_section_start:auth_section_end]

    # 查找所有 <li> 条目
    li_blocks = re.findall(r'<li>(.*?)</li>', auth_section, re.DOTALL)

    # 需要过滤的组织/团队名称（不是真实作者）
    # 包含：组织名、团队名、工作室名、以及含有特定关键词的名称
    skip_keywords = [
        "Mods", "Studio", "Studios", "Team", "Development",
        "开发团队", "工作室", "团队", "官方",
        "Minecraft Mods", "Pixel Studios"
    ]

    for li in li_blocks:
        # 提取作者名（简化正则）
        name_m = re.search(r'class="name"><a[^>]*>([^<]+)</a>', li)
        # 提取分工（从 title 属性）
        position_m = re.search(r'title="([^"]+)" class="position"', li)

        if name_m:
            name = name_m.group(1).strip()
            # 清理名称（去除可能的备注部分）
            name = re.split(r'\s*[-–]\s*', name)[0].strip()

            # 过滤组织名称（精确匹配或包含关键词）
            is_org = name in _SKIP_MCMOD_ORG_NAMES
            if not is_org:
                for keyword in skip_keywords:
                    if keyword in name:
                        is_org = True
                        break

            if is_org:
                continue

            # 解析分工
            roles = []
            if position_m:
                roles_str = position_m.group(1).strip()
                if roles_str:
                    roles = re.split(r'[、/，,]', roles_str)
                    roles = [r.strip() for r in roles if r.strip() and len(r.strip()) <= 10]

            # 添加作者（没有分工则默认为"开发者"）
            if name:
                authors.append({
                    "name": name,
                    "roles": roles if roles else ["开发者"]
                })

    # 限制最多返回 10 人（避免输出过长）
    return authors[:_MAX_MCMOD_AUTHORS]


def _extract_mcmod_community_stats(html: str) -> dict:
    """提取社区统计数据。返回 {"rating": 5.0, "page_views": 22200, ...}。"""
    stats = {
        "rating": 0,
        "rating_text": "",
        "positive_rate": 0,
        "page_views": 0,
        "favorites": 0,
        "downloads": 0,
        "integrations_count": 0,
        "last_updated": "",
        "revision_count": 0
    }

    # 评级和好评率
    rating_section = html.find("综合评级")
    if rating_section >= 0:
        section = html[rating_section:rating_section + _MAX_TAG_SECTION_LEN]

        # 评分数字
        rating_m = re.search(r'(\d+\.\d+)', section)
        if rating_m:
            stats["rating"] = float(rating_m.group(1))

        # 评级文字（如"名扬天下"）
        rating_text_m = re.search(r'"([^"]*?评价[^"]*?)"', section)
        if rating_text_m:
            stats["rating_text"] = rating_text_m.group(1)

        # 好评率
        rate_m = re.search(r'(\d+)%', section)
        if rate_m:
            stats["positive_rate"] = int(rate_m.group(1))

    # 页面浏览量
    views_m = re.search(r'页面浏览量[:：]?\s*([\d,\.]+)', html)
    if views_m:
        stats["page_views"] = int(float(views_m.group(1).replace(',', '')))

    # 收藏数
    fav_m = re.search(r'收藏[:：]?\s*([\d,\.]+)', html)
    if fav_m:
        stats["favorites"] = int(float(fav_m.group(1).replace(',', '')))

    # 整合包引用数
    integration_m = re.search(r'整合包引用[:：]?\s*(\d+)', html)
    if integration_m:
        stats["integrations_count"] = int(integration_m.group(1))

    # 修订次数
    revision_m = re.search(r'修订[:：]?\s*(\d+)', html)
    if revision_m:
        stats["revision_count"] = int(revision_m.group(1))

    # 最后更新时间
    update_m = re.search(r'(?:更新|更新在)\s*[:：]?\s*([\d]+[天小时日之前周月年前])', html)
    if update_m:
        stats["last_updated"] = update_m.group(1)

    return stats


def _decode_mcmod_obfuscated_link(encoded: str) -> str:
    """解码 MC百科的 Base64 混淆链接。失败返回空字符串。"""
    try:
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        return base64.b64decode(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as e:
        logger.debug(f"Link decode failed: {e}")
        return ""


def _add_cross_platform_ids(links: dict) -> None:
    """从已提取链接中解析跨平台 slug。在原地修改 links。"""
    cross_platform_ids = {}
    if "curseforge" in links:
        cf_slug = re.search(r'/minecraft/mc-mods/([^/\s"<>\)]+)', links["curseforge"])
        if cf_slug:
            cross_platform_ids["curseforge_slug"] = cf_slug.group(1)
    if "modrinth" in links:
        mr_slug = re.search(r'/(?:mod|shader|resourcepack|modpack)/([^/\s"<>\)]+)', links["modrinth"])
        if mr_slug:
            cross_platform_ids["modrinth_slug"] = mr_slug.group(1)
    if cross_platform_ids:
        links["cross_platform_ids"] = cross_platform_ids


def _extract_mcmod_external_links(html: str) -> dict:
    """提取模组的外部平台链接。返回 {"official": "...", "curseforge": "...", ...}。"""
    links = {}

    # 收集所有解码后的链接
    all_decoded = []
    obfuscated = re.findall(r'link\.mcmod\.cn/target/([A-Za-z0-9+/=]+)', html)
    for encoded in obfuscated:
        url = _decode_mcmod_obfuscated_link(encoded)
        if url and url.startswith("http"):
            all_decoded.append(url)

    # 分类存储链接
    curseforge_links = []
    github_links = []

    for url in all_decoded:
        # 官方网站（非已知平台的独立域名，仅设一次）
        if "official" not in links:
            if not any(x in url for x in _EXTERNAL_LINK_EXCLUDE_DOMAINS):
                links["official"] = url

        # CurseForge 收集（后续选最优）
        if "curseforge.com" in url:
            curseforge_links.append(url)
            continue

        # GitHub 收集（过滤 wiki/issues/pull，后续选主仓库）
        if "github.com" in url:
            if not any(x in url for x in ["/blob/", "/wiki", "/issues", "/pull/"]):
                github_links.append(url)
            continue

        # 其余平台：按规则表匹配，每个 key 只存第一个
        for pattern, key in _SIMPLE_LINK_RULES:
            if pattern(url) and key not in links:
                links[key] = url
                break

    # 选择 CurseForge 链接：优先 mc-mods，其次最短
    if curseforge_links:
        mc_mods_links = [u for u in curseforge_links if "/mc-mods/" in u]
        if mc_mods_links:
            links["curseforge"] = min(mc_mods_links, key=len)
        else:
            links["curseforge"] = min(curseforge_links, key=len)

    # 选择最短的 GitHub 链接（通常是主仓库）
    if github_links:
        links["github"] = min(github_links, key=len)

    # 跨平台 ID（用于精确关联 Modrinth/CurseForge）
    _add_cross_platform_ids(links)

    return links


def _extract_mcmod_field(html: str, field_label: str = "作者") -> str:
    """通用提取MC百科字段。返回字段值（带链接优先，否则纯文本）。"""
    # 先尝试提取带链接的值
    pattern = rf'{field_label}：</td><td[^>]*><a[^>]*>([^<]+)</a>'
    m = re.search(pattern, html)
    if m:
        return m.group(1).strip()

    # 降级为纯文本
    pattern = rf'{field_label}：</td><td[^>]*>([^<]+)</td>'
    m = re.search(pattern, html)
    return m.group(1).strip() if m else ""


def _extract_mcmod_content_list(html: str, class_id: str) -> dict:
    """提取模组资料列表。返回 {"1": {"label": "物品/方块", "count": 1016, "url": "..."}}。"""
    # 预定义映射（仅作 fallback，优先使用页面标题）
    content_types = {
        "1": "物品/方块",
        "4": "生物/实体",
        "5": "附魔/魔咒",
        "6": "BUFF/DEBUFF",
        "7": "多方块结构",
        "8": "自然生成",
        "9": "绑定热键",
        "10": "游戏设定",
    }

    result = {}

    # 查找所有 item/list 链接（严格匹配当前结构）
    pattern = rf'href="/item/list/{class_id}-(\d+)\.html"[^>]*>.*?<span class="title">([^<]+)</span>.*?<span class="count">\((\d+)条\)</span>'
    matches = re.findall(pattern, html, re.DOTALL)

    # Fallback: 宽松正则（兼容结构变化）
    if not matches:
        fallback_pattern = rf'href="/item/list/{class_id}-(\d+)\.html"[^>]*>(.*?)</a>'
        fallback_matches = re.findall(fallback_pattern, html, re.DOTALL)
        for type_id, inner_html in fallback_matches:
            type_id = type_id.strip()
            title_m = re.search(r'<span[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</span>', inner_html)
            count_m = re.search(r'(\d+)\s*条', inner_html)
            if title_m and count_m:
                matches.append((type_id, title_m.group(1), count_m.group(1)))

    for type_id, title, count in matches:
        type_id = type_id.strip()
        count = int(count.strip())
        if count > 0:
            label = title.strip() or content_types.get(type_id, f"类型{type_id}")
            result[type_id] = {
                "label": label,
                "count": count,
                "url": f"https://www.mcmod.cn/item/list/{class_id}-{type_id}.html",
            }

    return result


def _parse_mcmod_mod_result(html: str, url: str, name: str) -> dict:
    """从 MC百科 class 页面解析。name 来自搜索页，html 仅用于提取扩展字段。"""
    if _is_mcmod_blocked(html):
        return _build_mcmod_fallback_result(url, name, None, "mod")

    m = re.search(r"<title>([^<]+)</title>", html)
    raw_title = m.group(1).strip() if m else name

    # 从 <title> 提取中英文名（格式："中文名 (English) - MC百科|..."）
    zh_from_title, en_from_title = _parse_mcmod_title(raw_title)

    # 副标题 h4 作为英文名后备
    name_en = en_from_title
    if not name_en:
        h4_m = re.search(r'<h4[^>]*>\s*([^<\s][^<]*?)\s*</h4>', html)
        if h4_m:
            en_raw = h4_m.group(1).strip()
            if en_raw and en_raw != zh_from_title:
                name_en = en_raw

    # 中文名直接取自 title 解析结果
    name_zh = zh_from_title

    # 调用辅助函数提取各字段
    cover_image, screenshots = _extract_mcmod_cover(html)
    supported_versions = _extract_mcmod_versions(html)
    categories, tags = _extract_mcmod_categories(html)
    description = _extract_mcmod_description(html)
    relationships_raw = _extract_mcmod_relationships(html)
    parse_attempted = relationships_raw.pop("_parse_attempted", False)
    relationships = None
    if relationships_raw["requires"] or relationships_raw["integrates"]:
        relationships = {"requires": relationships_raw["requires"], "integrates": relationships_raw["integrates"]}
    elif parse_attempted:
        relationships = {"_error": "parse_failed"}
    author, status, source_type, has_changelog = _extract_mcmod_author_status(html)
    external_links = _extract_mcmod_external_links(html)

    # 新增：提取完整作者团队和社区数据
    author_team = _extract_mcmod_author_team(html)
    community_stats = _extract_mcmod_community_stats(html)

    # 提取 class_id 并获取资料列表
    class_id = re.search(r"/class/(\d+)", url).group(1) if url else ""
    content_list = _extract_mcmod_content_list(html, class_id) if class_id else {}

    # 原版内容识别：class/1 是 MC百科"原版内容"分类
    is_vanilla = bool(re.search(r"/class/1\.html", url))

    result = {
        "name": name_zh or raw_title or name,
        "name_en": name_en,
        "name_zh": name_zh or raw_title or name,
        "url": url,
        "source": "mcmod.cn",
        "source_id": re.search(r"/class/(\d+)", url).group(1) if url else "",
        "type": "mod",
        "is_vanilla": is_vanilla,
        "cover_image": cover_image,
        "screenshots": [],
        "supported_versions": supported_versions,
        "categories": categories,
        "tags": tags,
        "author": author,  # 兼容性：保留单一作者
        "author_team": author_team if author_team else None,  # 新增：完整作者团队
        "community_stats": community_stats if any(community_stats.values()) else None,  # 新增：社区数据
        "status": status,
        "source_type": source_type,
        "description": description,  # 返回完整描述（由调用方决定是否截断）
        "relationships": relationships,
        "has_changelog": has_changelog,
        "external_links": external_links if external_links else None,
        "content_list": content_list or None,
    }

    # 截断元信息
    truncated = _build_truncated_meta(description, _MAX_SEARCH_DESC_CHARS)
    if truncated:
        result["_truncated"] = truncated

    return result
