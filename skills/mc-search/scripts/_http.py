#!/usr/bin/env python3
"""mc-search HTTP/工具层：异常类、常量、CDN绕过、curl、HTML清洗"""

# ── 标准库导入 ─────────────────────────────────────────
import base64
import html as html_module  # 别名：与 html变量名区分
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent import futures as futures_module  # ThreadPoolExecutor
from enum import IntEnum
from pathlib import Path

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

# 注：MC百科所有子域名 (www + search + 其他) 和 minecraft.wiki 使用 curl_cffi；其余平台使用标准库

# 配置日志
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class SearchError(Exception):
    """搜索过程中的可区分错误基类。

    在以下场景会被 raise：
    - MC百科搜索结果页结构变化（无 search-result-list）
    - MC百科无结果
    - 作者搜索未找到作者页面
    - 作者页面被防火墙拦截
    """
    pass


HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _make_headers(extra: dict | None = None) -> dict:
    """构建标准 HTTP 请求头，可选合并额外字段。"""
    headers = dict(HTTP_HEADERS)
    if extra:
        headers.update(extra)
    return headers


# 常量定义
MIN_HTML_LEN = 1000         # 正常页面3-8KB，错误页<500B；核心检测阈值
MIN_HTML_LEN_ITEM = 500     # 物品页无侧边栏，结构更紧凑
_MIN_SHORT_TEXT_LEN = 35    # 低于此长度视为无意义内容
_MIN_DESCRIPTIVE_LI_LEN = 50  # 列表项需有足够描述性内容
_MIN_DESCRIPTION_LINE_LEN = 10  # 描述文字单行最小长度
_MIN_SECTION_MARKER_DISTANCE = 200  # section marker 最小距离
_MIN_TABLE_CELL_LEN = 2             # 表格单元格最小有意义内容长度
_MAX_TABLE_ITEMS = 50               # 单个表格最大处理行数（性能保护）
_MAX_VERSION_GROUPS = 5             # 版本组最大数量
_MAX_CHANGELOGS = 5                 # 更新日志最大数量
_MAX_FETCH_WORKERS = 5              # 详情并行获取最大 worker 数
_MODRINTH_API = "https://api.modrinth.com/v2"  # Modrinth API 基础 URL
_MAX_GALLERY = 0            # 默认不返回画廊（可配置）
_EMPTY_MODRINTH_RESULT = {"results": [], "total": 0, "returned": 0}  # 平台搜索失败时的空信封
_MAX_TAG_SECTION_LEN = 500  # 标签区段最大长度
_EXTERNAL_LINK_EXCLUDE_DOMAINS = ["curseforge", "modrinth", "github", "discord", "wikipedia", "mcbbs", "jenkins", "archive"]

# 模糊匹配参数（融合管线去重步骤使用）
FUZZY_MATCH_THRESHOLD = 0.85  # 模糊匹配相似度阈值，≥0.85 视为同一实体
FUZZY_MIN_LEN = 4             # 模糊匹配最小长度，短于 4 字符的 key 不做模糊匹配


# ── 外部链接分类：具名函数替代 lambda，提升可读性与可测试性 ──────────────

def _is_modrinth_link(url: str) -> bool:
    """判断是否为 Modrinth 链接。"""
    return "modrinth.com" in url


def _is_wiki_link(url: str) -> bool:
    """判断是否为 Wiki 链接（排除 GitHub）。"""
    return "wiki" in url.lower() and "github.com" not in url


def _is_discord_link(url: str) -> bool:
    """判断是否为 Discord 邀请链接。"""
    return "discord.gg" in url or "discord.com/invite" in url


def _is_jenkins_link(url: str) -> bool:
    """判断是否为 Jenkins/C I 链接。"""
    return "jenkins" in url.lower() or "ci." in url


def _is_mcbbs_link(url: str) -> bool:
    """判断是否为 MCBBS 链接。"""
    return "mcbbs" in url


# MC百科外部链接分类规则：(匹配函数, key)。按顺序匹配第一个命中，key 已存在则跳过
_SIMPLE_LINK_RULES = [
    (_is_modrinth_link, "modrinth"),
    (_is_wiki_link, "wiki"),
    (_is_discord_link, "discord"),
    (_is_jenkins_link, "jenkins"),
    (_is_mcbbs_link, "mcbbs"),
]
_MAX_TAG_TEXT_LEN = 20      # 单个标签最大字符数
_MAX_SEARCH_SEGMENT = 2000  # 搜索区段最大长度
_MAX_DESCRIPTION_SEGMENT = 70000  # 描述区段最大长度
_MAX_SEARCH_DESC_CHARS = 500  # 搜索结果描述最大字符数
_MAX_AUTHOR_SECTION = 50000  # 作者区段最大长度
_MAX_INFO_TABLE_SECTION = 2000  # 信息表区段最大长度
_MAX_VERSION_SECTION_LEN = 3000  # 版本检索区域长度
_MAX_VERSIONS_FETCH = 200    # 版本列表最大获取数
# 注：WAF 签名需保守选择。"折翼喵"在 MC百科 正常页脚中出现，此处不收录
_WAF_SIGNATURES = ["AIWAFCDN", "防火墙拦截", "访问被拒绝"]  # WAF/CDN 拦截页面特征签名
_WAF_CC_CHECK = "CC check"  # MC百科 CDN 盾检测关键词
_MIN_TOKEN_PAGE_LEN = 500   # yxd_token 页面长度阈值
_MAX_CC_PAGE_LEN = 10000    # CC check 页面最大长度阈值
_MCMOD_RETRY_CODES = (403, 502, 503)  # MC百科可重试的 HTTP 状态码
_SEARCH_CHANGELOG_LIMIT = 3  # 搜索结果中更新日志数量限制
_SKIP_MCMOD_ORG_NAMES = {"CaffeineMC"}  # 排除的非作者组织名
_DEFAULT_RESULTS_PER_PLATFORM = 10  # AI-first: Agent 场景默认结果数

_MAX_MCMOD_AUTHORS = 10           # MC百科作者最大数量
_KNOWN_LOADERS = {"fabric", "forge", "neoforge", "quilt"}  # 已知加载器集合

# CDN 绕过配置
_CURL_IMPERSONATE = "chrome124"  # curl_cffi 模拟的浏览器 TLS 指纹版本
_MCMOD_CDN_SHIELD = "https://www.mcmod.cn/cdn-shield/check"  # CDN 盾验证端点
_CC_CHECK_FIELDS = ["navigator", "userAgent", "windowWidth", "performance", "callPhantom"]  # CC check 字段列表
_CDN_BYPASS_RETRIES = 3  # CDN 绕过外层重试次数
_CDN_RETRY_ATTEMPTS = 2  # CC check 后重试原请求次数


# ═══════════════════════════════════════════════════════════════
# MC百科 网络层（CDN绕过 + curl封装）
# ═══════════════════════════════════════════════════════════════

def _is_mcmod_blocked(html: str) -> bool:
    """检测页面是否被 MC百科 WAF/防火墙/验证码拦截。"""
    if not html:
        return True
    # 503 + AIWAFCDN 是明确的 WAF 错误页
    if "Error Code: 503" in html and "AIWAFCDN" in html:
        return True
    # 短页面（<1000B）含可疑签名 → 被阻断
    if len(html) < MIN_HTML_LEN and any(sig in html for sig in _WAF_SIGNATURES):
        return True
    # Captcha/限流页面（通常 15KB+，不含 WAF 签名，需检测标题）
    title_m = re.search(r'<title>([^<]+)</title>', html)
    if title_m:
        title = title_m.group(1)
        if title in ("安全验证", "安全验证中", "访问间隔过短，请稍后再试"):
            return True
    return False


def _url_tail_key(url: str) -> str:
    """从 URL 提取尾部 ID 用于去重比较。
    /class/2785.html?foo=bar -> 2785
    """
    return url.split("?")[0].rstrip("/").rsplit("/", 1)[-1].lower()


def _extract_mcmod_id(url: str, prefix: str) -> str:
    """从MC百科URL提取数字ID。prefix: 'class'/'item'/'modpack'"""
    if not url:
        return ""
    m = re.search(rf'/{prefix}/(\d+)', url)
    return m.group(1) if m else ""


def _build_mcmod_fallback_result(url: str, name: str, meta: dict | None = None,
                                  content_type: str = "mod") -> dict:
    """当详情页被 WAF 拦截时，从搜索数据构建最小结果。"""
    if meta is None:
        meta = {}

    # 解析名称（格式："中文名 (English Name)" 或 "English Name"）
    name_zh = name
    name_en = ""
    m = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', name)
    if m:
        name_zh = m.group(1).strip()
        name_en = m.group(2).strip()

    # 确定类型和 source_id
    if content_type == "item":
        source_id = _extract_mcmod_id(url, "item")
        type_name = "item"
    elif content_type == "modpack":
        source_id = _extract_mcmod_id(url, "modpack")
        type_name = "modpack"
    else:
        source_id = _extract_mcmod_id(url, "class")
        type_name = "mod"

    # 分类：从 meta 中提取
    categories = []
    if meta.get("category"):
        try:
            categories = [int(meta["category"])]
        except (ValueError, TypeError):
            categories = [meta["category"]]

    # 描述：优先用 meta 中的，否则尝试从名称中提取（如无）
    description = meta.get("description", "")

    result = {
        "name": name_zh or name,
        "name_en": name_en,
        "name_zh": name_zh or name,
        "url": url,
        "source": "mcmod.cn",
        "source_id": source_id,
        "type": type_name,
        "is_vanilla": bool(re.search(r"/class/1\.html", url)),
        "cover_image": "",
        "screenshots": [],
        "supported_versions": [],
        "categories": categories,
        "tags": [],
        "author": None,
        "author_team": None,
        "community_stats": None,
        "status": None,
        "source_type": None,
        "description": description,
        "relationships": {"_error": "parse_failed"},
        "has_changelog": False,
        "external_links": None,
        "content_list": None,
    }
    return result


def _build_truncated_meta(description: str,
                          max_chars: int,
                          screenshots_meta: dict | None = None) -> dict | None:
    """构建截断元信息。无截断时返回 None。

    参数:
        description: 描述文本
        max_chars: 最大字符数
        screenshots_meta: 截图截断元信息（可选，默认 None）
    """
    truncated = dict(screenshots_meta) if screenshots_meta else {}
    if description and len(description) > max_chars:
        truncated["description"] = {"returned": max_chars, "total": len(description)}
    return truncated or None


def _apply_truncation(result: dict, field: str, max_chars: int) -> None:
    """对 result 中的指定字段进行截断，并添加 _truncated 元信息。原地修改。"""
    value = result.get(field)
    if value and len(value) > max_chars:
        full_len = len(value)
        result[field] = value[:max_chars]
        result.setdefault("_truncated", {})[field] = {"returned": max_chars, "total": full_len}


def _clean_mcmod_html(content: str) -> str:
    """清理 MC百科 HTML：移除 script/style/img 标签，转换 br/p 为换行。

    闭合标签存在性预检避免缺失标签时 re.DOTALL 全段扫描。
    """
    if '</script>' in content:
        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
    if '</style>' in content:
        content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
    content = re.sub(r"<img[^>]*>", "", content)
    content = re.sub(r"<br\s*/?>", "\n", content)
    content = re.sub(r"<p[^>]*>", "\n", content)
    return content


# 搜索评分常量 - 使用枚举类组织
class MatchScore(IntEnum):
    """搜索结果匹配度评分权重"""
    # 精确匹配
    EXACT_MATCH_BASE = 200
    EXACT_MATCH_MAX_BONUS = 20
    EXACT_MATCH_BONUS_FACTOR = 2

    # 前缀匹配
    PREFIX_BASE = 60
    PREFIX_MAX_BONUS = 15
    PREFIX_BONUS_FACTOR = 2

    # 全词匹配（词边界检查，防止 "OreSpawn" 匹配 "spawn"）
    WHOLE_WORD_BASE = 45

    # 包含匹配
    CONTAINS_BASE = 30
    CONTAINS_MAX_POS_BONUS = 10
    CONTAINED_IN_QUERY = 20

    # 辅助规则
    MIN_LENGTH_FOR_CONTAINED = 2
    SECONDARY_PENALTY = 10
    SECONDARY_MIN = 10

    # 特殊加分
    SNIPPET_BONUS = 5
    WIKI_ITEM_BONUS = 5
    MULTI_PLATFORM_BONUS = 10



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
# 过滤描述中的元数据行：如 "Mod (123)"、"Mod 讨论 (123)" 等
_MOD_META_PAT = re.compile(r"^(?:\(\d+\)\s*)?Mod(?:讨论|教程)\s*\(\d+\)")

# MC百科整合包多 filter 策略（按优先级）
_MCMOD_MODPACK_FILTERS = [
    _MCMOD_FILTER_MODPACK_ZH,   # 中文关键词效果最佳
    _MCMOD_FILTER_MOD,           # 模组搜索（补充）
    _MCMOD_FILTER_MODPACK_ALT,   # 另一种整合包过滤
    _MCMOD_FILTER_MODPACK_OLD,   # 旧版过滤（较少结果）
]

# === 项目类型常量 ===
# 文本类内容类型（MC百科 + Modrinth 都支持）
_TEXT_CONTENT_TYPES = frozenset({"mod", "item", "modpack"})
_VISUAL_CONTENT_TYPES = frozenset({"shader", "resourcepack"})
_MODRINTH_CONTENT_TYPES = _TEXT_CONTENT_TYPES | _VISUAL_CONTENT_TYPES

# === 平台优先级（数字越小越权威）===
# 默认优先级：MC百科 > Modrinth > Wiki（适用于 mod 和 item）
# 其他类型：Wiki > MC百科 > Modrinth（适用于 entity/biome/block/mechanic/dimension）
_CONTENT_PLATFORM_PRIORITY = {
    "default": {"mcmod.cn": 0, "modrinth": 1, "minecraft.wiki": 2, "minecraft.wiki/zh": 3},
    "other": {"minecraft.wiki": 0, "minecraft.wiki/zh": 1, "mcmod.cn": 2, "modrinth": 3},
}



def _clean_html_text(html_fragment: str, preserve_nl: bool = False) -> str:
    """去除所有 HTML 标签，转义实体，合并空白。

    preserve_nl=True 时保留换行符（仅合并水平空白），用于段落/列表等需要保留行结构的场景。
    """
    text = re.sub(r"<[^>]+>", "", html_fragment)
    text = html_module.unescape(text)
    if preserve_nl:
        text = re.sub(r"[ \t\r]+", " ", text).strip()
    else:
        text = re.sub(r"\s+", " ", text).strip()
    return text


# 平台开关

_platform_enabled = {"mcmod.cn": True, "modrinth": True, "minecraft.wiki": True, "minecraft.wiki/zh": True}
_PLATFORM_LOCK = threading.Lock()  # 保护 _platform_enabled 的并发读写


def set_platform_enabled(mcmod: bool = True, modrinth: bool = True, wiki: bool = True, wiki_zh: bool = True):
    """控制各平台搜索开关。

    Args:
        mcmod: MC百科开关
        modrinth: Modrinth 开关
        wiki: minecraft.wiki EN 开关
        wiki_zh: minecraft.wiki ZH 开关
    """
    global _platform_enabled
    with _PLATFORM_LOCK:
        _platform_enabled = {
            "mcmod.cn": mcmod,
            "modrinth": modrinth,
            "minecraft.wiki": wiki,
            "minecraft.wiki/zh": wiki_zh,
        }


# ── MC百科 CDN 绕过状态 ──────────────────────────────
# 每请求独立 Session + Cookie 缓存共享，消除多线程竞态
_MCMOD_COOKIES: dict[str, str] = {}
_MCMOD_COOKIES_LOCK = threading.RLock()
_MCMOD_BYPASSED = False
_MCMOD_BYPASSING = False
_MCMOD_STATE_LOCK = threading.RLock()


def _mcmod_host(url: str) -> str:
    """从 MC百科 URL 提取主机名，用于 cookie 域名。"""
    m = re.match(r'https?://([^/]+)', url)
    return m.group(1) if m else "www.mcmod.cn"


def _inject_cookies(session, base_url: str) -> None:
    """将缓存的绕过 Cookie 注入到 session 中（只读快照，无锁争用）。"""
    host = _mcmod_host(base_url)
    with _MCMOD_COOKIES_LOCK:
        cookies_snapshot = dict(_MCMOD_COOKIES)
    for name, value in cookies_snapshot.items():
        session.cookies.set(name, value, domain=host, path="/")


def _extract_and_cache_cookies(session, base_url: str) -> None:
    """从 session 提取 Cookie 并缓存（绕过成功后调用，原子替换）。"""
    host = _mcmod_host(base_url)
    new_cookies = {}
    for cookie in session.cookies.jar:
        if cookie.domain:
            cookie_domain = cookie.domain.lstrip('.')
            if host == cookie_domain or host.endswith('.' + cookie_domain):
                new_cookies[cookie.name] = cookie.value
    if new_cookies:
        with _MCMOD_COOKIES_LOCK:
            _MCMOD_COOKIES.clear()
            _MCMOD_COOKIES.update(new_cookies)


def _do_cdn_shield_post(session, base_url: str, headers: dict, timeout: int) -> None:
    """POST /cdn-shield/check 完成 CDN 验证，跟随 Location 重定向。"""
    data = {k: "false" for k in _CC_CHECK_FIELDS}
    data["v1"] = ""
    ch = {**headers, "Content-Type": "application/x-www-form-urlencoded",
          "Referer": base_url + "/", "Origin": base_url}
    r = session.post(
        base_url + "/cdn-shield/check", data=data,
        impersonate=_CURL_IMPERSONATE, headers=ch, allow_redirects=False, timeout=timeout
    )
    loc = r.headers.get("Location")
    if loc:
        session.get(
            urllib.parse.urljoin(base_url, loc),
            impersonate=_CURL_IMPERSONATE, headers=headers, timeout=timeout
        )


def _handle_yxd_token(session, text: str, base_url: str, headers: dict, timeout: int) -> str:
    """处理 yxd_token 页面：提取 token、设置 cookie、跟随重定向。
    返回重定向后的 HTML，失败返回空字符串。"""
    token_m = re.search(r"yxd_token=([^;'\"\s]+)", text)
    if not token_m:
        return ""
    host = _mcmod_host(base_url)
    session.cookies.set("yxd_token", token_m.group(1), domain=host, path="/")
    href_m = re.search(r"window\.location\.href='([^']+)'", text)
    if not href_m:
        return ""
    target = urllib.parse.urljoin(base_url, href_m.group(1))
    try:
        r = session.get(target, impersonate=_CURL_IMPERSONATE, headers=headers, timeout=timeout)
        return r.text
    except Exception as e:
        logger.warning(f"yxd_token redirect failed: {e}")
        return ""


def _bypass_mcmod_cdn(timeout: int = 15) -> bool:
    """绕过 www.mcmod.cn 的 CDN 盾。使用本地 Session，成功时缓存 Cookie。

    同一时刻只有一个线程执行绕过（_MCMOD_BYPASSING 互斥）。
    其他线程看到 _MCMOD_BYPASSING=True 时返回 False，由调用方重试等待。
    """
    global _MCMOD_BYPASSED, _MCMOD_BYPASSING

    with _MCMOD_STATE_LOCK:
        if _MCMOD_BYPASSED:
            return True
        if _MCMOD_BYPASSING:
            return False  # 另一个线程正在绕过
        _MCMOD_BYPASSING = True

    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        logger.error("curl_cffi 未安装，无法访问 MC百科 (www.mcmod.cn)")
        with _MCMOD_STATE_LOCK:
            _MCMOD_BYPASSING = False
        return False

    session = curl_requests.Session()
    base_url = "https://www.mcmod.cn"
    headers = _make_headers()

    try:
        r = session.get(
            base_url + "/", impersonate=_CURL_IMPERSONATE, headers=headers, timeout=timeout
        )
        page_text = r.text

        # yxd_token 页面：提取 token、设置 cookie、跟随重定向
        if 'yxd_token=' in page_text and len(page_text) < _MIN_TOKEN_PAGE_LEN:
            token_m = re.search(r"yxd_token=([^;'\"\s]+)", page_text)
            if not token_m:
                raise SearchError("yxd_token not found")
            session.cookies.set("yxd_token", token_m.group(1),
                                domain="www.mcmod.cn", path="/")
            href_m = re.search(r"window\.location\.href='([^']+)'", page_text)
            if href_m:
                target = urllib.parse.urljoin(base_url + "/", href_m.group(1))
                r = session.get(target, impersonate=_CURL_IMPERSONATE,
                                headers=headers, timeout=timeout)
                page_text = r.text

        # CC check：POST 浏览器指纹数据完成验证
        if _WAF_CC_CHECK in page_text and len(page_text) < _MAX_CC_PAGE_LEN:
            data = {k: "false" for k in _CC_CHECK_FIELDS}
            data["v1"] = ""
            ch = {**headers, "Content-Type": "application/x-www-form-urlencoded",
                  "Referer": base_url + "/", "Origin": base_url}
            r = session.post(
                base_url + "/cdn-shield/check", data=data,
                impersonate=_CURL_IMPERSONATE, headers=ch,
                allow_redirects=False, timeout=timeout
            )
            loc = r.headers.get("Location")
            if loc:
                session.get(
                    urllib.parse.urljoin(base_url, loc),
                    impersonate=_CURL_IMPERSONATE, headers=headers, timeout=timeout
                )

        # 绕过成功：缓存 Cookie，标记完成
        _extract_and_cache_cookies(session, base_url)
        with _MCMOD_STATE_LOCK:
            _MCMOD_BYPASSED = True
            _MCMOD_BYPASSING = False
        return True

    except Exception as e:
        logger.warning(f"MC百科 CDN 绕过失败: {e}")
        with _MCMOD_STATE_LOCK:
            _MCMOD_BYPASSING = False
        return False


def _reset_mcmod_session():
    """重置 MC百科 CDN 绕过状态和 Cookie 缓存。

    _MCMOD_BYPASSING 不在此清除——仅 _bypass_mcmod_cdn 管理该标志，
    避免多线程同时绕过时互相干扰。
    """
    global _MCMOD_BYPASSED
    with _MCMOD_STATE_LOCK:
        _MCMOD_BYPASSED = False
    with _MCMOD_COOKIES_LOCK:
        _MCMOD_COOKIES.clear()


def _curl_mcmod(url: str, timeout: int = 10) -> str:
    """使用 curl_cffi 请求 *.mcmod.cn。每请求独立 Session，Cookie 缓存共享。

    并发安全：每个调用创建自己的 Session，绕过 Cookie 从缓存注入后只读使用。
    WAF 恢复（yxd_token、CC check）在本地 Session 上处理，不污染其他线程。
    """
    headers = _make_headers()

    for attempt in range(_CDN_BYPASS_RETRIES):
        # 等待绕过完成（如果其他线程正在执行绕过）
        with _MCMOD_STATE_LOCK:
            bypassed = _MCMOD_BYPASSED
            bypassing = _MCMOD_BYPASSING

        if not bypassed and not bypassing:
            # 本线程负责绕过
            if _bypass_mcmod_cdn(timeout=timeout):
                pass  # 绕过成功
            elif attempt == 0:
                _reset_mcmod_session()
                time.sleep(0.5)
                continue
            else:
                return ""

        elif not bypassed and bypassing:
            # 另一线程正在绕过，退避等待
            if attempt < _CDN_BYPASS_RETRIES - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            return ""

        # 创建本地 Session，注入缓存 Cookie
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            return ""
        session = curl_requests.Session()
        _inject_cookies(session, url)

        try:
            r = session.get(url, impersonate=_CURL_IMPERSONATE, headers=headers, timeout=timeout)
        except Exception as e:
            logger.warning(f"MC百科请求失败 ({url}): {e}")
            if attempt == 0:
                _reset_mcmod_session()
            continue

        text = r.text

        # Captcha / 限流页面：退避后重试
        if '<title>安全验证</title>' in text[:2000] or '<title>访问间隔过短' in text[:2000]:
            _reset_mcmod_session()
            if attempt < _CDN_BYPASS_RETRIES - 1:
                time.sleep(1.0 + attempt)
            continue

        # yxd_token 页面：在本地 Session 上处理
        if 'yxd_token=' in text and len(text) < _MIN_TOKEN_PAGE_LEN:
            html = _handle_yxd_token(session, text, url, headers, timeout)
            if html:
                return html
            return ""

        # CC check：在本地 Session 上处理
        if _WAF_CC_CHECK in text and len(text) < _MAX_CC_PAGE_LEN:
            host = _mcmod_host(url)
            base = f"https://{host}"
            try:
                _do_cdn_shield_post(session, base, headers, timeout)
                for _ in range(_CDN_RETRY_ATTEMPTS):
                    r = session.get(url, impersonate=_CURL_IMPERSONATE, headers=headers, timeout=timeout)
                    if _WAF_CC_CHECK not in r.text or len(r.text) >= _MAX_CC_PAGE_LEN:
                        _extract_and_cache_cookies(session, base)
                        return r.text
            except Exception as e:
                logger.warning(f"CDN bypass post failed for {host}: {e}")
                _reset_mcmod_session()
            continue

        return text

    return ""


def _curl_wiki(url: str, timeout: int = 10) -> str:
    """使用 curl_cffi 请求 minecraft.wiki（绕过反爬虫拦截）。"""
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        logger.error("curl_cffi 未安装，无法访问 minecraft.wiki")
        return ""
    headers = _make_headers()
    try:
        r = curl_requests.get(url, impersonate=_CURL_IMPERSONATE, headers=headers, timeout=timeout)
        return r.text
    except Exception as e:
        logger.warning(f"Wiki 请求失败 ({url}): {e}")
        return ""


def curl(url: str, timeout: int = 10) -> str:
    """发起 HTTP 请求，返回 HTML 内容（失败返回空字符串）。

    - www.mcmod.cn / search.mcmod.cn：使用 curl_cffi + CDN 绕过
    - minecraft.wiki / zh.minecraft.wiki：使用 curl_cffi 绕过反爬
    - 其他 URL：标准 urllib.request

        """
    # MC百科所有子域名需要 CDN 绕过（www + search）
    if "://www.mcmod.cn/" in url or "://search.mcmod.cn/" in url:
        html = _curl_mcmod(url, timeout)
        return html
    # minecraft.wiki 需要 curl_cffi 绕过反爬
    if "://minecraft.wiki/" in url or "://zh.minecraft.wiki/" in url:
        return _curl_wiki(url, timeout)

    try:
        req = urllib.request.Request(
            url,
            headers=_make_headers()
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if "modrinth.com" in url and e.code == 429:
            logger.warning(f"Modrinth API 限流 (HTTP 429)，建议稍后重试。")
        elif "mcmod.cn" in url and e.code in _MCMOD_RETRY_CODES:
            logger.error(f"MC百科 (mcmod.cn) 服务暂时不可用 (HTTP {e.code})，可能正在维护或遭受攻击。建议稍后重试或使用 --platform modrinth 仅搜索 Modrinth。")
        else:
            logger.warning(f"HTTP {e.code} for {url}: {e.reason}")
        return ""
    except urllib.error.URLError as e:
        if "mcmod.cn" in url:
            logger.error(f"无法连接到 MC百科 (mcmod.cn)：{e.reason}。建议检查网络或使用 --platform modrinth。")
        else:
            logger.warning(f"URL error for {url}: {e.reason}")
        return ""
    except TimeoutError as e:
        if "mcmod.cn" in url:
            logger.warning(f"MC百科请求超时。建议稍后重试或使用 --platform modrinth 仅搜索 Modrinth。")
        else:
            logger.warning(f"Request timeout for {url}")
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
    # 闭合标签存在性预检：避免缺失 </a> 时 re.DOTALL 全段扫描
    if '</a>' in text:
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

    # 7. 处理代码块（闭合标签存在性预检）
    if '</pre>' in text:
        text = re.sub(r'<pre[^>]*>(.*?)</pre>', r'```\n\1\n```\n', text, flags=re.DOTALL | re.IGNORECASE)
    if '</code>' in text:
        text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL | re.IGNORECASE)

    # 8. 处理粗体和斜体（闭合标签存在性预检）
    if '</strong>' in text or '</b>' in text:
        text = re.sub(r'<(strong|b)[^>]*>(.*?)</\1>', r'**\2**', text, flags=re.DOTALL | re.IGNORECASE)
    if '</em>' in text or '</i>' in text:
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
