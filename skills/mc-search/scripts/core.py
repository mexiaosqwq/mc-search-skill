#!/usr/bin/env python3
"""mc-search 核心搜索模块：四平台并行搜索 + 统一结果格式 + 智能路由"""

import base64, concurrent.futures, hashlib, html as html_module, json, logging, os, re, time, urllib.parse, urllib.request
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class SearchError(Exception):
    """搜索过程中的可区分错误。"""
    pass


HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


# URL 解析工具
def _extract_url_id(url: str, prefix: str) -> str | None:
    """从 URL 提取 ID。/class/2785.html -> 2785"""
    m = re.search(rf'{re.escape(prefix)}(\d+)', url)
    return m.group(1) if m else None

def _extract_url_slug(url: str, prefix: str) -> str | None:
    """从 URL 提取 slug。/mod/sodium -> sodium"""
    m = re.search(rf'{re.escape(prefix)}([^/\s"<>\)]+)', url)
    return m.group(1) if m else None

def _build_absolute_url(base: str, path: str) -> str:
    """构建绝对 URL"""
    return path if path.startswith('http') else base.rstrip('/') + '/' + path.lstrip('/')

def _extract_title(html: str) -> str:
    """从 HTML 提取标题"""
    m = re.search(r"<title>([^<]+)</title>", html)
    return m.group(1).strip() if m else ""


# 常量定义
MIN_HTML_LEN = 1000        # class/mod 页面最小 HTML 长度
MIN_HTML_LEN_ITEM = 500    # item/recipe 页面最小 HTML 长度
_MIN_PARAGRAPH_LEN = 20    # 正文段落最小长度
_MIN_SHORT_TEXT_LEN = 35   # 短文本判定阈值
_MIN_DESCRIPTIVE_LI_LEN = 50  # 描述性<li>最小长度
_MIN_DESCRIPTION_LINE_LEN = 10  # 描述行最小长度
_MIN_SECTION_MARKER_DISTANCE = 200  # section marker 最小距离
_MAX_SECTION_PARAGRAPHS = 100  # 每 wiki 章节最多段落数
_MIN_TABLE_CELL_LEN = 2
_MAX_TABLE_ITEMS = 50
_MAX_VERSION_GROUPS = 5
_MAX_CHANGELOGS = 5
_MAX_FETCH_WORKERS = 4
_MAX_SCREENSHOTS = 0        # 默认不返回截图（可配置）
_MAX_GALLERY = 0            # 默认不返回画廊（可配置）
_MAX_TAG_SECTION_LEN = 500
_EXTERNAL_LINK_EXCLUDE_DOMAINS = ["curseforge", "modrinth", "github", "discord", "wikipedia", "mcbbs", "jenkins", "archive"]
_MAX_TAG_TEXT_LEN = 20
_MAX_SEARCH_SEGMENT = 2000
_MAX_DESCRIPTION_SEGMENT = 70000
_MAX_SEARCH_DESC_CHARS = 500      # search 命令描述最大字符数
_MAX_AUTHOR_SECTION = 50000
_MAX_INFO_TABLE_SECTION = 2000
_MAX_VERSION_SECTION_LEN = 3000  # 版本检索区域长度
_MAX_VERSIONS_FETCH = 200
_DEFAULT_RESULTS_PER_PLATFORM = 15
_WIKI_SNIPPET_SEGMENT_LEN = 5000
_WIKI_FALLBACK_SEGMENT_LEN = 20000
_WIKI_FULL_SCAN_LEN = 60000       # 英文 wiki infobox 可达 30000+ 字符
_WIKI_FIRST_TABLE_SEGMENT_LEN = 10000
_MIN_SNIPPET_LINE_LEN = 30
_MIN_CJK_SEGMENT_LEN = 8
_MAX_CJK_FALLBACK_SEGMENTS = 3
_MAX_WIKI_SECTIONS = 20
_MAX_TABLES_PER_SECTION = 10
_MAX_MCMOD_AUTHORS = 10
_KNOWN_LOADERS = {"fabric", "forge", "neoforge", "quilt"}
_MAX_WIKI_INTRO_PARAGRAPHS = 3


def _truncate_screenshots(screenshots: list, max_count: int) -> tuple[list, dict | None]:
    """截断截图列表并返回截断元信息。返回 (limited_list, truncated_meta_or_None)。"""
    limited = screenshots[:max_count]
    total = len(screenshots)
    meta = {"screenshots": {"returned": max_count, "total": total}} if total > max_count else None
    return limited, meta


# 搜索评分常量
_SCORE_EXACT_MATCH_BASE = 100
_SCORE_EXACT_MATCH_MAX_BONUS = 20
_SCORE_EXACT_MATCH_BONUS_FACTOR = 2
_SCORE_PREFIX_BASE = 60
_SCORE_PREFIX_MAX_BONUS = 15
_SCORE_PREFIX_BONUS_FACTOR = 2
_SCORE_CONTAINS_BASE = 30
_SCORE_CONTAINS_MAX_POS_BONUS = 10
_SCORE_CONTAINED_IN_QUERY = 20
_SCORE_MIN_LENGTH_FOR_CONTAINED = 2
_SCORE_SNIPPET_BONUS = 5
_SCORE_WIKI_ITEM_BONUS = 5
_SCORE_SECONDARY_PENALTY = 10
_SCORE_SECONDARY_MIN = 10
_SCORE_MULTI_PLATFORM_BONUS = 10

# Wiki 过滤关键词
_WIKI_SNIPPET_SKIP_KEYWORDS = [
    'disambiguation', 'may refer to',
    '本條目介紹的是', '本条目介绍的是',
    '關於其他用法', '关于其他用法',
    '消歧義', '消歧义',
    '請在加入後', '请在加入后',
    '具體要求', '具体要求',
]

# Wiki Heading 跳过 ID
_WIKI_HEADING_SKIP_IDS = {
    "mw-toc-heading", "References", "Navigation", "Videos", "Trivia",
    "p-personal-label", "p-navigation-label", "p-tb-label"
}
_WIKI_ZH_HEADING_SKIP_IDS = _WIKI_HEADING_SKIP_IDS | {
    "参考资料", "参考", "导航", "视频", "琐事",
    "p-interaction-label", "p-print-label", "p-toolbox-label"
}

# MC 百科搜索过滤器
_MCMOD_FILTER_MOD = "0"
_MCMOD_FILTER_ITEM = "3"
_MCMOD_FILTER_MODPACK_ZH = "2"
_MCMOD_FILTER_MODPACK_ALT = "20"
_MCMOD_FILTER_MODPACK_OLD = "10"    # 旧版整合包过滤（较少结果）

# MC百科描述过滤 — 公共跳过前缀（item 和 class 页面共用）
_MCMOD_COMMON_SKIP_PREFIXES = (
    "MC百科的目标是", "MC百科(mcmod.cn)的目标",
    "提供Minecraft(我的世界)MOD(模组)物品资料介绍",
)

# MC百科整合包多 filter 策略（按优先级）
_MCMOD_MODPACK_FILTERS = [
    _MCMOD_FILTER_MODPACK_ZH,   # 中文关键词效果最佳
    _MCMOD_FILTER_MOD,           # 模组搜索（补充）
    _MCMOD_FILTER_MODPACK_ALT,   # 另一种整合包过滤
    _MCMOD_FILTER_MODPACK_OLD,   # 旧版过滤（较少结果）
]

# === 项目类型常量 ===
# 文本类内容类型（MC百科 + Modrinth 都支持）
_TEXT_CONTENT_TYPES = {"mod", "item", "modpack"}

# 视觉类内容类型（仅 Modrinth 支持）
_VISUAL_CONTENT_TYPES = {"shader", "resourcepack"}

# === 平台优先级（数字越小越权威）===
# 默认优先级：MC百科 > Modrinth > Wiki（适用于 mod 和 item）
# 其他类型：Wiki > MC百科 > Modrinth（适用于 entity/biome/block/mechanic/dimension）
_CONTENT_PLATFORM_PRIORITY = {
    "default": {"mcmod.cn": 0, "modrinth": 1, "minecraft.wiki": 2, "minecraft.wiki/zh": 3},
    "other": {"minecraft.wiki": 0, "minecraft.wiki/zh": 1, "mcmod.cn": 2, "modrinth": 3},
}

# Wiki 解析辅助（read_wiki / read_wiki_zh 共用）

_EN_CONNECTORS_RE = re.compile(
    r"\b(and|which|that|for|with|to|is|are|was|were|has|have|been|"
    r"add|added|chang|fixed|updated|removed|introduced|included|"
    r"prevent|allow|make|made|increas|decreas|affect)\b",
    re.IGNORECASE,
)
_ZH_CONNECTORS_RE = re.compile(
    r"(和|与|或|但|是|为|有|在|被|由|可|会|能|将|已|使)",
)
# 匹配论坛元数据，如 (7)Mod讨论 (2) 或 Mod讨论 (19)
_MOD_META_PAT = re.compile(r"^(?:\(\d+\)\s*)?Mod(?:讨论|教程)\s*\(\d+\)")


def clean_html_text(html_fragment: str) -> str:
    """去除所有 HTML 标签，转义实体，合并空白。"""
    text = re.sub(r"<[^>]+>", "", html_fragment)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_valid_paragraph(text: str, lang: str = "en") -> bool:
    """判断是否为有意义的正文段落。lang="zh"时检测中文连接词。"""
    if not text or len(text) < _MIN_PARAGRAPH_LEN:
        return False
    if re.match(r"^[\#\.\[\/\{]", text):
        return False
    if text.startswith("{") and text.count('"') >= 4 and ":" in text:
        return False
    # 过滤维护模板/消歧义提示
    text_lower = text.lower()
    if any(kw.lower() in text_lower for kw in _WIKI_SNIPPET_SKIP_KEYWORDS):
        return False
    if len(text) > _MIN_SHORT_TEXT_LEN:
        return True
    # 短文本：需含连接词
    if lang == "zh":
        return bool(_EN_CONNECTORS_RE.search(text) or _ZH_CONNECTORS_RE.search(text))
    return bool(_EN_CONNECTORS_RE.search(text))



# 缓存系统

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
    except (OSError, json.JSONDecodeError) as e:
        logger.debug(f"Cache read failed: {e}")
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
    except OSError as e:
        logger.debug(f"Cache write failed: {e}")


def set_cache(enabled: bool, ttl: int = 3600):
    """由 CLI 调用启用缓存。"""
    global _cache_enabled, _cache_ttl
    _cache_enabled = enabled
    _cache_ttl = ttl


def set_screenshot_limit(limit: int):
    """设置截图返回数量限制。默认 0（不返回），可调整为任意正整数。"""
    global _MAX_SCREENSHOTS, _MAX_GALLERY
    _MAX_SCREENSHOTS = limit
    _MAX_GALLERY = limit


# 平台开关

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


def curl(url: str, timeout: int = 10) -> str:
    """发起HTTP请求，返回HTML内容（失败返回空字符串）。"""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": HTTP_HEADERS["User-Agent"],
                "Accept": HTTP_HEADERS["Accept"],
                "Accept-Language": HTTP_HEADERS["Accept-Language"],
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        logger.warning(f"HTTP {e.code} for {url}: {e.reason}")
        return ""
    except urllib.error.URLError as e:
        logger.warning(f"URL error for {url}: {e.reason}")
        return ""
    except Exception as e:
        logger.warning(f"Request failed for {url}: {e}")
        return ""


def _fetch_json(url: str, default=None) -> dict | list | None:
    """统一处理 JSON 获取，失败返回默认值。"""
    try:
        raw = curl(url)
        if not raw:
            return default if default is not None else {}
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed for {url}: {e}")
        return default if default is not None else {}


# 物品/方块解析（MC百科 /item/ 页面）

def _parse_mcmod_item_result(html: str, url: str, name: str) -> dict:
    """从 MC百科 item 页面解析。物品页面结构与 class 页面完全不同。"""
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
                    text = re.sub(r"<[^>]+>", "", segment)
                    text = html_module.unescape(text)
                    text = re.sub(r"[ \t\r]+", " ", text).strip()
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
    screenshots_limited, screenshots_meta = _truncate_screenshots(screenshots, _MAX_SCREENSHOTS)

    result = {
        "name": name_zh or raw_title or name,
        "name_en": name_en,
        "name_zh": name_zh or raw_title or name,
        "url": url,
        "source": "mcmod.cn",
        "source_id": re.search(r"/item/(\d+)", url).group(1) if url else "",
        "type": "item",
        "cover_image": cover_image,
        "screenshots": screenshots_limited,
        "category": category,
        "max_durability": max_durability,
        "max_stack": max_stack,
        "source_mod_name": mod_name,
        "source_mod_url": mod_url,
        "description": description[:_MAX_SEARCH_DESC_CHARS] if description else "",
        "has_recipe": "recipe" in html.lower() or "合成" in html,
    }

    # 截断元信息
    if screenshots_meta:
        result["_truncated"] = screenshots_meta

    return result


def fetch_item_recipe(item_url: str) -> dict:
    """获取物品合成表信息。返回 {"recipe_images": [], "recipe_materials": []}。"""
    key = _cache_key("recipe", item_url)
    cached = _cache_get("item", key)
    if cached is not None:
        return cached

    html = curl(item_url)
    if not html or len(html) < MIN_HTML_LEN_ITEM:
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



# 模组解析（MC百科 /class/ 页面）

def _parse_mcmod_title(raw_title: str) -> tuple[str, str]:
    """从 MC百科 <title> 解析中文名和英文名。返回 (name_zh, name_en)。"""
    name_zh = raw_title
    name_en = ""
    title_match = re.match(r"^(.+?)\s*(?:\(([^)]+)\))?\s*-", raw_title)
    if title_match:
        name_zh = title_match.group(1).strip()
        name_en = title_match.group(2).strip() if title_match.group(2) else ""
    return name_zh, name_en


def _extract_mcmod_cover(html: str) -> tuple[str, list[str]]:
    """提取封面图和截图。返回 (cover_image, screenshots)。"""
    cover_m = re.search(r'class="class-cover-image"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
    cover_image = cover_m.group(1) if cover_m else ""
    # 支持多种懒加载图片属性
    screenshots = []
    for attr in ['data-src', 'data-lazy-src', 'data-original']:
        screenshots.extend(re.findall(f'{attr}="([^"]+)"', html))
    # 去重并保持顺序
    screenshots = list(dict.fromkeys(screenshots))
    return cover_image, screenshots


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

    content = segment[:end]
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
    content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
    content = re.sub(r"<img[^>]*>", "", content)
    content = re.sub(r"<br\s*/?>", "\n", content)
    content = re.sub(r"<p[^>]*>", "\n", content)
    text = re.sub(r"<[^>]+>", "", content)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t\r]+", " ", text).strip()

    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if len(line) < _MIN_DESCRIPTION_LINE_LEN:
            continue
        lines.append(line)

    return "\n".join(lines)


def _extract_mcmod_modpack_stats(html: str) -> list[str]:
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
    # 提取元数据
    name_zh, name_en, author, status, categories = _extract_mcmod_modpack_metadata(html)

    # 封面图和截图
    cover_image, screenshots = _extract_mcmod_cover(html)

    # 描述
    description = _extract_mcmod_modpack_description(html)

    # 统计信息（仅版本列表）
    supported_versions = _extract_mcmod_modpack_stats(html)

    # 整合包类型判定（是否为 MC百科官方收录的整合包）
    is_official_modpack = bool(re.search(r'/modpack/\d+\.html', url))

    # 截图截断信息
    screenshots_limited, screenshots_meta = _truncate_screenshots(screenshots, _MAX_SCREENSHOTS)

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
        "screenshots": screenshots_limited,
        "supported_versions": supported_versions,
        "categories": categories,
        "author": author,
        "status": status,
        "description": description[:_MAX_SEARCH_DESC_CHARS] if description else "",
        "snippet": description[:_MAX_SEARCH_DESC_CHARS] if description else "",  # 与 search 接口保持一致
        "downloads": 0,  # MC百科整合包通常不提供下载量统计
    }

    # 截断元信息
    if screenshots_meta:
        result["_truncated"] = screenshots_meta

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
    content = segment[:end]
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
    content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
    content = re.sub(r"<img[^>]*>", "", content)
    content = re.sub(r"<br\s*/?>", "\n", content)
    content = re.sub(r"<p[^>]*>", "\n", content)
    content = re.sub(r"</li>", "\n", content)  # 列表项单独一行
    text = re.sub(r"<[^>]+>", "", content)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t\r]+", " ", text).strip()
    prefix_pat = r"^(?:Mod(?:介绍|教程|下载|讨论|特性|关系)|模组介绍|配方|前置Mod|联动Mod|更新日志|介绍)\s*"
    prev = None
    while prev != text:
        prev = text
        text = re.sub(prefix_pat, "", text).strip()
    skip_fragments = list(_MCMOD_COMMON_SKIP_PREFIXES) + [
        "关于百科", "百科帮助", "开发日志", "捐赠百科",
        "联系百科", "意见反馈", "©Copyright MC百科",
        "mcmod.cn | ", "鄂ICP备", "鄂公网安备",
    ]
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
        if any(p in line for p in ["©Copyright MC百科", "鄂ICP备", "鄂公网安备", "mcmod.cn | ", "百科帮助", "开发日志"]):
            continue
        # 过滤 HTML 残留（如 <li data-id=...）
        if re.search(r"<[a-z]+[\s>]", line, re.IGNORECASE):
            continue
        lines.append(line)
    # 不限制段落数，返回完整描述（JSON 模式下用户可自行处理）
    return "\n".join(lines)


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
    skip_names = {"CaffeineMC"}
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
            is_org = name in skip_names
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
        stats["page_views"] = int(views_m.group(1).replace(',', ''))

    # 收藏数
    fav_m = re.search(r'收藏[:：]?\s*([\d,\.]+)', html)
    if fav_m:
        stats["favorites"] = int(fav_m.group(1).replace(',', ''))

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


def _extract_mcmod_external_links(html: str) -> dict:
    """提取模组的外部平台链接。返回 {"official": "...", "curseforge": "...", ...}。"""
    links = {}

    # 辅助函数：解码 MC百科的 Base64 混淆链接
    def _decode_mcmod_link(encoded: str) -> str:
        try:
            # URL 中可能有缺失的 padding，补齐
            padding = 4 - len(encoded) % 4
            if padding != 4:
                encoded += "=" * padding
            decoded = base64.b64decode(encoded).decode("utf-8")
            return decoded
        except (ValueError, UnicodeDecodeError) as e:
            logger.debug(f"Link decode failed: {e}")
            return ""

    # 收集所有解码后的链接
    all_decoded = []
    obfuscated = re.findall(r'link\.mcmod\.cn/target/([A-Za-z0-9+/=]+)', html)
    for encoded in obfuscated:
        url = _decode_mcmod_link(encoded)
        if url and url.startswith("http"):
            all_decoded.append(url)

    # 分类存储链接
    curseforge_links = []
    github_links = []

    for url in all_decoded:
        # 官方网站（非已知平台的独立域名）
        if "official" not in links:
            if not any(x in url for x in _EXTERNAL_LINK_EXCLUDE_DOMAINS):
                links["official"] = url

        # CurseForge
        if "curseforge.com" in url:
            curseforge_links.append(url)

        # Modrinth
        elif "modrinth.com" in url and "modrinth" not in links:
            links["modrinth"] = url

        # GitHub
        elif "github.com" in url:
            if not any(x in url for x in ["/blob/", "/wiki", "/issues", "/pull/"]):
                github_links.append(url)

        # Wiki（非 GitHub Wiki）
        elif "wiki" in url.lower() and "github.com" not in url and "wiki" not in links:
            links["wiki"] = url

        # Discord
        elif ("discord.gg" in url or "discord.com/invite" in url) and "discord" not in links:
            links["discord"] = url

        # Jenkins CI
        elif "jenkins" in url.lower() or "ci." in url and "jenkins" not in links:
            links["jenkins"] = url

        # MCBBS
        elif "mcbbs" in url and "mcbbs" not in links:
            links["mcbbs"] = url

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

    # 方式2：提取明文链接（向后兼容）
    if "curseforge" not in links:
        cf = re.search(r'https?://(?:www\.)?curseforge\.com/minecraft/mc-mods/[^/\s"<>\)]+', html)
        if cf:
            links['curseforge'] = cf.group(0)

    if "modrinth" not in links:
        mr = re.search(r'https?://modrinth\.com/(?:mod|shader|resourcepack)/[^/\s"<>\)]+', html)
        if mr:
            links['modrinth'] = mr.group(0)

    if "github" not in links:
        all_gh = re.findall(r'https?://github\.com/[^\s"<>\)]+', html)
        main_gh = [u.rstrip(').,') for u in all_gh
                   if not any(x in u for x in ['/issues', '/commit', '/blob', '/wiki', '/releases/tag', '/pull/'])]
        if main_gh:
            links['github'] = min(main_gh, key=len)

    if "discord" not in links:
        dc = re.search(r'https?://(?:www\.)?(?:discord\.gg|discord\.com/invite)/[^\s"<>\)]+', html)
        if dc:
            links['discord'] = dc.group(0).rstrip(').,')

    # 提取跨平台 IDs（用于精确关联 Modrinth/CF）
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


def parse_mcmod_result(html: str, url: str, name: str) -> dict:
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
    external_links = _extract_mcmod_external_links(html)

    # 新增：提取完整作者团队和社区数据
    author_team = _extract_mcmod_author_team(html)
    community_stats = _extract_mcmod_community_stats(html)

    # 提取 class_id 并获取资料列表
    class_id = re.search(r"/class/(\d+)", url).group(1) if url else ""
    content_list = _extract_mcmod_content_list(html, class_id) if class_id else {}

    # 原版内容识别：class/1 是 MC百科"原版内容"分类
    is_vanilla = bool(re.search(r"/class/1\.html", url))

    # 截图截断信息
    screenshots_limited, screenshots_meta = _truncate_screenshots(screenshots, _MAX_SCREENSHOTS)

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
        "screenshots": screenshots_limited,
        "supported_versions": supported_versions,
        "categories": categories,
        "tags": tags,
        "author": author,  # 兼容性：保留单一作者
        "author_team": author_team if author_team else None,  # 新增：完整作者团队
        "community_stats": community_stats if any(community_stats.values()) else None,  # 新增：社区数据
        "status": status,
        "source_type": source_type,
        "description": description,  # 返回完整描述（由调用方决定是否截断）
        "relationships": relationships if relationships["requires"] or relationships["integrates"] else None,
        "has_changelog": has_changelog,
        "external_links": external_links if external_links else None,
        "content_list": content_list or None,
    }

    # 截断元信息
    if screenshots_meta:
        result["_truncated"] = screenshots_meta

    return result


def _parallel_fetch_with_fallback(items: list, fetch_func: callable, max_workers: int,
                                   filter_none: bool = True) -> list:
    """并行抓取带降级。返回结果列表（可选过滤None）。"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        results = []
        try:
            results = list(ex.map(fetch_func, items))
        except Exception as e:
            logger.warning(f"Parallel fetch failed: {e}, falling back to sequential")
            # 回退到逐个抓取，跳过失败项
            for item in items:
                try:
                    results.append(fetch_func(item))
                except (SearchError, OSError) as e:
                    logger.warning(f"Fetch failed for item: {e}")
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


def _parse_mcmod_search_results(html: str, content_type: str, keyword: str) -> list[tuple[str, str]]:
    """解析MC百科搜索结果页面，提取URL和名称对"""
    idx = html.find("search-result-list")
    if idx == -1:
        raise SearchError(f"MC百科 搜索结果页结构变化（无 search-result-list）：{keyword}")

    # 找到结果区域的结束位置（分页区域）
    end_idx = html.find('class="pagination"', idx)
    if end_idx == -1:
        end_idx = len(html)
    section = html[idx:end_idx]
    clean = re.sub(r"<em[^>]*>|</em>", "", section)

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
    for tier in [0, 1, 2, 3]:
        result.extend(tiers[tier])
    return result


def _fetch_mcmod_details(limited_pairs: list[tuple[str, str]], content_type: str) -> list[dict]:
    """并行抓取模组详情页"""
    if not limited_pairs:
        return []

    def _fetch_one(args):
        raw_url, name = args
        page_html = curl(raw_url)
        if content_type == "item":
            return _parse_mcmod_item_result(page_html, raw_url, name)
        elif content_type == "modpack":
            return _parse_mcmod_modpack_result(page_html, raw_url, name)
        return parse_mcmod_result(page_html, raw_url, name)

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

    # 1. 缓存检查
    key = _cache_key("mcmod", keyword, max_results, content_type)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    # 2. 构建搜索URL
    urls = _build_mcmod_search_urls(keyword, content_type)

    # 3. 执行搜索
    html = curl(urls[0])
    if not html:
        raise SearchError(f"MC百科 网络请求失败（空响应）：{keyword}")
    if len(html) < MIN_HTML_LEN:
        raise SearchError(f"MC百科 响应过短（可能被封）：{keyword}")

    # 4. 解析结果
    all_pairs = _parse_mcmod_search_results(html, content_type, keyword)

    # 5. 按匹配度排序
    reordered = _rank_by_name_match(all_pairs, keyword)

    # 6. 截断到 max_results
    limited_pairs = reordered[:max_results]

    # 7. 抓取详情
    results = _fetch_mcmod_details(limited_pairs, content_type)

    # 8. 截断描述（控制 token 消耗）
    for r in results:
        if r.get('description') and len(r['description']) > _MAX_SEARCH_DESC_CHARS:
            r['description'] = r['description'][:_MAX_SEARCH_DESC_CHARS]

    # 9. 缓存并返回
    _cache_set("search", key, results)
    return results


def search_mcmod_author(author_name: str, max_mods: int = 20) -> list[dict]:
    """MC百科按作者搜索。返回模组列表。"""
    key = _cache_key("mcmod_author", author_name, max_mods)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

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

    # 并行解析每个模组页面（使用通用辅助函数）
    def _fetch_mod(args):
        url, name = args
        full_url = f"https://www.mcmod.cn{url}"
        page = curl(full_url)
        if page and len(page) >= MIN_HTML_LEN:
            return parse_mcmod_result(page, full_url, name)
        return None

    limited_mods = unique_mods[:max_mods]
    results = _parallel_fetch_with_fallback(
        limited_mods, _fetch_mod,
        max_workers=min(len(limited_mods), _MAX_FETCH_WORKERS)
    )

    _cache_set("search", key, results)
    return results


def search_mcmod_modpack(keyword: str, max_results: int = 5) -> list[dict]:
    """MC百科整合包搜索。尝试多个filter策略，返回结果列表。"""
    key = _cache_key("mcmod_modpack", keyword, max_results)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    q = urllib.parse.quote(keyword)

    # 多 filter 策略：按优先级尝试不同的 filter 值
    all_pairs = []
    seen = set()

    for filter_val in _MCMOD_MODPACK_FILTERS:
        html = curl(f"https://search.mcmod.cn/s?key={q}&filter={filter_val}")
        if not html:
            continue

        idx = html.find("search-result-list")
        if idx == -1:
            continue

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

    # 并行抓取详情页
    def _fetch_one(args):
        raw_url, name = args
        page_html = curl(raw_url)
        return _parse_mcmod_modpack_result(page_html, raw_url, name)

    results = _parallel_fetch_with_fallback(
        limited_pairs, _fetch_one,
        max_workers=min(len(limited_pairs), _MAX_FETCH_WORKERS)
    )

    _cache_set("search", key, results)
    return results


def _build_modrinth_url(slug: str, project_type: str) -> str:
    """构建Modrinth URL。返回 "https://modrinth.com/{type}/{slug}"。"""
    return f"https://modrinth.com/{project_type or 'mod'}/{slug}"


def search_modrinth(keyword: str, max_results: int = 5, project_type: str = "mod") -> dict:
    """Modrinth搜索。返回 {"results": [...], "total": N, "returned": M}。

    每个结果包含完整description（与MC百科齐平）。
    """
    key = _cache_key("modrinth", keyword, max_results, project_type)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    q = urllib.parse.quote(keyword)
    url = f"https://api.modrinth.com/v2/search?query={q}&index=relevance&limit={max_results}"
    data = _fetch_json(url, {"hits": []})
    if not data or "hits" not in data:
        return {"results": [], "total": 0, "returned": 0}

    results = []
    for hit in data.get("hits", []):
        pt = hit.get("project_type", "")
        if project_type and pt and pt != project_type:
            continue

        slug = hit.get("slug", "")
        # 获取完整描述（与MC百科齐平，使用body前500字符）
        description = hit.get("description", "")
        changelogs = []
        full_info = fetch_mod_info(slug, no_limit=True) if slug else None
        if full_info:
            body = full_info.get("body", "")
            # 用body前_MAX_SEARCH_DESC_CHARS字符作为详细描述
            if body:
                description = body[:_MAX_SEARCH_DESC_CHARS] + ("..." if len(body) > _MAX_SEARCH_DESC_CHARS else "")
            # 提取前3条 changelogs（非 full 命令限制为3条）
            cl_list = full_info.get("changelogs", [])
            changelogs = cl_list[:3]

        result = {
            "name": hit.get("title", ""),
            "name_en": hit.get("title", ""),
            "name_zh": "",
            "url": _build_modrinth_url(slug, pt or project_type or "mod"),
            "source": "modrinth",
            "source_id": slug,
            "type": pt or project_type or "mod",
            "snippet": hit.get("description", ""),
            "description": description,  # 完整描述
            "downloads": hit.get("downloads", 0),
            "followers": hit.get("followers", 0),
            "icon_url": hit.get("icon_url", ""),
            "author": hit.get("author", ""),
            "versions": hit.get("versions", []),
            "changelogs": changelogs,  # 前3条更新日志
        }

        results.append(result)

    total = data.get("total_hits", 0)
    ret = {"results": results, "total": total, "returned": len(results)}
    _cache_set("search", key, ret)
    return ret


def _parse_modrinth_license(raw_license: dict | str) -> tuple[str, str, str]:
    """解析 Modrinth 许可证字段。返回 (id, name, url)。"""
    if isinstance(raw_license, dict):
        return (
            raw_license.get("id", ""),
            raw_license.get("name", ""),
            raw_license.get("url", ""),
        )
    return raw_license or "", "", ""


def _parse_modrinth_donations(data: dict) -> list[dict]:
    """解析 Modrinth 捐赠链接列表。"""
    return [
        {"platform": d.get("platform", ""), "url": d.get("url", "")}
        for d in data.get("donation_urls", [])
    ]


def _html_to_text(html: str) -> str:
    """将 HTML 转换为纯文本。

    处理常见的 HTML 标签：
    - <p>, <div>, <br>, <h1-h6> -> 换行
    - <a> -> 保留链接文本
    - <iframe> -> 提取 YouTube 链接
    - 去除 HTML 实体
    """
    if not html:
        return html

    text = html

    # 1. 提取 YouTube iframe 链接
    def replace_iframe(m):
        attrs = m.group(1)
        src_match = re.search(r'src="([^"]+)"', attrs)
        if src_match:
            src = src_match.group(1)
            if 'youtube' in src:
                return f'\n\n[YouTube 视频]({src})\n\n'
        return ''

    text = re.sub(r'<iframe([^>]*)>', replace_iframe, text, flags=re.IGNORECASE)

    # 2. 处理链接：<a href="...">text</a> -> text
    text = re.sub(r'<a[^>]*>(.*?)</a>', r'\1', text, flags=re.DOTALL | re.IGNORECASE)

    # 3. 处理图片：<img alt="..." src="..."> -> ![alt](src)
    def replace_img(m):
        alt_match = re.search(r'alt="([^"]*)"', m.group(0))
        src_match = re.search(r'src="([^"]*)"', m.group(0))
        alt = alt_match.group(1) if alt_match else ''
        src = src_match.group(1) if src_match else ''
        if alt and src:
            return f'![{alt}]({src})'
        return ''

    text = re.sub(r'<img[^>]*/?>', replace_img, text, flags=re.IGNORECASE)

    # 4. 处理标题标签 -> 加 ## 前缀
    text = re.sub(r'<h[1-6][^>]*>', '\n## ', text, flags=re.IGNORECASE)
    text = re.sub(r'</h[1-6]>', '\n', text, flags=re.IGNORECASE)

    # 5. 处理段落和换行
    text = re.sub(r'<(p|div|br|hr|blockquote)[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|br|hr|blockquote)>', '\n', text, flags=re.IGNORECASE)

    # 6. 处理列表
    text = re.sub(r'<li[^>]*>', '\n- ', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?(ul|ol)[^>]*>', '\n', text, flags=re.IGNORECASE)

    # 7. 处理代码块
    text = re.sub(r'<pre[^>]*>(.*?)</pre>', r'```\n\1\n```\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL | re.IGNORECASE)

    # 8. 处理粗体和斜体
    text = re.sub(r'<(strong|b)[^>]*>(.*?)</\1>', r'**\2**', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<(em|i)[^>]*>(.*?)</\1>', r'*\2*', text, flags=re.DOTALL | re.IGNORECASE)

    # 9. 移除所有剩余的 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)

    # 10. 处理 HTML 实体
    text = html_module.unescape(text)

    # 11. 清理多余空行（超过2个连续空行 -> 2个）
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 12. 将 \xa0 (nbsp) 替换为普通空格
    text = text.replace('\xa0', ' ')

    # 13. 去除首尾空白
    text = text.strip()

    return text


def _clean_modrinth_body(body: str) -> str:
    """清洗 Modrinth body 字段：HTML 转文本 + 移除赞助者名单。

    步骤：
    1. 将 HTML 转换为纯文本
    2. 截断到 "Our Patrons" 等标记处
    """
    if not body:
        return body

    # 1. 先转换 HTML 为纯文本
    text = _html_to_text(body)

    # 2. 定义多个可能的截断标记（按优先级排序）
    cut_markers = [
        "## Our Patrons",
        "### Our Patrons",
        "Our Patrons",
        "## Patrons",
        "### Patrons",
        "## Supporters",
        "### Supporters",
    ]

    best_cut_pos = len(text)  # 默认不截断

    for marker in cut_markers:
        pos = text.find(marker)
        if pos != -1 and pos < best_cut_pos:
            best_cut_pos = pos

    # 如果找到了截断位置，截取并添加提示
    if best_cut_pos < len(text):
        cut_text = text[:best_cut_pos].rstrip()
        # 如果截取后为空，返回原文
        if not cut_text:
            return text
        return cut_text + "\n\n*(赞助者名单等冗长内容已省略)*"

    return text


def _build_modrinth_result(data: dict, project_id: str, body: str, gallery: list[str], ctx: dict) -> dict:
    """构建Modrinth结果字典。返回包含name/url/downloads等字段的dict。"""
    project_type = data.get("project_type", "mod")
    project_url = f"https://modrinth.com/{project_type}/{data.get('slug', '')}"

    return {
        "name": data.get("title", ""),
        "slug": data.get("slug", ""),
        "id": project_id,
        "description": data.get("description", ""),
        "body": body,
        "author": None,
        "license": ctx.get("license_id", ""),
        "license_name": ctx.get("license_name", ""),
        "license_url": ctx.get("license_url", ""),
        "categories": data.get("categories", []),
        "display_categories": data.get("display_categories", []),
        "client_side": data.get("client_side", ""),
        "server_side": data.get("server_side", ""),
        "source_url": data.get("source_url") or None,
        "wiki_url": data.get("wiki_url") or None,
        "issues_url": data.get("issues_url") or None,
        "discord_url": data.get("discord_url") or None,
        "donation_urls": ctx.get("donation_urls", []),
        "updated": data.get("updated", ""),
        "published": data.get("published", ""),
        "followers": data.get("followers", 0),
        "icon_url": data.get("icon_url") or "",
        "gallery": gallery,
        "latest_version": None,
        "game_versions": [],
        "loaders": [],
        "downloads": data.get("downloads", 0),
        "type": project_type,
        "source": "modrinth",
        "url": project_url,
    }


def _format_modrinth_versions(project_id: str, no_limit: bool) -> dict:
    """获取并格式化Modrinth版本信息"""
    versions = _fetch_json(f"https://api.modrinth.com/v2/project/{project_id}/version?max={_MAX_VERSIONS_FETCH}", [])
    if not versions:
        return {}

    # 获取最新版本信息
    latest = versions[0]
    result = {
        "latest_version": latest.get("version_number", ""),
        "game_versions": latest.get("game_versions", []),
        "loaders": latest.get("loaders", []),
    }

    # 按mod版本号分组（去掉loader前缀和mc<ver>-前缀）
    known_loaders = _KNOWN_LOADERS
    seen_mod_vers = {}
    for v in versions:
        vn = v.get("version_number", "")
        if not vn:
            continue
        stripped_ver = vn
        for ld in known_loaders:
            if stripped_ver.endswith(f"-{ld}"):
                stripped_ver = stripped_ver[:-len(ld) - 1]
                break
        mod_ver = re.sub(r'^mc[\d\.]+-', '', stripped_ver) or stripped_ver
        if mod_ver not in seen_mod_vers:
            seen_mod_vers[mod_ver] = {"game_versions": set(), "loaders": set()}
        seen_mod_vers[mod_ver]["game_versions"].update(v.get("game_versions", []))
        seen_mod_vers[mod_ver]["loaders"].update(v.get("loaders", []))

    items = [(k, {"game_versions": sorted(v["game_versions"]), "loaders": sorted(v["loaders"])})
             for k, v in seen_mod_vers.items()]

    version_total = len(items)
    result["version_groups"] = items if no_limit else items[:_MAX_VERSION_GROUPS]
    result["_version_total"] = version_total  # 用于截断元信息

    # changelog处理 - 根据 no_limit 标志区分数量
    # no_limit=True (full命令): 取前5个
    # no_limit=False (普通命令): 取前3个
    changelog_limit = _MAX_CHANGELOGS if no_limit else 3
    changelogs = []
    for v in versions[:changelog_limit]:
        cl = v.get("changelog", "").strip()
        if cl:
            changelogs.append({
                "version": v.get("version_number", ""),
                "date": (v.get("date_published") or "")[:10],
                "changelog": cl,
            })
    changelog_total = sum(1 for v in versions if v.get("changelog", "").strip())
    result["changelogs"] = changelogs
    result["_changelog_total"] = changelog_total  # 用于截断元信息

    return result


def _fetch_modrinth_team_author(project_id: str) -> str:
    """从团队成员中获取作者"""
    team = _fetch_json(f"https://api.modrinth.com/v2/project/{project_id}/members", [])
    for m in team:
        if m.get("role") in ("Owner", "Developer", "Project Lead"):
            return m.get("user", {}).get("username") or m.get("user", {}).get("name", "")
    return ""


def fetch_mod_info(mod_id: str, no_limit: bool = False) -> dict | None:
    """
    获取 mod 完整信息（Modrinth）。
    mod_id 可以是 slug 或 project_id。
    no_limit: True 时返回完整数据（用于 full 命令），False 时使用默认限制并返回 _truncated 元信息。
    """
    # 1. 缓存检查
    cache_key = _cache_key("modinfo", mod_id, "full" if no_limit else "limited")
    cached = _cache_get("mod", cache_key)
    if cached is not None:
        return cached

    # 2. API调用
    data = _fetch_json(f"https://api.modrinth.com/v2/project/{mod_id}")
    if not data:
        return None

    project_id = data.get("id", "")

    # 3. 解析许可证和捐赠
    license_id, license_name, license_url = _parse_modrinth_license(data.get("license"))
    donation_urls = _parse_modrinth_donations(data)

    # 4. 处理body和gallery（无限制，返回完整数据）
    raw_body = data.get("body") or ""
    # 清洗：移除 "Our Patrons" 及之后的赞助者名单（Modrinth 特有脏数据）
    body = _clean_modrinth_body(raw_body)

    raw_gallery = [g.get("url") for g in data.get("gallery", []) if g.get("url")]
    gallery_total = len(raw_gallery)

    # 5. 构建结果
    ctx = {
        "license_id": license_id,
        "license_name": license_name,
        "license_url": license_url,
        "donation_urls": donation_urls,
    }
    result = _build_modrinth_result(data, project_id, body, raw_gallery, ctx)

    # 6. 添加截断元信息（仅当实际截断时）
    truncated = {}
    if gallery_total > _MAX_GALLERY and not no_limit:
        truncated["gallery"] = {"returned": _MAX_GALLERY, "total": gallery_total}

    # 7. 获取作者
    result["author"] = _fetch_modrinth_team_author(project_id)

    # 8. 获取版本信息
    version_info = _format_modrinth_versions(project_id, no_limit)
    if version_info:
        result.update({
            "latest_version": version_info.get("latest_version"),
            "game_versions": version_info.get("game_versions"),
            "loaders": version_info.get("loaders"),
            "version_groups": version_info.get("version_groups"),
            "changelogs": version_info.get("changelogs"),
        })
        # 添加截断元信息
        if not no_limit:
            version_total = version_info.get("_version_total", 0)
            changelog_total = version_info.get("_changelog_total", 0)
            if version_total > _MAX_VERSION_GROUPS:
                truncated["version_groups"] = {"returned": _MAX_VERSION_GROUPS, "total": version_total}
            if changelog_total > _MAX_CHANGELOGS:
                truncated["changelogs"] = {"returned": _MAX_CHANGELOGS, "total": changelog_total}

    # 9. 添加截断元信息并返回
    if truncated:
        result["_truncated"] = truncated

    _cache_set("mod", cache_key, result)
    return result


def search_modrinth_author(username: str, max_results: int = 10) -> list[dict]:
    """Modrinth作者搜索。返回作者作品列表。"""
    key = _cache_key("author", username, max_results)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    q = urllib.parse.quote(username)
    # colon in filter=authors: must stay unencoded
    url = f"https://api.modrinth.com/v2/search?query={q}&filter=authors:{q}&index=relevance&limit={max_results}"
    data = _fetch_json(url)
    if not data or "hits" not in data:
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

    if not project_id:
        proj = _fetch_json(f"https://api.modrinth.com/v2/project/{mod_id}")
        if not proj:
            return {"deps": {}, "error": "PROJECT_NOT_FOUND"}
        project_id = proj.get("id", mod_id)

    deps = {}
    deps_data = _fetch_json(f"https://api.modrinth.com/v2/project/{project_id}/dependencies")
    if not deps_data:
        return {"deps": {}, "error": "API_ERROR"}

    for dep_proj in deps_data.get("projects", []):
        slug = dep_proj.get("slug", "")
        dep_id = dep_proj.get("id", "")
        client = dep_proj.get("client_side", "unknown")
        server = dep_proj.get("server_side", "unknown")

        key = slug or dep_id
        deps[key] = {
            "name": dep_proj.get("title", slug or dep_id),
            "slug": slug,
            "id": dep_id,
            "client_side": client,
            "server_side": server,
            "url": f"https://modrinth.com/mod/{slug}" if slug else None,
            # 不再派生 "type" 字段，因为它有误导性
        }

    result = {"deps": deps}
    _cache_set("mod", cache_key, result)
    return result


def _clean_wiki_segment(segment: str) -> str:
    """清理 wiki HTML 片段：移除脚本/样式/媒体标签和 wiki 标记，返回纯文本。"""
    segment = re.sub(r'<script[^>]*>.*?</script>', ' ', segment, flags=re.DOTALL)
    segment = re.sub(r'<style[^>]*>.*?</style>', ' ', segment, flags=re.DOTALL)
    segment = re.sub(r'<img[^>]*/?>', ' ', segment, flags=re.IGNORECASE)
    segment = re.sub(r'<source[^>]*/?>', ' ', segment, flags=re.IGNORECASE)
    segment = re.sub(r'<picture[^>]*/?>', ' ', segment, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', segment)
    text = re.sub(r'<[a-zA-Z]\w*\s[^>]*', ' ', text)
    text = re.sub(r'\[\[[^\]]*\]\]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _wiki_extract_snippet(html: str, start: int, source: str = "") -> tuple[str, str]:
    """从 wiki 页面提取描述 snippet。返回 (snippet, snippet_source)。

    直接解析 <p> 标签内容，而非将整个 HTML 压缩为单行，
    以避免 infobox/nav 等非正文内容混入。
    """
    snippet = ""
    snippet_source = ""

    # 限制搜索范围，避免扫描整页
    segment = html[start:start+_WIKI_FALLBACK_SEGMENT_LEN]

    # 判断 <p> 标签内容是否为有效描述文本
    def _is_valid_snippet_para(text: str) -> bool:
        if not text or len(text) < _MIN_SNIPPET_LINE_LEN:
            return False
        # 跳过 JSON/模板数据（英文 wiki infobox 用 <p> 包裹 JSON）
        if text.startswith('{') or text.startswith('['):
            return False
        # 跳过消歧义行
        if any(kw in text.lower() for kw in _WIKI_SNIPPET_SKIP_KEYWORDS):
            return False
        return True

    # 方法1：intro 区域（第一个 heading 之前）的 <p> 标签
    heading_m = re.search(r'<h[234][^>]*id="[^"]+"[^>]*>', segment)
    intro_html = segment[:heading_m.start()] if heading_m else segment[:_WIKI_SNIPPET_SEGMENT_LEN]

    snippet_parts = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", intro_html, re.DOTALL):
        # 移除 <style> 块（保留其余内容）
        p = re.sub(r"<style[^>]*>.*?</style>", "", p, flags=re.DOTALL | re.IGNORECASE)
        if re.search(r"<script|application/ld\+json", p, re.IGNORECASE):
            continue
        clean = clean_html_text(p)
        if _is_valid_snippet_para(clean):
            snippet_parts.append(clean)
            if sum(len(p) for p in snippet_parts) >= _MAX_SEARCH_DESC_CHARS:
                break

    # 方法2：intro 区域无有效段落时，扫描更大范围的所有 <p>（跳过 infobox）
    # 英文 wiki 页面的描述性段落常在 infobox/TOC 之后（可达 30000+ 字符）
    if not snippet_parts:
        large_segment = html[start:start+_WIKI_FULL_SCAN_LEN]
        for p in re.findall(r"<p[^>]*>(.*?)</p>", large_segment, re.DOTALL):
            p = re.sub(r"<style[^>]*>.*?</style>", "", p, flags=re.DOTALL | re.IGNORECASE)
            if re.search(r"<script|application/ld\+json", p, re.IGNORECASE):
                continue
            clean = clean_html_text(p)
            if _is_valid_snippet_para(clean):
                snippet_parts.append(clean)
                if sum(len(p) for p in snippet_parts) >= _MAX_SEARCH_DESC_CHARS:
                    break

    if snippet_parts:
        snippet = ' '.join(snippet_parts)[:_MAX_SEARCH_DESC_CHARS]
        snippet_source = "intro"

    # Fallback：CJK 连续片段（中文 wiki）
    if not snippet:
        large_text = _clean_wiki_segment(html[start:start+_WIKI_FALLBACK_SEGMENT_LEN])
        cjk_segments = re.findall(r'[\u4e00-\u9fff]{10,}', large_text)
        if cjk_segments:
            for seg in cjk_segments[:_MAX_CJK_FALLBACK_SEGMENTS]:
                if len(seg) > _MIN_CJK_SEGMENT_LEN:
                    snippet = seg[:_MAX_SEARCH_DESC_CHARS]
                    snippet_source = "fallback"
                    break

    # Fallback：英文句子片段（英文 wiki 页面内容主要在表格/列表时，<p> 标签可能为空）
    if not snippet:
        large_text = _clean_wiki_segment(html[start:start+_WIKI_FULL_SCAN_LEN])
        # 找第一个包含字母的连续英文片段（至少 40 字符）
        en_segments = re.findall(r'[A-Za-z][\w\s,;:\-\'\"()]{40,}', large_text)
        for seg in en_segments[:3]:
            seg = seg.strip()
            # 排除 CSS/JS 残留
            if not any(kw in seg.lower() for kw in ('font-style', 'display:', 'margin-', 'padding-', 'background')):
                snippet = seg[:_MAX_SEARCH_DESC_CHARS]
                snippet_source = "fallback"
                break
    return snippet, snippet_source


def _add_variant_param(url: str) -> str:
    """为中文 wiki URL 添加 variant=zh-hans 参数。"""
    url = re.sub(r"[&?](?:amp;)?variant=zh-[a-z]+", "", url)
    separator = "&" if "?" in url else "?"
    return url + separator + "variant=zh-hans"


def _make_wiki_result(name, url, source, source_id, snippet, sections,
                      title_field=""):
    """构造 wiki 搜索结果 dict。title_field 决定哪个 name 字段填入标题。"""
    return {
        "name": name,
        "name_en": name if title_field == "name_en" else "",
        "name_zh": name if title_field == "name_zh" else "",
        "url": url,
        "source": source,
        "source_id": source_id,
        "type": "other",
        "sections": sections,
        "snippet": snippet,
    }


def _wiki_direct_access(
    html: str,
    base_url: str,
    source: str,
    title_field: str,
    add_variant: bool,
) -> list[dict] | None:
    """处理 wiki 直接访问（页面已找到）。返回结果列表或 None。"""
    m_title = re.search(r"<title>([^<]+)</title>", html)
    title_text = m_title.group(1) if m_title else ""
    is_direct = (
        'id="firstHeading"' in html
        and "Special:Search" not in title_text
        and "Search results" not in title_text
        and "的搜索结果" not in title_text
    )
    if not is_direct:
        return None

    canon_m = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html)
    og_m = re.search(r'<meta[^>]+property="og:url"[^>]+content="([^"]+)"', html)
    article_url = canon_m.group(1) if canon_m else (og_m.group(1) if og_m else None)
    page_title = re.sub(r"\s*[–-]\s*(中文 )?Minecraft Wiki.*", "", title_text).strip()

    # 提取 h2 和 h3 标题
    headings = re.findall(r"<h([23])[^>]*>(.*?)</h\1>", html, re.DOTALL)
    sections = []
    for level, content in headings[:_MAX_WIKI_SECTIONS]:
        clean = re.sub(r"<[^>]+>", "", content).strip()
        if clean:
            prefix = "▸ " if level == "2" else "  - "
            sections.append(f"{prefix}{clean}")

    # 提取 snippet
    snippet = ""
    parser_output = re.search(r'<div[^>]+class="[^"]*mw-parser-output[^"]*"[^>]*>', html)
    if parser_output:
        snippet, _ = _wiki_extract_snippet(html, parser_output.end(), source)

    if add_variant and article_url:
        article_url = _add_variant_param(article_url)

    result = _make_wiki_result(
        name=page_title,
        url=article_url or "",
        source=source,
        source_id=article_url.split("/")[-1] if article_url else "",
        snippet=snippet,
        sections=sections,
        title_field=title_field,
    )
    result["_direct_match"] = True
    return [result]


def _wiki_api_search(
    keyword: str,
    base_url: str,
    source: str,
    title_field: str,
    add_variant: bool,
    max_results: int,
) -> list[dict]:
    """MediaWiki API 搜索。返回结果列表。"""
    results = []
    q = urllib.parse.quote(keyword)
    api_url = f"{base_url}/api.php?action=query&list=search&srsearch={q}&format=json&srlimit={max_results}"
    raw = curl(api_url)
    if not raw:
        return results
    try:
        data = json.loads(raw)
        hits = data.get("query", {}).get("search", [])
        for hit in hits[:max_results]:
            title = hit.get("title", "")
            page_id = hit.get("pageid", 0)
            snippet = hit.get("snippet", "")
            clean_snippet = re.sub(r'<[^>]+>', '', snippet) if snippet else ""
            # 清理 MediaWiki 标记残留（[[|]]、[[...]] 等）
            clean_snippet = re.sub(r'\[\[[^]]*\|([^\]]*)\]\]', r'\1', clean_snippet)  # [[a|b]] → b
            clean_snippet = re.sub(r'\[\[([^\]]*)\]\]', r'\1', clean_snippet)          # [[a]] → a
            clean_snippet = re.sub(r'\[\[?\|?\]?\]?', '', clean_snippet)               # 残留 [[|]]
            clean_snippet = re.sub(r'\s+', ' ', clean_snippet).strip()
            article_url = f"{base_url}/w/{urllib.parse.quote(title.replace(' ', '_'))}"
            if add_variant:
                article_url = _add_variant_param(article_url)
            results.append(_make_wiki_result(
                name=title,
                url=article_url,
                source=source,
                source_id=str(page_id),
                snippet=clean_snippet,
                sections=[],
                title_field=title_field,
            ))
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        logger.warning(f"Wiki search parse failed for {keyword}: {e}")
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
    """
    minecraft.wiki 搜索通用实现。

    参数:
        base_url: wiki 根 URL
        cache_prefix: 缓存 key 前缀
        source: source 字段值
        title_field: 标题填入哪个字段（"name_en" / "name_zh" / ""）
        add_variant: 是否添加 ?variant=zh-hans
    """
    key = _cache_key(cache_prefix, keyword, max_results)
    cached = _cache_get("search", key)
    if cached is not None:
        return cached

    results = []
    q = urllib.parse.quote(keyword)

    # 方法1：尝试直接访问（精确匹配，信息更丰富：有 sections、有真实 snippet）
    html = curl(f"{base_url}/w/Special:Search?search={q}&go=Go")
    if html and len(html) >= MIN_HTML_LEN:
        direct = _wiki_direct_access(
            html, base_url, source, title_field, add_variant)
        if direct:
            results.extend(direct)

    # 方法2：MediaWiki API 搜索（补充更多相关结果）
    api_results = _wiki_api_search(
        keyword, base_url, source, title_field, add_variant, max_results)

    # 去重：API 结果中与直接访问结果同名的跳过（URL 去重，避免繁简体同名问题）
    # 若直接命中 snippet 过短，用 API 结果的 snippet 补充
    if results:
        direct_urls = {r.get("url", "").split("?")[0].rstrip("/").rsplit("/", 1)[-1].lower()
                       for r in results}
        for r in api_results:
            r_url_key = r.get("url", "").split("?")[0].rstrip("/").rsplit("/", 1)[-1].lower()
            if r_url_key in direct_urls:
                # 同一页面：若直接命中 snippet 过短，用 API snippet 替换
                if len(r.get("snippet", "")) > 50:
                    for dr in results:
                        dr_url = dr.get("url", "").split("?")[0].rstrip("/").rsplit("/", 1)[-1].lower()
                        if dr_url == r_url_key and len(dr.get("snippet", "")) < 60:
                            dr["snippet"] = r["snippet"]
            else:
                results.append(r)
    else:
        results = api_results

    _cache_set("search", key, results)
    return results


def search_wiki(keyword: str, max_results: int = 5) -> list[dict]:
    """minecraft.wiki 搜索（英文）。"""
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
    """minecraft.wiki/zh 中文 wiki 搜索。"""
    return _search_wiki_impl(
        keyword=keyword,
        base_url="https://zh.minecraft.wiki",
        cache_prefix="wiki_zh",
        source="minecraft.wiki/zh",
        title_field="name_zh",
        add_variant=True,
        max_results=max_results,
    )


def _extract_wiki_infobox(html: str) -> dict:
    """
    提取 wiki infobox 结构化数据（优先 table.infobox，支持多种格式）。

    尝试顺序:
    1. table.infobox（标准格式）
    2. div.infobox 内嵌套表格
    3. mw-parser-output 后第一个带 th 的表格
    4. 中文 wiki 分散表格（合并提取）
    """
    # 格式1: table.infobox（最可靠）
    infobox_html = _try_extract_standard_infobox(html)
    if infobox_html:
        return _parse_infobox_table(infobox_html)

    # 格式2: div.infobox 内有嵌套表格
    infobox_html = _try_extract_div_infobox(html)
    if infobox_html:
        return _parse_infobox_table(infobox_html)

    # 格式3: mw-parser-output 后的第一个表格
    infobox_html = _try_extract_first_table(html)
    if infobox_html:
        return _parse_infobox_table(infobox_html)

    # 格式4: 中文 wiki 的分散表格
    zh_data = _try_extract_chinese_wiki_tables(html)
    if zh_data:
        return zh_data

    return {}


def _try_extract_standard_infobox(html: str) -> str | None:
    """尝试提取标准 table.infobox 格式。"""
    match = re.search(r'<table[^>]+class="[^"]*infobox[^"]*"[^>]*>(.*?)</table>', html, re.DOTALL)
    return match.group(1) if match else None


def _try_extract_div_infobox(html: str) -> str | None:
    """尝试提取 div.infobox 内嵌套的表格。"""
    div_match = re.search(r'<div[^>]+class="[^"]*infobox[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not div_match:
        return None

    div_content = div_match.group(1)
    table_in_div = re.search(r'<table[^>]*>(.*?)</table>', div_content, re.DOTALL)
    return table_in_div.group(1) if table_in_div else None


def _try_extract_first_table(html: str) -> str | None:
    """尝试提取 mw-parser-output 后的第一个带 th 的表格。"""
    parser = re.search(r'<div[^>]+class="mw-content-ltr mw-parser-output"', html)
    if not parser:
        parser = re.search(r'<div[^>]+class="[^"]*mw-parser-output[^"]*"[^>]*>', html)
    if not parser:
        return None

    segment = html[parser.end():parser.end()+_WIKI_FIRST_TABLE_SEGMENT_LEN]
    first_table = re.search(r'<table[^>]*>(.*?)</table>', segment, re.DOTALL)
    if first_table and '<th' in first_table.group(0):
        return first_table.group(1)
    return None


def _try_extract_chinese_wiki_tables(html: str) -> dict | None:
    """尝试提取中文 wiki 的分散表格（合并多个相关表格）。"""
    if not any(marker in html for marker in ['zh-Hant', 'zh-Hans', '中文']):
        return None

    key_fields = ['名稱', '稀有度', '耐久度', '攻擊', '防御', '生命值']
    all_tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)

    data = {}
    for table in all_tables:
        if not any(kw in table for kw in key_fields) or '<th' not in table:
            continue

        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL)
        for row in rows:
            cells = re.findall(r'<(th|td)[^>]*>(.*?)</\1>', row, re.DOTALL)
            if len(cells) == 2:
                key = clean_html_text(cells[0][1])
                value = clean_html_text(cells[1][1])
                if key and not key.startswith(('{{', '{|', 'Module:')) and len(key) < 30:
                    data[key] = value

    return data if data else None


def _parse_infobox_table(infobox_html: str) -> dict:
    """解析 infobox 表格的 key-value 对。"""
    data = {}
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', infobox_html, re.DOTALL)
    for row in rows:
        cells = re.findall(r'<(th|td)[^>]*>(.*?)</\1>', row, re.DOTALL)
        if len(cells) == 2:
            key = clean_html_text(cells[0][1])
            value = clean_html_text(cells[1][1])
            if key and not key.startswith(('{{', '{|', 'Module:')):
                data[key] = value
    return data


def _extract_main_image(html: str) -> str:
    """提取页面主要图片（infobox 图片）。"""
    img = re.search(
        r'<div[^>]+class="[^"]*infobox[^"]*"[^>]*>.*?'
        r'<img[^>]+src="([^"]+)"',
        html, re.DOTALL
    )
    if img:
        return img.group(1)

    img = re.search(
        r'<div[^>]+id="mw-content-text"[^>]*>.*?'
        r'<img[^>]+src="([^"]+)"',
        html, re.DOTALL
    )
    return img.group(1) if img else ""


def _extract_intro_paragraphs(content_html: str, para_skip_prefixes: tuple, source: str) -> list[str]:
    """提取 wiki 页面首段介绍（第一个 heading 之前的内容）。"""
    # 解析 heading 位置
    heading_map = []
    for m in re.finditer(r'<h([234])[^>]*id="([^"]+)"[^>]*>(.*?)</h\1>', content_html, re.DOTALL):
        heading_map.append(m.start())

    if not heading_map:
        return []

    # 提取第一个 heading 之前的段落
    first_heading_pos = heading_map[0]
    pre_heading_html = content_html[:first_heading_pos]
    intro_paragraphs = []

    for p in re.findall(r"<p[^>]*>(.*?)</p>", pre_heading_html, re.DOTALL):
        if re.search(r"<script|application/ld\+json", p, re.IGNORECASE):
            continue
        clean = clean_html_text(p)
        if any(clean.startswith(prefix) for prefix in para_skip_prefixes):
            continue
        if _is_valid_paragraph(clean, lang="en" if source == "minecraft.wiki" else "zh"):
            intro_paragraphs.append(clean)
            if len(intro_paragraphs) >= _MAX_WIKI_INTRO_PARAGRAPHS:
                break

    return intro_paragraphs


def _extract_sections(
    content_html: str,
    heading_skip_ids: set[str],
    para_skip_prefixes: tuple[str, ...],
    source: str,
    intro_paragraphs: list[str],
    max_paragraphs: int
) -> tuple[list[dict], list[str]]:
    """解析 heading 并提取所有章节内容。"""
    # 解析 heading 映射
    heading_map = []
    for m in re.finditer(r'<h([234])[^>]*id="([^"]+)"[^>]*>(.*?)</h\1>', content_html, re.DOTALL):
        lvl = int(m.group(1))
        h_id = m.group(2)
        h_text = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        heading_map.append((lvl, h_id, h_text, m.start()))

    sections_output = []
    paragraphs = list(intro_paragraphs)  # 先添加首段
    current_h2 = None

    for i, (lvl, h_id, h_text, h_start) in enumerate(heading_map):
        if h_id in heading_skip_ids:
            continue
        if lvl == 2:
            current_h2 = h_text
            # h2 也提取内容（之前跳过了 h2，导致"生成""用途"等大节内容丢失）

        next_start = heading_map[i + 1][3] if i + 1 < len(heading_map) else len(content_html)
        section_html = content_html[h_start:next_start]

        # 提取章节段落
        section_paragraphs = _extract_section_paragraphs(
            section_html, para_skip_prefixes, source
        )

        # 提取表格行
        table_rows = _extract_table_items_from_section(section_html, source, len(section_paragraphs))

        # 构建章节输出
        section_lines = section_paragraphs[:_MAX_SECTION_PARAGRAPHS]
        if table_rows and not section_paragraphs:
            # 纯表格章节：直接展开表格行
            section_lines = table_rows[:_MAX_SECTION_PARAGRAPHS]
        elif table_rows:
            # 有段落也有表格：追加表格行
            section_lines.extend(table_rows[:_MAX_SECTION_PARAGRAPHS - len(section_lines)])

        if section_lines:
            sections_output.append({
                "heading": h_text,
                "parent": current_h2,
                "content": section_lines,
            })
            paragraphs.extend(section_lines)

        # 支持-1表示无限制
        if max_paragraphs > 0 and len(paragraphs) >= max_paragraphs:
            paragraphs = paragraphs[:max_paragraphs]
            break

    return sections_output, paragraphs


def _extract_section_paragraphs(section_html: str, para_skip_prefixes: tuple, source: str) -> list[str]:
    """提取单个章节的段落内容。"""
    section_paragraphs = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", section_html, re.DOTALL):
        if re.search(r"<script|application/ld\+json", p, re.IGNORECASE):
            continue
        clean = clean_html_text(p)
        if any(clean.startswith(prefix) for prefix in para_skip_prefixes):
            continue
        if _is_valid_paragraph(clean, lang="en" if source == "minecraft.wiki" else "zh"):
            section_paragraphs.append(clean)
            if len(section_paragraphs) >= _MAX_SECTION_PARAGRAPHS:
                break

    # 英文 wiki：从 <li> 中提取描述性条目
    if source == "minecraft.wiki" and not section_paragraphs:
        for li in re.findall(r"<li[^>]*>(.*?)</li>", section_html, re.DOTALL):
            clean = clean_html_text(li)
            if len(clean) >= _MIN_DESCRIPTIVE_LI_LEN and re.match(
                    r"^(Added|Changed|Fixed|Updated|Removed|Introduced|Can now|Made|New|Affects?|Allows?|Prevents?|Makes?|Provides?)", clean):
                section_paragraphs.append(clean)
                break

    # 中文 wiki：从 <li> 中提取列表内容
    if source != "minecraft.wiki" and not section_paragraphs:
        for li in re.findall(r"<li[^>]*>(.*?)</li>", section_html, re.DOTALL):
            clean = clean_html_text(li)
            if len(clean) >= _MIN_PARAGRAPH_LEN and not clean.startswith(("[", "编辑", "注：")):
                section_paragraphs.append(clean)
                if len(section_paragraphs) >= 5:
                    break

    return section_paragraphs


def _extract_table_items_from_section(section_html: str, source: str, current_para_count: int) -> list[str]:
    """从章节中提取表格行内容（每行所有列，用 | 分隔）。"""
    table_rows = []
    if current_para_count < _MAX_SECTION_PARAGRAPHS:
        tables = re.findall(r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>.*?</table>', section_html, re.DOTALL)
        for tbl in tables[:_MAX_TABLES_PER_SECTION]:
            rows = _extract_table_rows(tbl, max_rows=_MAX_TABLE_ITEMS)
            table_rows.extend(rows)
    return table_rows


def _extract_table_items(table_html: str, max_items: int = 8) -> list[str]:
    """从 wiki table 中提取第一列的 item 名称列表（向后兼容）。"""
    items = []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
    for row in rows[1:]:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
        if not cells:
            continue
        cell_text = clean_html_text(cells[0])
        if cell_text and len(cell_text) >= _MIN_TABLE_CELL_LEN and not re.match(r"^[\s\-\d]+$", cell_text):
            # 过滤 CSS/样式代码泄漏
            if re.match(r"\.\w+-", cell_text) or "{" in cell_text or "display:" in cell_text:
                continue
            items.append(cell_text)
        if len(items) >= max_items:
            break
    return items


def _extract_table_rows(table_html: str, max_rows: int = 50) -> list[str]:
    """从 wiki table 中提取每行完整内容（多列用 | 分隔）。"""
    rows_out = []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
    for row in rows[1:]:  # 跳过表头行
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
        if not cells:
            continue
        cleaned = []
        for cell in cells:
            text = clean_html_text(cell).strip()
            # 清理 MediaWiki 残留标记
            text = re.sub(r'\[\[[^]]*\|([^\]]*)\]\]', r'\1', text)  # [[a|b]] → b
            text = re.sub(r'\[\[([^\]]*)\]\]', r'\1', text)          # [[a]] → a
            text = re.sub(r'\[\[?\|?\]?\]?', '', text)               # 残留 [[|]]
            text = text.strip()
            if not text or re.match(r"^[\s\-\d]+$", text):
                continue
            # 过滤 CSS/样式代码泄漏
            if re.match(r"\.\w+-", text) or "{" in text or "display:" in text:
                continue
            cleaned.append(text)
        if not cleaned:
            continue
        # 单列直接输出，多列用 | 分隔
        if len(cleaned) == 1:
            rows_out.append(cleaned[0])
        else:
            rows_out.append(" | ".join(cleaned))
        if len(rows_out) >= max_rows:
            break
    return rows_out


def _read_wiki_impl(url: str, max_paragraphs: int,
                    para_skip_prefixes: tuple[str, ...],
                    heading_skip_ids: set[str],
                    source: str,
                    include_infobox: bool = True) -> dict:
    """
    读取 wiki 页面正文（英文 / 中文共用实现）。

    参数：
      para_skip_prefixes: 段落前缀跳过词（如 "History of", "v ", "历史", "编辑"）
      heading_skip_ids:   heading id 跳过集合
      source:             返回结果的 source 字段值
      include_infobox:    是否在结果中包含 infobox 数据
    """
    html = curl(url)
    if not html or len(html) < MIN_HTML_LEN_ITEM:
        return {"error": "NO_CONTENT"}

    m_title = re.search(r'<h1[^>]*id="firstHeading"[^>]*>(.*?)</h1>', html, re.DOTALL)
    title = html_module.unescape(re.sub(r"<[^>]+>", "", m_title.group(1)).strip()) if m_title else "UNKNOWN"

    # 提取 infobox 结构化数据（在移除之前）
    infobox_data = _extract_wiki_infobox(html)

    # 提取主要图片
    main_image = _extract_main_image(html)

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
    # 移除 navbox（infobox 已提取，不再需要特殊处理）
    content_html = re.sub(
        r'<table[^>]+class="[^"]*navbox[^"]*"[^>]*>.*?</table>',
        "", content_html, flags=re.DOTALL
    )

    # 提取首段介绍
    intro_paragraphs = _extract_intro_paragraphs(content_html, para_skip_prefixes, source)

    # 解析 heading 并提取章节内容
    sections_output, paragraphs = _extract_sections(
        content_html, heading_skip_ids, para_skip_prefixes,
        source, intro_paragraphs, max_paragraphs
    )

    result = {
        "name": title,
        "url": url,
        "source": source,
        "language": "zh" if "minecraft.wiki/zh" in source or "zh.minecraft.wiki" in source else "en",
        "content": paragraphs,
        "_sections": sections_output,
    }

    # 添加 infobox 结构化数据（如果有）
    if infobox_data:
        result["infobox"] = infobox_data

    # 添加主要图片（如果有）
    if main_image:
        result["main_image"] = main_image

    if not include_infobox and "infobox" in result:
        del result["infobox"]

    return result


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
    return _read_wiki_impl(
        url, max_paragraphs,
        para_skip_prefixes=("历史", "编辑", "History of", "v ", "[edit"),
        heading_skip_ids=_WIKI_ZH_HEADING_SKIP_IDS,
        source="minecraft.wiki/zh",
        include_infobox=include_infobox,
    )


def search_all(keyword: str, max_per_source: int = 3, timeout: int = 12,
               content_type: str = "mod", fuse: bool = False) -> dict:
    """
    四平台并行搜索，返回统一格式。
    timeout: 整体超时秒数
    content_type: "mod" | "item" | "modpack" | "entity" | "biome" | "dimension" | "shader" | "resourcepack"
      - 同时决定每平台最大结果数（_DEFAULT_RESULTS_PER_PLATFORM）
      - shader/resourcepack 仅搜索 Modrinth
      - modpack 仅搜索 MC百科 + Modrinth
    fuse: True 时返回 {"results": [...融合列表...], "platform_stats": {platform: {total, returned}}}
         False 时返回 {platform: [results]}（向后兼容）
    """
    # 验证关键词：拦截空关键词
    if not keyword or not keyword.strip():
        return {"results": [], "platform_stats": {}}

    # 按 content_type 分级设置每平台结果数（用户指定优先）
    per_source = max_per_source if max_per_source != 3 else _DEFAULT_RESULTS_PER_PLATFORM
    results = {"mcmod.cn": [], "modrinth": [], "minecraft.wiki": [], "minecraft.wiki/zh": []}
    stats = {"mcmod.cn": {"total": 0, "returned": 0},
             "modrinth": {"total": 0, "returned": 0},
             "minecraft.wiki": {"total": 0, "returned": 0},
             "minecraft.wiki/zh": {"total": 0, "returned": 0}}

    # 根据 content_type 决定启用的平台
    pe = _platform_enabled.copy()
    if content_type in _VISUAL_CONTENT_TYPES:
        # shader/resourcepack 仅 Modrinth 支持
        pe["mcmod.cn"] = False
        pe["minecraft.wiki"] = False
        pe["minecraft.wiki/zh"] = False
    elif content_type == "modpack":
        # modpack 不支持 wiki
        pe["minecraft.wiki"] = False
        pe["minecraft.wiki/zh"] = False

    def _wrap_mcmod():
        try:
            # 支持 mod 和 modpack 类型
            valid_types = ("mod", "item", "modpack")
            ct = content_type if content_type in valid_types else "mod"
            return search_mcmod(keyword, per_source, content_type=ct)
        except (SearchError, OSError) as e:
            logger.warning(f"MC百科搜索失败: {e}")
            return []

    def _wrap_mr():
        try:
            # Modrinth 支持所有类型
            mr_type = content_type if content_type in (_TEXT_CONTENT_TYPES | _VISUAL_CONTENT_TYPES) else "mod"
            return search_modrinth(keyword, per_source, project_type=mr_type)
        except (SearchError, OSError) as e:
            logger.warning(f"Modrinth搜索失败: {e}")
            return {"results": [], "total": 0, "returned": 0}

    def _wrap_wiki():
        try:
            return search_wiki(keyword, per_source)
        except (SearchError, OSError) as e:
            logger.warning(f"Wiki搜索失败: {e}")
            return []

    def _wrap_wiki_zh():
        try:
            return search_wiki_zh(keyword, per_source)
        except (SearchError, OSError) as e:
            logger.warning(f"中文Wiki搜索失败: {e}")
            return []

    workers = []
    futures_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_FETCH_WORKERS) as ex:
        if pe.get("mcmod.cn", False):
            f = ex.submit(_wrap_mcmod)
            futures_map[f] = "mcmod.cn"
            workers.append(f)
        if pe.get("modrinth", False):
            f = ex.submit(_wrap_mr)
            futures_map[f] = "modrinth"
            workers.append(f)
        if pe.get("minecraft.wiki", False):
            f = ex.submit(_wrap_wiki)
            futures_map[f] = "minecraft.wiki"
            workers.append(f)
        if pe.get("minecraft.wiki/zh", False):
            f = ex.submit(_wrap_wiki_zh)
            futures_map[f] = "minecraft.wiki/zh"
            workers.append(f)

        for future in concurrent.futures.as_completed(workers):
            key = futures_map[future]
            try:
                raw = future.result(timeout=timeout)
            except (TimeoutError, OSError, SearchError) as e:
                logger.warning(f"平台 {key} 获取结果失败: {e}")
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


def _calc_name_score(name_lc: str, query_lc: str) -> int:
    """
    计算单个名称字段的相关性分数（使用常量）。

    评分逻辑:
    - 精确匹配: 100 + 短名称奖励
    - 前缀匹配: 60 + 短名称奖励
    - 包含查询词: 30 + 位置奖励
    - 名称被包含: 20
    """
    if not name_lc or not query_lc:
        return 0

    # 1. 精确匹配
    if name_lc == query_lc:
        bonus = max(0, _SCORE_EXACT_MATCH_MAX_BONUS - len(name_lc) * _SCORE_EXACT_MATCH_BONUS_FACTOR)
        return _SCORE_EXACT_MATCH_BASE + bonus

    # 2. 前缀匹配
    if name_lc.startswith(query_lc):
        bonus = max(0, _SCORE_PREFIX_MAX_BONUS - len(query_lc) * _SCORE_PREFIX_BONUS_FACTOR)
        return _SCORE_PREFIX_BASE + bonus

    # 3. 包含查询词
    pos = name_lc.find(query_lc)
    if pos >= 0:
        pos_bonus = max(0, _SCORE_CONTAINS_MAX_POS_BONUS - pos)
        return _SCORE_CONTAINS_BASE + pos_bonus

    # 4. 名称被包含
    if len(name_lc) >= _SCORE_MIN_LENGTH_FOR_CONTAINED and name_lc in query_lc:
        return _SCORE_CONTAINED_IN_QUERY

    return 0


def _score_relevance(query: str, hit: dict, content_type: str = "mod") -> float:
    """
    计算单条搜索结果与查询词的相关性分数（优化版，0-150+）。

    评分规则:
      - 主字段精确匹配: 100 + 短名称奖励(最多+20)
      - 主字段前缀匹配: 60 + 短名称奖励(最多+15)
      - 主字段包含查询词: 30 + 位置奖励(最多+10)
      - 主字段被包含于查询词: 20 (适合缩写搜索)
      - 次字段匹配: 同级别 -10 分
      - Snippet 包含查询词: +5
      - Wiki item 来源: +5
      - 多平台命中: 每多一个平台 +10 (在 _fuse_results 中计算)
    """
    if not query or not hit:
        return 0.0

    # 直接命中的 wiki 页面（通过 go=Go 跳转），给予高基础分
    if hit.get("_direct_match"):
        return _SCORE_EXACT_MATCH_BASE

    name_zh = (hit.get("name_zh") or "").lower()
    name_en = (hit.get("name_en") or "").lower()
    q = query.strip().lower()
    if not q:
        return 0.0

    # 1. 选择主要/次要评分字段
    primary = name_zh if _is_cjk(q) else name_en
    secondary = name_en if primary == name_zh else name_zh
    if not primary:
        primary, secondary = secondary, ""

    # 2. 计算名称分数
    score = _calc_name_score(primary, q)
    if score == 0 and secondary:
        score = _calc_name_score(secondary, q)
        if score > 0:
            score = max(score - _SCORE_SECONDARY_PENALTY, _SCORE_SECONDARY_MIN)

    # 3. Snippet 加分
    snippet = (hit.get("snippet") or "").lower()
    if snippet and q in snippet:
        score += _SCORE_SNIPPET_BONUS

    # 4. Wiki item 来源加分
    platform = hit.get("_platform", hit.get("source", ""))
    if content_type == "item" and platform in ("minecraft.wiki", "minecraft.wiki/zh"):
        score += _SCORE_WIKI_ITEM_BONUS

    return score


def _fuse_results(results: dict, content_type: str = "mod", query_keyword: str = "") -> list[dict]:
    """
    跨平台去重合并，按相关性分数排序。

    排序规则：相关性分数 DESC → 多平台命中加权 → 平台优先级 ASC（tiebreaker）
    content_type 用于调整不同类型内容的平台优先级。
    """
    if content_type is None:
        content_type = "mod"

    # 步骤1: 打分并过滤
    scored = _score_and_filter(results, content_type, query_keyword)

    # 步骤2: 统计平台命中
    name_platform_count = _count_platform_hits(scored)

    # 步骤3: 去重
    by_name = _deduplicate_by_name(scored, name_platform_count)

    # 步骤4: 排序
    sorted_entries = _sort_entries(by_name)

    # 步骤5: 构建输出
    return _build_fused_output(sorted_entries, scored)


def _score_and_filter(results: dict, content_type: str, query_keyword: str) -> list[dict]:
    """步骤1: 给所有结果打分，同时过滤无关结果。"""
    prio_key = "default" if content_type in ("mod", "item") else "other"
    platform_prio = _CONTENT_PLATFORM_PRIORITY[prio_key]

    scored = []
    for platform, hits in results.items():
        for h in hits:
            # 过滤 MC百科 安全验证（captcha）空数据
            h_name = h.get("name_zh") or h.get("name") or ""
            if platform == "mcmod.cn" and h_name == "安全验证中":
                continue

            score = _score_relevance(query_keyword, h, content_type=content_type)
            # 过滤 wiki 无匹配结果（分数为 0）
            if content_type == "mod" and platform in ("minecraft.wiki", "minecraft.wiki/zh"):
                if score == 0:
                    continue

            priority = platform_prio.get(platform, 99)
            scored.append({**h, "_platform": platform, "_score": score, "_priority": priority})

    return scored


def _entry_name_key(entry: dict) -> str:
    """从搜索结果中提取标准化名称键。"""
    return (entry.get("name_zh") or entry.get("name_en") or entry.get("name") or "").lower()


def _count_platform_hits(scored: list[dict]) -> dict[str, set]:
    """步骤2: 统计每个名称在多少个平台出现。"""
    name_platform_count = {}
    for entry in scored:
        key = _entry_name_key(entry)
        if key:
            if key not in name_platform_count:
                name_platform_count[key] = set()
            name_platform_count[key].add(entry["_platform"])
    return name_platform_count


def _deduplicate_by_name(scored: list[dict], name_platform_count: dict) -> dict[str, dict]:
    """步骤3: 同名去重（按分数从高到低，同分时保留平台权威度高的）。"""
    by_name = {}
    for entry in scored:
        key = _entry_name_key(entry)
        if not key:
            continue

        # 多平台命中加权
        platform_count = len(name_platform_count.get(key, set()))
        if platform_count > 1:
            entry["_score"] += (platform_count - 1) * _SCORE_MULTI_PLATFORM_BONUS

        if key not in by_name:
            by_name[key] = entry
        elif entry["_score"] > by_name[key]["_score"]:
            by_name[key] = entry
        elif entry["_score"] == by_name[key]["_score"]:
            if entry["_priority"] < by_name[key]["_priority"]:
                by_name[key] = entry

    return by_name


def _sort_entries(by_name: dict[str, dict]) -> list[dict]:
    """步骤4: 排序（分数 DESC，同分时 priority ASC 即高优先级在前）。"""
    return sorted(by_name.values(), key=lambda e: (e["_score"], -e["_priority"]), reverse=True)


def _build_fused_output(sorted_entries: list[dict], scored: list[dict]) -> list[dict]:
    """步骤5: 构建融合结果输出。"""
    fused = []
    for entry in sorted_entries:
        # 保留分数，移除其他 _ 字段
        merged = {k: v for k, v in entry.items() if not k.startswith("_") or k == "_score"}

        # 收集所有同名结果的平台，并去重
        entry_name = _entry_name_key(entry)
        platforms = [e["_platform"] for e in scored
                     if _entry_name_key(e) == entry_name]
        merged["_sources"] = list(dict.fromkeys(platforms))

        if len(merged["_sources"]) > 1:
            # 多平台同名结果：组合 source 字段（如 "mcmod.cn|modrinth"）
            merged["source"] = "|".join(merged["_sources"])

        fused.append(merged)
    return fused
