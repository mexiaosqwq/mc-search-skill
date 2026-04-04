#!/usr/bin/env python3
"""
mc-search 核心搜索模块
统一接口：四平台并行搜索 + 统一结果格式 + 智能路由
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
# 解析常量
# ─────────────────────────────────────────
_MIN_HTML_LEN = 1000        # HTML 内容最小长度阈值（class/mod 页面）
_MIN_HTML_LEN_ITEM = 500    # HTML 内容最小长度阈值（item/recipe 页面）
_MIN_PARAGRAPH_LEN = 20     # 正文段落最小长度
_MIN_SHORT_TEXT_LEN = 35    # 短文本判定阈值（用于判断是否为 item 名）
_MIN_DESCRIPTIVE_LI_LEN = 50  # 描述性 <li> 最小长度
_MAX_SECTION_PARAGRAPHS = 2  # 每 wiki 章节最多段落数
_MIN_TABLE_CELL_LEN = 2     # table cell 最小长度
_MAX_TABLE_ITEMS = 8        # table 最大 item 数
_MAX_BODY_CHARS = 5000      # ModRinth 详情 body 字段最大截断长度
_MAX_VERSION_GROUPS = 5     # 版本组最多显示数
_MAX_CHANGELOGS = 5         # 更新日志最多显示数
_SOURCE_MAX = {              # search_all 每平台最多结果（按 content_type 分级）
    "mod": 3,
    "item": 10,
    "entity": 6,
    "biome": 6,
    "dimension": 4,
}
_MAX_ITEM_DESC_PARAGRAPHS = 5   # 物品页面描述最多段落数
_MAX_MOD_DESC_PARAGRAPHS = 8    # 模组页面描述最多段落数

# ─────────────────────────────────────────
# Wiki 解析辅助（read_wiki / read_wiki_zh 共用）
# ─────────────────────────────────────────
_EN_CONNECTORS_RE = re.compile(
    r"\b(and|which|that|for|with|to|is|are|was|were|has|have|been|"
    r"add|added|chang|fixed|updated|removed|introduced|included|"
    r"prevent|allow|make|made|increas|decreas|affect)\b",
    re.IGNORECASE,
)
_ZH_CONNECTORS_RE = re.compile(
    r"\b(和|与|或|但|是|为|有|在|被|由|可|会|能|将|已|使)\b",
)


def _clean_html_text(html_fragment: str) -> str:
    """去除所有 HTML 标签，转义实体，合并空白。"""
    text = re.sub(r"<[^>]+>", "", html_fragment)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_valid_paragraph(text: str, lang: str = "en") -> bool:
    """判断是否为有意义的正文段落。

    lang: "en"（默认）仅英文连接词；"zh" 额外检测中文连接词。
    """
    if not text or len(text) < _MIN_PARAGRAPH_LEN:
        return False
    if re.match(r"^[\#\.\[\/\{]", text):
        return False
    # JSON 碎片
    if text.startswith("{") and text.count('"') >= 4 and ":" in text:
        return False
    # 短名词短语过滤（通常是版本页 item 名，不是 intro）
    if len(text) <= _MIN_SHORT_TEXT_LEN:
        en_found = _EN_CONNECTORS_RE.search(text)
        if not en_found:
            if lang == "zh":
                if not _ZH_CONNECTORS_RE.search(text):
                    return False
            else:
                return False
    return True


# ─────────────────────────────────────────
# 缓存系统
# ─────────────────────────────────────────

_cache_enabled = False
_cache_ttl = 3600  # 默认 1 小时


def _cache_dir() -> Path:
    return Path(os.path.expanduser("~/.cache/mc-search"))


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

_platform_enabled = {"mcmod.cn": True, "modrinth": True, "minecraft.wiki": True, "minecraft.wiki/zh": True}


def set_platform_enabled(mcmod: bool = True, modrinth: bool = True, wiki: bool = True, wiki_zh: bool = True):
    """由 CLI 调用控制哪些平台启用。"""
    global _platform_enabled
    _platform_enabled = {
        "mcmod.cn": mcmod,
        "modrinth": modrinth,
        "minecraft.wiki": wiki,
        "minecraft.wiki/zh": wiki_zh,
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
    if r.returncode != 0:
        return ""  # 静默失败，由调用方通过长度检查处理
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
                    skip_prefixes = [
                        "MC百科的目标是", "MC百科(mcmod.cn)的目标",
                        "提供Minecraft(我的世界)MOD(模组)物品资料介绍",
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
                        if len(line) < 10:
                            continue
                        if any(line.startswith(p) for p in skip_prefixes):
                            continue
                        if any(p in line for p in ("MCmod does not have a description", "for navigation", "player can edit description")):
                            continue
                        lines.append(line)
                    description = "\n".join(lines[:_MAX_ITEM_DESC_PARAGRAPHS])
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
        "has_recipe": "recipe" in html.lower() or "合成" in html,
    }


def get_item_recipe(item_url: str) -> dict:
    """
    获取物品的合成表信息（降级方案：返回截图URL列表+材料文本）。
    MC百科 item 页面合成表区块以 <table class="recipe-table"> 为主。
    """
    key = _cache_key("recipe", item_url)
    cached = _cache_get("item", key)
    if cached is not None:
        return cached

    html = _curl(item_url)
    if not html or len(html) < _MIN_HTML_LEN_ITEM:
        return {"error": "NO_CONTENT"}

    result = {"recipe_images": [], "recipe_materials": []}

    # 提取合成表图片（recipe-table 中的 img）
    recipe_imgs = re.findall(
        r'<table[^>]*class="[^"]*recipe[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"',
        html, re.DOTALL | re.IGNORECASE
    )
    result["recipe_images"] = [img for img in recipe_imgs if img and not img.startswith("data:")]

    # 提取材料文本（从 recipe-table 附近的文本节点）
    material_patterns = [
        r'配方：</td><td[^>]*>(.*?)</td>',
        r'材料：</td><td[^>]*>(.*?)</td>',
        r'合成素材：</td><td[^>]*>(.*?)</td>',
    ]
    for pat in material_patterns:
        m = re.search(pat, html, re.DOTALL)
        if m:
            mats = re.findall(r'<img[^>]+alt="([^"]+)"', m.group(1), re.IGNORECASE)
            if mats:
                result["recipe_materials"] = [r.strip() for r in mats if r.strip()]
                break
            # 降级：提取纯文本
            text = re.sub(r"<[^>]+>", "", m.group(1))
            text = html_module.unescape(text).strip()
            if text:
                result["recipe_materials"] = [t.strip() for t in text.split() if t.strip()]
                break

    _cache_set("item", key, result)
    return result


# ─────────────────────────────────────────
# 模组解析（MC百科 /class/ 页面）
# ─────────────────────────────────────────

def _extract_mcmod_cover(html: str) -> tuple[str, list[str]]:
    """提取封面图和截图。返回 (cover_image, screenshots)。"""
    cover_m = re.search(r'class="class-cover-image"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
    cover_image = cover_m.group(1) if cover_m else ""
    screenshots = re.findall(r'class="figure"[^>]*>.*?data-src="([^"]+)"', html, re.DOTALL)
    return cover_image, screenshots


def _extract_mcmod_versions(html: str) -> list[str]:
    """从版本检索区提取支持的游戏版本列表。"""
    ver_idx = html.find("版本检索")
    ver_section = html[ver_idx:ver_idx + 3000] if ver_idx >= 0 else ""
    return list(set(re.findall(r'mcver=(\d+\.\d+(?:\.\d+)?)', ver_section)))


def _extract_mcmod_categories(html: str) -> tuple[list[str], list[str]]:
    """提取分类（面包屑）和模组标签。返回 (categories, tags)。"""
    categories = re.findall(r'href="/class/category/\d+-1\.html"[^>]*>([^<]+)</a>', html)
    tags_idx = html.find("模组标签:")
    tags = []
    if tags_idx >= 0:
        tag_section = html[tags_idx:tags_idx + 300]
        tags = re.findall(r'>([^<]+)<', tag_section)
        tags = [t.strip() for t in tags if t.strip()]
    return categories, tags


def _extract_mcmod_description(html: str) -> str:
    """提取 Mod 介绍正文描述。"""
    intro_idx = html.find("Mod介绍")
    if intro_idx < 0:
        return ""
    segment = html[intro_idx:intro_idx + 10000]
    section_markers = ["配方", "Mod关系", "Mod前置", "Mod联动",
                       "更新日志", "常见问题", "排行榜", "相关链接",
                       "text-area-post", "class-post-list"]
    end = len(segment)
    for marker in section_markers:
        idx = segment.find(marker)
        if idx > 200:
            end = min(end, idx)
    content = segment[:end]
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
    content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
    content = re.sub(r"<img[^>]*>", "", content)
    content = re.sub(r"<br\s*/?>", "\n", content)
    content = re.sub(r"<p[^>]*>", "\n", content)
    text = re.sub(r"<[^>]+>", "", content)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t\r]+", " ", text).strip()
    prefix_pat = r"^(?:Mod(?:介绍|教程|下载|讨论|特性|关系)|模组介绍|配方|前置Mod|联动Mod|更新日志|介绍)\s*"
    prev = None
    while prev != text:
        prev = text
        text = re.sub(prefix_pat, "", text).strip()
    skip_fragments = [
        "MC百科的目标是", "MC百科(mcmod.cn)的目标",
        "提供Minecraft(我的世界)MOD(模组)物品资料介绍",
        "关于百科", "百科帮助", "开发日志", "捐赠百科",
        "联系百科", "意见反馈", "©Copyright MC百科",
        "mcmod.cn | ", "鄂ICP备", "鄂公网安备",
    ]
    para_title_pat = r"^(?:概述|简介|正文)\s*"
    # 匹配论坛元数据，如 (7)Mod讨论 (2)
    _mod_meta_pat = re.compile(r"^\(\d+\)\s*Mod(?:讨论|教程)\s*\(\d+\)")
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        line = re.sub(para_title_pat, "", line).strip()
        line = re.sub(r"[。！？]\s*概述(?=[^\s])", lambda m: m.group(0)[0], line)
        if len(line) < 10:
            continue
        if any(line.startswith(p) for p in skip_fragments):
            continue
        if _mod_meta_pat.match(line):
            continue
        if re.search(r"MC百科\s*\(mcmod\.cn\)\s*的?目标是", line):
            line = re.sub(r"MC百科\s*\(mcmod\.cn\)\s*的?目标是.*", "", line).strip()
        if len(line) < 10:
            continue
        if any(p in line for p in ["©Copyright MC百科", "鄂ICP备", "鄂公网安备", "mcmod.cn | ", "百科帮助", "开发日志"]):
            continue
        lines.append(line)
    return "\n".join(lines[:_MAX_MOD_DESC_PARAGRAPHS])


def _extract_mcmod_relationships(html: str) -> dict:
    """提取前置Mod和联动Mod关系。返回 {"requires": [], "integrates": []}。"""
    relationships = {"requires": [], "integrates": []}
    for m in re.finditer(r'(前置Mod|联动的Mod):</span><ul>(.*?)</ul>', html, re.DOTALL):
        label = m.group(1)
        ul = m.group(2)
        links = re.findall(r'href="(/class/(\d+)\.html)"[^>]*>([^<]+)</a>', ul)
        for _, cid, raw in links:
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
    return relationships


def _extract_mcmod_author_status(html: str) -> tuple:
    """提取作者、状态、开源属性。返回 (author, status, source_type)。"""
    author = None
    author_idx = html.find("Mod作者/开发团队")
    if author_idx >= 0:
        auth_section = html[author_idx:author_idx + 500]
        author_m = re.search(r'title="([^"-]+)', auth_section)
        if author_m:
            author = author_m.group(1).strip()

    log_idx = html.find("更新日志")
    has_changelog = False
    if log_idx >= 0:
        has_changelog = "暂无日志" not in html[log_idx:log_idx + 500]

    status = None
    status_m = re.search(r'class="class-status[^"]*"[^>]*>([^<]+)<', html)
    if status_m:
        status = status_m.group(1).strip()

    source_type = None
    src_m = re.search(r'class="class-source[^"]*"[^>]*>([^<]+)<', html)
    if src_m:
        st = src_m.group(1).strip()
        source_type = "open_source" if ("开源" in st or "open" in st.lower()) else "closed_source"

    return author, status, source_type, has_changelog


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
        zh_part = re.match(r'^(.+?)\s*\(', raw_title)
        name_zh = zh_part.group(1).strip() if zh_part else raw_title

    # 调用辅助函数提取各字段
    cover_image, screenshots = _extract_mcmod_cover(html)
    supported_versions = _extract_mcmod_versions(html)
    categories, tags = _extract_mcmod_categories(html)
    description = _extract_mcmod_description(html)
    relationships = _extract_mcmod_relationships(html)
    author, status, source_type, has_changelog = _extract_mcmod_author_status(html)

    # 原版内容识别：class/1 是 MC百科"原版内容"分类
    is_vanilla = bool(re.search(r"/class/1\.html", url))

    return {
        "name": name_zh or raw_title or name,
        "name_en": name_en,
        "name_zh": name_zh or raw_title or name,
        "url": url,
        "source": "mcmod.cn",
        "source_id": re.search(r"/class/(\d+)", url).group(1) if url else "",
        "type": "mod",
        "is_vanilla": is_vanilla,
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
    if len(html) < _MIN_HTML_LEN:
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

    # 去重并限制数量
    seen = set()
    limited_pairs = []
    for raw_url, name in pairs:
        name = name.strip()
        if name and raw_url not in seen and not name.startswith("www."):
            seen.add(raw_url)
            limited_pairs.append((raw_url, name))
            if len(limited_pairs) >= max_results:
                break

    # 并行抓取详情页（每个结果单独请求太慢）
    def _fetch_one(args):
        raw_url, name = args
        page_html = _curl(raw_url)
        if content_type == "item":
            return _parse_mcmod_item_result(page_html, raw_url, name)
        return _parse_mcmod_result(page_html, raw_url, name)

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(limited_pairs), 4)) as ex:
        results = list(ex.map(_fetch_one, limited_pairs))

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
    if not html or len(html) < _MIN_HTML_LEN:
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
    if not page_html or len(page_html) < _MIN_HTML_LEN:
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
        if page and len(page) >= _MIN_HTML_LEN:
            result = _parse_mcmod_result(page, full_url, name)
            results.append(result)

    _cache_set("search", key, results)
    return results


def search_modrinth(keyword: str, max_results: int = 5, project_type: str = "mod") -> dict:
    """
    Modrinth API 搜索。

    返回 {"results": [...], "total": int, "returned": int}
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
        return {"results": [], "total": 0, "returned": 0}

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
    total = data.get("total_hits", 0)
    ret = {"results": results, "total": total, "returned": len(results)}
    _cache_set("search", key, ret)
    return ret


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
        "body": (data.get("body") or "")[:_MAX_BODY_CHARS],
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
            result["version_groups"] = items[:_MAX_VERSION_GROUPS]

            # 最近 5 条 changelog
            changelogs = []
            for v in versions[:_MAX_CHANGELOGS]:
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


def _search_wiki_impl(
    keyword: str,
    base_url: str,
    cache_prefix: str,
    source: str,
    use_title_for_name_en: bool,
    use_title_for_name_zh: bool,
    add_variant: bool,
    max_results: int = 5,
) -> list[dict]:
    """
    minecraft.wiki 搜索通用实现。

    参数:
        base_url: wiki 根 URL
        cache_prefix: 缓存 key 前缀
        source: source 字段值
        use_title_for_name_en: True 时 name_en=page_title，否则 name_en=""
        use_title_for_name_zh: True 时 name_zh=page_title，否则 name_zh=""
        add_variant: 是否添加 ?variant=zh-cn
    """
    key = _cache_key(cache_prefix, keyword, max_results)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    results = []
    q = urllib.parse.quote(keyword)

    # 方法1：尝试直接访问
    html = _curl(f"{base_url}/w/Special:Search?search={q}&go=Go")

    if html and len(html) >= _MIN_HTML_LEN:
        m_title = re.search(r"<title>([^<]+)</title>", html)
        title_text = m_title.group(1) if m_title else ""
        is_direct = (
            'id="firstHeading"' in html
            and "Special:Search" not in title_text
            and "Search results" not in title_text
            and "的搜索结果" not in title_text
        )

        if is_direct:
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
            if add_variant and article_url and "variant=zh-cn" not in article_url:
                separator = "&" if "?" in article_url else "?"
                article_url = article_url + separator + "variant=zh-cn"
            results.append({
                "name": page_title,
                "name_en": page_title if use_title_for_name_en else "",
                "name_zh": page_title if use_title_for_name_zh else "",
                "url": article_url or "",
                "source": source,
                "source_id": article_url.split("/")[-1] if article_url else "",
                "type": _infer_wiki_type(page_title, article_url or ""),
                "sections": sections,
            })
            _cache_set("search", key, results)
            return results

    # 方法2：MediaWiki API 搜索
    api_url = f"{base_url}/api.php?action=query&list=search&srsearch={q}&format=json&srlimit={max_results}"
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
                    "name_en": title if use_title_for_name_en else "",
                    "name_zh": title if use_title_for_name_zh else "",
                    "url": f"{base_url}/w/{urllib.parse.quote(title.replace(' ', '_'))}",
                    "source": source,
                    "source_id": str(page_id),
                    "type": _infer_wiki_type(title, ""),
                    "sections": [],
                })
        except Exception:
            pass

    _cache_set("search", key, results)
    return results


def search_wiki(keyword: str, max_results: int = 5) -> list[dict]:
    """minecraft.wiki 搜索（英文）。"""
    return _search_wiki_impl(
        keyword=keyword,
        base_url="https://minecraft.wiki",
        cache_prefix="wiki",
        source="minecraft.wiki",
        use_title_for_name_en=True,
        use_title_for_name_zh=False,
        add_variant=False,
        max_results=max_results,
    )


def search_wiki_zh(keyword: str, max_results: int = 5) -> list[dict]:
    """minecraft.wiki/zh 中文 wiki 搜索。"""
    return _search_wiki_impl(
        keyword=keyword,
        base_url="https://zh.minecraft.wiki",
        cache_prefix="wiki_zh",
        source="minecraft.wiki/zh",
        use_title_for_name_en=False,
        use_title_for_name_zh=True,
        add_variant=True,
        max_results=max_results,
    )


def _infer_wiki_type(name: str, url: str = "") -> str:
    """从 URL 路径推断 wiki 条目类型，fallback 到名称关键词。"""
    path = url.lower()
    if "/block/" in path or path.endswith("_block") or path.endswith("_ore"):
        return "block"
    if "/item/" in path or path.endswith("_item") or "/entity/" in path or "/mob/" in path:
        return "entity"
    if "/crafting" in path or "/brewing" in path or "/enchanting" in path:
        return "mechanic"
    if "/biome/" in path or "_biome" in path:
        return "biome"
    if "/dimension/" in path or "_dimension" in path or "/nether" in path or "/the_end" in path or "/overworld" in path:
        return "dimension"

    n = name.lower()
    if any(k in n for k in ["block", "ore", "wood", "stone", "dirt", "sand"]):
        return "block"
    if any(k in n for k in ["sword", "pickaxe", "axe", "helmet", "chestplate",
                              "hoe", "shovel", "bow", "arrow", "shield"]):
        return "item"
    if any(k in n for k in ["zombie", "skeleton", "creeper", "enderman", "pig", "cow",
                              "sheep", "chicken", "spider", "slime", "blaze",
                              "wither", "ender_dragon", "ghast", "zombie_pigman",
                              "silverfish", "vex", "evoker", "vindicator"]):
        return "entity"
    if any(k in n for k in ["crafting", "enchant", "brewing", "smelting",
                              "furnace", "anvil", "beacon"]):
        return "mechanic"
    # biome 关键词
    if any(k in n for k in ["forest", "desert", "taiga", "savanna", "plains",
                             "mountain", "swamp", "jungle", "ice", "ocean",
                             "river", "mushroom", "badlands", "savanna", "cherry"]):
        return "biome"
    # dimension 关键词
    if any(k in n for k in ["nether", "the_end", "overworld", "end_dim", "nether_dim"]):
        return "dimension"
    # 中文关键词
    if any(k in n for k in ["剑", "刀", "斧", "镐", "铲", "锄", "弓", "箭", "盾",
                              "盔甲", "头盔", "胸甲", "护腿", "靴子", "钻石", "铁",
                              "金", "铜", "绿宝石", "下界合金", "鞘翅"]):
        return "item"
    if any(k in n for k in ["方块", "石头", "泥土", "沙子", "圆石", "木板", "矿石",
                              "原木", "树叶", "玻璃", "冰", "雪", "草", "花", "蘑菇"]):
        return "block"
    if any(k in n for k in ["僵尸", "骷髅", "苦力怕", "末影人", "猪", "牛", "羊",
                              "鸡", "蜘蛛", "史莱姆", "烈焰人", "凋灵", "末影龙",
                              "恶魂", "猪灵", "潜影贝", "卫道士", "唤魔者"]):
        return "entity"
    if any(k in n for k in ["下界", "末地", "主世界", "地狱", "末地城", "要塞"]):
        return "dimension"
    if any(k in n for k in ["森林", "沙漠", "针叶林", "热带雨林", "沼泽", "海洋",
                              "河流", "高山", "平原", "蘑菇岛"]):
        return "biome"
    if any(k in n for k in ["合成", "附魔", "酿造", "熔炉", "高炉", "烟熏",
                              "铁砧", "制图台", "锻造台", "砂轮"]):
        return "mechanic"
    return "other"


def _read_wiki_impl(url: str, max_paragraphs: int,
                    para_skip_prefixes: tuple[str, ...],
                    heading_skip_ids: set[str],
                    source: str) -> dict:
    """
    读取 wiki 页面正文（英文 / 中文共用实现）。

    参数：
      para_skip_prefixes: 段落前缀跳过词（如 "History of", "v ", "历史", "编辑"）
      heading_skip_ids:   heading id 跳过集合
      source:             返回结果的 source 字段值
    """
    html = _curl(url)
    if not html or len(html) < _MIN_HTML_LEN_ITEM:
        return {"error": "NO_CONTENT"}

    m_title = re.search(r'<h1[^>]*id="firstHeading"[^>]*>(.*?)</h1>', html, re.DOTALL)
    title = html_module.unescape(re.sub(r"<[^>]+>", "", m_title.group(1)).strip()) if m_title else "UNKNOWN"

    m_content = re.search(
        r'<div[^>]+id="mw-content-text"[^>]*>(.*?)'
        r'(?:<div[^>]+class="[^"]*navbox|<div[^>]+id="catlinks|<div[^>]+class="[^"]*printfooter)',
        html, re.DOTALL
    )
    if not m_content:
        return {"error": "NO_CONTENT"}

    content_html = m_content.group(1)

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
    heading_map = []
    for m in re.finditer(r'<h([234])[^>]*id="([^"]+)"[^>]*>(.*?)</h\1>', content_html, re.DOTALL):
        lvl = int(m.group(1))
        h_id = m.group(2)
        h_text = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        heading_map.append((lvl, h_id, h_text, m.start()))

    # ── 辅助 ──────────────────────────────────────────────────────
    def _extract_table_items(table_html: str, max_items: int = 8) -> list[str]:
        """从 wiki table 中提取第一列的 item 名称列表。"""
        items = []
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
        for row in rows[1:]:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
            if not cells:
                continue
            cell_text = _clean_html_text(cells[0])
            if cell_text and len(cell_text) >= _MIN_TABLE_CELL_LEN and not re.match(r"^[\s\-\d]+$", cell_text):
                items.append(cell_text)
            if len(items) >= max_items:
                break
        return items

    # ── 提取每个叶章节的正文内容 ──────────────────────────────────
    sections_output = []
    paragraphs = []
    current_h2 = None

    for i, (lvl, h_id, h_text, h_start) in enumerate(heading_map):
        if h_id in heading_skip_ids:
            continue
        if lvl == 2:
            current_h2 = h_text
            continue

        next_start = heading_map[i + 1][3] if i + 1 < len(heading_map) else len(content_html)
        section_html = content_html[h_start:next_start]

        section_paragraphs = []
        for p in re.findall(r"<p[^>]*>(.*?)</p>", section_html, re.DOTALL):
            if re.search(r"<script|application/ld\+json", p, re.IGNORECASE):
                continue
            clean = _clean_html_text(p)
            if any(clean.startswith(prefix) for prefix in para_skip_prefixes):
                continue
            if _is_valid_paragraph(clean, lang="en" if source == "minecraft.wiki" else "zh"):
                section_paragraphs.append(clean)
                if len(section_paragraphs) >= _MAX_SECTION_PARAGRAPHS:
                    break

        # 英文 wiki：从 <li> 中提取描述性条目（版本页的 intro 常在 <li> 里）
        if source == "minecraft.wiki" and not section_paragraphs:
            for li in re.findall(r"<li[^>]*>(.*?)</li>", section_html, re.DOTALL):
                clean = _clean_html_text(li)
                if len(clean) >= _MIN_DESCRIPTIVE_LI_LEN and re.match(
                        r"^(Added|Changed|Fixed|Updated|Removed|Introduced|Can now|Made|New|Affects?|Allows?|Prevents?|Makes?|Provides?)", clean):
                    section_paragraphs.append(clean)
                    break

        # 英文 wiki：提取 table 中的 item 名称（版本页的主要内容）
        table_items = []
        if source == "minecraft.wiki" and len(section_paragraphs) < _MAX_SECTION_PARAGRAPHS:
            tables = re.findall(r"<table[^>]*class=\"[^\"]*wikitable[^\"]*\"[^>]*>.*?</table>",
                                section_html, re.DOTALL)
            for tbl in tables[:3]:
                items = _extract_table_items(tbl, max_items=_MAX_TABLE_ITEMS)
                table_items.extend(items)

        section_lines = section_paragraphs[:_MAX_SECTION_PARAGRAPHS]
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
        "source": source,
        "content": paragraphs,
        "_sections": sections_output,
    }


def read_wiki(url: str, max_paragraphs: int = 5) -> dict:
    """读取 minecraft.wiki 英文 wiki 页面正文。"""
    return _read_wiki_impl(
        url, max_paragraphs,
        para_skip_prefixes=("History of", "v ", "[edit"),
        heading_skip_ids={"mw-toc-heading", "References", "Navigation", "Videos", "Trivia"},
        source="minecraft.wiki",
    )


def read_wiki_zh(url: str, max_paragraphs: int = 5) -> dict:
    """读取 minecraft.wiki/zh 中文 wiki 页面正文。"""
    return _read_wiki_impl(
        url, max_paragraphs,
        para_skip_prefixes=("历史", "编辑", "History of", "v ", "[edit"),
        heading_skip_ids={"mw-toc-heading", "References", "Navigation", "Videos", "Trivia",
                          "参考资料", "导航", "视频", "琐事"},
        source="minecraft.wiki/zh",
    )


def search_all(keyword: str, max_per_source: int = 3, timeout: int = 12,
               content_type: str = "mod", fuse: bool = False) -> dict:
    """
    四平台并行搜索，返回统一格式。
    timeout: 整体超时秒数
    content_type: "mod" | "item" | "entity" | "biome" | "dimension"
      - 同时决定每平台最大结果数（_SOURCE_MAX 字典）
    fuse: True 时返回 {"results": [...融合列表...], "platform_stats": {platform: {total, returned}}}
         False 时返回 {platform: [results]}（向后兼容）
    """
    # 按 content_type 分级设置每平台结果数
    per_source = _SOURCE_MAX.get(content_type, max_per_source)
    results = {"mcmod.cn": [], "modrinth": [], "minecraft.wiki": [], "minecraft.wiki/zh": []}
    stats = {"mcmod.cn": {"total": 0, "returned": 0},
             "modrinth": {"total": 0, "returned": 0},
             "minecraft.wiki": {"total": 0, "returned": 0},
             "minecraft.wiki/zh": {"total": 0, "returned": 0}}
    pe = _platform_enabled

    def _wrap_mcmod():
        try:
            ct = content_type if content_type in ("mod", "item") else "mod"
            return search_mcmod(keyword, per_source, content_type=ct)
        except Exception:
            return []

    def _wrap_mr():
        try:
            return search_modrinth(keyword, per_source)
        except Exception:
            return {"results": [], "total": 0, "returned": 0}

    def _wrap_wiki():
        try:
            return search_wiki(keyword, per_source)
        except Exception:
            return []

    def _wrap_wiki_zh():
        try:
            return search_wiki_zh(keyword, per_source)
        except Exception:
            return []

    workers = []
    futures_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
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
        if pe["minecraft.wiki/zh"]:
            f = ex.submit(_wrap_wiki_zh)
            futures_map[f] = "minecraft.wiki/zh"
            workers.append(f)

        for future in concurrent.futures.as_completed(workers):
            key = futures_map[future]
            try:
                raw = future.result(timeout=timeout)
            except Exception:
                raw = [] if key != "modrinth" else {"results": [], "total": 0, "returned": 0}

            if key == "modrinth" and isinstance(raw, dict):
                results[key] = raw.get("results", [])
                stats[key] = {"total": raw.get("total", 0), "returned": raw.get("returned", 0)}
            else:
                results[key] = raw if isinstance(raw, list) else []
                stats[key] = {"total": len(results[key]), "returned": len(results[key])}

        # 取消未完成的 futures，避免后台线程泄漏
        for f in workers:
            f.cancel()

    if fuse:
        fused = _fuse_results(results, content_type=content_type, query_keyword=keyword)
        return {"results": fused, "platform_stats": stats}
    return results


def _is_cjk(text: str) -> bool:
    """检测文本是否包含 CJK 字符。"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def _score_relevance(query: str, hit: dict, content_type: str = "mod") -> float:
    """计算单条搜索结果与查询词的相关性分数（0-110）。

    评分规则：
      - 精确等于 → 100
      - 完整包含查询词 → 50
      - 名称以查询词开头 → 30
      - 查询词包含于名称 → 20
      - 无匹配 → 0
    对于 item 类型，wiki 来源的分数额外 +5（vanilla 物品权威来源）。
    """
    if not query or not hit:
        return 0.0

    # 决定用哪个名字字段评分
    name_zh = hit.get("name_zh") or ""
    name_en = hit.get("name_en") or ""
    name = hit.get("name") or ""

    q = query.strip().lower()
    if not q:
        return 0.0

    # 优先用搜索词对应语言的名称
    if _is_cjk(q):
        primary = name_zh
        secondary = name_en
    else:
        primary = name_en
        secondary = name_zh

    # 如果主字段为空，用次字段
    if not primary:
        primary = secondary
        secondary = ""

    primary_lc = primary.lower()
    secondary_lc = secondary.lower()

    score = 0

    # 精确等于
    if primary_lc == q:
        score = 100
    # 完整包含
    elif q in primary_lc:
        score = 50
    # 名称以查询词开头
    elif primary_lc.startswith(q):
        score = 30
    # 查询词包含于名称
    elif q in primary_lc:
        score = 20
    # 次字段检查
    elif secondary_lc and q == secondary_lc:
        score = 90   # 次字段精确匹配，略低于主字段精确
    elif secondary_lc and q in secondary_lc:
        score = 40

    # item 类型：wiki 是 vanilla 物品的权威来源，+5 加权
    platform = hit.get("_platform", hit.get("source", ""))
    if content_type == "item" and platform in ("minecraft.wiki", "minecraft.wiki/zh"):
        score += 5

    return score


# 平台优先级（数字越小越权威，用于 tiebreaker）
_PLATFORM_PRIORITY = {
    "mcmod.cn": 0,
    "modrinth": 1,
    "minecraft.wiki": 2,
    "minecraft.wiki/zh": 3,
}

# 按 content_type 调整的平台优先级
_CONTENT_PLATFORM_PRIORITY = {
    "item": {"minecraft.wiki": 0, "minecraft.wiki/zh": 1, "mcmod.cn": 2, "modrinth": 3},
    "entity": {"minecraft.wiki": 0, "minecraft.wiki/zh": 1, "mcmod.cn": 2, "modrinth": 3},
    "biome": {"minecraft.wiki": 0, "minecraft.wiki/zh": 1, "mcmod.cn": 2, "modrinth": 3},
    "block": {"minecraft.wiki": 0, "minecraft.wiki/zh": 1, "mcmod.cn": 2, "modrinth": 3},
    "mechanic": {"minecraft.wiki": 0, "minecraft.wiki/zh": 1, "mcmod.cn": 2, "modrinth": 3},
    "dimension": {"minecraft.wiki": 0, "minecraft.wiki/zh": 1, "mcmod.cn": 2, "modrinth": 3},
}


def _fuse_results(results: dict, content_type: str = "mod", query_keyword: str = "") -> list[dict]:
    """跨平台去重合并，按相关性分数排序。

    排序规则：相关性分数 DESC → 平台优先级 ASC（tiebreaker）
    content_type 用于调整不同类型内容的平台优先级。
    """
    platform_prio = (_CONTENT_PLATFORM_PRIORITY.get(content_type)
                     or {"mcmod.cn": 0, "modrinth": 1, "minecraft.wiki": 2, "minecraft.wiki/zh": 3})

    # 第一步：给所有结果打分，同时过滤无关结果
    scored = []
    for platform, hits in results.items():
        for h in hits:
            # 当搜索 mod 时，过滤 wiki 的 type="other" 结果（非模组相关内容）
            if content_type == "mod" and platform in ("minecraft.wiki", "minecraft.wiki/zh"):
                if h.get("type") == "other":
                    continue  # 跳过 wiki 的杂项结果
            score = _score_relevance(query_keyword, h, content_type=content_type)
            # platform_prio: 数值越小越权威；sort by (-score, priority) 使 同分时高优先级（即 priority 大）排前面
            priority = platform_prio.get(platform, 99)
            scored.append({**h, "_platform": platform, "_score": score, "_priority": priority})

    # 第二步：同名去重（按分数从高到低，同分时保留平台权威度高的）
    by_name = {}
    for entry in scored:
        key = (entry.get("name_zh") or entry.get("name_en") or entry.get("name") or "").lower()
        if not key:
            continue
        if key not in by_name:
            by_name[key] = entry
        elif entry["_score"] > by_name[key]["_score"]:
            by_name[key] = entry
        elif entry["_score"] == by_name[key]["_score"]:
            # 同分时：priority 数值大（即更权威）的赢
            if entry["_priority"] > by_name[key]["_priority"]:
                by_name[key] = entry

    # 第三步：排序（分数 DESC，同分时 priority DESC）
    sorted_entries = sorted(by_name.values(),
                            key=lambda e: (e["_score"] * -1, e["_priority"] * -1))

    # 第四步：构建融合结果
    fused = []
    for entry in sorted_entries:
        merged = {k: v for k, v in entry.items() if not k.startswith("_")}
        # 收集所有同名结果的平台，并去重
        platforms = [e["_platform"] for e in scored
                     if (e.get("name_zh") or e.get("name_en") or e.get("name") or "").lower()
                     == (entry.get("name_zh") or entry.get("name_en") or entry.get("name") or "").lower()]
        merged["_sources"] = list(dict.fromkeys(platforms))  # 去重并保持顺序
        if len(merged["_sources"]) > 1:
            merged["source"] = "|".join(merged["_sources"])
        fused.append(merged)

    return fused
