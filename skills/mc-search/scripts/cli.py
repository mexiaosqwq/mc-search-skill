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


# ─────────────────────────────────────────
# 装饰器
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# 常量
# ─────────────────────────────────────────

_SOURCE_TYPE_LABELS = {"open_source": "开源", "closed_source": "闭源"}

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
_DISPLAY_CHANGELOG_MAX = 120    # changelog 预览最大长度


# ─────────────────────────────────────────
# 共享工具函数
# ─────────────────────────────────────────

def _parse_mod_identifier(mod_arg: str) -> dict:
    """
    解析模组标识参数，返回标识字典。

    返回: {
        "class_id": str | None,   # MC百科 class ID
        "mcmod_name": str | None, # MC百科 搜索名称
        "mr_slug": str | None,    # Modrinth slug
    }
    """
    if mod_arg.startswith("https://www.mcmod.cn/class/"):
        m = re.search(r"/class/(\d+)", mod_arg)
        return {"class_id": m.group(1) if m else None, "mcmod_name": None, "mr_slug": None}
    if mod_arg.startswith("https://modrinth.com/mod/"):
        m = re.search(r"/mod/([^/?]+)", mod_arg)
        return {"class_id": None, "mcmod_name": None, "mr_slug": m.group(1) if m else None}
    if mod_arg.isdigit():
        return {"class_id": mod_arg, "mcmod_name": None, "mr_slug": None}
    return {"class_id": None, "mcmod_name": mod_arg, "mr_slug": None}


# ─────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────

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
                   choices=["mod", "item", "entity", "biome", "dimension"],
                   help="内容类型（默认 mod）；用于融合排序偏好，不影响搜索范围")
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
    fl = sub.add_parser("full", help="一键获取模组完整信息（搜索→详情→Modrinth→依赖）")
    fl.add_argument("mod", help="模组名称 / MC百科 class ID / class URL / Modrinth slug")
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
        ident = _parse_mod_identifier(mod_arg)

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

    def _cmd_full():
        """一键获取模组完整信息：MC百科详情 + Modrinth详情 + 依赖树（全部并行）。"""

        t0 = time.time()
        mod_arg = args.mod
        result = {
            "mcmod": None,
            "modrinth": None,
            "dependencies": None,
            "search_results": [],
        }

        # ── 解析模组标识 ───────────────────────────────────────────
        ident = _parse_mod_identifier(mod_arg)

        # Modrinth URL：单独处理（直接返回，无须查 MC百科）
        if ident["mr_slug"]:
            result["modrinth"] = core.get_mod_info(ident["mr_slug"], no_limit=True)
            if not args.skip_dep:
                result["dependencies"] = core.get_mod_dependencies(
                    ident["mr_slug"], project_id=result["modrinth"].get("id"))
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                mr = result.get("modrinth")
                deps = result.get("dependencies")
                if mr:
                    print(f"  名称：{mr.get('name')} ({mr.get('slug', '')})")
                    print(f"  平台：Modrinth | {mr.get('url', '')}")
                    print(f"  下载：{mr.get('downloads', 0):,} | 关注：{mr.get('followers', 0):,}")
                    print(f"  最新版本：{mr.get('latest_version')} [{', '.join(mr.get('loaders', []))}]")
                if deps and deps.get('deps'):
                    print(f"\n  ── 依赖 ──")
                    print_deps(deps)
            print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
            return

        class_id = ident["class_id"]
        mcmod_name = ident["mcmod_name"]

        # ── 阶段一：获取 MC百科信息 ───────────────────────────────
        # 抓取模组页面
        if class_id:
            html = core._curl(f"https://www.mcmod.cn/class/{class_id}.html")
            if html and len(html) >= core._MIN_HTML_LEN:
                result["mcmod"] = core._parse_mcmod_result(html, f"https://www.mcmod.cn/class/{class_id}.html", "")
        elif mcmod_name:
            try:
                hits = core.search_mcmod(mcmod_name, max_results=1)
            except core._SearchError:
                hits = []
            result["search_results"] = hits
            if hits:
                first = hits[0]
                cid_match = re.search(r"/class/(\d+)", first.get("url", ""))
                if cid_match:
                    html = core._curl(f"https://www.mcmod.cn/class/{cid_match.group(1)}.html")
                    if html and len(html) >= core._MIN_HTML_LEN:
                        result["mcmod"] = core._parse_mcmod_result(html, first["url"], first.get("name", ""))

        # 搜索结果（用于确定 Modrinth 搜索词）
        if mcmod_name and not result["search_results"]:
            try:
                result["search_results"] = core.search_mcmod(mcmod_name, max_results=3)
            except core._SearchError:
                result["search_results"] = []

        # 无任何结果时提前退出
        if not result["mcmod"] and not result["modrinth"]:
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(f"未找到名为 [{mod_arg}] 的模组信息")
            print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
            return

        # ── 阶段二：获取 Modrinth 信息 ───────────────────────────
        mr_search_name = (
            result["mcmod"].get("name_en")
            if result["mcmod"] else None
        ) or mcmod_name or (
            result["search_results"][0].get("name_en")
            if result["search_results"] else None
        )

        mr_info = None
        if mr_search_name and not args.skip_mr:
            try:
                data = core.search_modrinth(mr_search_name, max_results=1)
            except Exception:
                data = {"results": [], "total": 0, "returned": 0}
            hits = data.get("results", [])
            if hits:
                hit_name = hits[0].get("name") or hits[0].get("name_en") or ""
                norm_search = re.sub(r"[^a-z0-9]", "", mr_search_name.lower())
                norm_hit = re.sub(r"[^a-z0-9]", "", hit_name.lower())
                shorter = norm_search if len(norm_search) <= len(norm_hit) else norm_hit
                longer = norm_hit if shorter == norm_search else norm_search
                if shorter in longer and len(longer) <= len(shorter) * 1.3:
                    slug = hits[0].get("source_id", "")
                    if slug:
                        try:
                            mr_info = core.get_mod_info(slug, no_limit=True)
                        except Exception:
                            mr_info = None
                else:
                    result["_mr_tentative"] = hit_name
        result["modrinth"] = mr_info

        # ── 阶段三：依赖查询 ───────────────────────────
        if not args.skip_dep and mr_info:
            try:
                result["dependencies"] = core.get_mod_dependencies(
                    mr_info.get("slug", ""), project_id=mr_info.get("id"))
            except Exception:
                pass

        # ── 输出 ─────────────────────────────────────────────────
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            mc = result.get("mcmod")
            mr = result.get("modrinth")
            deps = result.get("dependencies")
            if mc:
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
                        print(f"  前置Mod：{', '.join(r['name_zh'] for r in reqs)}")
            if mr:
                print(f"\n  ── Modrinth ──")
                print(f"  下载：{mr.get('downloads', 0):,} | 关注：{mr.get('followers', 0):,}")
                print(f"  最新版本：{mr.get('latest_version')} [{', '.join(mr.get('loaders', []))}]")
                print(f"  {mr.get('url', '')}")
            elif result.get("_mr_tentative"):
                print(f"\n  ── Modrinth ──")
                print(f"  ⚠️ 名称未确认匹配（MC百科 name_en 可能对应其他 mod），请自行确认")
                print(f"  参考搜索词：{mr_search_name} → Modrinth 结果：{result['_mr_tentative']}")
            if deps and deps.get('deps'):
                print(f"\n  ── 依赖 ──")
                mod_name = mr.get('name', '') if mr else mc.get('name_zh', '') if mc else ''
                print_deps(deps, mod_name)

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


# ─────────────────────────────────────────
# 打印函数
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# 通用输出辅助函数
# ─────────────────────────────────────────

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
