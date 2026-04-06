#!/usr/bin/env python3
"""
mc-search CLI — Minecraft 聚合搜索工具
四平台并行，结果格式一致
"""

import argparse
import contextlib
import functools
import json
import os
import re
import sys
import time
import urllib.parse

from . import core

# 完整描述保存目录
# 优先级：环境变量 > 当前目录下的 output 文件夹 > 用户主目录
_OUTPUT_DIR = os.environ.get(
    "MC_SEARCH_OUTPUT_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
)


def _save_full_description(project_name: str, content: str, content_type: str = "mod") -> str:
    """
    保存完整描述到文件。

    参数:
        project_name: 项目名称（用于文件名）
        content: 完整描述内容
        content_type: 内容类型（mod/shader/resourcepack/modpack）

    返回:
        文件路径
    """
    # 清理项目名称，只保留安全字符
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\u4e00-\u9fff]', '_', project_name)[:50]
    filename = f"{safe_name}_{content_type}_full.md"

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(_OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {project_name} - 完整描述\n\n")
        f.write(f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"---\n\n")
        f.write(content)

    return filepath


def _timed(func):
    """自动计时装饰器：打印函数执行耗时到 stderr（JSON 模式下禁用）。

    注意：必须返回 result，否则被装饰函数会返回 None。
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.time()
        result = func(*args, **kwargs)
        # JSON 模式下不输出耗时（避免污染 stderr 被重定向到 stdout）
        if '--json' not in sys.argv:
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
_DEFAULT_PARAGRAPHS = 20  # wiki 页面默认段落数（提升信息量）

# 显示截断长度
_DISPLAY_WIKI_PARAGRAPHS = 4    # wiki 搜索后自动 read 的段落数
_DISPLAY_WIKI_SNIPPET_MAX = 150  # wiki 搜索 snippet 最大字符数
_DISPLAY_MR_SNIPPET_MAX = 120    # Modrinth 搜索 snippet 最大字符数
_DISPLAY_LINE_MAX = 200         # 单行最大显示字符数（search/wiki 命令）
_DISPLAY_READ_LINE_MAX = 250    # read 命令正文单行最大长度
_DISPLAY_MODRINTH_BODY_MAX = 500  # full 命令 Modrinth body 每段最大字符数
_DISPLAY_INFO_DESC_MAX = 1500   # info 命令描述正文最大字符数
_DISPLAY_INFO_DESC_TRUNCATE = 1000  # info 命令描述智能截断阈值
_DISPLAY_CHANGELOG_MAX = 100    # full 命令 changelog 每段最大字符数
_DISPLAY_MR_INFO_SNIPPET_MAX = 100  # info -m 命令 MR snippet 最大字符数
_MATCH_THRESHOLD_EXACT = 200    # Modrinth 精确匹配分数
_MATCH_THRESHOLD_FUZZY = 150    # Modrinth 模糊匹配分数

# 匹配分数阈值
_MATCH_SCORE_SUBSTRING = 50     # 子串匹配分数
_MATCH_SCORE_PREFIX = 30        # 前缀匹配分数
_MATCH_SCORE_MINIMUM_ACCEPTABLE = 50  # 最低可接受分数

# 显示截断值
_DISPLAY_MAX_VER_GROUP = 8      # 版本组最多显示数
_DISPLAY_MAX_GALLERY = 10       # 图库最多显示数
_DISPLAY_MAX_SCREENSHOTS = 3    # 截图最多显示数
_DISPLAY_MAX_SECTIONS = 5       # wiki 章节最多显示数
_DISPLAY_MAX_CHANGELOGS = 2     # 更新日志最多显示数
_DISPLAY_MAX_PREVIEW_PARAS = 5  # 预览段落最多显示数
_DISPLAY_MAX_RECIPE_IMAGES = 4  # 合成表图片最多显示数
_DISPLAY_MAX_VERSIONS = 8       # 支持版本最多显示数

# 保存阈值
_SAVE_BODY_LENGTH_THRESHOLD = 3000    # Modrinth body 保存文件阈值
_SAVE_DESC_LENGTH_THRESHOLD = 5000    # MC百科简介保存文件阈值

# Modrinth 正文预览相关
_MODRINTH_PREVIEW_LEN = 2000          # 预览最大字符数
_MODRINTH_PREVIEW_SENTENCE_MIN = 1500  # 预览句子截断最小位置
_MODRINTH_PREVIEW_MAX_PARAS = 10      # 预览最多段落数

# MC百科简介预览相关
_MCMDOD_DESC_PREVIEW_LEN = 1500       # 预览最大字符数
_MCMDOD_DESC_PREVIEW_SENTENCE_MIN = 1000  # 预览句子截断最小位置
_MCMDOD_DESC_PREVIEW_MAX_PARAS = 5    # 预览最多段落数

# 平台标识常量
_PLATFORM_MCMOD = "mcmod"
_PLATFORM_MODRINTH = "modrinth"


def _print_error_or_json(error_msg: dict, is_json: bool):
    """打印错误消息（支持 JSON 和文本两种格式）。"""
    if is_json:
        print(json.dumps(error_msg, ensure_ascii=False))
    else:
        print(error_msg["message"])


# URL 构造辅助函数

def _mcmod_class_url(class_id: str) -> str:
    """生成 MC百科 class 页面 URL。"""
    return f"https://www.mcmod.cn/class/{class_id}.html"


def _modrinth_project_url(slug: str, project_type: str = "mod") -> str:
    """生成 Modrinth 项目 URL。"""
    return f"https://modrinth.com/{project_type}/{slug}"


def _mcmod_search_url(keyword: str, filter_val: str) -> str:
    """生成 MC百科搜索 URL。"""
    q = urllib.parse.quote(keyword)
    return f"https://search.mcmod.cn/s?key={q}&filter={filter_val}"


# 文本清理辅助函数

def _clean_markdown(text: str, full_clean: bool = False) -> str:
    """
    清理 Markdown/HTML 标记，用于显示摘要。

    参数:
        text: 原始文本
        full_clean: True 时执行完整清理（包括代码块、标题等）

    返回:
        清理后的纯文本
    """
    if not text:
        return ""

    if full_clean:
        # 完整清理（用于 body 等长文本）
        text = re.sub(r'```[\s\S]*?```', '', text)  # 代码块
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # 图片
        text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)  # 链接→文本
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # 加粗
        text = re.sub(r'\*(.+?)\*', r'\1', text)  # 斜体
        text = re.sub(r'`{1,3}.*?`{1,3}', '', text)  # 代码
        text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)  # 标题
        text = re.sub(r'<[^>]+>', '', text)  # HTML
        text = re.sub(r'\n{3,}', '\n\n', text)  # 多余空行
        return text.strip()  # 保留换行
    else:
        # 基本清理（用于 snippet）
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # 图片
        text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)  # 链接→文本
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # 加粗
        text = re.sub(r'\*(.+?)\*', r'\1', text)  # 斜体
        text = re.sub(r'`{1,3}.*?`{1,3}', '', text)  # 代码
        text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)  # 标题
        text = re.sub(r'<[^>]+>', '', text)  # HTML

    text = re.sub(r'\s+', ' ', text).strip()
    return text


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
    s.add_argument("--json", action="store_true", help="以 JSON 格式输出")
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
    w.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    w.add_argument("keyword", help="搜索关键词")
    w.add_argument("-n", "--max", type=int, default=_DEFAULT_WIKI_MAX)
    w.add_argument("-r", "--read", action="store_true", help="搜索后直接读取第一个页面正文")
    w.add_argument("-t", "--timeout", type=int, default=_DEFAULT_TIMEOUT, help=f"超时秒数（默认{_DEFAULT_TIMEOUT}）")

    r = sub.add_parser("read", help="读取 wiki 页面正文")
    r.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    r.add_argument("url", help="页面 URL")
    r.add_argument("-p", "--paragraphs", type=int, default=_DEFAULT_PARAGRAPHS)

    mr = sub.add_parser("mr", help="Modrinth 搜索（支持光影/纹理包）")
    mr.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    mr.add_argument("keyword", help="搜索关键词")
    mr.add_argument("-n", "--max", type=int, default=_DEFAULT_WIKI_MAX)
    mr.add_argument("-t", "--type", dest="ptype", default="mod",
                    choices=["mod", "shader", "resourcepack"],
                    help="项目类型（默认 mod）")

    dp = sub.add_parser("dep", help="查看 mod 依赖树（Modrinth）")
    dp.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    dp.add_argument("mod_id", help="Mod ID（slug 或 project id）")

    at = sub.add_parser("author", help="按作者搜索 Modrinth 项目（支持模糊匹配）")
    at.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    at.add_argument("username", help="作者用户名（Modrinth username）")
    at.add_argument("-n", "--max", type=int, default=_DEFAULT_AUTHOR_MAX, help=f"最多结果（默认{_DEFAULT_AUTHOR_MAX}）")

    if_info = sub.add_parser("info", help="读取 MC百科模组详情（默认全字段，可选 -T/-a/-d/-v/-g/-c/-s/-S/-m）")
    if_info.add_argument("--json", action="store_true", help="以 JSON 格式输出")
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
    fl.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    fl.add_argument("project", help="名称 / MC百科 URL/ID / Modrinth URL/slug（支持 mod/shader/resourcepack/modpack）")
    fl.add_argument("--skip-dep", dest="skip_dep", action="store_true",
                    help="跳过依赖查询（加速）")
    fl.add_argument("--skip-mr", dest="skip_mr", action="store_true",
                    help="跳过 Modrinth 查询（加速）")

    args = parser.parse_args()

    # 修复：全局 --json 传播到子命令
    # 当用户使用 "mc-search --json full xxx" 时，argparse 可能只设置子命令的 json 为 True
    # 所以这里统一确保所有子命令的 json 标志与全局一致
    import sys as _sys
    if '--json' in _sys.argv:
        args.json = True

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
                    sys.exit(1)
                else:
                    print(f"[{args.author_name}] 的 MC百科 作品（共 {len(hits)} 个）：")
                    for h in hits:
                        print_hit(h)
            return

        # 校验空关键词
        if not args.keyword or not args.keyword.strip():
            print("错误: 搜索关键词不能为空")
            sys.exit(1)

        # 去除关键词前后空格
        args.keyword = args.keyword.strip()

        results = core.search_all(args.keyword, max_per_source=args.max,
                                  timeout=args.timeout, content_type=args.content_type,
                                  fuse=True)
        if args.json:
            _json(results)
        else:
            # 融合结果：统一按相关性排序，逐条打印（platform_stats 仅在 JSON 中显示）
            if not results.get("results"):
                print(f"所有平台均无 [{args.keyword}] 相关结果")
                sys.exit(1)
            else:
                for h in results["results"]:
                    print_hit(h)

    @_timed
    def _cmd_wiki():
        # 使用 search_all 同时搜索双 wiki（英文 + 中文）
        core.set_platform_enabled(mcmod=False, modrinth=False, wiki=True, wiki_zh=True)
        result = core.search_all(args.keyword, max_per_source=args.max,
                                  timeout=args.timeout, content_type="entity",
                                  fuse=True)
        hits = result.get("results", [])
        if not hits:
            if args.json:
                _json([])
            else:
                print(f"minecraft.wiki 无 [{args.keyword}] 相关结果")
            return
        if args.json:
            _json(hits)
        else:
            for i, h in enumerate(hits[:10], 1):
                name = h.get("name_zh") or h.get("name_en") or h.get("name", "?")
                source = h.get("source", "")
                sections = h.get("sections", [])
                snippet = h.get("snippet", "")

                print(f"  {i}. {name} 【{source}】")

                # 清理 HTML 标签显示摘要
                if snippet:
                    # 去除所有 HTML 标签（包括 <img>, <script>, <style> 等）
                    clean_snippet = re.sub(r'<[^>]+>', '', snippet)
                    # 去除多余空白和换行
                    clean_snippet = re.sub(r'\s+', ' ', clean_snippet).strip()
                    # 截断到_DISPLAY_WIKI_SNIPPET_MAX字符
                    if len(clean_snippet) > _DISPLAY_WIKI_SNIPPET_MAX:
                        clean_snippet = clean_snippet[:_DISPLAY_WIKI_SNIPPET_MAX] + '...'
                    if clean_snippet:
                        print(f"     摘要: {clean_snippet}")

                # 显示章节
                if sections:
                    print(f"     章节：")
                    for sec in sections[:5]:
                        print(f"       {sec}")

                # 显示链接
                url = h.get("url", "")
                if url:
                    print(f"     → {url}")
                print()
            if args.read and hits:
                print("\n[读取正文...]")
                # 根据来源选择正确的 wiki 读取函数
                source = hits[0].get("source", "")
                if source == "minecraft.wiki/zh":
                    content = core.read_wiki_zh(hits[0]["url"], max_paragraphs=_DISPLAY_WIKI_PARAGRAPHS)
                else:
                    content = core.read_wiki(hits[0]["url"], max_paragraphs=_DISPLAY_WIKI_PARAGRAPHS)
                if "error" not in content:
                    for i, p in enumerate(content["content"], 1):
                        print(f"  {i}. {p[:_DISPLAY_LINE_MAX]}")

    @_timed
    def _cmd_read():
        # 判断是否为中文 wiki URL
        if "zh.minecraft.wiki" in args.url or args.url.startswith("minecraft.wiki/w/zh"):
            content = core.read_wiki_zh(args.url, max_paragraphs=args.paragraphs)
        else:
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
        # 校验空关键词
        if not args.keyword or not args.keyword.strip():
            print("错误: 搜索关键词不能为空")
            return

        args.keyword = args.keyword.strip()

        data = core.search_modrinth(args.keyword, max_results=args.max, project_type=args.ptype)
        if args.json:
            _json(data)
        elif not data.get("results"):
            print(f"Modrinth 无 [{args.keyword}] 相关结果（类型：{args.ptype}）")
            sys.exit(1)
        else:
            for i, h in enumerate(data["results"][:10], 1):
                name = h.get("name", "?")
                ptype = h.get("type", "mod")
                snippet = h.get("snippet", "")

                print(f"  {i}. {name} 【modrinth】")
                print(f"     类型: {ptype}")

                # 清理 Markdown 标记显示摘要
                if snippet:
                    clean_snippet = _clean_markdown(snippet)
                    # 截断到_DISPLAY_MR_SNIPPET_MAX字符
                    if len(clean_snippet) > _DISPLAY_MR_SNIPPET_MAX:
                        clean_snippet = clean_snippet[:_DISPLAY_MR_SNIPPET_MAX] + '...'
                    if clean_snippet:
                        print(f"     {clean_snippet}")

                # 显示链接
                url = h.get("url", "")
                if url:
                    print(f"     → {url}")
                print()

    @_timed
    def _cmd_dep():
        info = core.fetch_mod_info(args.mod_id)
        if not info:
            error_msg = {"error": "MOD_NOT_FOUND", "message": f"[{args.mod_id}] 未在 Modrinth 上找到该 mod"}
            _print_error_or_json(error_msg, args.json)
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
        # 校验空用户名
        if not args.username or not args.username.strip():
            print("错误: 作者用户名不能为空")
            sys.exit(1)
            return

        args.username = args.username.strip()

        hits = core.search_author(args.username, max_results=args.max)
        if args.json:
            _json(hits)
        elif not hits:
            print(f"Modrinth 无 [{args.username}] 的作品（用户名不存在或无公开项目）")
            sys.exit(1)
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
            error_msg = {"error": "MR_URL_NOT_SUPPORTED", "message": "info 命令不支持 Modrinth URL，请使用 mod 名称或 MC百科 URL/ID"}
            _print_error_or_json(error_msg, args.json)
            return

        if ident["class_id"]:
            class_id = ident["class_id"]
        elif ident["mcmod_name"]:
            try:
                results = core.search_mcmod(ident["mcmod_name"], max_results=1)
            except core._SearchError:
                results = []
            if not results:
                error_msg = {"error": "MOD_NOT_FOUND", "message": f"未找到名为 [{ident['mcmod_name']}] 的模组"}
                _print_error_or_json(error_msg, args.json)
                return
            match = re.search(r"/class/(\d+)", results[0].get("url", ""))
            if not match:
                error_msg = {"error": "INVALID_ID", "message": "无法解析模组 ID"}
                _print_error_or_json(error_msg, args.json)
                return
            class_id = match.group(1)
        else:
            print(f"无法解析模组标识：{mod_arg}")
            sys.exit(1)
            return

        # 抓取 class 页面
        html = core._curl(_mcmod_class_url(class_id))
        if not html or len(html) < core._MIN_HTML_LEN:
            print(f"无法获取模组页面（ID: {class_id}）")
            sys.exit(1)
            return

        # 检测 MC百科错误页面（重定向到 /error/）
        if '/error/' in html or 'Jump' in html and '/error/' in html:
            print(f"错误: 未找到 ID 为 {class_id} 的模组页面（MC百科返回错误页面）")
            sys.exit(1)
            return

        info = core._parse_mcmod_result(html, _mcmod_class_url(class_id), "")

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

        # 显示描述正文（按字符数限制）
        if show_all:
            desc = info.get("description", "")
            if desc:
                # 清理 HTML 标签
                clean_desc = re.sub(r'<[^>]+>', '', desc)
                clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()

                if clean_desc:
                    print(f"\n  简介：")
                    if len(clean_desc) > _DISPLAY_INFO_DESC_MAX:
                        truncated = clean_desc[:_DISPLAY_INFO_DESC_MAX]
                        last_period = max(truncated.rfind('。'), truncated.rfind('！'), truncated.rfind('？'), truncated.rfind('\n'))
                        if last_period > _DISPLAY_INFO_DESC_TRUNCATE:
                            truncated = truncated[:last_period + 1]
                        print(f"    {truncated}")
                        remaining = len(clean_desc) - len(truncated)
                        print(f"    ...（还有 {remaining} 字符，完整内容请查看网页）")
                    else:
                        print(f"    {clean_desc}")

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
                        print(f"    {best['snippet'][:_DISPLAY_MR_INFO_SNIPPET_MAX]}")
                    # 显示完整 Modrinth 信息
                    slug = best.get("source_id", "")
                    if slug:
                        mr_info = core.fetch_mod_info(slug)
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
                recipe_data = core.fetch_item_recipe(recipe_url)
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
            url = _mcmod_class_url(class_id)
            html = core._curl(url)
            if html and len(html) >= core._MIN_HTML_LEN:
                return core._parse_mcmod_result(html, url, ""), []

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

        html = core._curl(_mcmod_class_url(cid_match.group(1)))
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
                info = core.fetch_mod_info(direct_slug, no_limit=True)
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
                best_score = _MATCH_THRESHOLD_EXACT
                best_match = hit
                break

            # 检查名称是否完全匹配
            norm_hit = re.sub(r"[^a-z0-9]", "", hit_name.lower())
            if norm_hit == norm_search:
                best_score = _MATCH_THRESHOLD_FUZZY
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
                    return core.fetch_mod_info(slug, no_limit=True), None
                except Exception:
                    pass

        # 无精确匹配，返回第一个结果作为候选
        return None, hits[0].get("name") or hits[0].get("name_en") or ""

    @_timed
    def _cmd_full():
        """一键获取完整信息：支持模组/光影/材质包/整合包。"""
        project_arg = args.project
        result = {
            "mcmod": None,
            "modrinth": None,
            "dependencies": None,
            "search_results": [],
            "saved_files": [],  # 保存的文件路径列表（AI Agent 友好）
        }

        # ── 解析项目标识 ───────────────────────────────────────────
        ident = _parse_project_identifier(project_arg)

        # Modrinth URL：直接处理（支持 mod/shader/resourcepack/modpack）
        if ident["mr_slug"]:
            # 从 URL 提取项目类型
            mr_type = "mod"
            mr_type_match = re.search(r'modrinth\.com/(mod|shader|resourcepack|modpack)/', project_arg)
            if mr_type_match:
                mr_type = mr_type_match.group(1)

            # 直接通过slug精确获取（禁止搜索fallback）
            result["modrinth"] = core.fetch_mod_info(ident["mr_slug"], no_limit=True)

            # 如果URL中的slug不存在，直接返回错误
            if result["modrinth"] is None:
                result["error"] = "URL_NOT_FOUND"
                result["message"] = f"Modrinth上不存在slug为 '{ident['mr_slug']}' 的项目"
                if args.json:
                    _json_print(result)
                else:
                    print(result["message"])
                sys.exit(1)

            # 获取依赖
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
                    # 注意：不在这里输出联动模组，后续统一在依赖关系部分输出
                    if deps and deps.get('deps'):
                        print(f"\n  ── 依赖 ──")
                        print_deps(deps)
                else:
                    print(f"未找到该项目（slug: {ident['mr_slug']}）")
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
                    mr_info = core.fetch_mod_info(slug, no_limit=True)
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
            result["error"] = "NOT_FOUND"
            result["message"] = f"未找到 [{project_arg}] 的相关信息"
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(f"未找到名为 [{project_arg}] 的项目信息")
            sys.exit(1)
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
                _print_full_mcmod_info(mc, full_desc=True, saved_files=result.get("saved_files"))
            if mr:
                print(f"\n  ── Modrinth ──")
                _print_full_modrinth_info(mr, saved_files=result.get("saved_files"))
            elif result.get("_mr_tentative"):
                print(f"\n  ── Modrinth ──")
                print(f"  ⚠️ 名称未确认匹配，请自行确认")
                print(f"  参考搜索词 → Modrinth 结果：{result['_mr_tentative']}")

            # 依赖信息 - 前置依赖用 Modrinth，联动用 MC百科
            mc_integrations = []
            if mc:
                rel = mc.get('relationships') or {}
                mc_integrations = rel.get('integrates', []) if rel else []

            has_mr_deps = deps and deps.get('deps')

            # 依赖关系输出
            if has_mr_deps or mc_integrations:
                print(f"\n  ── 依赖关系 ──")

                # Modrinth 依赖 - 展示运行环境要求
                if has_mr_deps:
                    mr_deps = deps.get('deps', {})
                    if isinstance(mr_deps, dict):
                        print(f"  依赖模组（共 {len(mr_deps)} 个）：")
                        for slug, dep_info in mr_deps.items():
                            client_req = dep_info.get('client_side', 'unknown')
                            server_req = dep_info.get('server_side', 'unknown')

                            def env_label(v):
                                return {"required": "必需", "optional": "可选",
                                        "unsupported": "不支持", "unknown": "未知"}.get(v, v)

                            dep_name = dep_info.get('name', slug)
                            dep_desc = dep_info.get('summary') or dep_info.get('snippet') or ''

                            print(f"    • {dep_name}")
                            if dep_desc:
                                desc_lines = dep_desc.split('\n')
                                for line in desc_lines[:2]:
                                    print(f"      {line.strip()}")
                            print(f"      客户端:{env_label(client_req)}, 服务端:{env_label(server_req)}")
                            print(f"      {_modrinth_project_url(slug)}")

                # 联动模组 - 使用 MC百科 数据
                if mc_integrations:
                    if has_mr_deps:
                        print(f"")  # 空行分隔
                    print(f"  联动模组（{len(mc_integrations)} 个）：")
                    for int_mod in mc_integrations:
                        int_name = int_mod.get('name_zh') or int_mod.get('name_en', '?')
                        int_url = int_mod.get('url', '')
                        int_desc = int_mod.get('summary') or int_mod.get('snippet') or ''
                        print(f"    • {int_name}")
                        if int_desc:
                            desc_lines = int_desc.split('\n')
                            for line in desc_lines[:2]:
                                print(f"      {line.strip()}")
                        if int_url:
                            print(f"      {int_url}")
            else:
                print(f"\n  ── 依赖关系 ──")
                print(f"  无")

            # 未找到任何信息
            if not mc and not mr:
                print(f"未找到名为 [{project_arg}] 的项目信息")
                sys.exit(1)

        # JSON 模式：检查是否全 null/空
        if args.json:
            if all(v is None or v == [] for v in [result["mcmod"], result["modrinth"]]):
                result["error"] = "NOT_FOUND"
                result["message"] = f"未找到 [{project_arg}] 的相关信息"
                _json_print(result)
                sys.exit(1)

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
                        return core.fetch_mod_info(slug, no_limit=True)
                    except Exception:
                        pass

            # 名称精确匹配
            if hit_name_norm == norm_arg:
                slug = hit.get("source_id", "") or hit.get("slug", "")
                if slug:
                    try:
                        return core.fetch_mod_info(slug, no_limit=True)
                    except Exception:
                        pass

        # 无精确匹配，返回第一个作为候选
        return direct_hits[0] if direct_hits else None
    except Exception:
        return None


def _print_full_modrinth_info(mr: dict, saved_files: list = None):
    """打印 Modrinth 详细信息。

    参数:
        mr: Modrinth 数据
        saved_files: 用于收集保存的文件路径列表（AI Agent 友好）
    """
    print(f"\n【Modrinth - {mr.get('name', '?')}】")
    print(f"  平台: {mr.get('url', '')}")

    # 核心统计信息
    print(f"\n  统计:")
    print(f"    下载: {mr.get('downloads', 0):>10,} 次")
    print(f"    关注: {mr.get('followers', 0):>10,} 人")
    print(f"    作者: {mr.get('author', '?')}")
    print(f"    许可: {mr.get('license_name', 'N/A')}")

    # 双端支持情况（重点显示）
    client = mr.get('client_side', 'unknown')
    server = mr.get('server_side', 'unknown')
    side_map = {
        'required': '必需安装',
        'optional': '可选安装',
        'unsupported': '不支持'
    }
    print(f"\n  双端支持:")
    print(f"    客户端: {side_map.get(client, client)}")
    print(f"    服务端: {side_map.get(server, server)}")
    if client == 'required' and server == 'required':
        print(f"    → 这是双端必需模组，客户端和服务端都必须安装")
    elif client == 'optional' or server == 'optional':
        print(f"    → 这是双端可选模组")

    # 完整描述（详细说明）- 智能摘要 + 自动保存
    body = mr.get('body', '')
    if body:
        clean_body = _clean_markdown(body, full_clean=True)
        body_len = len(clean_body)

        # 如果描述超过阈值，保存到文件并显示摘要
        if body_len > _SAVE_BODY_LENGTH_THRESHOLD:
            # 保存完整描述到文件
            proj_name = mr.get('name', 'unknown')
            proj_type = mr.get('type', 'mod')
            filepath = _save_full_description(proj_name, clean_body, proj_type)

            # 添加到 AI Agent 友好的文件列表
            if saved_files is not None:
                saved_files.append(filepath)

            # 显示摘要
            print(f"\n  【详细说明】")
            preview_len = min(_MODRINTH_PREVIEW_LEN, body_len)
            preview = clean_body[:preview_len]
            # 在句子边界处截断
            last_period = max(preview.rfind('.'), preview.rfind('。'), preview.rfind('\n'))
            if last_period > _MODRINTH_PREVIEW_SENTENCE_MIN:
                preview = preview[:last_period + 1]
            elif last_period > 0:
                preview = preview[:last_period + 1] + '...'

            paras = preview.split('\n')
            for i, p in enumerate(paras[:_MODRINTH_PREVIEW_MAX_PARAS], 1):
                if p.strip():
                    print(f"    {p.strip()}")

            # 显示保存提示
            print(f"\n  💾 完整描述已保存到文件:")
            print(f"     {filepath}")
            print(f"     （共 {body_len} 字符）")
        else:
            # 短描述直接显示
            print(f"\n  【详细说明】")
            paras = clean_body.split('\n')
            for i, p in enumerate(paras, 1):
                if p.strip():
                    text = p.strip()
                    if len(text) > _DISPLAY_MODRINTH_BODY_MAX:
                        text = text[:_DISPLAY_MODRINTH_BODY_MAX] + '...'
                    print(f"    {text}")

    # 分类和标签
    categories = mr.get('categories', [])
    display_cats = mr.get('display_categories', [])
    if categories or display_cats:
        print(f"\n  分类:")
        all_cats = set(categories + display_cats)
        print(f"    {', '.join(sorted(all_cats))}")
    else:
        print(f"\n  分类: 暂无")

    # 外部链接
    links = []
    if mr.get('source_url'):
        links.append(f"源码: {mr['source_url']}")
    if mr.get('issues_url'):
        links.append(f"问题: {mr['issues_url']}")
    if mr.get('wiki_url'):
        links.append(f"Wiki: {mr['wiki_url']}")
    if mr.get('discord_url'):
        links.append(f"Discord: {mr['discord_url']}")
    if links:
        print(f"\n  相关链接:")
        for link in links:
            print(f"    • {link}")
    else:
        print(f"\n  相关链接: 暂无")

    # 版本信息
    vg = mr.get("version_groups", [])
    if vg:
        print(f"\n  版本信息 (展示前{min(8, len(vg))}个，共{len(vg)}个):")
        for vname, vinfo in vg[:8]:
            gvs = ', '.join(vinfo.get('game_versions', [])[:3])
            lds = ', '.join(vinfo.get('loaders', []))
            print(f"    • {vname}")
            print(f"      Minecraft: {gvs}")
            print(f"      加载器: {lds}")
        if len(vg) > 8:
            print(f"    ... 还有 {len(vg) - 8} 个版本")

    # 更新日志（如果可用）
    changelogs = mr.get('changelogs', [])
    if changelogs:
        print(f"\n  最近更新:")
        for cl in changelogs[:2]:
            print(f"    • v{cl.get('version', '?')} ({cl.get('date', '?')})")
            log_text = cl.get('changelog', '')
            if log_text:
                log_clean = re.sub(r'[-*]', '', log_text).strip()[:_DISPLAY_CHANGELOG_MAX]
                if log_clean:
                    print(f"      {log_clean}")

    # 画廊（截图）
    gallery = mr.get('gallery', [])
    if gallery:
        gallery_total = len(gallery)
        display_count = min(10, gallery_total)
        print(f"\n  截图 (共 {gallery_total} 张，显示前 {display_count} 张):")
        for i, img_url in enumerate(gallery[:display_count], 1):
            print(f"    {i}. {img_url}")
        if gallery_total > display_count:
            print(f"    ... 还有 {gallery_total - display_count} 张")

def _print_full_mcmod_info(mc: dict, full_desc: bool = False, saved_files: list = None):
    """打印 MC百科详细信息。

    参数:
        mc: MC百科数据
        full_desc: True 时显示完整简介，不截断
        saved_files: 用于收集保存的文件路径列表（AI Agent 友好）
    """
    print(f"\n【MC百科 - {mc.get('name_zh')}】")
    print(f"  平台: {mc.get('url', '')}")

    # 状态和类型
    if mc.get('status'):
        print(f"  状态: {mc['status']}  (类型: {mc.get('type', '?')})")

    # 作者团队信息
    author_team = mc.get('author_team', [])
    if author_team:
        print(f"\n  作者团队 ({len(author_team)}人):")
        for member in author_team:
            name = member.get('name', '?')
            roles = ', '.join(member.get('roles', []))
            print(f"    • {name} ({roles})")
    elif mc.get('author'):
        print(f"  作者: {mc['author']}")

    # 模组简介（按字符数限制，更合理）
    desc = mc.get('description', '')
    if desc:
        # 清理 HTML 标签
        clean_desc = re.sub(r'<[^>]+>', '', desc)
        clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()

        if clean_desc:
            print(f"\n  简介：")
            desc_len = len(clean_desc)

            # 如果简介非常长（超过阈值），保存到文件
            if desc_len > _SAVE_DESC_LENGTH_THRESHOLD:
                proj_name = mc.get('name_zh', 'unknown')
                proj_type = 'mod'
                filepath = _save_full_description(proj_name, clean_desc, proj_type)

                # 添加到 AI Agent 友好的文件列表
                if saved_files is not None:
                    saved_files.append(filepath)

                print(f"    💾 完整简介已保存到文件:")
                print(f"       {filepath}")
                print(f"       （共 {desc_len} 字符）")
                # 显示简要摘要
                print(f"\n    【简要摘要】")
                preview = clean_desc[:_MCMDOD_DESC_PREVIEW_LEN]
                last_period = max(preview.rfind('。'), preview.rfind('！'), preview.rfind('？'), preview.rfind('\n'))
                if last_period > _MCMDOD_DESC_PREVIEW_SENTENCE_MIN:
                    preview = preview[:last_period + 1]
                paras = preview.split('\n')
                for p in paras[:_MCMDOD_DESC_PREVIEW_MAX_PARAS]:
                    if p.strip():
                        print(f"    {p.strip()}")
            elif full_desc or desc_len <= _DISPLAY_INFO_DESC_MAX:
                # 完整显示
                paras = clean_desc.split('\n')
                for p in paras:
                    if p.strip():
                        print(f"    {p.strip()}")
            else:
                # 截断显示
                truncated = clean_desc[:_DISPLAY_INFO_DESC_MAX]
                last_period = max(truncated.rfind('。'), truncated.rfind('！'), truncated.rfind('？'), truncated.rfind('\n'))
                if last_period > _DISPLAY_INFO_DESC_TRUNCATE:
                    truncated = truncated[:last_period + 1]
                print(f"    {truncated}")
                remaining = len(clean_desc) - len(truncated)
                print(f"    ...（还有 {remaining} 字符，完整内容请查看网页）")

    # 支持版本
    vers = mc.get('supported_versions', [])
    if vers:
        print(f"\n  支持版本 ({len(vers)}个):")
        print(f"    {', '.join(vers[:8])}")
        if len(vers) > 8:
            print(f"    ... 还有 {len(vers) - 8} 个版本")

    # 分类和标签
    cats = mc.get('categories', [])
    tags = mc.get('tags', [])
    if cats or tags:
        print(f"\n  分类标签:")
        if cats:
            print(f"    分类: {', '.join(cats)}")
        if tags:
            print(f"    标签: {', '.join(tags)}")

    # 依赖关系 - 已移至 _cmd_full 统一处理
    # 此处不再输出依赖信息，避免重复

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
    # 优先使用 snippet（更简洁），fallback 到 description
    desc = h.get("snippet") or h.get("description", "")
    if desc:
        desc = _clean_markdown(desc)
        # search 命令用 200 字符（快速浏览）
        if len(desc) > _DISPLAY_LINE_MAX:  # _DISPLAY_LINE_MAX = 200
            desc = desc[:_DISPLAY_LINE_MAX] + "…"
        print(f"     {desc}")

    # ── 封面图 ──
    cover = h.get("cover_image")
    if cover:
        print(f"     封面: {cover}")

    # ── 截图（最多 3 张，避免刷屏）──
    shots = h.get("screenshots", [])
    if shots:
        shot_count = min(3, len(shots))
        print(f"     截图 ({len(shots)} 张):")
        for s in shots[:shot_count]:
            print(f"       - {s[:80]}")

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
    """打印依赖树（Modrinth数据来源）。"""
    dep_dict = deps.get("deps", {})
    if not dep_dict:
        print(f"[{mod_name}] 无声明依赖")
        return

    print(f"[{mod_name}] 依赖列表（共 {len(dep_dict)} 个）：")

    # 运行环境标签映射
    def env_label(value):
        labels = {
            "required": "必需",
            "optional": "可选",
            "unsupported": "不支持",
            "unknown": "未知"
        }
        return labels.get(value, value)

    for dep_id, dep in dep_dict.items():
        client_req = dep.get('client_side', 'unknown')
        server_req = dep.get('server_side', 'unknown')

        client_label = env_label(client_req)
        server_label = env_label(server_req)

        dep_name = dep.get('name', dep_id)
        dep_url = dep.get('url', '')

        print(f"  • {dep_name}")
        print(f"    运行环境: 客户端{client_label}, 服务端{server_label}")
        if dep_url:
            print(f"    {dep_url}")



if __name__ == "__main__":
    main()
