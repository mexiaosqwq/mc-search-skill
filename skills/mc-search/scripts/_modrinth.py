#!/usr/bin/env python3
"""mc-search Modrinth 模块 — 搜索/详情/依赖/作者"""

import json
import re
import time
import urllib.parse
import urllib.request

from ._http import (
    logger, SearchError,
    curl, _fetch_json,
    _html_to_text, _clean_html_text,
    _build_truncated_meta, _apply_truncation,
    _DEFAULT_RESULTS_PER_PLATFORM,
    HTTP_HEADERS,
    _MODRINTH_API,
    _MAX_FETCH_WORKERS,
    _MAX_SEARCH_DESC_CHARS,
    _SEARCH_CHANGELOG_LIMIT,
    _MAX_VERSIONS_FETCH,
    _KNOWN_LOADERS,
    _MAX_VERSION_GROUPS,
    _MAX_CHANGELOGS,
    _MAX_GALLERY,
)
from ._mcmod_search import _parallel_fetch_with_fallback


# ═══════════════════════════════════════════════════════════════
# Modrinth API
# ═══════════════════════════════════════════════════════════════

def _build_modrinth_url(slug: str, project_type: str) -> str:
    """构建Modrinth URL。返回 "https://modrinth.com/{type}/{slug}"。"""
    return f"https://modrinth.com/{project_type or 'mod'}/{slug}"



def search_modrinth(keyword: str, max_results: int = 5, project_type: str = "mod") -> dict:
    """Modrinth搜索。返回 {"results": [...], "total": N, "returned": M}。

    每个结果包含完整description（与MC百科齐平）。详情（body+changelogs）并行获取。
    """
    q = urllib.parse.quote(keyword)
    url = f"{_MODRINTH_API}/search?query={q}&index=relevance&limit={max_results}"
    data = _fetch_json(url, {"hits": []})
    if not data or "hits" not in data:
        return {"results": [], "total": 0, "returned": 0}

    # 1. 收集匹配的 hits
    matched_hits = []
    for hit in data.get("hits", []):
        proj_type = hit.get("project_type", "")
        if project_type and proj_type and proj_type != project_type:
            continue
        matched_hits.append((hit, hit.get("slug", "")))

    if not matched_hits:
        # 分类容错：project_type 过滤无结果时，去过滤重试（如 Iris 被归为 mod 非 shader）
        if project_type and project_type != "mod":
            for hit in data.get("hits", []):
                matched_hits.append((hit, hit.get("slug", "")))
        if not matched_hits:
            return {"results": [], "total": data.get("total_hits", 0), "returned": 0}

    # 2. 并行获取详情（body + changelogs）
    def _fetch_detail(args):
        hit, slug = args
        if not slug:
            return (hit, None)
        try:
            return (hit, fetch_mod_info(slug, no_limit=True))
        except Exception as e:
            logger.debug(f"detail fetch failed for {hit.get('slug')}: {e}")
            hit["_body_error"] = "fetch_failed"
            return (hit, None)

    details = _parallel_fetch_with_fallback(
        matched_hits, _fetch_detail,
        max_workers=min(len(matched_hits), _MAX_FETCH_WORKERS)
    )

    # 3. 构建结果（保持搜索 API 的顺序）
    results = []
    for hit, full_info in details:
        proj_type = hit.get("project_type", "")
        slug = hit.get("slug", "")
        description = hit.get("description", "")
        changelogs = []
        if full_info:
            body = full_info.get("body", "")
            if body:
                description = body[:_MAX_SEARCH_DESC_CHARS] + ("..." if len(body) > _MAX_SEARCH_DESC_CHARS else "")
            cl_list = full_info.get("changelogs", [])
            changelogs = cl_list[:_SEARCH_CHANGELOG_LIMIT]

        result = {
            "name": hit.get("title", ""),
            "name_en": hit.get("_name_en") or hit.get("title", ""),
            "name_zh": "",
            "url": _build_modrinth_url(slug, proj_type or project_type or "mod"),
            "source": "modrinth",
            "source_id": slug,
            "type": proj_type or project_type or "mod",
            "snippet": hit.get("description", ""),
            "description": description,
            "downloads": hit.get("downloads", 0),
            "followers": hit.get("follows", hit.get("followers", 0)),
            "icon_url": hit.get("icon_url", ""),
            "author": hit.get("author", ""),
            "supported_versions": hit.get("versions", []),
            "changelogs": changelogs,
        }
        results.append(result)

    total = data.get("total_hits", 0)
    return {"results": results, "total": total, "returned": len(results)}


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
    versions = _fetch_json(f"{_MODRINTH_API}/project/{project_id}/version?max={_MAX_VERSIONS_FETCH}", [])
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
        for loader in known_loaders:
            if stripped_ver.endswith(f"-{loader}"):
                stripped_ver = stripped_ver[:-len(loader) - 1]
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
    # no_limit=True: 取前5个
    # no_limit=False (普通命令): 取前3个
    changelog_limit = _MAX_CHANGELOGS if no_limit else _SEARCH_CHANGELOG_LIMIT
    changelogs = []
    for v in versions[:changelog_limit]:
        cl = v.get("changelog", "").strip()
        if cl:
            changelogs.append({
                "version": v.get("version_number", ""),
                "date": (v.get("date_published") or "").split("T")[0],
                "changelog": cl,
            })
    changelog_total = sum(1 for v in versions if v.get("changelog", "").strip())
    result["changelogs"] = changelogs
    result["_changelog_total"] = changelog_total  # 用于截断元信息

    return result


def _fetch_modrinth_team_author(project_id: str) -> str:
    """从团队成员中获取作者"""
    team = _fetch_json(f"{_MODRINTH_API}/project/{project_id}/members", [])
    for m in team:
        if m.get("role") in ("Owner", "Developer", "Project Lead"):
            return m.get("user", {}).get("username") or m.get("user", {}).get("name", "")
    return ""


def fetch_mod_info(mod_id: str, no_limit: bool = False) -> dict | None:
    """
    获取 mod 完整信息（Modrinth）。
    mod_id 可以是 slug 或 project_id。
    no_limit: True 时返回完整数据，False 时使用默认限制并返回 _truncated 元信息。
    失败时返回 {"_error": "not_found"} / {"_error": "rate_limited"} / {"_error": "api_failed"}。
    """
    data, error = _fetch_modrinth_project(mod_id)
    if error:
        return {"_error": error}
    return _build_modrinth_info_result(data, no_limit)


def _fetch_modrinth_project(mod_id: str) -> tuple[dict | None, str | None]:
    """获取 Modrinth 项目原始数据。

    Returns:
        (data, error) 元组。成功时 (dict, None)；失败时 (None, "not_found"|"rate_limited"|"api_failed"|"parse_failed")。
    """
    url = f"{_MODRINTH_API}/project/{mod_id}"
    try:
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            logger.warning(f"Modrinth API 限流 (HTTP 429)，建议稍后重试。")
            return None, "rate_limited"
        logger.warning(f"HTTP {e.code} for {url}: {e.reason}")
        return None, "not_found" if e.code == 404 else "api_failed"
    except urllib.error.URLError as e:
        logger.warning(f"URL error for {url}: {e.reason}")
        return None, "api_failed"
    except TimeoutError:
        logger.warning(f"Modrinth API 请求超时。")
        return None, "api_failed"

    if not raw:
        return None, "not_found"
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        return None, "parse_failed"


def _build_modrinth_info_result(data: dict, no_limit: bool = False) -> dict:
    """从 Modrinth 项目数据构建完整信息结果（含作者/版本/截断元信息）。"""
    project_id = data.get("id", "")

    # 解析许可证和捐赠
    license_id, license_name, license_url = _parse_modrinth_license(data.get("license"))
    donation_urls = _parse_modrinth_donations(data)

    # 处理 body 和 gallery
    raw_body = data.get("body") or ""
    body = _clean_modrinth_body(raw_body)
    raw_gallery = [g.get("url") for g in data.get("gallery", []) if g.get("url")]
    gallery_total = len(raw_gallery)

    # 构建基础结果
    ctx = {
        "license_id": license_id,
        "license_name": license_name,
        "license_url": license_url,
        "donation_urls": donation_urls,
    }
    result = _build_modrinth_result(data, project_id, body, raw_gallery, ctx)

    # 截断元信息
    truncated = {}
    if gallery_total > _MAX_GALLERY and not no_limit:
        truncated["gallery"] = {"returned": _MAX_GALLERY, "total": gallery_total}

    # 获取作者
    result["author"] = _fetch_modrinth_team_author(project_id)

    # 获取版本信息
    version_info = _format_modrinth_versions(project_id, no_limit)
    if version_info:
        result.update({
            "latest_version": version_info.get("latest_version"),
            "game_versions": version_info.get("game_versions"),
            "loaders": version_info.get("loaders"),
            "version_groups": version_info.get("version_groups"),
            "changelogs": version_info.get("changelogs"),
        })
        if not no_limit:
            version_total = version_info.get("_version_total", 0)
            changelog_total = version_info.get("_changelog_total", 0)
            if version_total > _MAX_VERSION_GROUPS:
                truncated["version_groups"] = {"returned": _MAX_VERSION_GROUPS, "total": version_total}
            if changelog_total > _MAX_CHANGELOGS:
                truncated["changelogs"] = {"returned": _MAX_CHANGELOGS, "total": changelog_total}

    if truncated:
        result["_truncated"] = truncated

    return result


def search_modrinth_author(username: str, max_results: int = 10) -> list[dict]:
    """Modrinth 按作者搜索。返回该作者在 Modrinth 的所有作品列表。

    Args:
        username: 作者用户名（需精确匹配）
        max_results: 最大返回作品数，默认 10

    Returns:
        作品列表，每项含 name, name_en, url, source, source_id, type,
        description, downloads, followers, icon_url, author, supported_versions 等字段。
    """
    q = urllib.parse.quote(username)
    # colon in filter=authors: must stay unencoded
    url = f"{_MODRINTH_API}/search?query={q}&filter=authors:{q}&index=relevance&limit={max_results}"
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
    return results


def get_mod_dependencies(mod_id: str, project_id: str = None) -> dict:
    """
    获取 mod 正向依赖（从最新版本提取）。
    返回 {"deps": {mod_slug: {id, name, slug, client_side, server_side, url}}}
    失败时返回 {"deps": {}, "_error": "not_found"}
    """
    if not project_id:
        proj = _fetch_json(f"{_MODRINTH_API}/project/{mod_id}")
        if not proj:
            return {"deps": {}, "_error": "not_found"}
        project_id = proj.get("id", mod_id)

    # 获取最新版本的正向依赖（?limit=1 保证返回最新版本）
    versions = _fetch_json(
        f"{_MODRINTH_API}/project/{project_id}/version?limit=1", default=[])
    if not versions:
        return {"deps": {}, "_error": "not_found"}

    latest = versions[0] if isinstance(versions, list) else versions
    dep_entries = latest.get("dependencies", [])

    # 过滤：仅保留正向依赖（排除 incompatible）
    valid_ids = []
    for dep in dep_entries:
        if dep.get("dependency_type", "") in ("required", "optional", "embedded"):
            pid = dep.get("project_id", "")
            if pid:
                valid_ids.append(pid)

    if not valid_ids:
        return {"deps": {}}

    # 批量获取依赖项目元数据（1 次 API 调用替代 N 次）
    ids_json = json.dumps(valid_ids)
    dep_projects = _fetch_json(
        f"{_MODRINTH_API}/projects?ids={urllib.parse.quote(ids_json)}",
        default=[])
    if not dep_projects:
        return {"deps": {}}

    deps = {}
    for dp in dep_projects:
        slug = dp.get("slug", "")
        dep_id = dp.get("id", "")
        key = slug or dep_id
        deps[key] = {
            "name": dp.get("title", slug or dep_id),
            "slug": slug,
            "id": dep_id,
            "client_side": dp.get("client_side", "unknown"),
            "server_side": dp.get("server_side", "unknown"),
            "url": f"https://modrinth.com/mod/{slug}" if slug else None,
        }

    return {"deps": deps}
