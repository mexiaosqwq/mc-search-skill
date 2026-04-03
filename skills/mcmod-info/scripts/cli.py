#!/usr/bin/env python3
"""
mcmod-info CLI — Minecraft 模组+游戏内容信息查询
统一入口，三平台并行，结果格式一致
"""

import argparse
import contextlib
import json
import re
import sys
import time

from . import core


# ─────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="mcmod-info: Minecraft 模组+游戏内容查询",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出（所有命令）")
    parser.add_argument("--cache", action="store_true", help="启用本地缓存（TTL 1小时）")
    parser.add_argument("--no-mcmod", dest="no_mcmod", action="store_true", help="禁用 MC百科")
    parser.add_argument("--no-mr", dest="no_mr", action="store_true", help="禁用 Modrinth")
    parser.add_argument("--no-wiki", dest="no_wiki", action="store_true", help="禁用 minecraft.wiki")
    parser.add_argument("-o", "--output", dest="output", default=None, help="输出到文件而非 stdout")
    sub = parser.add_subparsers(dest="cmd")

    s = sub.add_parser("search", help="三平台并行搜索（MC百科+Modrinth+minecraft.wiki）")
    s.add_argument("keyword", nargs="?", help="搜索关键词（作者搜索时忽略）")
    s.add_argument("-n", "--max", type=int, default=3, help="每平台最多结果（默认3）")
    s.add_argument("-t", "--timeout", type=int, default=12, help="超时秒数（默认12）")
    s.add_argument("--type", dest="content_type", default="mod",
                   choices=["mod", "item"],
                   help="MC百科内容类型（默认 mod）")
    s.add_argument("--author", dest="author_name", default=None,
                   help="MC百科作者搜索（仅搜 MC百科，忽略 --type）")

    w = sub.add_parser("wiki", help="minecraft.wiki 搜索")
    w.add_argument("keyword", help="搜索关键词")
    w.add_argument("-n", "--max", type=int, default=5)
    w.add_argument("-r", "--read", action="store_true", help="搜索后直接读取第一个页面正文")

    r = sub.add_parser("read", help="读取 wiki 页面正文")
    r.add_argument("url", help="页面 URL")
    r.add_argument("-p", "--paragraphs", type=int, default=5)

    mr = sub.add_parser("mr", help="Modrinth 搜索（支持光影/纹理包）")
    mr.add_argument("keyword", help="搜索关键词")
    mr.add_argument("-n", "--max", type=int, default=5)
    mr.add_argument("-t", "--type", dest="ptype", default="mod",
                    choices=["mod", "shader", "resourcepack"],
                    help="项目类型（默认 mod）")

    dp = sub.add_parser("dep", help="查看 mod 依赖树（Modrinth）")
    dp.add_argument("mod_id", help="Mod ID（slug 或 project id）")
    dp.add_argument("--installed", dest="installed_version", default=None,
                    help="当前安装的版本号（用于参考，不做版本对比）")

    uc = sub.add_parser("update-check", help="检查 mod 是否有新版本")
    uc.add_argument("mod_id", help="Mod ID（slug 或 project id）")
    uc.add_argument("--installed", dest="installed_version", required=True,
                    help="当前安装的版本号")

    at = sub.add_parser("author", help="按作者搜索 Modrinth 项目（支持模糊匹配）")
    at.add_argument("username", help="作者用户名（Modrinth username）")
    at.add_argument("-n", "--max", type=int, default=10, help="最多结果（默认10）")

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
    )

    # 全局 --output 辅助
    _out_buf = []
    def _run_and_capture(func):
        """执行函数，stdout 写入 args.output 文件（如果指定）。"""
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                with contextlib.redirect_stdout(f):
                    func()
            print(f"[已写入 {args.output}]", file=sys.stderr)
        else:
            func()

    def _cmd_search():
        t0 = time.time()
        if args.author_name:
            # MC百科作者搜索（单平台）
            try:
                hits = core.search_mcmod_author(args.author_name, max_mods=args.max)
            except Exception as e:
                hits = []
            if args.json:
                _json({"mcmod.cn (作者)": hits, "modrinth": [], "minecraft.wiki": []})
            else:
                if not hits:
                    print(f"MC百科 未找到作者 [{args.author_name}] 的页面（作者名需精确匹配）")
                else:
                    print(f"[{args.author_name}] 的 MC百科 作品（共 {len(hits)} 个）：")
                    for h in hits:
                        print_hit(h)
            print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
            return
        results = core.search_all(args.keyword, max_per_source=args.max,
                                  timeout=args.timeout, content_type=args.content_type)
        if args.json:
            _json(results)
        else:
            print_results(results, keyword=args.keyword)
        print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)

    def _cmd_wiki():
        t0 = time.time()
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
                content = core.read_wiki(hits[0]["url"], max_paragraphs=4)
                if "error" not in content:
                    for i, p in enumerate(content["content"], 1):
                        print(f"  {i}. {p[:200]}")
        print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)

    def _cmd_read():
        t0 = time.time()
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
                        print(f"    {line[:200]}")
            else:
                # 降级：平铺段落
                for i, p in enumerate(content["content"], 1):
                    print(f"\n  {i}. {p[:250]}")
        print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)

    def _cmd_mr():
        t0 = time.time()
        hits = core.search_modrinth(args.keyword, max_results=args.max, project_type=args.ptype)
        if args.json:
            _json(hits)
        elif not hits:
            print(f"Modrinth 无 [{args.keyword}] 相关结果（类型：{args.ptype}）")
        else:
            for h in hits:
                print_hit(h)
        print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)

    def _cmd_dep():
        t0 = time.time()
        info = core.get_mod_info(args.mod_id)
        if not info:
            print(f"[{args.mod_id}] 未在 Modrinth 上找到该 mod")
            print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
            return
        result = core.get_mod_dependencies(args.mod_id, project_id=info.get("id"))
        deps = result.get("deps", {})
        opt_cnt = result.get("optional_count", 0)
        req_cnt = result.get("required_count", 0)

        if args.json:
            _json(result)
        elif result.get("error") == "API_ERROR":
            print(f"[{args.mod_id}]（{info.get('name', args.mod_id)}）查询依赖时网络错误")
        elif not deps:
            print(f"[{args.mod_id}]（{info.get('name', args.mod_id)}）无声明依赖")
        else:
            print(f"[{info.get('name', args.mod_id)}] 依赖树（必需:{req_cnt} | 可选:{opt_cnt}）：")
            for dep_id, dep in deps.items():
                side = f"client:{dep['client_side']} / server:{dep['server_side']}"
                print(f"  [{dep['type']}] {dep['name']} ({side})")
                if dep.get("url"):
                    print(f"    {dep['url']}")
        print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)

    def _cmd_update_check():
        t0 = time.time()
        info = core.get_mod_info(args.mod_id)
        if not info:
            print(f"[{args.mod_id}] 未找到该 mod（Modrinth）")
            print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
            return

        latest = info.get("latest_version") or "未知"
        installed = args.installed_version or "未知"
        is_latest = latest == installed or installed == "未知"
        game_versions = info.get("game_versions", [])
        loaders = info.get("loaders", [])
        source_url = info.get("source_url")
        issues_url = info.get("issues_url")
        discord_url = info.get("discord_url")
        updated = info.get("updated", "")[:10]
        downloads = info.get("downloads", 0)
        followers = info.get("followers", 0)
        author = info.get("author") or "未知"
        license_id = info.get("license", "")

        version_groups = info.get("version_groups", [])
        changelogs = info.get("changelogs", [])
        body = info.get("body", "")

        if args.json:
            _json({
                "name": info.get("name"),
                "slug": info.get("slug"),
                "author": author,
                "license": license_id,
                "source_url": source_url,
                "issues_url": issues_url,
                "discord_url": discord_url,
                "icon_url": info.get("icon_url", ""),
                "installed": installed,
                "latest": latest,
                "game_versions": game_versions,
                "loaders": loaders,
                "downloads": downloads,
                "followers": followers,
                "updated": updated,
                "is_latest": is_latest,
                "url": info.get("url"),
                "version_groups": version_groups,
                "changelogs": changelogs,
                "body": body,
            })
        else:
            print(f"[{info.get('name')}]  by {author}")
            print(f"  最新版本: {latest}  ({', '.join(loaders) if loaders else '无加载器'} | {', '.join(game_versions) if game_versions else '无版本信息'})")
            if version_groups:
                print(f"  版本历史：")
                for mod_ver, meta in version_groups:
                    ld = ", ".join(meta["loaders"])
                    gv = ", ".join(meta["game_versions"][:4])
                    print(f"    {mod_ver}  [{ld}]  游戏: {gv}")
            if changelogs:
                cl = changelogs[0]
                clines = cl["changelog"].split("\n")
                preview = clines[0][:120] + ("..." if len(clines[0]) > 120 or len(clines) > 1 else "")
                print(f"  最新更新 ({cl['version']} / {cl['date']})：")
                print(f"    {preview}")
            if is_latest:
                print(f"  状态: ✅ 已是最新（当前: {installed}）")
            else:
                print(f"  当前版本: {installed}  →  最新版本: {latest}")
                print(f"  状态: 🔁 有新版本！")
            print(f"  下载: {downloads:,}  |  关注: {followers:,}")
            print(f"  更新时间: {updated}")
            if source_url:
                print(f"  开源: {source_url}")
            if discord_url:
                print(f"  Discord: {discord_url}")
            if issues_url:
                print(f"  Issues: {issues_url}")
            print(f"  {info.get('url')}")
        print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)

    def _cmd_author():
        t0 = time.time()
        hits = core.search_author(args.username, max_results=args.max)
        if args.json:
            _json(hits)
        elif not hits:
            print(f"Modrinth 无 [{args.username}] 的作品（用户名不存在或无公开项目）")
        else:
            print(f"[{args.username}] 的 Modrinth 作品（共 {len(hits)} 个）：")
            for h in hits:
                print_hit(h)
        print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)

    def _cmd_info():
        """MC百科模组详情，默认全字段，支持按 -t/-a/-d/-v/-R/-g/-c/-s 过滤。"""
        t0 = time.time()
        mod_arg = args.mod

        # 解析 mod 参数：class URL、纯数字 ID 或名称
        if mod_arg.startswith("https://www.mcmod.cn/class/"):
            class_id = re.search(r"/class/(\d+)", mod_arg).group(1)
        elif mod_arg.isdigit():
            class_id = mod_arg
        else:
            # 按名称搜索，取第一个结果
            results = core.search_mcmod(mod_arg, max_results=1)
            if not results:
                print(f"未找到名为 [{mod_arg}] 的模组")
                print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
                return
            match = re.search(r"/class/(\d+)", results[0].get("url", ""))
            if not match:
                print(f"无法解析模组 ID")
                print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
                return
            class_id = match.group(1)

        # 抓取 class 页面（search_mcmod 已缓存，只获取一次）
        html = core._curl(f"https://www.mcmod.cn/class/{class_id}.html")
        if not html or len(html) < 1000:
            print(f"无法获取模组页面（ID: {class_id}）")
            print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
            return

        info = core._parse_mcmod_result(html, f"https://www.mcmod.cn/class/{class_id}.html", "")

        if args.json:
            _json(info)
            print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)
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
                stype_map = {"open_source": "开源", "closed_source": "闭源"}
                if st:
                    print(f"  状态：{st}")
                if stype:
                    print(f"  开源属性：{stype_map.get(stype, stype)}")

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
            print(f"  来源：{info.get('source', 'mcmod.cn')}")
            print(f"  页面：{info.get('url', '')}")
            sid = info.get("source_id", "")
            print(f"  Class ID：{sid}")

        # --mr: 额外查询 Modrinth（用 name_en 或 name 搜索）
        if args.modrinth:
            mr_name = info.get("name_en") or info.get("name", "")
            if mr_name:
                mr_results = core.search_modrinth(mr_name, max_results=3)
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

        # 作者引导
        author = info.get("author")
        if author and not args.modrinth:
            safe_author = author.replace(" ", "_")
            print(f"\n  💡 同作者其他作品：search --author {safe_author}")

        print(f"\n[耗时: {time.time()-t0:.1f}s]", file=sys.stderr)

    # 分发
    commands = {
        "search": _cmd_search,
        "wiki": _cmd_wiki,
        "read": _cmd_read,
        "mr": _cmd_mr,
        "dep": _cmd_dep,
        "update-check": _cmd_update_check,
        "author": _cmd_author,
        "info": _cmd_info,
    }

    if args.cmd in commands:
        _run_and_capture(commands[args.cmd])
    else:
        parser.print_help()


# ─────────────────────────────────────────
# 打印函数
# ─────────────────────────────────────────

def print_results(results: dict, keyword: str):
    """打印三平台搜索结果（同结果合并提示 + 同名消歧）。"""
    total = sum(len(v) for v in results.values())
    if total == 0:
        print(f"三个平台均无 [{keyword}] 相关结果")
        return

    # 收集第一个模组结果（用于后续提示）
    first_mod_name = None
    first_mcmod_hit = None
    for src, hits in results.items():
        for h in hits:
            if h.get("type") == "mod" and first_mod_name is None:
                first_mod_name = h.get("name_en") or h.get("name") or h.get("name_zh") or ""
                if h.get("source") == "mcmod.cn":
                    first_mcmod_hit = h

    for src, hits in results.items():
        if not hits:
            continue
        print(f"\n  [{src}]")
        # 检测同名碰撞（按 name 统计出现次数）
        name_count: dict[str, int] = {}
        for h in hits:
            n = (h.get("name_zh") or h.get("name") or "").lower()
            name_count[n] = name_count.get(n, 0) + 1

        for i, h in enumerate(hits):
            # 统计同名出现次数，用于消歧
            n = (h.get("name_zh") or h.get("name") or "").lower()
            dup_count = name_count.get(n, 1)
            print_hit(h, index=i, total=dup_count)

    # 操作提示
    if first_mod_name:
        slug = first_mcmod_hit.get("source_id", "") if first_mcmod_hit else ""
        author = first_mcmod_hit.get("author") if first_mcmod_hit else None
        mod_name_for_info = first_mcmod_hit.get("name_zh") or first_mod_name if first_mcmod_hit else first_mod_name
        print(f"\n  💡 更多操作：")
        print(f"     info {mod_name_for_info}        # 查看详细信息（MC百科）")
        if slug:
            print(f"     dep {slug}              # 查看依赖（Modrinth）")
            print(f"     update-check {slug} --installed <ver>  # 检查更新")
        if author:
            safe_author = author.replace(" ", "_")
            print(f"     search --author {safe_author}  # 查看作者其他作品（MC百科）")
        else:
            en_name = first_mcmod_hit.get("name_en") if first_mcmod_hit else ""
            if en_name:
                print(f"     author {en_name}          # 查看作者其他作品（Modrinth）")


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
    打印单个搜索结果（含消歧信息）。
    index/total: 该结果在其分组中的位置，用于检测同名项。
    """
    # ── 名称行 ──
    name = h.get("name_zh") or h.get("name", "?")
    en = h.get("name_en", "")
    badge = _type_badge(h)
    name_line = f"{name} {badge}".strip()
    if en and en != name:
        name_line = f"{name_line} ({en})"
    print(f"  {name_line}")

    # ── 消歧信息（当同名或多项时显示） ──
    src = h.get("source", "")
    htype = h.get("type", "mod")

    # MC百科：显示分类（模组）或资料分类（物品）
    if src == "mcmod.cn":
        if htype == "item":
            # 物品：资料分类 + 所属模组 + 耐久/堆叠
            cat = h.get("category")
            mod_name = h.get("source_mod_name")
            mod_url = h.get("source_mod_url")
            dur = h.get("max_durability")
            stack = h.get("max_stack")
            meta = []
            if cat:
                meta.append(f"分类:{cat}")
            if dur:
                meta.append(f"耐久:{dur}")
            if stack:
                meta.append(f"堆叠:{stack}")
            if meta:
                print(f"    {' | '.join(meta)}")
            if mod_name:
                print(f"    来自: {mod_name}")
                if mod_url:
                    print(f"    {mod_url}")
        else:
            # 模组：分类 + 状态
            cats = h.get("categories", [])
            if cats:
                print(f"    分类: {' | '.join(cats)}")
            st = h.get("status")
            stype = h.get("source_type")
            stype_map = {"open_source": "开源", "closed_source": "闭源"}
            meta = []
            if st:
                meta.append(st)
            if stype:
                meta.append(stype_map.get(stype, stype))
            if meta:
                print(f"    {' '.join(meta)}")

    # Modrinth：显示类型（同名不同类时）
    elif src == "modrinth" and total > 1:
        pt = h.get("type", "mod")
        print(f"    类型: {pt}")

    # ── URL ──
    if h.get("url"):
        print(f"    {h['url']}")

    # ── 描述/摘要（MC百科有 description，Modrinth 有 snippet） ──
    desc = h.get("description") or h.get("snippet", "")
    if desc:
        first_line = desc.strip().split("\n")[0][:120]
        if first_line:
            print(f"    {first_line}")

    # ── Wiki 章节 ──
    if h.get("sections"):
        for s in h["sections"][:5]:
            print(f"    · {s}")


if __name__ == "__main__":
    main()
