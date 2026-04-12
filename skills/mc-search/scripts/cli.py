#!/usr/bin/env python3
"""
mc-search CLI — Minecraft 聚合搜索工具
三命令扁平结构：search / show / wiki
"""

import argparse
import contextlib
import functools
import json
import os
import re
import sys
import time

from . import core

# ── 常量 ──────────────────────────────────────────────

_OUTPUT_DIR = os.environ.get(
    "MC_SEARCH_OUTPUT_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
)

# CLI 默认值（网络请求和显示配置）
_DEFAULT_MAX = 3
_DEFAULT_TIMEOUT = 12
_DEFAULT_WIKI_MAX = 5
_DEFAULT_PARAGRAPHS = 20
_EXACT_SEARCH_MAX = 5

# 显示截断配置（控制输出长度）
_DISPLAY_WIKI_PARAGRAPHS = -1
_DISPLAY_WIKI_SNIPPET_MAX = 150
_DISPLAY_WIKI_MAX_RESULTS = 10
_DISPLAY_WIKI_MAX_SECTIONS = 5
_DISPLAY_LINE_MAX = 200
_DISPLAY_READ_LINE_MAX = 250
_DISPLAY_MODRINTH_BODY_MAX = 500
_DISPLAY_INFO_DESC_MAX = 1500
_DISPLAY_INFO_DESC_TRUNCATE = 1000
_DISPLAY_CHANGELOG_MAX = 100
_DISPLAY_MAX_VERSIONS = 8
_DISPLAY_MAX_GALLERY = 10
_DISPLAY_MAX_AUTHOR_TEAM = 10
_DISPLAY_MAX_SEARCH_SHOTS = 3
_DISPLAY_MAX_SEARCH_SECTIONS = 5
_DISPLAY_URL_TRUNCATE = 80
_DISPLAY_MAX_RECIPE_IMAGES = 4

# 文件保存阈值（超过此长度自动保存）
_SAVE_BODY_LENGTH_THRESHOLD = 3000
_SAVE_DESC_LENGTH_THRESHOLD = 5000

# Modrinth 正文预览配置
_MODRINTH_PREVIEW_LEN = 2000
_MODRINTH_PREVIEW_SENTENCE_MIN = 1500
_MODRINTH_PREVIEW_MAX_PARAS = 10

# MC百科简介预览
_MCMOD_DESC_PREVIEW_LEN = 1500
_MCMOD_DESC_PREVIEW_SENTENCE_MIN = 1000
_MCMOD_DESC_PREVIEW_MAX_PARAS = 5

# Modrinth URL 正则表达式
_MODRINTH_URL_RE = re.compile(r"https://modrinth\.com/(mod|shader|resourcepack|modpack)/([^/?]+)")
_MODRINTH_SLUG_RE = re.compile(r"/(?:mod|shader|resourcepack|modpack)/([^/?#]+)")

# 文本映射表（平台状态翻译）
_SOURCE_TYPE_LABELS = {"open_source": "开源", "closed_source": "闭源"}
_SIDE_LABELS = {"required": "必需", "optional": "可选", "unsupported": "不支持", "unknown": "未知"}
_PROJECT_TYPE_LABELS = {
    "mod": "模组", "modpack": "整合包", "resourcepack": "材质包",
    "shader": "光影包", "block": "方块", "item": "物品", "entity": "实体",
}

# 搜索平台开关配置：(mcmod, modrinth, wiki, wiki_zh)
_PLATFORM_FLAGS = {
    "all":      (True,  True,  True,  True),
    "mcmod":    (True,  False, False, False),
    "modrinth": (False, True,  False, False),
    "wiki":     (False, False, True,  False),
    "wiki-zh":  (False, False, False, True),
}


def _find_sentence_boundary(text: str) -> int:
    """
    查找文本中最后一个句子边界位置。
    
    Args:
        text: 输入文本
        
    Returns:
        最后一个句子边界（。！？。.\n）的位置索引
    """
    """查找文本中最后一个句子边界位置。"""
    return max(text.rfind('。'), text.rfind('！'), text.rfind('？'),
               text.rfind('.'), text.rfind('\n'))


# info 字段输出配置：(属性名，显示标签，格式化函数)
# formatter 接收 info dict，返回要 print 的行列表，或 None 跳过
# formatter 接收 info dict，返回要 print 的行列表，或 None 跳过
def _fmt_title(info: dict) -> list:
    """
    格式化名称字段输出。
    
    Args:
        info: 模组信息字典
    
    Returns:
        要打印的行列表
    """
    lines = [f"  名称：{info.get('name_zh', '')}"]
    name_en = info.get("name_en", "")
    if name_en:
        lines.append(f"  英文名：{name_en}")
    lines.append(f"  平台：{info.get('source', 'mcmod.cn')}")
    lines.append(f"  链接：{info.get('url', '')}")
    return lines

def _fmt_status(info: dict) -> list | None:
    """
    格式化状态/开源属性字段输出。
    
    Args:
        info: 模组信息字典
    
    Returns:
        要打印的行列表，或 None 跳过
    """
    lines = []
    st = info.get("status")
    stype = info.get("source_type")
    if st:
        lines.append(f"  状态：{st}")
    if stype:
        lines.append(f"  开源属性：{_SOURCE_TYPE_LABELS.get(stype, stype)}")
    return lines or None

def _fmt_author(info: dict) -> list | None:
    """
    格式化作者字段输出。
    
    Args:
        info: 模组信息字典
    
    Returns:
        要打印的行列表，或 None 跳过
    """
    a = info.get("author")
    return [f"  作者：{a}"] if a else None

def _fmt_desc(info: dict, *, standalone: bool = True) -> list | None:
    """
    格式化简介字段输出（仅在 standalone 模式时输出）。

    描述仅在 standalone（全字段）模式时输出（不可单独过滤）。

    Args:
        info: 模组信息字典
        standalone: 是否全字段模式

    Returns:
        要打印的行列表，或 None 跳过
    """
    if not standalone:
        return None
    desc = info.get("description", "")
    if not desc:
        return None
    clean = core.clean_html_text(desc)
    if not clean:
        return None
    lines = ["\n  简介："]
    if len(clean) > _DISPLAY_INFO_DESC_MAX:
        truncated = clean[:_DISPLAY_INFO_DESC_MAX]
        last = _find_sentence_boundary(truncated)
        if last > _DISPLAY_INFO_DESC_TRUNCATE:
            truncated = truncated[:last + 1]
        lines.append(f"    {truncated}")
        lines.append(f"    ...（还有 {len(clean) - len(truncated)} 字符，完整内容请查看网页）")
    else:
        lines.append(f"    {clean}")
    return lines

def _fmt_deps(info):
    rel = info.get("relationships")
    if not rel:
        return ["  依赖：无（暂无关联模组）"]
    lines = []
    reqs = rel.get("requires", [])
    integ = rel.get("integrates", [])
    if reqs:
        lines.append(f"  前置Mod（{len(reqs)}）：")
        for r in reqs:
            lines.append(f"    - {r['name_zh']} ({r['name_en']})  {r['url']}")
    if integ:
        lines.append(f"  联动Mod（{len(integ)}）：")
        for r in integ:
            lines.append(f"    - {r['name_zh']} ({r['name_en']})  {r['url']}")
    return lines or ["  依赖：无（暂无关联模组）"]

def _fmt_versions(info):
    vers = info.get("supported_versions", [])
    if vers:
        return [f"  支持版本（{len(vers)}）：{', '.join(vers)}"]
    return ["  支持版本：无数据"]

def _fmt_cats(info):
    cats = info.get("categories", [])
    tags = info.get("tags", [])
    if cats or tags:
        lines = [f"  分类：{' | '.join(cats)}"]
        if tags:
            lines.append(f"  标签：{' '.join(tags)}")
        return lines
    return ["  分类/标签：无数据"]

def _fmt_gallery(info):
    lines = []
    cover = info.get("cover_image", "")
    shots = info.get("screenshots", [])
    if cover:
        lines.append(f"  封面：{cover}")
    if shots:
        lines.append(f"  截图（{len(shots)}）：")
        for s in shots:
            lines.append(f"    {s}")
    return lines or None

def _fmt_source(info, *, standalone=True):
    lines = []
    if not standalone:
        lines.append(f"  平台：{info.get('source', 'mcmod.cn')}")
        lines.append(f"  链接：{info.get('url', '')}")
    sid = info.get("source_id", "")
    lines.append(f"  Class ID：{sid}")
    return lines

_INFO_FIELDS = [
    ("title",    "仅名称/别名", _fmt_title),
    ("status",   "仅状态/开源属性", _fmt_status),
    ("author",   "仅作者",        _fmt_author),
    ("deps",     "仅前置/联动",    _fmt_deps),
    ("versions", "仅版本",        _fmt_versions),
    ("cats",     "仅分类/标签",    _fmt_cats),
    ("gallery",  "仅截图/封面",    _fmt_gallery),
    ("source",   "仅来源链接",     _fmt_source),
]


# ── 辅助函数 ──────────────────────────────────────────

def _save_full_description(project_name: str, content: str, content_type: str = "mod") -> str:
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\u4e00-\u9fff]', '_', project_name)[:50]
    filename = f"{safe_name}_{content_type}_full.md"
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(_OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {project_name} - 完整描述\n\n")
        f.write(f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
        f.write(content)
    return filepath


def _timed(json_mode=False):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            t0 = time.time()
            result = func(*args, **kwargs)
            if not json_mode:
                print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
            return result
        return wrapper
    return decorator


def _clean_markdown(text: str, full_clean: bool = False) -> str:
    if not text:
        return ""
    if full_clean:
        text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`{1,3}.*?`{1,3}', '', text)
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'<[^>]+>', '', text)
    if full_clean:
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    return re.sub(r'\s+', ' ', text).strip()


def _parse_project_identifier(project_arg: str) -> dict:
    if project_arg.startswith("https://www.mcmod.cn/class/"):
        m = re.search(r"/class/(\d+)", project_arg)
        return {"class_id": m.group(1) if m else None, "mcmod_name": None, "mr_slug": None}
    mr_match = _MODRINTH_URL_RE.search(project_arg)
    if mr_match:
        return {"class_id": None, "mcmod_name": None, "mr_slug": mr_match.group(2)}
    if project_arg.isdigit():
        return {"class_id": project_arg, "mcmod_name": None, "mr_slug": None}
    return {"class_id": None, "mcmod_name": project_arg, "mr_slug": None}


def _extract_slug_from_url(url: str) -> str:
    match = _MODRINTH_SLUG_RE.search(url)
    return match.group(1) if match else url


def _mcmod_class_url(class_id: str) -> str:
    return f"https://www.mcmod.cn/class/{class_id}.html"


def _print_error(msg: str, code: str, is_json: bool):
    """统一的错误输出。"""
    if is_json:
        print(json.dumps({"error": code, "message": msg}, ensure_ascii=False))
    else:
        print(msg)


# ── 显示函数 ──────────────────────────────────────────

def _type_badge(hit: dict) -> str:
    t = hit.get("type", "mod")
    badges = {"shader": "【光影】", "resourcepack": "【材质包】", "item": "【物品】"}
    return badges.get(t, f"【{t}】" if t != "mod" else "")


def _print_hit(hit: dict):
    name = hit.get("name_zh") or hit.get("name", "?")
    en = hit.get("name_en", "")
    src = hit.get("source", "")
    htype = hit.get("type", "mod")
    badge = _type_badge(hit)

    header = f"  ── {name}"
    if en and en != name:
        header += f" ({en})"
    if badge:
        header += f" {badge}"
    header += f" 【{src}】"
    print(header)

    # 元数据
    if src == "mcmod.cn":
        if htype == "item":
            cat = hit.get("category")
            mod_name = hit.get("source_mod_name")
            dur = hit.get("max_durability")
            stack = hit.get("max_stack")
            meta = []
            if cat: meta.append(f"分类: {cat}")
            if dur: meta.append(f"耐久: {dur}")
            if stack: meta.append(f"堆叠: {stack}")
            if meta: print(f"     {' | '.join(meta)}")
            if mod_name: print(f"     来自: {mod_name}")
        else:
            cats = hit.get("categories", [])
            st = hit.get("status")
            source_type = hit.get("source_type")
            author = hit.get("author")
            meta = []
            if cats: meta.append(f"分类: {' | '.join(cats)}")
            if st: meta.append(f"状态: {st}")
            if source_type: meta.append(_SOURCE_TYPE_LABELS.get(source_type, source_type))
            for m in meta:
                print(f"     {m}")
            if author: print(f"     作者: {author}")
    elif src == "modrinth":
        pt = hit.get("type", "mod")
        print(f"     类型: {pt}")

    # 描述
    desc = hit.get("snippet") or hit.get("description", "")
    if desc:
        desc = _clean_markdown(desc)
        if len(desc) > _DISPLAY_LINE_MAX:
            desc = desc[:_DISPLAY_LINE_MAX] + "…"
        print(f"     {desc}")

    # 封面 + 截图
    cover = hit.get("cover_image")
    if cover: print(f"     封面: {cover}")
    shots = hit.get("screenshots", [])
    if shots:
        print(f"     截图 ({len(shots)} 张):")
        for s in shots[:_DISPLAY_MAX_SEARCH_SHOTS]:
            print(f"       - {s[:_DISPLAY_URL_TRUNCATE]}")

    # Wiki 章节
    if hit.get("sections"):
        for s in hit["sections"][:_DISPLAY_MAX_SEARCH_SECTIONS]:
            print(f"     · {s}")

    url = hit.get("url")
    if url: print(f"     → {url}")


def _print_deps(deps: dict, mod_name: str = ""):
    dep_dict = deps.get("deps", {})
    if not dep_dict:
        print(f"[{mod_name}] 无声明依赖")
        return
    print(f"[{mod_name}] 依赖列表（共 {len(dep_dict)} 个）：")
    for dep_id, dep in dep_dict.items():
        client_label = _SIDE_LABELS.get(dep.get('client_side', 'unknown'), '?')
        server_label = _SIDE_LABELS.get(dep.get('server_side', 'unknown'), '?')
        dep_name = dep.get('name', dep_id)
        dep_url = dep.get('url', '')
        print(f"  • {dep_name}")
        print(f"    运行环境: 客户端{client_label}, 服务端{server_label}")
        if dep_url: print(f"    {dep_url}")


def _print_mr_stats(mr: dict):
    """打印 Modrinth 统计信息 + 双端支持。"""
    print(f"\n  统计:")
    print(f"    下载: {mr.get('downloads', 0):>10,} 次")
    print(f"    关注: {mr.get('followers', 0):>10,} 人")
    print(f"    作者: {mr.get('author', '?')}")
    print(f"    许可: {mr.get('license_name', 'N/A')}")

    client = mr.get('client_side', 'unknown')
    server = mr.get('server_side', 'unknown')
    print(f"\n  双端支持:")
    print(f"    客户端: {_SIDE_LABELS.get(client, client)}")
    print(f"    服务端: {_SIDE_LABELS.get(server, server)}")
    if client == 'required' and server == 'required':
        print(f"    → 这是双端必需模组，客户端和服务端都必须安装")
    elif client == 'optional' or server == 'optional':
        print(f"    → 这是双端可选模组")


def _print_mr_body(mr: dict, saved_files: list = None):
    """打印 Modrinth 正文预览。"""
    body = mr.get('body', '')
    if not body:
        return
    clean_body = _clean_markdown(body, full_clean=True)
    body_len = len(clean_body)
    if body_len > _SAVE_BODY_LENGTH_THRESHOLD:
        proj_name = mr.get('name', 'unknown')
        proj_type = mr.get('type', 'mod')
        filepath = _save_full_description(proj_name, clean_body, proj_type)
        if saved_files is not None:
            saved_files.append(filepath)
        print(f"\n  【详细说明】")
        preview = clean_body[:min(_MODRINTH_PREVIEW_LEN, body_len)]
        last_period = _find_sentence_boundary(preview)
        if last_period > _MODRINTH_PREVIEW_SENTENCE_MIN:
            preview = preview[:last_period + 1]
        elif last_period > 0:
            preview = preview[:last_period + 1] + '...'
        for p in preview.split('\n')[:_MODRINTH_PREVIEW_MAX_PARAS]:
            if p.strip(): print(f"    {p.strip()}")
        print(f"\n  💾 完整描述已保存到文件:")
        print(f"     {filepath}")
        print(f"     （共 {body_len} 字符）")
    else:
        print(f"\n  【详细说明】")
        for p in clean_body.split('\n'):
            if p.strip():
                text = p.strip()
                if len(text) > _DISPLAY_MODRINTH_BODY_MAX:
                    text = text[:_DISPLAY_MODRINTH_BODY_MAX] + '...'
                print(f"    {text}")


def _print_mr_versions(mr: dict):
    """打印 Modrinth 版本信息 + 更新日志。"""
    vg = mr.get("version_groups", [])
    if vg:
        print(f"\n  版本信息 (展示前{min(_DISPLAY_MAX_VERSIONS, len(vg))}个，共{len(vg)}个):")
        for vname, vinfo in vg[:_DISPLAY_MAX_VERSIONS]:
            gvs = ', '.join(vinfo.get('game_versions', [])[:3])
            lds = ', '.join(vinfo.get('loaders', []))
            print(f"    • {vname}")
            print(f"      Minecraft: {gvs}")
            print(f"      加载器: {lds}")
        if len(vg) > _DISPLAY_MAX_VERSIONS:
            print(f"    ... 还有 {len(vg) - _DISPLAY_MAX_VERSIONS} 个版本")

    changelogs = mr.get('changelogs', [])
    if changelogs:
        print(f"\n  最近更新:")
        for cl in changelogs:
            print(f"    • v{cl.get('version', '?')} ({cl.get('date', '?')})")
            log_text = cl.get('changelog', '')
            if log_text:
                log_clean = re.sub(r'[-*]', '', log_text).strip()[:_DISPLAY_CHANGELOG_MAX]
                if log_clean: print(f"      {log_clean}")


def _print_mr_gallery(mr: dict):
    """打印 Modrinth 截图画廊。"""
    gallery = mr.get('gallery', [])
    if not gallery:
        return
    total = len(gallery)
    display = min(_DISPLAY_MAX_GALLERY, total)
    print(f"\n  截图 (共 {total} 张，显示前 {display} 张):")
    for i, img_url in enumerate(gallery[:display], 1):
        print(f"    {i}. {img_url}")
    if total > display:
        print(f"    ... 还有 {total - display} 张")


def _print_full_modrinth_info(mr: dict, saved_files: list = None):
    print(f"\n【Modrinth - {mr.get('name', '?')}】")
    print(f"  平台: {mr.get('url', '')}")

    _print_mr_stats(mr)
    _print_mr_body(mr, saved_files)

    categories = mr.get('categories', [])
    display_cats = mr.get('display_categories', [])
    all_cats = set(categories + display_cats)
    print(f"\n  分类: {', '.join(sorted(all_cats))}" if all_cats else "\n  分类: 暂无")

    links = []
    if mr.get('source_url'): links.append(f"源码: {mr['source_url']}")
    if mr.get('issues_url'): links.append(f"问题: {mr['issues_url']}")
    if mr.get('wiki_url'): links.append(f"Wiki: {mr['wiki_url']}")
    if mr.get('discord_url'): links.append(f"Discord: {mr['discord_url']}")
    if links:
        print(f"\n  相关链接:")
        for link in links: print(f"    • {link}")
    else:
        print(f"\n  相关链接: 暂无")

    _print_mr_versions(mr)
    _print_mr_gallery(mr)


def _print_full_mcmod_info(mc: dict, full_desc: bool = False, saved_files: list = None):
    print(f"\n【MC百科 - {mc.get('name_zh')}】")
    print(f"  平台: {mc.get('url', '')}")

    if mc.get('status'):
        print(f"  状态: {mc['status']}  (类型: {mc.get('type', '?')})")

    desc = mc.get('description', '')
    if desc:
        clean_desc = core.clean_html_text(desc)
        if clean_desc:
            print(f"\n  简介：")
            desc_len = len(clean_desc)
            if desc_len > _SAVE_DESC_LENGTH_THRESHOLD:
                proj_name = mc.get('name_zh', 'unknown')
                filepath = _save_full_description(proj_name, clean_desc, 'mod')
                if saved_files is not None:
                    saved_files.append(filepath)
                print(f"    💾 完整简介已保存到文件:")
                print(f"       {filepath}")
                print(f"       （共 {desc_len} 字符）")
                print(f"\n    【简要摘要】")
                preview = clean_desc[:_MCMOD_DESC_PREVIEW_LEN]
                last_period = _find_sentence_boundary(preview)
                if last_period > _MCMOD_DESC_PREVIEW_SENTENCE_MIN:
                    preview = preview[:last_period + 1]
                for p in preview.split('\n')[:_MCMOD_DESC_PREVIEW_MAX_PARAS]:
                    if p.strip(): print(f"    {p.strip()}")
            elif full_desc or desc_len <= _DISPLAY_INFO_DESC_MAX:
                for p in clean_desc.split('\n'):
                    if p.strip(): print(f"    {p.strip()}")
            else:
                truncated = clean_desc[:_DISPLAY_INFO_DESC_MAX]
                last_period = _find_sentence_boundary(truncated)
                if last_period > _DISPLAY_INFO_DESC_TRUNCATE:
                    truncated = truncated[:last_period + 1]
                print(f"    {truncated}")
                print(f"    ...（还有 {desc_len - len(truncated)} 字符，完整内容请查看网页）")

    vers = mc.get('supported_versions', [])
    if vers:
        print(f"\n  支持版本 ({len(vers)}个):")
        print(f"    {', '.join(vers[:_DISPLAY_MAX_VERSIONS])}")
        if len(vers) > _DISPLAY_MAX_VERSIONS:
            print(f"    ... 还有 {len(vers) - _DISPLAY_MAX_VERSIONS} 个版本")

    cats = mc.get('categories', [])
    tags = mc.get('tags', [])
    if cats or tags:
        print(f"\n  分类标签:")
        if cats: print(f"    分类: {', '.join(cats)}")
        if tags: print(f"    标签: {' '.join(tags)}")

    author_team = mc.get('author_team', [])
    if author_team:
        print(f"  开发团队（{len(author_team)} 人）：")
        for member in author_team:
            roles_str = ', '.join(member.get('roles', []))
            print(f"    - {member.get('name', '?')}（{roles_str}）")
        if len(author_team) == _DISPLAY_MAX_AUTHOR_TEAM:
            print(f"    （还有更多成员，仅显示前 {_DISPLAY_MAX_AUTHOR_TEAM} 人）")
    elif mc.get('author'):
        print(f"  作者: {mc['author']}")


# ── 内部搜索辅助 ──────────────────────────────────────

def _search_modrinth_exact(keyword: str) -> dict | None:
    """在 Modrinth 上精确搜索项目。"""
    try:
        direct_data = core.search_modrinth(keyword, max_results=_EXACT_SEARCH_MAX)
        direct_hits = direct_data.get("results", [])
        if not direct_hits:
            return None
        norm_arg = re.sub(r"[^a-z0-9_-]", "", keyword.lower().replace(" ", "-"))
        for hit in direct_hits:
            hit_slug = (hit.get("slug", "") or "").lower()
            hit_name_raw = hit.get("name") or hit.get("name_en") or ""
            hit_name_norm = re.sub(r"[^a-z0-9]", "", hit_name_raw.lower())
            # slug 或名称精确匹配
            if hit_slug == norm_arg or hit_name_norm == norm_arg:
                slug = hit.get("source_id", "") or hit.get("slug", "")
                if slug:
                    try: return core.fetch_mod_info(slug, no_limit=True)
                    except Exception: pass
        return direct_hits[0] if direct_hits else None
    except Exception:
        return None


def _is_captcha(info: dict) -> bool:
    """检测 MC百科 返回的是否为安全验证（captcha）空数据。"""
    name = info.get("name_zh") or info.get("name") or ""
    return name == "安全验证中"


def _fetch_mcmod_info(class_id: str, mcmod_name: str) -> tuple[dict, list, str]:
    """获取 MC百科模组信息。返回 (mcmod_info, search_results, err_type)。
    err_type: None=成功, "NOT_FOUND"=页面不存在, "CAPTCHA"=验证码, "FETCH_FAILED"=获取失败。
    """
    if class_id:
        url = _mcmod_class_url(class_id)
        html = core.curl(url)
        if not html or len(html) < core.MIN_HTML_LEN:
            return None, [], "FETCH_FAILED"
        if '/error/' in html:
            return None, [], "NOT_FOUND"
        parsed = core._parse_mcmod_result(html, url, "")
        if _is_captcha(parsed):
            return None, [], "CAPTCHA"
        return parsed, [], None

    if not mcmod_name:
        return None, [], None

    try:
        hits = core.search_mcmod(mcmod_name, max_results=1)
    except core.SearchError:
        hits = []
    if not hits:
        return None, [], None

    first = hits[0]
    cid_match = re.search(r"/class/(\d+)", first.get("url", ""))
    if not cid_match:
        return None, hits, None
    html = core.curl(_mcmod_class_url(cid_match.group(1)))
    if not html or len(html) < core.MIN_HTML_LEN:
        return None, hits, "FETCH_FAILED"
    parsed = core._parse_mcmod_result(html, first["url"], first.get("name", ""))
    if _is_captcha(parsed):
        return None, hits, "CAPTCHA"
    return parsed, hits, None


def _output_full_result(result: dict, is_json: bool):
    """输出双平台全量结果（JSON 或文本）。"""
    if is_json:
        output = {k: v for k, v in result.items() if not k.startswith("_")}
        print(json.dumps(output, ensure_ascii=False))
        return

    mc = result.get("mcmod")
    mr = result.get("modrinth")
    deps = result.get("dependencies")
    saved_files = result.get("saved_files", [])

    if mc:
        _print_full_mcmod_info(mc, full_desc=True, saved_files=saved_files)
    if mr:
        print(f"\n  ── Modrinth ──")
        _print_full_modrinth_info(mr, saved_files=saved_files)

    # 依赖：Modrinth 前置 + MC百科联动
    mc_integrations = []
    if mc:
        rel = mc.get('relationships') or {}
        mc_integrations = rel.get('integrates', []) if rel else []
    has_mr_deps = deps and deps.get('deps')

    if has_mr_deps or mc_integrations:
        print(f"\n  ── 依赖关系 ──")
        if has_mr_deps:
            _print_deps(deps, mr.get("name", "") if mr else "")
        if mc_integrations:
            if has_mr_deps: print()
            print(f"  联动模组（{len(mc_integrations)} 个）：")
            for int_mod in mc_integrations:
                int_name = int_mod.get('name_zh') or int_mod.get('name_en', '?')
                int_url = int_mod.get('url', '')
                int_desc = int_mod.get('summary') or int_mod.get('snippet') or ''
                print(f"    • {int_name}")
                if int_desc:
                    for line in int_desc.split('\n')[:2]:
                        print(f"      {line.strip()}")
                if int_url: print(f"      {int_url}")
    elif mr or mc:
        print(f"\n  ── 依赖关系 ──")
        print(f"  无")


# ── CLI 入口 ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="mc-search: Minecraft 聚合搜索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # 全局选项
    parser.add_argument("--json", action="store_true", dest="global_json",
                        help="以 JSON 格式输出（推荐）")
    parser.add_argument("--cache", action="store_true", help="启用本地缓存（TTL 1小时）")
    parser.add_argument("--screenshots", type=int, default=0,
                        help="返回截图数量（默认 0，即不返回）")
    parser.add_argument("--no-mcmod", dest="no_mcmod", action="store_true", help="禁用 MC百科")
    parser.add_argument("--no-mr", dest="no_mr", action="store_true", help="禁用 Modrinth")
    parser.add_argument("--no-wiki", dest="no_wiki", action="store_true", help="禁用 minecraft.wiki")
    parser.add_argument("--no-wiki-zh", dest="no_wiki_zh", action="store_true", help="禁用 minecraft.wiki/zh")
    parser.add_argument("-o", "--output", dest="output", default=None, help="输出到文件")

    sub = parser.add_subparsers(dest="cmd")

    # ── search ──
    search_parser = sub.add_parser("search", help="多平台搜索")
    search_parser.add_argument("keyword", nargs="?", help="搜索关键词")
    search_parser.add_argument("--type", dest="content_type", default="mod",
                   choices=["mod", "item", "modpack", "shader", "resourcepack"],
                   help="内容类型（默认 mod）")
    search_parser.add_argument("--shader", action="store_const", const="shader", dest="content_type",
                   help="快捷：搜光影包")
    search_parser.add_argument("--modpack", action="store_const", const="modpack", dest="content_type",
                   help="快捷：搜整合包")
    search_parser.add_argument("--resourcepack", action="store_const", const="resourcepack", dest="content_type",
                   help="快捷：搜材质包")
    search_parser.add_argument("--platform", "-p",
                   choices=["all", "mcmod", "modrinth", "wiki", "wiki-zh"],
                   default="all", help="指定平台（默认 all）")
    search_parser.add_argument("--author", dest="author_name", default=None,
                   help="按作者搜索（MC百科+Modrinth）")
    search_parser.add_argument("-n", "--max", type=int, default=_DEFAULT_MAX,
                   help=f"每平台最多结果（默认{_DEFAULT_MAX}）")
    search_parser.add_argument("--timeout", type=int, default=_DEFAULT_TIMEOUT,
                   help=f"超时秒数（默认{_DEFAULT_TIMEOUT}）")

    # ── show ──
    show_parser = sub.add_parser("show", help="查看详情/依赖/合成表")
    show_parser.add_argument("name", help="名称 / MC百科 URL/ID / Modrinth URL/slug")
    show_parser.add_argument("--full", action="store_true",
                    help="双平台完整信息")
    show_parser.add_argument("--deps", action="store_true",
                    help="仅依赖关系（快捷路径）")
    show_parser.add_argument("--recipe", action="store_true",
                    help="显示合成表（仅 item）")
    show_parser.add_argument("--skip-dep", dest="skip_dep", action="store_true",
                    help="跳过依赖查询（仅 --full）")
    show_parser.add_argument("--skip-mr", dest="skip_mr", action="store_true",
                    help="跳过 Modrinth（仅 --full）")
    # 字段过滤（MC百科路径生效）
    show_parser.add_argument("-T", "--title", action="store_true", help="仅名称/别名")
    show_parser.add_argument("-a", "--author", action="store_true", help="仅作者")
    show_parser.add_argument("-d", "--deps-field", action="store_true", help="仅前置/联动")
    show_parser.add_argument("-v", "--versions", action="store_true", help="仅版本")
    show_parser.add_argument("-g", "--gallery", action="store_true", help="仅截图/封面")
    show_parser.add_argument("-c", "--cats", action="store_true", help="仅分类/标签")
    show_parser.add_argument("-s", "--source", action="store_true", help="仅来源链接")
    show_parser.add_argument("-S", "--status", action="store_true", help="仅状态/开源属性")

    # ── wiki ──
    wiki_parser = sub.add_parser("wiki", help="原版 Wiki 搜索与阅读")
    wiki_parser.add_argument("keyword", help="搜索关键词 或 wiki 页面 URL")
    wiki_parser.add_argument("-n", "--max", type=int, default=_DEFAULT_WIKI_MAX,
                   help=f"最多结果（默认{_DEFAULT_WIKI_MAX}）")
    wiki_parser.add_argument("-r", "--read", action="store_true",
                   help="搜索后读取第一个结果正文")
    wiki_parser.add_argument("-p", "--paragraphs", type=int, default=_DEFAULT_PARAGRAPHS,
                   help=f"段落数（读取页面时，默认{_DEFAULT_PARAGRAPHS}）")
    wiki_parser.add_argument("--timeout", type=int, default=_DEFAULT_TIMEOUT,
                   help=f"超时秒数（默认{_DEFAULT_TIMEOUT}）")

    args = parser.parse_args()

    # 统一 --json
    args.json = getattr(args, 'global_json', False) or getattr(args, 'json', False)

    # 全局设置
    if args.cache:
        core.set_cache(True)
    core.set_screenshot_limit(args.screenshots)
    core.set_platform_enabled(
        mcmod=not args.no_mcmod,
        modrinth=not args.no_mr,
        wiki=not args.no_wiki,
        wiki_zh=not args.no_wiki_zh,
    )

    def _json(obj):
        if args.json:
            print(json.dumps(obj, ensure_ascii=False))

    def _run_and_capture(func):
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                with contextlib.redirect_stdout(f):
                    func()
            print(f"[已写入 {args.output}]", file=sys.stderr)
        else:
            func()

    # ============================================================
    # search 命令
    # ============================================================
    @_timed(json_mode=args.json)
    def _cmd_search():
        # ── 作者搜索：双平台并行 ──
        if args.author_name:
            author = args.author_name.strip()
            if not author:
                _print_error("错误: 作者名不能为空", "EMPTY_AUTHOR", args.json)
                sys.exit(1)

            mcmod_hits = []
            mr_hits = []
            # MC百科
            try:
                mcmod_hits = core.search_mcmod_author(author, max_mods=args.max)
            except Exception:
                pass
            # Modrinth
            try:
                mr_hits = core.search_modrinth_author(author, max_results=args.max)
            except Exception:
                pass

            if args.json:
                _json({"mcmod": mcmod_hits, "modrinth": mr_hits,
                       "mcmod_count": len(mcmod_hits), "modrinth_count": len(mr_hits)})
            else:
                if mcmod_hits:
                    print(f"[{author}] 的 MC百科 作品（共 {len(mcmod_hits)} 个）：")
                    for hit in mcmod_hits:
                        _print_hit(hit)
                if mr_hits:
                    if mcmod_hits: print()
                    print(f"[{author}] 的 Modrinth 作品（共 {len(mr_hits)} 个）：")
                    for hit in mr_hits:
                        _print_hit(hit)
                if not mcmod_hits and not mr_hits:
                    _print_error(f"MC百科 和 Modrinth 均未找到 [{author}] 的作品", "NO_RESULTS", args.json)
                    sys.exit(1)
            return

        # ── 关键词搜索 ──
        if not args.keyword or not args.keyword.strip():
            _print_error("错误: 搜索关键词不能为空", "EMPTY_KEYWORD", args.json)
            sys.exit(1)
        args.keyword = args.keyword.strip()

        content_type = args.content_type

        # 快捷标志自动限定平台：shader/resourcepack 仅 Modrinth
        if content_type in ("shader", "resourcepack") and args.platform == "all":
            args.platform = "modrinth"

        # ── 单平台搜索 ──
        if args.platform != "all":
            flags = _PLATFORM_FLAGS.get(args.platform)
            if flags:
                core.set_platform_enabled(*flags)

            if args.platform == "modrinth":
                data = core.search_modrinth(args.keyword, max_results=args.max, project_type=content_type)
                hits = data.get("results", [])
                if args.json:
                    _json({"results": hits, "platform": "modrinth", "returned": len(hits)})
                else:
                    if not hits:
                        _print_error(f"Modrinth 无 [{args.keyword}] 相关结果", "NO_RESULTS", args.json)
                        sys.exit(1)
                    for hit in hits:
                        _print_hit(hit)
            else:
                result = core.search_all(args.keyword, max_per_source=args.max,
                                          timeout=args.timeout, content_type=content_type,
                                          fuse=True)
                hits = result.get("results", [])
                if args.json:
                    _json({"results": hits, "platform": args.platform, "returned": len(hits)})
                else:
                    if not hits:
                        _print_error(f"{args.platform} 无 [{args.keyword}] 相关结果", "NO_RESULTS", args.json)
                        sys.exit(1)
                    for hit in hits:
                        _print_hit(hit)
            return

        # ── 多平台并行搜索 ──
        results = core.search_all(args.keyword, max_per_source=args.max,
                                  timeout=args.timeout, content_type=content_type,
                                  fuse=True)
        if args.json:
            _json(results)
        else:
            if not results.get("results"):
                _print_error(f"所有平台均无 [{args.keyword}] 相关结果", "NO_RESULTS", args.json)
                sys.exit(1)
            for hit in results["results"]:
                _print_hit(hit)

    # ============================================================
    # show 命令
    # ============================================================
    @_timed(json_mode=args.json)
    def _cmd_show():
        name = args.name
        ident = _parse_project_identifier(name)

        # ── --deps 快捷路径：只查 Modrinth 依赖 ──
        if args.deps:
            slug = None
            if ident["mr_slug"]:
                slug = ident["mr_slug"]
            elif name.startswith("http") and "modrinth.com" in name:
                slug = _extract_slug_from_url(name)
            else:
                hit = _search_modrinth_exact(name)
                if hit:
                    slug = hit.get("source_id") or hit.get("slug")

            if not slug:
                _print_error(f"未找到相关项目: {name}", "NOT_FOUND", args.json)
                sys.exit(1)

            try:
                deps = core.get_mod_dependencies(slug, project_id=None)
                if args.json:
                    _json(deps)
                else:
                    _print_deps(deps, slug)
            except Exception as e:
                _print_error(f"获取依赖失败: {e}", "FETCH_FAILED", args.json)
                sys.exit(1)
            return

        # ── --full：双平台全量 ──
        if args.full:
            _show_full(name, ident)
            return

        # ── 默认：按输入类型自动选平台 ──
        _show_default(name, ident)

    def _show_full(name: str, ident: dict):
        """show --full 双平台全量输出。"""
        result = {"mcmod": None, "modrinth": None, "dependencies": None, "saved_files": []}
        skip_mr = args.skip_mr or args.no_mr
        skip_dep = args.skip_dep
        skip_mcmod = args.no_mcmod

        # Modrinth URL：直接 slug 获取
        if ident["mr_slug"]:
            result["modrinth"] = core.fetch_mod_info(ident["mr_slug"], no_limit=True)
            if result["modrinth"] is None:
                _print_error(f"Modrinth上不存在slug为 '{ident['mr_slug']}' 的项目", "URL_NOT_FOUND", args.json)
                sys.exit(1)
            mr_name = result["modrinth"].get("name", "")
            if mr_name and not skip_mcmod:
                mcmod_info, _, _ = _fetch_mcmod_info(None, mr_name)
                if mcmod_info and _is_captcha(mcmod_info):
                    mcmod_info = None
                result["mcmod"] = mcmod_info
            if not skip_dep:
                result["dependencies"] = core.get_mod_dependencies(
                    ident["mr_slug"], project_id=result["modrinth"].get("id"))
            _output_full_result(result, args.json)
            return

        # MC百科 URL/ID 或纯名称
        class_id = ident["class_id"]
        mcmod_name = ident["mcmod_name"]

        mcmod_info = None
        if not skip_mcmod:
            mcmod_info, _, _ = _fetch_mcmod_info(class_id, mcmod_name)
            if mcmod_info and _is_captcha(mcmod_info):
                mcmod_info = None
        result["mcmod"] = mcmod_info

        mr_info = None
        if not skip_mr:
            mr_search_name = (mcmod_info.get("name_en") if mcmod_info else None) or mcmod_name
            if mr_search_name:
                mr_hit = _search_modrinth_exact(mr_search_name)
                if mr_hit and isinstance(mr_hit, dict):
                    slug = mr_hit.get("source_id") or mr_hit.get("slug")
                    if slug:
                        try: mr_info = core.fetch_mod_info(slug, no_limit=True)
                        except Exception: mr_info = None
        result["modrinth"] = mr_info

        if not result["mcmod"] and not result["modrinth"]:
            _print_error(f"未找到 [{name}] 的相关信息", "NOT_FOUND", args.json)
            sys.exit(1)

        if not skip_dep and mr_info:
            try:
                result["dependencies"] = core.get_mod_dependencies(
                    mr_info.get("slug", ""), project_id=mr_info.get("id"))
            except Exception:
                pass

        _output_full_result(result, args.json)

    def _show_default(name: str, ident: dict):
        """show 默认：MC百科 URL/ID/中文名→MC百科，Modrinth URL/slug→Modrinth。"""
        saved_files = []
        # Modrinth 路径
        if ident["mr_slug"] is not None:
            if args.no_mr:
                _print_error("已禁用 Modrinth（--no-mr）", "DISABLED", args.json)
                sys.exit(1)
            slug = ident["mr_slug"]
            try:
                info = core.fetch_mod_info(slug, no_limit=True)
                if info:
                    if args.json:
                        _json(info)
                    else:
                        _print_full_modrinth_info(info, saved_files=saved_files)
                    return
            except Exception:
                pass
            _print_error(f"无法获取 Modrinth 项目信息: {slug}", "NOT_FOUND", args.json)
            sys.exit(1)

        # MC百科路径，失败时回退 Modrinth
        if args.no_mcmod:
            info, err_type, err_msg = None, "DISABLED", "已禁用 MC百科（--no-mcmod）"
        else:
            info, err_type, err_msg = _show_mcmod(name, ident)
        if info:
            _print_mcmod_show_info(info, name)
            return

        # MC百科失败，尝试 Modrinth 回退（仅当用户输入是名称而非数字ID/URL时）
        if not args.no_mr and not ident["class_id"]:
            hit = _search_modrinth_exact(name)
            if hit:
                slug = hit.get("source_id") or hit.get("slug")
                if slug:
                    try:
                        mr_info = core.fetch_mod_info(slug, no_limit=True)
                        if mr_info:
                            if args.json:
                                _json(mr_info)
                            else:
                                _print_full_modrinth_info(mr_info, saved_files=saved_files)
                            return
                    except Exception:
                        pass

        # Modrinth 也失败（或已禁用），输出原始错误
        _print_error(err_msg, err_type, args.json)
        sys.exit(1)

    def _show_mcmod(name: str, ident: dict):
        """获取 MC百科模组信息。返回 (info, err_type, err_msg)。
        成功: (info_dict, None, None)；失败: (None, err_type, err_msg)。
        """
        class_id = ident["class_id"]
        mcmod_name = ident["mcmod_name"]

        if not class_id and not mcmod_name:
            return None, "INVALID_INPUT", f"无法解析: {name}"

        info, _, err_type = _fetch_mcmod_info(class_id, mcmod_name)

        if not info:
            err_messages = {
                "NOT_FOUND": f"未找到 ID 为 {class_id} 的模组页面" if class_id else f"未找到名为 [{mcmod_name}] 的模组",
                "CAPTCHA": "安全验证",
                "FETCH_FAILED": f"无法获取模组页面（ID: {class_id}）" if class_id else f"无法获取模组页面",
            }
            msg = err_messages.get(err_type, f"未找到名为 [{mcmod_name}] 的模组")
            return None, err_type or "NOT_FOUND", msg

        return info, None, None

    def _print_mcmod_show_info(info: dict, name: str):
        """打印 MC百科 show 结果（字段过滤/描述/合成表/提示）。"""
        if args.json:
            _json(info)
            return

        # 判断是否全字段输出
        standalone = not any((args.title, args.author, args.deps_field, args.versions,
                            args.gallery, args.cats, args.source, args.status))

        # 数据驱动输出
        for attr, label, fmt in _INFO_FIELDS:
            if standalone or getattr(args, attr, False):
                if attr == "title":
                    lines = fmt(info)
                elif attr == "source":
                    lines = fmt(info, standalone=standalone)
                else:
                    lines = fmt(info)
                if lines:
                    for line in lines:
                        print(line)

        # 描述（仅在 standalone 时输出）
        desc_lines = _fmt_desc(info, standalone=standalone)
        if desc_lines:
            for line in desc_lines:
                print(line)

        # --recipe
        if args.recipe:
            recipe_url = info.get("url", "")
            if recipe_url:
                recipe_data = core.fetch_item_recipe(recipe_url)
                if recipe_data.get("error"):
                    print(f"  合成表：获取失败（{recipe_data.get('error')}）")
                else:
                    imgs = recipe_data.get("recipe_images", [])
                    mats = recipe_data.get("recipe_materials", [])
                    if imgs:
                        print(f"  合成表图片（{len(imgs)}张）：")
                        for img in imgs[:_DISPLAY_MAX_RECIPE_IMAGES]:
                            print(f"    {img}")
                    if mats:
                        print(f"  合成材料：{' | '.join(mats)}")
                    if not imgs and not mats:
                        print(f"  合成表：无材料数据")

        # 提示（仅 standalone）
        if standalone:
            a = info.get("author")
            if a and not args.deps:
                print(f"\n  💡 同作者其他作品：search --author {a.replace(' ', '_')}")
            if info.get("has_recipe"):
                print(f"\n  💡 该物品有合成表：show {name} --recipe")

    # ============================================================
    # wiki 命令
    # ============================================================
    @_timed(json_mode=args.json)
    def _cmd_wiki():
        keyword = args.keyword

        # ── URL 检测：直接读取 wiki 页面 ──
        if keyword.startswith("http"):
            if "zh.minecraft.wiki" in keyword or keyword.startswith("minecraft.wiki/w/zh"):
                content = core.read_wiki_zh(keyword, max_paragraphs=args.paragraphs)
            else:
                content = core.read_wiki(keyword, max_paragraphs=args.paragraphs)
            if args.json:
                _json(content)
            elif "error" in content:
                _print_error(f"读取失败: {content['error']}", "READ_ERROR", args.json)
            else:
                print(f"[{content['name']}]")
                print(f"  {content['url']}")
                sections = content.get("_sections", [])
                if sections:
                    for sec in sections:
                        parent = sec.get("parent")
                        heading = sec.get("heading", "")
                        if parent:
                            print(f"\n  ▸ [{parent}] {heading}")
                        else:
                            print(f"\n  ▸ {heading}")
                        for line in sec.get("content", []):
                            print(f"    {line[:_DISPLAY_READ_LINE_MAX]}")
                else:
                    for i, p in enumerate(content["content"], 1):
                        print(f"\n  {i}. {p[:_DISPLAY_READ_LINE_MAX]}")
            return

        # ── 关键词搜索 wiki ──
        core.set_platform_enabled(mcmod=False, modrinth=False,
                                  wiki=not args.no_wiki, wiki_zh=not args.no_wiki_zh)
        result = core.search_all(keyword, max_per_source=args.max,
                                  timeout=args.timeout, content_type="vanilla",
                                  fuse=True)
        hits = result.get("results", [])
        if not hits:
            if args.json:
                _json([])
            else:
                _print_error(f"minecraft.wiki 无 [{keyword}] 相关结果", "NO_RESULTS", args.json)
            return

        # -r 读取第一个结果（JSON/text 共用）
        if args.read and hits:
            source = hits[0].get("source", "")
            if source == "minecraft.wiki/zh":
                content = core.read_wiki_zh(hits[0]["url"], max_paragraphs=_DISPLAY_WIKI_PARAGRAPHS)
            else:
                content = core.read_wiki(hits[0]["url"], max_paragraphs=_DISPLAY_WIKI_PARAGRAPHS)
        else:
            content = None

        if args.json:
            if content and "error" not in content:
                hits[0]["read_content"] = content
            _json(hits)
        else:
            for i, hit in enumerate(hits[:_DISPLAY_WIKI_MAX_RESULTS], 1):
                name = hit.get("name_zh") or hit.get("name_en") or hit.get("name", "?")
                source = hit.get("source", "")
                snippet = hit.get("snippet", "")
                sections = hit.get("sections", [])

                print(f"  {i}. {name} 【{source}】")

                if snippet:
                    clean_snippet = core.clean_html_text(snippet)
                    if len(clean_snippet) > _DISPLAY_WIKI_SNIPPET_MAX:
                        clean_snippet = clean_snippet[:_DISPLAY_WIKI_SNIPPET_MAX] + '...'
                    if clean_snippet:
                        print(f"     摘要: {clean_snippet}")

                if sections:
                    print(f"     章节：")
                    for sec in sections[:_DISPLAY_WIKI_MAX_SECTIONS]:
                        print(f"       {sec}")

                url = hit.get("url", "")
                if url:
                    print(f"     → {url}")
                print()

            # -r 读取正文输出
            if content and "error" not in content:
                print("\n[读取正文...]")
                for i, p in enumerate(content["content"], 1):
                    print(f"  {i}. {p[:_DISPLAY_LINE_MAX]}")

    # ── 命令分发 ──
    commands = {
        "search": _cmd_search,
        "show":   _cmd_show,
        "wiki":   _cmd_wiki,
    }

    if args.cmd in commands:
        _run_and_capture(commands[args.cmd])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
