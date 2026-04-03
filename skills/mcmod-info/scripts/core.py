#!/usr/bin/env python3
"""
mcmod-info 核心搜索模块
统一接口：三平台并行搜索 + 统一结果格式 + 智能路由
"""

import hashlib
import html as html_module
import json
import os
import re
import subprocess
import time
import urllib.parse
import concurrent.futures
from pathlib import Path

# ─────────────────────────────────────────
# 错误类型（用于区分网络/解析/无结果）
# ─────────────────────────────────────────

class _SearchError(Exception):
    """搜索过程中的可区分错误。"""
    pass


# ─────────────────────────────────────────
# 统一结果 Schema
# {
#   "name": str,        # 名称（最优先显示）
#   "name_en": str,     # 英文名
#   "name_zh": str,     # 中文名
#   "url": str,         # 主链接
#   "source": str,      # 来源平台
#   "source_id": str,   # 来源平台内的ID（如 class/23352）
#   "type": str,        # mod | item | block | entity | mechanic
#   "snippet": str,     # 摘要/描述
#   "sections": list,  # 章节/分类（wiki用）
#   "content": list,    # 正文段落（read用）
# }
# ─────────────────────────────────────────

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# ─────────────────────────────────────────
# 缓存系统
# ─────────────────────────────────────────

_cache_enabled = False
_cache_ttl = 3600  # 默认 1 小时


def _cache_dir() -> Path:
    return Path(os.path.expanduser("~/.cache/mcmod-info"))


def _cache_key(*parts: str) -> str:
    """生成缓存 key。"""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _cache_get(cache_type: str, key: str) -> dict | None:
    """读取缓存，成功返回 dict，失败/过期返回 None。"""
    if not _cache_enabled:
        return None
    p = _cache_dir() / cache_type / f"{key}.json"
    if not p.exists():
        return None
    try:
        age = time.time() - p.stat().st_mtime
        if age > _cache_ttl:
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_set(cache_type: str, key: str, data: dict):
    """写入缓存。"""
    if not _cache_enabled:
        return
    try:
        d = _cache_dir() / cache_type
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{key}.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def set_cache(enabled: bool, ttl: int = 3600):
    """由 CLI 调用启用缓存。"""
    global _cache_enabled, _cache_ttl
    _cache_enabled = enabled
    _cache_ttl = ttl


# ─────────────────────────────────────────
# 平台开关
# ─────────────────────────────────────────

_platform_enabled = {"mcmod.cn": True, "modrinth": True, "minecraft.wiki": True}


def set_platform_enabled(mcmod: bool = True, modrinth: bool = True, wiki: bool = True):
    """由 CLI 调用控制哪些平台启用。"""
    global _platform_enabled
    _platform_enabled = {
        "mcmod.cn": mcmod,
        "modrinth": modrinth,
        "minecraft.wiki": wiki,
    }


def _curl(url: str, timeout: int = 10) -> str:
    r = subprocess.run(
        ["curl", "-s", "-L",
         "-H", f"User-Agent: {HTTP_HEADERS['User-Agent']}",
         "-H", f"Accept: {HTTP_HEADERS['Accept']}",
         "-H", f"Accept-Language: {HTTP_HEADERS['Accept-Language']}",
         "--max-time", str(timeout), url],
        capture_output=True, timeout=timeout + 5,
    )
    return r.stdout.decode("utf-8", errors="replace")


# ─────────────────────────────────────────
# 物品/方块解析（MC百科 /item/ 页面）
# ─────────────────────────────────────────

def _parse_mcmod_item_result(html: str, url: str, name: str) -> dict:
    """从 MC百科 item 页面解析。物品页面结构与 class 页面完全不同。"""
    m = re.search(r"<title>([^<]+)</title>", html)
    raw_title = m.group(1).strip() if m else name

    # 从 title 中分离中文名和 (英文名)
    # 格式: "嵌金钻石剑 (嵌金钻石剑) - [MEaT]更多装备与工具 - MC百科"
    name_zh = raw_title
    name_en = ""
    title_match = re.match(r"^(.+?)\s*(?:\(([^)]+)\))?\s*-", raw_title)
    if title_match:
        name_zh = title_match.group(1).strip()
        name_en = title_match.group(2).strip() if title_match.group(2) else ""

    # 封面图（item 页面也用 class-cover-image）
    cover_m = re.search(r'class="class-cover-image"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
    cover_image = cover_m.group(1) if cover_m else ""

    # 截图
    screenshots = re.findall(r'class="figure"[^>]*>.*?data-src="([^"]+)"', html, re.DOTALL)

    # 资料分类 / 最大耐久 / 最大堆叠（从 item-info-table 提取）
    category = ""
    max_durability = None
    max_stack = None
    mod_name = ""
    mod_url = ""

    info_idx = html.find('item-info-table"')
    if info_idx >= 0:
        info_section = html[info_idx:info_idx + 2000]
        # 资料分类
        cat_m = re.search(r'资料分类：</td><td[^>]*>([^<]+)<', info_section)
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
        mod_links = re.findall(r'href="(/class/\d+\.html)"[^>]*>([^<]+)<', info_section)
        if mod_links:
            mod_url = "https://www.mcmod.cn" + mod_links[0][0]
            mod_name = mod_links[0][1].strip()

    # 物品介绍（item-content common-text font14 div）
    # 使用 regex 匹配完整 <div> 标签，然后用 depth 计数找闭合标签
    description = ""
    tag_m = re.search(r'<div[^>]*class="[^"]*item-content[^"]*font14[^"]*"[^>]*>', html)
    if tag_m:
        tag_end = tag_m.end()  # position of '>' in opening tag
        search = html[tag_end:tag_end + 2000]
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
                    text = re.sub(r"<[^>]+>", "", segment)
                    text = html_module.unescape(text)
                    text = re.sub(r"[ \t\r]+", " ", text).strip()
                    skip_prefixes = ["MC百科的目标是", "MC百科(mcmod.cn)的目标",
                                     "提供Minecraft(我的世界)MOD(模组)物品资料介绍"]
                    lines = []
                    for line in text.split("\n"):
                        line = line.strip()
                        if len(line) < 10:
                            continue
                        if any(line.startswith(p) for p in skip_prefixes):
                            continue
                        lines.append(line)
                    description = "\n".join(lines[:5])
                    break

    return {
        "name": name_zh or raw_title or name,
        "name_en": name_en,
        "name_zh": name_zh or raw_title or name,
        "url": url,
        "source": "mcmod.cn",
        "source_id": re.search(r"/item/(\d+)", url).group(1) if url else "",
        "type": "item",
        "cover_image": cover_image,
        "screenshots": screenshots[:6],
        "category": category,
        "max_durability": max_durability,
        "max_stack": max_stack,
        "source_mod_name": mod_name,
        "source_mod_url": mod_url,
        "description": description,
    }


# ─────────────────────────────────────────
# 模组解析（MC百科 /class/ 页面）
# ─────────────────────────────────────────

def _parse_mcmod_result(html: str, url: str, name: str) -> dict:
    """从 MC百科 class 页面解析。name 来自搜索页，html 仅用于提取扩展字段。"""
    m = re.search(r"<title>([^<]+)</title>", html)
    raw_title = re.sub(r"\s*-\s*MC百科\|.*", "", m.group(1)).strip() if m else name

    # 副标题 h4 通常含英文名
    name_en = ""
    h4_m = re.search(r'<h4[^>]*>\s*([^<\s][^<]*?)\s*</h4>', html)
    if h4_m:
        en_raw = h4_m.group(1).strip()
        if en_raw and en_raw != raw_title:
            name_en = en_raw

    # 从原始标题中分离中文名和英文名（格式："中文名 (English Name)"）
    name_zh = raw_title
    if name_en:
        # 从 "Xxx (Yyy)" 中提取中文部分
        zh_part = re.match(r'^(.+?)\s*\(', raw_title)
        if zh_part:
            name_zh = zh_part.group(1).strip()
        else:
            name_zh = raw_title

    # 封面图
    cover_m = re.search(r'class="class-cover-image"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
    cover_image = cover_m.group(1) if cover_m else ""

    # 截图（懒加载，用 data-src）
    screenshots = re.findall(r'class="figure"[^>]*>.*?data-src="([^"]+)"', html, re.DOTALL)

    # 支持的游戏版本（从版本检索区提取 mcver 参数）
    ver_idx = html.find("版本检索")
    ver_section = html[ver_idx:ver_idx + 3000] if ver_idx >= 0 else ""
    supported_versions = list(set(re.findall(r'mcver=(\d+\.\d+(?:\.\d+)?)', ver_section)))

    # 分类（面包屑）
    categories = re.findall(r'href="/class/category/\d+-1\.html"[^>]*>([^<]+)</a>', html)

    # 模组标签（标签: xxx yyy 形式）
    tags_idx = html.find("模组标签:")
    tags = []
    if tags_idx >= 0:
        tag_section = html[tags_idx:tags_idx + 300]
        tags = re.findall(r'>([^<]+)<', tag_section)
        tags = [t.strip() for t in tags if t.strip()]

    # Mod介绍（正文描述）
    description = ""
    intro_idx = html.find("Mod介绍")
    if intro_idx >= 0:
        segment = html[intro_idx:intro_idx + 10000]
        # 找到下一个 section 的起始位置
        section_markers = ["配方", "Mod关系", "Mod前置", "Mod联动",
                           "更新日志", "常见问题", "排行榜", "相关链接",
                           "text-area-post", "class-post-list"]
        end = len(segment)
        for marker in section_markers:
            idx = segment.find(marker)
            if idx > 200:
                end = min(end, idx)
        content = segment[:end]
        # 清理
        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
        content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
        content = re.sub(r"<img[^>]*>", "", content)
        content = re.sub(r"<br\s*/?>", "\n", content)
        content = re.sub(r"<p[^>]*>", "\n", content)
        # 提取文本行
        text = re.sub(r"<[^>]+>", "", content)
        text = html_module.unescape(text)
        text = re.sub(r"[ \t\r]+", " ", text).strip()
        # 清理：循环去掉开头的 section 标题标记（可能有多个，如 "Mod介绍介绍"）
        prefix_pat = r"^(?:Mod(?:介绍|教程|下载|讨论|特性|关系)|模组介绍|配方|前置Mod|联动Mod|更新日志|介绍)\s*"
        prev = None
        while prev != text:
            prev = text
            text = re.sub(prefix_pat, "", text).strip()
        # 过滤 MC百科站点头部广告 / 段落标题 / 页脚版权
        skip_fragments = [
            "MC百科的目标是", "MC百科(mcmod.cn)的目标",
            "提供Minecraft(我的世界)MOD(模组)物品资料介绍",
            "关于百科", "百科帮助", "开发日志", "捐赠百科",
            "联系百科", "意见反馈", "©Copyright MC百科",
            "mcmod.cn | ", "鄂ICP备", "鄂公网安备",
        ]
        # 段落标题：行首的 "简介" / "概述" / "正文"（后跟空格的情况）
        para_title_pat = r"^(?:概述|简介|正文)\s*"
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            # 去掉段落标题前缀（支持无空格分隔的情况）
            line = re.sub(para_title_pat, "", line).strip()
            # 去掉句中段落标题："！概述" / "。概述" → "！"
            line = re.sub(r"[。！？]\s*概述(?=[^\s])", lambda m: m.group(0)[0], line)
            if len(line) < 10:
                continue
            if any(line.startswith(p) for p in skip_fragments):
                continue
            # 过滤句中混入的页脚/版权文字
            if re.search(r"MC百科\s*\(mcmod\.cn\)\s*的?目标是", line):
                line = re.sub(r"MC百科\s*\(mcmod\.cn\)\s*的?目标是.*", "", line).strip()
            if len(line) < 10:
                continue
            if any(p in line for p in ["©Copyright MC百科", "鄂ICP备", "鄂公网安备", "mcmod.cn | ", "百科帮助", "开发日志"]):
                continue
            lines.append(line)
        description = "\n".join(lines[:8])  # 最多 8 行

    # Mod关系：前置Mod + 联动的Mod
    relationships = {"requires": [], "integrates": []}
    for m in re.finditer(r'(前置Mod|联动的Mod):</span><ul>(.*?)</ul>', html, re.DOTALL):
        label = m.group(1)
        ul = m.group(2)
        links = re.findall(r'href="(/class/(\d+)\.html)"[^>]*>([^<]+)</a>', ul)
        for _, cid, raw in links:
            raw = raw.strip()
            # Parse "Name (Alias)" pattern
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

    # 作者（从 Mod作者/开发团队 区提取 title 属性）
    author = None
    author_idx = html.find("Mod作者/开发团队")
    if author_idx >= 0:
        auth_section = html[author_idx:author_idx + 500]
        author_m = re.search(r'title="([^"-]+)', auth_section)
        if author_m:
            author = author_m.group(1).strip()

    # 是否有更新日志
    log_idx = html.find("更新日志")
    has_changelog = False
    if log_idx >= 0:
        has_changelog = "暂无日志" not in html[log_idx:log_idx + 500]

    # 模组状态：活跃 / 不活跃
    status = None
    status_m = re.search(r'class="class-status[^"]*"[^>]*>([^<]+)<', html)
    if status_m:
        status = status_m.group(1).strip()

    # 开源/闭源
    source_type = None
    src_m = re.search(r'class="class-source[^"]*"[^>]*>([^<]+)<', html)
    if src_m:
        st = src_m.group(1).strip()
        if "开源" in st or "open" in st.lower():
            source_type = "open_source"
        else:
            source_type = "closed_source"

    return {
        "name": name_zh or raw_title or name,
        "name_en": name_en,
        "name_zh": name_zh or raw_title or name,
        "url": url,
        "source": "mcmod.cn",
        "source_id": re.search(r"/class/(\d+)", url).group(1) if url else "",
        "type": "mod",
        "cover_image": cover_image,
        "screenshots": screenshots[:6],
        "supported_versions": supported_versions,
        "categories": categories,
        "tags": tags,
        "author": author,
        "status": status,
        "source_type": source_type,
        "description": description,
        "relationships": relationships if relationships["requires"] or relationships["integrates"] else None,
        "has_changelog": has_changelog,
    }


def search_mcmod(keyword: str, max_results: int = 5, content_type: str = "mod") -> list[dict]:
    """
    MC百科 搜索。

    content_type: "mod" | "item"
      - "mod"  → filter=0  → /class/ 页面（综合排序，主模组更靠前）
      - "item" → filter=3  → /item/  页面（物品/方块）
    """
    # filter 映射
    filter_map = {"mod": "0", "item": "3"}
    filter_val = filter_map.get(content_type, "0")

    key = _cache_key("mcmod", keyword, max_results, content_type)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    q = urllib.parse.quote(keyword)
    html = _curl(f"https://search.mcmod.cn/s?key={q}&filter={filter_val}")
    if not html:
        raise _SearchError(f"MC百科 网络请求失败（空响应）：{keyword}")
    if len(html) < 1000:
        raise _SearchError(f"MC百科 响应过短（可能被封）：{keyword}")

    idx = html.find("search-result-list")
    if idx == -1:
        raise _SearchError(f"MC百科 搜索结果页结构变化（无 search-result-list）：{keyword}")

    section = html[idx:idx + 15000]
    clean = re.sub(r"<em[^>]*>|</em>", "", section)

    # 物品用 /item/ URL，模组用 /class/ URL
    if content_type == "item":
        pairs = re.findall(
            r'href="(https://www\.mcmod\.cn/item/\d+\.html)">([^<]+)</a>',
            clean,
        )
    else:
        pairs = re.findall(
            r'href="(https://www\.mcmod\.cn/class/\d+\.html)">([^<]+)</a>',
            clean,
        )

    if not pairs:
        raise _SearchError(f"MC百科 无结果（{content_type}）：{keyword}")

    seen = set()
    results = []
    for raw_url, name in pairs:
        name = name.strip()
        # 用 URL 而非 name 去重
        if name and raw_url not in seen and not name.startswith("www."):
            seen.add(raw_url)
            page_html = _curl(raw_url)
            if content_type == "item":
                result = _parse_mcmod_item_result(page_html, raw_url, name)
            else:
                result = _parse_mcmod_result(page_html, raw_url, name)
            results.append(result)
            if len(results) >= max_results:
                break
    _cache_set("search", key, results)
    return results


def search_mcmod_author(author_name: str, max_mods: int = 20) -> list[dict]:
    """
    MC百科 按作者名搜索，返回该作者的所有模组。

    使用 filter=0 搜索，当结果包含 /author/ 页面时解析其所有模组链接。
    """
    key = _cache_key("mcmod_author", author_name, max_mods)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    q = urllib.parse.quote(author_name)
    html = _curl(f"https://search.mcmod.cn/s?key={q}&filter=0")
    if not html or len(html) < 1000:
        raise _SearchError(f"MC百科 作者搜索网络失败：{author_name}")

    idx = html.find("search-result-list")
    if idx == -1:
        raise _SearchError(f"MC百科 作者搜索结果页结构变化：{author_name}")

    section = html[idx:idx + 15000]
    clean = re.sub(r"<em[^>]*>|</em>", "", section)

    # 找 /author/ URL（搜索词精确匹配作者名时会出现）
    author_urls = re.findall(r'href="(https://www\.mcmod\.cn/author/\d+\.html)"', clean)
    if not author_urls:
        raise _SearchError(f"MC百科 未找到作者 [{author_name}] 的页面（作者名需精确匹配）")

    author_url = author_urls[0]

    # 解析作者页面，获取所有模组
    page_html = _curl(author_url)
    if not page_html or len(page_html) < 1000:
        raise _SearchError(f"MC百科 作者页面获取失败：{author_name}")

    # 从作者页面提取所有 /class/ 链接
    mod_links = re.findall(r'href="(/class/\d+\.html)"[^>]*>([^<]+)</a>', page_html)
    # 去重
    seen = set()
    unique_mods = []
    for url, name in mod_links:
        if url not in seen and name.strip() and not name.startswith("www."):
            seen.add(url)
            unique_mods.append((url, name.strip()))

    # 解析每个模组页面（取前 max_mods 个）
    results = []
    for url, name in unique_mods[:max_mods]:
        full_url = f"https://www.mcmod.cn{url}"
        page = _curl(full_url)
        if page and len(page) >= 1000:
            result = _parse_mcmod_result(page, full_url, name)
            results.append(result)

    _cache_set("search", key, results)
    return results


def search_modrinth(keyword: str, max_results: int = 5, project_type: str = "mod") -> list[dict]:
    """
    Modrinth API 搜索。

    project_type: "mod" | "shader" | "resourcepack"
    """
    key = _cache_key("modrinth", keyword, max_results, project_type)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    q = urllib.parse.quote(keyword)
    url = f"https://api.modrinth.com/v2/search?query={q}&index=relevance&limit={max_results}"
    try:
        raw = _curl(url)
        data = json.loads(raw)
    except Exception:
        return []

    results = []
    for hit in data.get("hits", []):
        pt = hit.get("project_type", "")
        if project_type and pt and pt != project_type:
            continue
        results.append({
            "name": hit.get("title", ""),
            "name_en": hit.get("title", ""),
            "name_zh": "",
            "url": f"https://modrinth.com/mod/{hit.get('slug','')}",
            "source": "modrinth",
            "source_id": hit.get("slug", ""),
            "type": pt or project_type or "mod",
            "snippet": hit.get("description", ""),
        })
    _cache_set("search", key, results)
    return results


def get_mod_info(mod_id: str) -> dict | None:
    """
    获取 mod 完整信息（Modrinth）。
    mod_id 可以是 slug 或 project_id。
    """
    cache_key = _cache_key("modinfo", mod_id)
    cached = _cache_get("mod", cache_key)
    if cached is not None:
        return cached

    try:
        raw = _curl(f"https://api.modrinth.com/v2/project/{mod_id}")
        data = json.loads(raw)
    except Exception:
        return None

    project_id = data.get("id", "")
    result = {
        "name": data.get("title", ""),
        "slug": data.get("slug", ""),
        "id": project_id,
        "description": data.get("description", ""),
        "body": (data.get("body") or "")[:5000],     # 截断至 5000 字符（--json 专用）
        "author": None,
        "license": data.get("license", {}).get("id", "") if isinstance(data.get("license"), dict) else (data.get("license", "") or ""),
        "categories": data.get("categories", []),
        "client_side": data.get("client_side", ""),
        "server_side": data.get("server_side", ""),
        "source_url": data.get("source_url") or None,
        "issues_url": data.get("issues_url") or None,
        "discord_url": data.get("discord_url") or None,
        "updated": data.get("updated", ""),
        "published": data.get("published", ""),
        "followers": data.get("followers", 0),
        "icon_url": data.get("icon_url") or "",
        "gallery": [g.get("url") for g in data.get("gallery", []) if g.get("url")][:10],   # 最多 10 张
        "latest_version": None,
        "game_versions": [],
        "loaders": [],
        "downloads": data.get("downloads", 0),
        "source": "modrinth",
        "url": f"https://modrinth.com/mod/{data.get('slug', '')}",
    }

    # 获取团队成员（作者）
    try:
        team_raw = _curl(f"https://api.modrinth.com/v2/project/{project_id}/members")
        team = json.loads(team_raw)
        for m in team:
            if m.get("role") in ("Owner", "Developer", "Project Lead"):
                result["author"] = m.get("user", {}).get("username") or m.get("user", {}).get("name", "")
                break
    except Exception:
        pass

    # 获取所有版本，聚合：按 mod 版本号分组（去掉 loader 前缀和 mc<ver>- 前缀）
    try:
        ver_raw = _curl(f"https://api.modrinth.com/v2/project/{project_id}/version?max=20")
        versions = json.loads(ver_raw)
        if versions:
            latest = versions[0]
            result["latest_version"] = latest.get("version_number", "")
            result["game_versions"] = latest.get("game_versions", [])
            result["loaders"] = latest.get("loaders", [])

            known_loaders = {"fabric", "forge", "neoforge", "quilt"}
            seen_mod_vers = {}
            for v in versions:
                vn = v.get("version_number", "")
                if not vn:
                    continue
                # Strip -<loader> suffix, then mc<game_ver>- prefix
                tmp = vn
                for ld in known_loaders:
                    if tmp.endswith(f"-{ld}"):
                        tmp = tmp[:-len(ld) - 1]
                        break
                mod_ver = re.sub(r'^mc[\d\.]+-', '', tmp) or tmp
                if mod_ver not in seen_mod_vers:
                    seen_mod_vers[mod_ver] = {"game_versions": set(), "loaders": set()}
                seen_mod_vers[mod_ver]["game_versions"].update(v.get("game_versions", []))
                seen_mod_vers[mod_ver]["loaders"].update(v.get("loaders", []))
            items = [(k, {"game_versions": sorted(v["game_versions"]), "loaders": sorted(v["loaders"])})
                     for k, v in seen_mod_vers.items()]
            result["version_groups"] = items[:5]

            # 最近 5 条 changelog
            changelogs = []
            for v in versions[:5]:
                cl = v.get("changelog", "").strip()
                if cl:
                    changelogs.append({
                        "version": v.get("version_number", ""),
                        "date": (v.get("date_published") or "")[:10],
                        "changelog": cl,
                    })
            result["changelogs"] = changelogs
    except Exception:
        pass

    _cache_set("mod", cache_key, result)
    return result


def search_author(username: str, max_results: int = 10) -> list[dict]:
    """
    Modrinth 按作者名搜索所有作品。

    使用 filter=authors:{username} 过滤，配合 query={username} 提高相关性。
    注意：filter 中的冒号保持未编码状态，Modrinth API 要求原始冒号。
    """
    key = _cache_key("author", username, max_results)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    q = urllib.parse.quote(username)
    # colon in filter=authors: must stay unencoded
    url = f"https://api.modrinth.com/v2/search?query={q}&filter=authors:{q}&index=relevance&limit={max_results}"
    try:
        raw = _curl(url)
        data = json.loads(raw)
    except Exception:
        return []

    results = []
    for hit in data.get("hits", []):
        results.append({
            "name": hit.get("title", ""),
            "name_en": hit.get("title", ""),
            "name_zh": "",
            "url": f"https://modrinth.com/mod/{hit.get('slug', '')}",
            "source": "modrinth",
            "source_id": hit.get("slug", ""),
            "type": hit.get("project_type", "mod"),
            "snippet": hit.get("description", ""),
        })
    _cache_set("search", key, results)
    return results


def get_mod_dependencies(mod_id: str, project_id: str = None) -> dict:
    """
    获取 mod 依赖树。
    返回 {"deps": {...}, "optional_count": int, "required_count": int}
    - deps: {mod_slug: {name, slug, client_side, server_side, type, url}}
    """
    cache_key = _cache_key("deps", mod_id)
    cached = _cache_get("mod", cache_key)
    if cached is not None:
        return cached

    try:
        if not project_id:
            proj_raw = _curl(f"https://api.modrinth.com/v2/project/{mod_id}")
            proj = json.loads(proj_raw)
            project_id = proj.get("id", mod_id)
    except Exception:
        return {"deps": {}, "optional_count": 0, "required_count": 0, "error": "PROJECT_NOT_FOUND"}

    deps = {}
    optional_count = 0
    required_count = 0
    try:
        raw = _curl(f"https://api.modrinth.com/v2/project/{project_id}/dependencies")
        deps_data = json.loads(raw)
    except Exception:
        return {"deps": {}, "optional_count": 0, "required_count": 0, "error": "API_ERROR"}

    for dep_proj in deps_data.get("projects", []):
        slug = dep_proj.get("slug", "")
        dep_id = dep_proj.get("id", "")
        client = dep_proj.get("client_side", "unknown")
        server = dep_proj.get("server_side", "unknown")

        if client == "required" or server == "required":
            dtype = "required"
            required_count += 1
        elif client == "optional" or server == "optional":
            dtype = "optional"
            optional_count += 1
        elif client == "unsupported" or server == "unsupported":
            dtype = "unsupported"
        else:
            dtype = "unknown"

        key = slug or dep_id
        deps[key] = {
            "name": dep_proj.get("title", slug or dep_id),
            "slug": slug,
            "id": dep_id,
            "client_side": client,
            "server_side": server,
            "type": dtype,
            "url": f"https://modrinth.com/mod/{slug}" if slug else None,
        }

    result = {"deps": deps, "optional_count": optional_count, "required_count": required_count}
    _cache_set("mod", cache_key, result)
    return result


def search_wiki(keyword: str, max_results: int = 5) -> list[dict]:
    """
    minecraft.wiki 搜索（使用 MediaWiki API，绕过 JS 渲染问题）。

    优先尝试直接访问文章（wiki 有 URL 自动补全），
    若返回搜索列表则用 MediaWiki API 获取结构化结果。
    """
    key = _cache_key("wiki", keyword, max_results)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    results = []

    # 方法1：尝试直接访问（URL 自动补全到文章页）
    q = urllib.parse.quote(keyword)
    html = _curl(f"https://minecraft.wiki/w/Special:Search?search={q}&go=Go")

    if html and len(html) >= 1000:
        m_title = re.search(r"<title>([^<]+)</title>", html)
        title_text = m_title.group(1) if m_title else ""
        is_direct = (
            'id="firstHeading"' in html
            and "Special:Search" not in title_text
        )

        if is_direct:
            # 直接跳转到文章页
            canon_m = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html)
            article_url = canon_m.group(1) if canon_m else (
                re.search(r'<meta[^>]+property="og:url"[^>]+content="([^"]+)"', html).group(1)
                if re.search(r'<meta[^>]+property="og:url"', html) else None
            )
            page_title = re.sub(r"\s*–\s*Minecraft Wiki.*", "", title_text).strip()
            h3s = re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.DOTALL)
            sections = [
                re.sub(r"<[^>]+>", "", h).strip()
                for h in h3s[:max_results]
                if re.sub(r"<[^>]+>", "", h).strip()
            ]
            results.append({
                "name": page_title,
                "name_en": page_title,
                "name_zh": "",
                "url": article_url or "",
                "source": "minecraft.wiki",
                "source_id": article_url.split("/")[-1] if article_url else "",
                "type": _infer_wiki_type(page_title, article_url or ""),
                "sections": sections,
            })
            _cache_set("search", key, results)
            return results

    # 方法2：使用 MediaWiki API 搜索（结构化 JSON，无需 JS）
    api_url = f"https://minecraft.wiki/api.php?action=query&list=search&srsearch={q}&format=json&srlimit={max_results}"
    raw = _curl(api_url)
    if raw:
        try:
            data = json.loads(raw)
            hits = data.get("query", {}).get("search", [])
            for hit in hits[:max_results]:
                title = hit.get("title", "")
                page_id = hit.get("pageid", 0)
                results.append({
                    "name": title,
                    "name_en": title,
                    "name_zh": "",
                    "url": f"https://minecraft.wiki/w/{urllib.parse.quote(title.replace(' ', '_'))}",
                    "source": "minecraft.wiki",
                    "source_id": str(page_id),
                    "type": _infer_wiki_type(title, ""),
                    "sections": [],
                })
        except Exception:
            pass

    _cache_set("search", key, results)
    return results


def _infer_wiki_type(name: str, url: str = "") -> str:
    """从 URL 路径推断 wiki 条目类型，fallback 到名称关键词。"""
    path = url.lower()
    if "/block/" in path or path.endswith("_block") or path.endswith("_ore"):
        return "block"
    if "/item/" in path or path.endswith("_item") or "/entity/" in path or "/mob/" in path:
        return "entity"
    if "/crafting" in path or "/brewing" in path or "/enchanting" in path:
        return "mechanic"

    n = name.lower()
    if any(k in n for k in ["block", "ore", "wood", "stone", "dirt", "sand"]):
        return "block"
    if any(k in n for k in ["sword", "pickaxe", "axe", "helmet", "chestplate",
                              "hoe", "shovel", "bow", "arrow", "shield"]):
        return "item"
    if any(k in n for k in ["zombie", "skeleton", "creeper", "enderman", "pig", "cow",
                              "sheep", "chicken", "spider", "slime", "blaze"]):
        return "entity"
    if any(k in n for k in ["crafting", "enchant", "brewing", "smelting",
                              "furnace", "anvil", "beacon"]):
        return "mechanic"
    return "other"


def read_wiki(url: str, max_paragraphs: int = 5) -> dict:
    """
    读取 wiki 页面正文。

    解析策略：
    - 构建 h2/h3/h4 标题层级结构（适配版本页如 Java_Edition_26.1）
    - 每个 h3/h4 叶章节提取其 intro paragraph
    - 版本页内容大量在 table 单元格中，也一并提取 item 名称
    - infobox / script / navbox 等无关区块提前过滤
    """
    html = _curl(url)
    if not html or len(html) < 500:
        return {"error": "NO_CONTENT"}

    m_title = re.search(r'<h1[^>]*id="firstHeading"[^>]*>(.*?)</h1>', html, re.DOTALL)
    title = html_module.unescape(re.sub(r"<[^>]+>", "", m_title.group(1)).strip()) if m_title else "UNKNOWN"

    # 提取正文区块
    m_content = re.search(
        r'<div[^>]+id="mw-content-text"[^>]*>(.*?)'
        r'(?:<div[^>]+class="[^"]*navbox|<div[^>]+id="catlinks|<div[^>]+class="[^"]*printfooter)',
        html, re.DOTALL
    )
    if not m_content:
        return {"error": "NO_CONTENT"}

    content_html = m_content.group(1)

    # 预过滤：script / infobox / wiki-logo
    content_html = re.sub(
        r'<script[^>]+type="application/ld\+json"[^>]*>.*?</script>',
        "", content_html, flags=re.DOTALL
    )
    content_html = re.sub(
        r'<table[^>]+class="[^"]*infobox[^"]*"[^>]*>.*?</table>',
        "", content_html, flags=re.DOTALL
    )
    content_html = re.sub(
        r'<table[^>]+class="[^"]*navbox[^"]*"[^>]*>.*?</table>',
        "", content_html, flags=re.DOTALL
    )

    # ── 解析所有 heading，构建层级 ──────────────────────────────────
    # 收集所有 heading：{level, id, text, start_offset}
    heading_map = []   # list of (level, h_id, text, start)
    for m in re.finditer(r'<h([234])[^>]*id="([^"]+)"[^>]*>(.*?)</h\1>', content_html, re.DOTALL):
        lvl = int(m.group(1))
        h_id = m.group(2)
        h_text = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        heading_map.append((lvl, h_id, h_text, m.start()))

    # ── 辅助：从原始 HTML 中提取纯文本 ──────────────────────────────
    def _clean_text(html_fragment: str) -> str:
        """去除所有 HTML 标签，转义实体，合并空白。"""
        text = re.sub(r"<[^>]+>", "", html_fragment)
        text = html_module.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _is_valid_para(text: str) -> bool:
        """判断是否为有意义的正文段落。"""
        if not text or len(text) < 20:
            return False
        if re.match(r"^[\#\.\[\/\{]", text):
            return False
        if text.startswith("History of") or text.startswith("v ") or text.startswith("[edit"):
            return False
        # JSON 碎片
        if text.startswith("{") and text.count('"') >= 4 and ":" in text:
            return False
        # 短名词短语过滤（通常是版本页 item 名，不是 intro）
        # item 名特征：短（<=35），不含连接词（and/which/that），不描述动作
        if len(text) <= 35:
            connectors = re.findall(r"\b(and|which|that|for|with|to|is|are|was|were|has|have|been|add|added|chang|fixed|updated|removed|introduced|included|prevent|allow|make|made|increas|decreas|affect)\b", text.lower())
            if not connectors:
                return False
        return True

    def _extract_table_items(table_html: str, max_items: int = 8) -> list[str]:
        """从 wiki table 中提取第一列的 item 名称列表。"""
        items = []
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
        for row in rows[1:]:  # 跳过表头
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
            if not cells:
                continue
            # 第一列：提取纯文本
            cell_text = _clean_text(cells[0])
            # 过滤按钮/控件类文字
            if cell_text and len(cell_text) >= 2 and not re.match(r"^[\s\-\d]+$", cell_text):
                items.append(cell_text)
            if len(items) >= max_items:
                break
        return items

    # ── 提取每个叶章节的正文内容 ──────────────────────────────────
    # 从 h2 顶层遍历，对每个 h2 及其下层 h3/h4 进行内容收集
    sections_output = []   # list of {"heading": "H3 Text", "parent": "H2 Text", "content": [lines]}
    paragraphs = []         # 兼容旧接口：把所有有意义段落平铺

    current_h2 = None       # 追踪当前父级 h2
    for i, (lvl, h_id, h_text, h_start) in enumerate(heading_map):
        # 跳过目录和无关 heading
        if h_id in ("mw-toc-heading", "References", "Navigation", "Videos", "Trivia"):
            continue
        # h2：更新当前父级标题，但不作为章节输出
        if lvl == 2:
            current_h2 = h_text
            continue

        # 该章节内容范围：heading 结束 → 下一 heading 开始
        next_start = heading_map[i + 1][3] if i + 1 < len(heading_map) else len(content_html)
        section_html = content_html[h_start:next_start]

        # 找 intro paragraph（<p> 或 <li> 中带描述性动词的条目）
        section_paragraphs = []
        for p in re.findall(r"<p[^>]*>(.*?)</p>", section_html, re.DOTALL):
            if re.search(r"<script|application/ld\+json", p, re.IGNORECASE):
                continue
            clean = _clean_text(p)
            if _is_valid_para(clean):
                section_paragraphs.append(clean)
                if len(section_paragraphs) >= 2:  # 每个章节最多 2 段
                    break

        # 也从 <li> 中提取描述性条目（版本页的 intro 常在 <li> 里）
        if not section_paragraphs:
            for li in re.findall(r"<li[^>]*>(.*?)</li>", section_html, re.DOTALL):
                clean = _clean_text(li)
                # 描述性 <li>：较长（>=50 chars）且以动词开头
                if len(clean) >= 50 and re.match(r"^(Added|Changed|Fixed|Updated|Removed|Introduced|Can now|Made|New|Affects?|Allows?|Prevents?|Makes?|Provides?)", clean):
                    section_paragraphs.append(clean)
                    break

        # 提取 table 中的 item 名称（版本页的主要内容）
        table_items = []
        if len(section_paragraphs) < 2:
            tables = re.findall(r"<table[^>]*class=\"[^\"]*wikitable[^\"]*\"[^>]*>.*?</table>",
                                section_html, re.DOTALL)
            for tbl in tables[:3]:  # 最多 3 个 table
                items = _extract_table_items(tbl, max_items=10)
                table_items.extend(items)

        # 合并输出
        section_lines = section_paragraphs[:2]
        if table_items and not section_paragraphs:
            section_lines = [f"[{len(table_items)} items: {', '.join(table_items[:6])}{'...' if len(table_items) > 6 else ''}]"]
        elif table_items:
            section_lines.append(f"[+ {len(table_items)} table items]")

        if section_lines:
            sections_output.append({
                "heading": h_text,
                "parent": current_h2,
                "content": section_lines,
            })
            paragraphs.extend(section_lines)

        if len(paragraphs) >= max_paragraphs:
            paragraphs = paragraphs[:max_paragraphs]
            break

    return {
        "name": title,
        "url": url,
        "source": "minecraft.wiki",
        "content": paragraphs,
        "_sections": sections_output,   # 内部结构化数据，供 CLI 渲染层级
    }

def search_all(keyword: str, max_per_source: int = 3, timeout: int = 12,
               content_type: str = "mod") -> dict:
    """
    三平台并行搜索，返回统一格式。
    timeout: 整体超时秒数
    content_type: "mod" | "item"（仅影响 MC百科）
    """
    results = {"mcmod.cn": [], "modrinth": [], "minecraft.wiki": []}
    pe = _platform_enabled

    def _wrap_mcmod():
        try:
            return search_mcmod(keyword, max_per_source, content_type=content_type)
        except Exception:
            return []

    def _wrap_mr():
        try:
            return search_modrinth(keyword, max_per_source)
        except Exception:
            return []

    def _wrap_wiki():
        try:
            return search_wiki(keyword, max_per_source)
        except Exception:
            return []

    workers = []
    futures_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        if pe["mcmod.cn"]:
            f = ex.submit(_wrap_mcmod)
            futures_map[f] = "mcmod.cn"
            workers.append(f)
        if pe["modrinth"]:
            f = ex.submit(_wrap_mr)
            futures_map[f] = "modrinth"
            workers.append(f)
        if pe["minecraft.wiki"]:
            f = ex.submit(_wrap_wiki)
            futures_map[f] = "minecraft.wiki"
            workers.append(f)

        for future in concurrent.futures.as_completed(workers):
            key = futures_map[future]
            try:
                results[key] = future.result(timeout=timeout)
            except Exception:
                results[key] = []

    return results
