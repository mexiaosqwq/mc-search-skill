#!/usr/bin/env python3
"""
mc-search CLI — Minecraft 聚合搜索工具
四平台并行，结果格式一致
"""

import argparse
import contextlib
import functools
import json
import re
import sys
import time

from . import core


def _timed(func):
    """自动计时装饰器：打印函数执行耗时到 stderr。

    注意：必须返回 result，否则被装饰函数会返回 None。
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.time()
        result = func(*args, **kwargs)
        print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
        return result
    return wrapper


_SOURCE_TYPE_LABELS = {"open_source": "开源", "closed_source": "闭源"}
_SIDE_LABELS = {"required": "必需", "optional": "可选", "unsupported": "不支持"}
_PROJECT_TYPE_LABELS = {
    "mod": "模组",
    "shader": "光影包",
    "resourcepack": "材质包",
    "modpack": "整合包",
}

def _print_side_info(mr: dict):
    """打印 Modrinth 运行环境信息。"""
    cs = mr.get('client_side', '')
    ss = mr.get('server_side', '')

    # 简化显示：两端相同则合并
    if cs and ss and cs == ss:
        label = _SIDE_LABELS.get(cs, cs)
        print(f"  运行环境：客户端/服务端均{label}")
    else:
        side_info = []
        if cs:
            side_info.append(f"客户端: {_SIDE_LABELS.get(cs, cs)}")
        if ss:
            side_info.append(f"服务端: {_SIDE_LABELS.get(ss, ss)}")
        if side_info:
            print(f"  运行环境：{' | '.join(side_info)}")


def _print_version_groups(vg: list, max_display: int = 7):
    """打印 Modrinth 版本列表（默认显示前 7 个）。"""
    if vg:
        total = len(vg)
        print(f"  版本列表：（共 {total} 个，显示前 {min(max_display, total)} 个）")
        for mod_ver, meta in vg[:max_display]:
            ld = ", ".join(meta.get("loaders", []))
            gv = ", ".join(meta.get("game_versions", [])[:4])
            print(f"    {mod_ver}  [{ld}]  游戏: {gv}")
        if total > max_display:
            print(f"    ... 还有 {total - max_display} 个版本")


def _json_print(obj):
    """打印 JSON 格式输出。"""
    print(json.dumps(obj, ensure_ascii=False))

# CLI 默认值
_DEFAULT_MAX = 3        # 每平台最多结果
_DEFAULT_TIMEOUT = 12    # 整体超时秒数
_DEFAULT_WIKI_MAX = 5   # wiki 默认最多结果
_DEFAULT_AUTHOR_MAX = 10  # 作者搜索默认最多结果
_DEFAULT_PARAGRAPHS = 5  # wiki 页面默认段落数

# 显示截断长度
_DISPLAY_WIKI_PARAGRAPHS = 4    # wiki 搜索后自动 read 的段落数
_DISPLAY_LINE_MAX = 200         # 单行最大显示字符数（search/wiki 命令）
_DISPLAY_READ_LINE_MAX = 250    # read 命令正文单行最大长度



# 共享工具函数

def _parse_project_identifier(project_arg: str) -> dict:
    """
    解析项目标识参数，返回标识字典。

    支持：模组 (mod)、光影包 (shader)、材质包 (resourcepack)、整合包 (modpack)

    返回: {
        "class_id": str | None,   # MC百科 class ID
        "mcmod_name": str | None, # MC百科 搜索名称
        "mr_slug": str | None,    # Modrinth slug
    }
    """
    if project_arg.startswith("https://www.mcmod.cn/class/"):
        m = re.search(r"/class/(\d+)", project_arg)
        return {"class_id": m.group(1) if m else None, "mcmod_name": None, "mr_slug": None}
    # Modrinth 项目 URL（支持 mod/shader/resourcepack/modpack）
    mr_match = re.search(r"https://modrinth\.com/(mod|shader|resourcepack|modpack)/([^/?]+)", project_arg)
    if mr_match:
        return {"class_id": None, "mcmod_name": None, "mr_slug": mr_match.group(2)}
    if project_arg.isdigit():
        return {"class_id": project_arg, "mcmod_name": None, "mr_slug": None}
    return {"class_id": None, "mcmod_name": project_arg, "mr_slug": None}



# CLI 入口

def main():
    parser = argparse.ArgumentParser(
        description="mc-search: Minecraft 聚合搜索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出（所有命令）")
    parser.add_argument("--cache", action="store_true", help="启用本地缓存（TTL 1小时）")
    parser.add_argument("--no-mcmod", dest="no_mcmod", action="store_true", help="禁用 MC百科")
    parser.add_argument("--no-mr", dest="no_mr", action="store_true", help="禁用 Modrinth")
    parser.add_argument("--no-wiki", dest="no_wiki", action="store_true", help="禁用 minecraft.wiki")
    parser.add_argument("--no-wiki-zh", dest="no_wiki_zh", action="store_true", help="禁用 minecraft.wiki/zh 中文wiki")
    parser.add_argument("-o", "--output", dest="output", default=None, help="输出到文件而非 stdout")
    sub = parser.add_subparsers(dest="cmd")

    s = sub.add_parser("search", help="多平台并行搜索（MC百科+Modrinth+minecraft.wiki+minecraft.wiki/zh）")
    s.add_argument("keyword", nargs="?", help="搜索关键词（作者搜索时忽略）")
    s.add_argument("-n", "--max", type=int, default=_DEFAULT_MAX, help=f"每平台最多结果（默认{_DEFAULT_MAX}）")
    s.add_argument("-t", "--timeout", type=int, default=_DEFAULT_TIMEOUT, help=f"超时秒数（默认{_DEFAULT_TIMEOUT}）")
    s.add_argument("--type", dest="content_type", default="mod",
                   choices=["mod", "item", "modpack", "entity", "biome", "dimension", "shader", "resourcepack"],
                   help="内容类型（默认 mod）；用于融合排序偏好，同时决定搜索范围（modpack/shader/resourcepack 仅搜 Modrinth）")
    s.add_argument("--author", dest="author_name", default=None,
                   help="MC百科作者搜索（仅搜 MC百科，忽略 --type）")
    s.add_argument("--fuse", action="store_true",
                   help="融合四平台结果去重（--json 时自动融合）")

    w = sub.add_parser("wiki", help="minecraft.wiki 搜索")
    w.add_argument("keyword", help="搜索关键词")
    w.add_argument("-n", "--max", type=int, default=_DEFAULT_WIKI_MAX)
    w.add_argument("-r", "--read", action="store_true", help="搜索后直接读取第一个页面正文")

    r = sub.add_parser("read", help="读取 wiki 页面正文")
    r.add_argument("url", help="页面 URL")
    r.add_argument("-p", "--paragraphs", type=int, default=_DEFAULT_PARAGRAPHS)

    mr = sub.add_parser("mr", help="Modrinth 搜索（支持光影/纹理包）")
    mr.add_argument("keyword", help="搜索关键词")
    mr.add_argument("-n", "--max", type=int, default=_DEFAULT_WIKI_MAX)
    mr.add_argument("-t", "--type", dest="ptype", default="mod",
                    choices=["mod", "shader", "resourcepack"],
                    help="项目类型（默认 mod）")

    dp = sub.add_parser("dep", help="查看 mod 依赖树（Modrinth）")
    dp.add_argument("mod_id", help="Mod ID（slug 或 project id）")

    at = sub.add_parser("author", help="按作者搜索 Modrinth 项目（支持模糊匹配）")
    at.add_argument("username", help="作者用户名（Modrinth username）")
    at.add_argument("-n", "--max", type=int, default=_DEFAULT_AUTHOR_MAX, help=f"最多结果（默认{_DEFAULT_AUTHOR_MAX}）")

    if_info = sub.add_parser("info", help="读取 MC百科模组详情（默认全字段，可选 -T/-a/-d/-v/-g/-c/-s/-S/-m）")
    if_info.add_argument("mod", help="模组名称 / MC百科 class ID / class URL")
    if_info.add_argument("-T", "--title", action="store_true", help="仅显示名称/别名")
    if_info.add_argument("-a", "--author", action="store_true", help="仅显示作者")
    if_info.add_argument("-d", "--deps", action="store_true", help="仅显示前置/联动模组")
    if_info.add_argument("-v", "--versions", action="store_true", help="仅显示支持的游戏版本")
    if_info.add_argument("-g", "--gallery", action="store_true", help="仅显示截图/封面")
    if_info.add_argument("-c", "--cats", action="store_true", help="仅显示分类/标签")
    if_info.add_argument("-s", "--source", action="store_true", help="仅显示来源链接")
    if_info.add_argument("-S", "--status", action="store_true", help="仅显示状态/开源属性")
    if_info.add_argument("-m", "--mr", dest="modrinth", action="store_true",
                        help="同时查询 Modrinth")
    if_info.add_argument("-r", "--recipe", action="store_true",
                        help="显示物品/方块合成表（仅 item 类型有效）")

    # 全量信息命令：一次获取搜索+详情+Modrinth+依赖
    fl = sub.add_parser("full", help="一键获取完整信息（模组/光影/材质/整合包：搜索→详情→依赖→版本）")
    fl.add_argument("project", help="名称 / MC百科 URL/ID / Modrinth URL/slug（支持 mod/shader/resourcepack/modpack）")
    fl.add_argument("--skip-dep", dest="skip_dep", action="store_true",
                    help="跳过依赖查询（加速）")
    fl.add_argument("--skip-mr", dest="skip_mr", action="store_true",
                    help="跳过 Modrinth 查询（加速）")

    args = parser.parse_args()

    # 全局 --json 辅助
    def _json(obj):
        if args.json:
            print(json.dumps(obj, ensure_ascii=False))

    # 全局 --cache 和平台开关
    if args.cache:
        core.set_cache(True)

    core.set_platform_enabled(
        mcmod=not args.no_mcmod,
        modrinth=not args.no_mr,
        wiki=not args.no_wiki,
        wiki_zh=not args.no_wiki_zh,
    )

    # 全局 --output 辅助
    def _run_and_capture(func):
        """执行函数，stdout 写入 args.output 文件（如果指定）。"""
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                with contextlib.redirect_stdout(f):
                    func()
            print(f"[已写入 {args.output}]", file=sys.stderr)
        else:
            func()

    @_timed
    def _cmd_search():
        if args.author_name:
            # MC百科作者搜索（单平台）
            try:
                hits = core.search_mcmod_author(args.author_name, max_mods=args.max)
            except Exception as e:
                hits = []
            if args.json:
                _json(hits)
            else:
                if not hits:
                    print(f"MC百科 未找到作者 [{args.author_name}] 的页面（作者名需精确匹配）")
                else:
                    print(f"[{args.author_name}] 的 MC百科 作品（共 {len(hits)} 个）：")
                    for h in hits:
                        print_hit(h)
            return
        results = core.search_all(args.keyword, max_per_source=args.max,
                                  timeout=args.timeout, content_type=args.content_type,
                                  fuse=True)
        if args.json:
            _json(results)
        else:
            # 融合结果：统一按相关性排序，逐条打印（platform_stats 仅在 JSON 中显示）
            if not results.get("results"):
                print(f"所有平台均无 [{args.keyword}] 相关结果")
            else:
                for h in results["results"]:
                    print_hit(h)

    @_timed
    def _cmd_wiki():
        hits = core.search_wiki(args.keyword, max_results=args.max)
        if not hits:
            print(f"minecraft.wiki 无 [{args.keyword}] 相关结果")
            return
        if args.json:
            _json(hits)
        else:
            for h in hits:
                print_hit(h)
            if args.read and hits:
                print("\n[读取正文...]")
                content = core.read_wiki(hits[0]["url"], max_paragraphs=_DISPLAY_WIKI_PARAGRAPHS)
                if "error" not in content:
                    for i, p in enumerate(content["content"], 1):
                        print(f"  {i}. {p[:_DISPLAY_LINE_MAX]}")

    @_timed
    def _cmd_read():
        content = core.read_wiki(args.url, max_paragraphs=args.paragraphs)
        if args.json:
            _json(content)
        elif "error" in content:
            print(f"读取失败: {content['error']}")
        else:
            print(f"[{content['name']}]")
            print(f"  {content['url']}")
            sections = content.get("_sections", [])
            if sections:
                # 层级输出：显示父级 h2 + 当前 h3 标题
                for sec in sections:
                    parent = sec.get("parent")
                    heading = sec.get("heading", "")
                    if parent:
                        print(f"\n  ▸ [{parent}] {heading}")
                    else:
                        print(f"\n  ▸ {heading}")
                    for line in sec.get("content", []):
                        print(f"    {line[:_DISPLAY_LINE_MAX]}")
            else:
                # 降级：平铺段落
                for i, p in enumerate(content["content"], 1):
                    print(f"\n  {i}. {p[:_DISPLAY_READ_LINE_MAX]}")

    @_timed
    def _cmd_mr():
        data = core.search_modrinth(args.keyword, max_results=args.max, project_type=args.ptype)
        if args.json:
            _json(data)
        elif not data.get("results"):
            print(f"Modrinth 无 [{args.keyword}] 相关结果（类型：{args.ptype}）")
        else:
            for h in data["results"]:
                print_hit(h)

    @_timed
    def _cmd_dep():
        info = core.get_mod_info(args.mod_id)
        if not info:
            print(f"[{args.mod_id}] 未在 Modrinth 上找到该 mod")
            return
        result = core.get_mod_dependencies(args.mod_id, project_id=info.get("id"))

        if args.json:
            _json(result)
        elif result.get("error") == "API_ERROR":
            print(f"[{args.mod_id}]（{info.get('name', args.mod_id)}）查询依赖时网络错误")
        elif not result.get("deps"):
            print(f"[{args.mod_id}]（{info.get('name', args.mod_id)}）无声明依赖")
        else:
            print_deps(result, info.get('name', args.mod_id))

    @_timed
    def _cmd_author():
        hits = core.search_author(args.username, max_results=args.max)
        if args.json:
            _json(hits)
        elif not hits:
            print(f"Modrinth 无 [{args.username}] 的作品（用户名不存在或无公开项目）")
        else:
            print(f"[{args.username}] 的 Modrinth 作品（共 {len(hits)} 个）：")
            for h in hits:
                print_hit(h)

    @_timed
    def _cmd_info():
        """MC百科模组详情，默认全字段，支持按 -T/-a/-d/-v/-g/-c/-s/-S/-m/-r 过滤。"""
        mod_arg = args.mod
        ident = _parse_project_identifier(mod_arg)

        if ident["mr_slug"]:
            print(f"info 命令不支持 Modrinth URL，请使用 mod 名称或 MC百科 URL/ID")
            return

        if ident["class_id"]:
            class_id = ident["class_id"]
        elif ident["mcmod_name"]:
            try:
                results = core.search_mcmod(ident["mcmod_name"], max_results=1)
            except core._SearchError:
                results = []
            if not results:
                print(f"未找到名为 [{ident['mcmod_name']}] 的模组")
                return
            match = re.search(r"/class/(\d+)", results[0].get("url", ""))
            if not match:
                print(f"无法解析模组 ID")
                return
            class_id = match.group(1)
        else:
            print(f"无法解析模组标识：{mod_arg}")
            return

        # 抓取 class 页面
        html = core._curl(f"https://www.mcmod.cn/class/{class_id}.html")
        if not html or len(html) < core._MIN_HTML_LEN:
            print(f"无法获取模组页面（ID: {class_id}）")
            return

        info = core._parse_mcmod_result(html, f"https://www.mcmod.cn/class/{class_id}.html", "")

        if args.json:
            _json(info)
            return

        # 无过滤参数时默认全字段
        show_all = not any([args.title, args.author, args.deps, args.versions,
                            args.gallery, args.cats, args.source, args.status])

        name_en = info.get("name_en", "")
        name_zh = info.get("name_zh", "")
        if show_all or args.title:
            print(f"  名称：{name_zh}")
            if name_en:
                print(f"  英文名：{name_en}")
            print(f"  平台：{info.get('source', 'mcmod.cn')}")
            print(f"  链接：{info.get('url', '')}")

        if show_all or args.status:
            st = info.get("status")
            stype = info.get("source_type")
            if st or stype:
                if st:
                    print(f"  状态：{st}")
                if stype:
                    print(f"  开源属性：{_SOURCE_TYPE_LABELS.get(stype, stype)}")

        if show_all or args.author:
            author = info.get("author")
            if author:
                print(f"  作者：{author}")

        if show_all or args.deps:
            rel = info.get("relationships")
            if rel:
                reqs = rel.get("requires", [])
                integ = rel.get("integrates", [])
                if reqs:
                    print(f"  前置Mod（{len(reqs)}）：")
                    for r in reqs:
                        print(f"    - {r['name_zh']} ({r['name_en']})  {r['url']}")
                if integ:
                    print(f"  联动Mod（{len(integ)}）：")
                    for r in integ:
                        print(f"    - {r['name_zh']} ({r['name_en']})  {r['url']}")
            else:
                print(f"  依赖：无（暂无关联模组）")

        if show_all or args.versions:
            vers = info.get("supported_versions", [])
            print(f"  支持版本（{len(vers)}）：{', '.join(vers)}" if vers else "  支持版本：无数据")

        if show_all or args.cats:
            cats = info.get("categories", [])
            tags = info.get("tags", [])
            if cats or tags:
                print(f"  分类：{' | '.join(cats)}")
                if tags:
                    print(f"  标签：{' '.join(tags)}")
            else:
                print(f"  分类/标签：无数据")

        if show_all or args.gallery:
            cover = info.get("cover_image", "")
            shots = info.get("screenshots", [])
            if cover:
                print(f"  封面：{cover}")
            if shots:
                print(f"  截图（{len(shots)}）：")
                for s in shots:
                    print(f"    {s}")

        if show_all or args.source:
            # 仅在 -s 选项时显示平台/链接（默认输出已在 title 段显示）
            if args.source and not show_all:
                print(f"  平台：{info.get('source', 'mcmod.cn')}")
                print(f"  链接：{info.get('url', '')}")
            sid = info.get("source_id", "")
            print(f"  Class ID：{sid}")

        # --mr: 额外查询 Modrinth（用 name_en 或 name 搜索）
        if args.modrinth:
            mr_name = info.get("name_en") or info.get("name", "")
            if mr_name:
                mr_data = core.search_modrinth(mr_name, max_results=3)
                mr_results = mr_data.get("results", [])
                if mr_results:
                    # 找最匹配的（名字最相近的）
                    best = mr_results[0]
                    print(f"\n  ── Modrinth ──")
                    print(f"    {best.get('name', '')}")
                    print(f"    {best.get('url', '')}")
                    if best.get('snippet'):
                        print(f"    {best['snippet'][:100]}")
                    # 显示完整 Modrinth 信息
                    slug = best.get("source_id", "")
                    if slug:
                        mr_info = core.get_mod_info(slug)
                        if mr_info:
                            print(f"    下载：{mr_info.get('downloads', 0):,}")
                            print(f"    关注：{mr_info.get('followers', 0):,}")
                            print(f"    许可：{mr_info.get('license', '')}")
                            vg = mr_info.get("version_groups", [])
                            if vg:
                                latest_v, latest_meta = vg[0]
                                print(f"    最新版本：{latest_v}  [{', '.join(latest_meta['loaders'])}]  游戏: {', '.join(latest_meta['game_versions'][:3])}")
                else:
                    print(f"\n  ── Modrinth ──  未找到相关项目")

        # 作者引导（仅在无过滤参数时显示）
        author = info.get("author")
        if author and show_all and not args.modrinth:
            safe_author = author.replace(" ", "_")
            print(f"\n  💡 同作者其他作品：search --author {safe_author}")

        # 合成表提示（仅在无过滤参数时显示）
        if info.get("has_recipe") and show_all:
            print(f"\n  💡 该物品有合成表：info {mod_arg} -r")

        # 合成表查询
        if args.recipe:
            recipe_url = info.get("url", "")
            if recipe_url:
                recipe_data = core.get_item_recipe(recipe_url)
                if recipe_data.get("error"):
                    print(f"  合成表：获取失败（{recipe_data.get('error')}）")
                else:
                    imgs = recipe_data.get("recipe_images", [])
                    mats = recipe_data.get("recipe_materials", [])
                    if imgs:
                        print(f"  合成表图片（{len(imgs)}张）：")
                        for img in imgs[:4]:
                            print(f"    {img}")
                    if mats:
                        print(f"  合成材料：{' | '.join(mats)}")
                    if not imgs and not mats:
                        print(f"  合成表：无材料数据")

    def _fetch_mcmod_info(class_id: str, mcmod_name: str) -> tuple[dict, list]:
        """获取 MC百科模组信息。返回 (mcmod_info, search_results)。"""
        if class_id:
            html = core._curl(f"https://www.mcmod.cn/class/{class_id}.html")
            if html and len(html) >= core._MIN_HTML_LEN:
                return core._parse_mcmod_result(html, f"https://www.mcmod.cn/class/{class_id}.html", ""), []

        if not mcmod_name:
            return None, []

        try:
            hits = core.search_mcmod(mcmod_name, max_results=1)
        except core._SearchError:
            hits = []

        if not hits:
            return None, []

        first = hits[0]
        cid_match = re.search(r"/class/(\d+)", first.get("url", ""))
        if not cid_match:
            return None, hits

        html = core._curl(f"https://www.mcmod.cn/class/{cid_match.group(1)}.html")
        if html and len(html) >= core._MIN_HTML_LEN:
            return core._parse_mcmod_result(html, first["url"], first.get("name", "")), hits

        return None, hits

    def _fetch_modrinth_info(mr_search_name: str, skip_mr: bool, direct_slug: str = None) -> tuple[dict | None, str | None]:
        """获取 Modrinth 模组信息。返回 (modrinth_info, tentative_name)。

        Args:
            mr_search_name: 搜索关键词
            skip_mr: 是否跳过 Modrinth 查询
            direct_slug: 直接指定的 slug（优先使用）
        """
        if skip_mr:
            return None, None

        # 如果有直接指定的 slug，优先使用
        if direct_slug:
            try:
                info = core.get_mod_info(direct_slug, no_limit=True)
                if info:
                    return info, None
            except Exception:
                pass

        if not mr_search_name:
            return None, None

        try:
            data = core.search_modrinth(mr_search_name, max_results=5)
        except Exception:
            data = {"results": [], "total": 0, "returned": 0}

        hits = data.get("results", [])
        if not hits:
            return None, None

        # 尝试精确匹配：找名称或 slug 与搜索词最接近的
        norm_search = re.sub(r"[^a-z0-9]", "", mr_search_name.lower())
        best_match = None
        best_score = 0

        for hit in hits:
            hit_name = hit.get("name") or hit.get("name_en") or ""
            hit_slug = hit.get("slug", "") or ""

            # 检查 slug 是否完全匹配
            if hit_slug.lower() == norm_search or hit_slug.lower() == mr_search_name.lower():
                best_score = 200
                best_match = hit
                break

            # 检查名称是否完全匹配
            norm_hit = re.sub(r"[^a-z0-9]", "", hit_name.lower())
            if norm_hit == norm_search:
                best_score = 150
                best_match = hit
                continue

            # 模糊匹配
            score = 0
            if norm_search in norm_hit or norm_hit in norm_search:
                score = 50
            elif norm_search.startswith(norm_hit[:3]) or norm_hit.startswith(norm_search[:3]):
                score = 30

            if score > best_score:
                best_score = score
                best_match = hit

        # 如果找到较好匹配（分数>=50），获取详细信息
        if best_match and best_score >= 50:
            slug = best_match.get("source_id", "") or best_match.get("slug", "")
            if slug:
                try:
                    return core.get_mod_info(slug, no_limit=True), None
                except Exception:
                    pass

        # 无精确匹配，返回第一个结果作为候选
        return None, hits[0].get("name") or hits[0].get("name_en") or ""

def _search_modrinth_exact(keyword: str) -> dict | None:
    """在 Modrinth 上精确搜索项目（slug/名称完全匹配）。"""
    try:
        direct_data = core.search_modrinth(keyword, max_results=5)
        direct_hits = direct_data.get("results", [])

        if not direct_hits:
            return None

        norm_arg = re.sub(r"[^a-z0-9_-]", "", keyword.lower().replace(" ", "-"))
        for hit in direct_hits:
            hit_slug = (hit.get("slug", "") or "").lower()
            hit_name_raw = hit.get("name") or hit.get("name_en") or ""
            hit_name_norm = re.sub(r"[^a-z0-9]", "", hit_name_raw.lower())

            # slug 完全匹配（最高优先级）
            if hit_slug == norm_arg:
                slug = hit.get("source_id", "") or hit.get("slug", "")
                if slug:
                    try:
                        return core.get_mod_info(slug, no_limit=True)
                    except Exception:
                        pass

            # 名称精确匹配
            if hit_name_norm == norm_arg:
                slug = hit.get("source_id", "") or hit.get("slug", "")
                if slug:
                    try:
                        return core.get_mod_info(slug, no_limit=True)
                    except Exception:
                        pass

        # 无精确匹配，返回第一个作为候选
        return direct_hits[0] if direct_hits else None
    except Exception:
        return None


def _print_full_modrinth_info(mr: dict):
    """打印 Modrinth 详细信息。"""
    print(f"  下载：{mr.get('downloads', 0):,} | 关注：{mr.get('followers', 0):,}")
    _print_side_info(mr)
    # 显示简介
    desc = mr.get('description', '')
    if desc:
        print(f"  简介：{desc}")
    vg = mr.get("version_groups", [])
    if vg:
        _print_version_groups(vg)
    else:
        print(f"  最新版本：{mr.get('latest_version')} [{', '.join(mr.get('loaders', []))}]")
    print(f"  链接：{mr.get('url', '')}")

def _print_full_mcmod_info(mc: dict):
    """打印 MC百科详细信息。"""
    print(f"  名称：{mc.get('name_zh')} ({mc.get('name_en', '')})")
    print(f"  平台：MC百科 | {mc.get('url', '')}")
    if mc.get('author'):
        print(f"  作者：{mc['author']}")
    if mc.get('status'):
        print(f"  状态：{mc['status']}")
        vers = mc.get('supported_versions', [])
        if vers:
            print(f"  支持版本：{', '.join(vers)}")
        rel = mc.get('relationships')
        if rel:
            reqs = rel.get('requires', [])
            if reqs:
                # 去重：按 name_zh 去重，保留首次出现
                seen = set()
                unique_reqs = []
                for r in reqs:
                    name = r.get('name_zh') or r.get('name_en') or ''
                    if name and name not in seen:
                        seen.add(name)
                        unique_reqs.append(r)
                print(f"  前置Mod：{', '.join(r['name_zh'] for r in unique_reqs)}")
            # 联动模组
            integrations = rel.get('integrates', [])
            if integrations:
                print(f"  联动模组：{', '.join(r['name_zh'] for r in integrations[:5])}")
                if len(integrations) > 5:
                    print(f"    （还有 {len(integrations) - 5} 个）")

        # 显示完整的作者团队信息
        author_team = mc.get('author_team')
        if author_team:
            total_count = len(author_team)
            # 检查是否有限制（超过10人会被截断）
            # 这里可以通过实际页面数据来判断
            print(f"  开发团队（{total_count} 人）：")
            for member in author_team:
                roles_str = ', '.join(member['roles'])
                print(f"    - {member['name']}（{roles_str}）")
            if total_count == 10:
                print(f"    （还有更多成员，仅显示前 10 人）")

    def _cmd_full():
        """一键获取完整信息：支持模组/光影/材质包/整合包。"""
        t0 = time.time()
        project_arg = args.project
        result = {
            "mcmod": None,
            "modrinth": None,
            "dependencies": None,
            "search_results": [],
        }

        # ── 解析项目标识 ───────────────────────────────────────────
        ident = _parse_project_identifier(project_arg)

        # Modrinth URL：直接处理（支持 mod/shader/resourcepack/modpack）
        if ident["mr_slug"]:
            result["modrinth"] = core.get_mod_info(ident["mr_slug"], no_limit=True)
            if result["modrinth"] and not args.skip_dep:
                result["dependencies"] = core.get_mod_dependencies(
                    ident["mr_slug"], project_id=result["modrinth"].get("id"))
            if args.json:
                _json_print(result)
            else:
                mr = result.get("modrinth")
                deps = result.get("dependencies")
                if mr:
                    print(f"  名称：{mr.get('name')} ({mr.get('slug', '')})")
                    print(f"  平台：Modrinth | {mr.get('url', '')}")
                    proj_type = mr.get('type', 'mod')
                    proj_type_label = _PROJECT_TYPE_LABELS.get(proj_type, proj_type)
                    print(f"  类型：{proj_type_label}")
                    _print_full_modrinth_info(mr)
                    if deps and deps.get('deps'):
                        print(f"\n  ── 依赖 ──")
                        print_deps(deps)
                else:
                    print(f"未找到该项目（slug: {ident['mr_slug']}）")
            print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
            return

        # 非 Modrinth URL：尝试通过 Modrinth 搜索匹配
        class_id = ident["class_id"]
        mcmod_name = ident["mcmod_name"]

        # ── 阶段一：获取 Modrinth 信息（优先 slug 精确匹配）──
        mr_info = None
        tentative_name = None

        if not args.skip_mr and mcmod_name:
            mr_hit = _search_modrinth_exact(mcmod_name)
            if mr_hit and isinstance(mr_hit, dict) and mr_hit.get("slug"):
                slug = mr_hit.get("source_id") or mr_hit.get("slug")
                try:
                    mr_info = core.get_mod_info(slug, no_limit=True)
                except Exception:
                    mr_info = None
            if mr_hit and not mr_info:
                tentative_name = mr_hit.get("name") or mr_hit.get("name_en") or ""

        # ── 阶段二：获取 MC百科信息（仅 mod/item/modpack）──
        mcmod_info, search_results = _fetch_mcmod_info(class_id, mcmod_name)
        result["mcmod"] = mcmod_info
        result["search_results"] = search_results

        # 如果 MC百科 未找到且 Modrinth 也未有结果，提前退出
        if not result["mcmod"] and not mr_info:
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(f"未找到名为 [{project_arg}] 的项目信息")
            print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
            return

        # ── 阶段三：补充 Modrinth 信息（如果阶段一未找到）──
        if not mr_info:
            mr_search_name = (
                result["mcmod"].get("name_en")
                if result["mcmod"] else None
            ) or mcmod_name
            mr_info, tentative_name = _fetch_modrinth_info(mr_search_name, args.skip_mr, direct_slug=None)
        result["modrinth"] = mr_info
        if tentative_name:
            result["_mr_tentative"] = tentative_name

        # ── 阶段三：依赖查询 ──
        if not args.skip_dep and mr_info:
            try:
                result["dependencies"] = core.get_mod_dependencies(
                    mr_info.get("slug", ""), project_id=mr_info.get("id"))
            except Exception:
                pass

        # ── 输出 ──
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            mc = result.get("mcmod")
            mr = result.get("modrinth")
            deps = result.get("dependencies")

            if mc:
                _print_full_mcmod_info(mc)
            if mr:
                print(f"\n  ── Modrinth ──")
                _print_full_modrinth_info(mr)
            elif result.get("_mr_tentative"):
                print(f"\n  ── Modrinth ──")
                print(f"  ⚠️ 名称未确认匹配，请自行确认")
                print(f"  参考搜索词 → Modrinth 结果：{result['_mr_tentative']}")

            # 依赖信息
            has_deps = deps and deps.get('deps')
            mc_requires = []
            mc_integrations = []
            if mc:
                rel = mc.get('relationships') or {}
                mc_requires = rel.get('requires', []) if rel else []
                mc_integrations = rel.get('integrates', []) if rel else []

            if has_deps or mc_requires:
                print(f"\n  ── 依赖关系 ──")

                if mc_requires:
                    seen = set()
                    unique_requires = []
                    for req in mc_requires:
                        req_name = req.get('name_zh') or req.get('name_en') or ''
                        if req_name and req_name not in seen:
                            seen.add(req_name)
                            unique_requires.append(req)

                    print(f"[MC百科] 前置模组（{len(unique_requires)} 个）：")
                    for req in unique_requires:
                        req_name = req.get('name_zh') or req.get('name_en') or ''
                        print(f"  - {req_name}")
                        print(f"    {req.get('url', '')}")

                if has_deps:
                    mr_deps = deps.get('deps', {})
                    if isinstance(mr_deps, dict):
                        req_count = deps.get('required_count', 0)
                        opt_count = deps.get('optional_count', 0)
                        print(f"\n[Modrinth] 依赖树（必需:{req_count} | 可选:{opt_count}）：")
                        for slug, dep_info in list(mr_deps.items())[:8]:
                            dep_name = dep_info.get('name', slug)
                            dep_type = dep_info.get('type', 'required')
                            print(f"  [{dep_type}] {dep_name}")
                            print(f"    https://modrinth.com/mod/{slug}")
                        if len(mr_deps) > 8:
                            print(f"  ... 还有 {len(mr_deps) - 8} 个依赖")

                if mc_requires and not has_deps:
                    print(f"\n  ℹ️  Modrinth 依赖信息暂缺")

            # 联动模组
            if mc_integrations:
                print(f"\n  ── 联动模组 ──")
                print(f"  （共 {len(mc_integrations)} 个，显示前 5 个）")
                for int_mod in mc_integrations[:5]:
                    int_name = int_mod.get('name_zh') or int_mod.get('name_en') or ''
                    int_url = int_mod.get('url', '')
                    print(f"  - {int_name}")
                    if int_url:
                        print(f"    {int_url}")
                if len(mc_integrations) > 5:
                    print(f"  ... 还有 {len(mc_integrations) - 5} 个")

            # 未找到任何信息
            if not mc and not mr:
                print(f"未找到名为 [{project_arg}] 的项目信息")

        print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)

    # 分发
    commands = {
        "search": _cmd_search,
        "wiki": _cmd_wiki,
        "read": _cmd_read,
        "mr": _cmd_mr,
        "dep": _cmd_dep,
        "author": _cmd_author,
        "info": _cmd_info,
        "full": _cmd_full,
    }

    if args.cmd in commands:
        _run_and_capture(commands[args.cmd])
    else:
        parser.print_help()



# 打印函数

def _type_badge(h: dict) -> str:
    """返回类型标识字符串（用于消歧）。"""
    t = h.get("type", "mod")
    if t == "shader":
        return "【光影】"
    if t == "resourcepack":
        return "【材质包】"
    if t == "item":
        return "【物品】"
    if t == "mod":
        return ""
    return f"【{t}】"


def print_hit(h: dict, index: int = 0, total: int = 1):
    """
    打印单个搜索结果（规整格式）。
    """
    name = h.get("name_zh") or h.get("name", "?")
    en = h.get("name_en", "")
    src = h.get("source", "")
    htype = h.get("type", "mod")
    badge = _type_badge(h)

    # 头部：名称 + 类型 + 来源
    header = f"  ── {name}"
    if en and en != name:
        header += f" ({en})"
    if badge:
        header += f" {badge}"
    header += f" 【{src}】"
    print(header)

    # ── 元数据 ──
    if src == "mcmod.cn":
        if htype == "item":
            cat = h.get("category")
            mod_name = h.get("source_mod_name")
            dur = h.get("max_durability")
            stack = h.get("max_stack")
            meta = []
            if cat:
                meta.append(f"分类: {cat}")
            if dur:
                meta.append(f"耐久: {dur}")
            if stack:
                meta.append(f"堆叠: {stack}")
            if meta:
                print(f"     {' | '.join(meta)}")
            if mod_name:
                print(f"     来自: {mod_name}")
        else:
            cats = h.get("categories", [])
            st = h.get("status")
            source_type = h.get("source_type")
            author = h.get("author")
            meta = []
            if cats:
                meta.append(f"分类: {' | '.join(cats)}")
            if st:
                meta.append(f"状态: {st}")
            if source_type:
                meta.append(_SOURCE_TYPE_LABELS.get(source_type, source_type))
            for m in meta:
                print(f"     {m}")
            if author:
                print(f"     作者: {author}")
    elif src == "modrinth":
        pt = h.get("type", "mod")
        print(f"     类型: {pt}")

    # ── 描述 ──
    desc = h.get("description") or h.get("snippet", "")
    if desc:
        # 清洗 HTML 标签和多余空白
        desc = re.sub(r"<[^>]+>", "", desc)
        desc = re.sub(r"\s+", " ", desc).strip()
        if len(desc) > _DISPLAY_LINE_MAX:
            desc = desc[:_DISPLAY_LINE_MAX] + "…"
        print(f"     {desc}")

    # ── Wiki 章节 ──
    if h.get("sections"):
        for s in h["sections"][:5]:
            print(f"     · {s}")

    # ── URL ──
    url = h.get("url")
    if url:
        print(f"     → {url}")



# 通用输出辅助函数

def print_deps(deps: dict, mod_name: str = ""):
    """打印依赖树。"""
    dep_dict = deps.get("deps", {})
    if not dep_dict:
        print(f"[{mod_name}] 无声明依赖")
        return
    opt_cnt = deps.get("optional_count", 0)
    req_cnt = deps.get("required_count", 0)
    print(f"[{mod_name}] 依赖树（必需:{req_cnt} | 可选:{opt_cnt}）：")
    for dep_id, dep in dep_dict.items():
        side = f"client:{dep['client_side']} / server:{dep['server_side']}"
        print(f"  [{dep['type']}] {dep['name']} ({side})")
        if dep.get("url"):
            print(f"    {dep['url']}")



if __name__ == "__main__":
    main()
