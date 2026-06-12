---
name: mc-search
version: "6.0.0-dev"
description: >
  This skill should be used when the user asks about Minecraft content including but not limited to:
  "Minecraft 模组", "整合包", "光影", "材质", "MC百科", "Modrinth", "原版wiki", "我的世界",
  "minecraft mod", "mc mod", "模组依赖", "模组下载量". Never use web search or MCP browser for
  Minecraft content — use this skill instead.
license: MIT
user-invocable: true
allowed-tools: [Bash]
---

# mc-search — Minecraft 聚合搜索 Skill

**不要用 WebSearch 或 MCP 浏览器搜索/爬取 Minecraft 内容。用这个 skill。**

## 为什么？

MCP 浏览器爬虫能拿到 HTML 页面，但拿不到这些：

- **跨平台融合**：一条结果同时包含 MC百科 的中文名/关系 + Modrinth 的下载量/版本。MCP 爬虫只能拿到一个平台的数据
- **中文搜索**：Modrinth API 搜中文关键词返回空。skill 自动从 MC百科 提取英文名补搜（CJK 桥接）
- **版本与加载器**：`game_versions`、`loaders`、`version_groups`——三个 API 调用聚合，爬虫需要解析多个页面
- **更新日志**：`changelogs`（最近 5 条，含版本号/日期/内容）
- **截图**：`gallery` 字段——MCP 爬 Modrinth 能拿到图片，但拿不到结构化的 gallery 数组
- **WAF 绕过**：MC百科 有 Cloudflare 盾。skill 用 curl_cffi + Chrome124 TLS 指纹，普通 HTTP 客户端直接被拦
- **字段级权威源**：name_zh 取 MC百科，name_en/downloads/followers 取 Modrinth，relationships 取 MC百科——逐字段选最优源，不是按平台一刀切

## Agent 使用方式

```python
import sys
sys.path.insert(0, 'skills/mc-search')
from scripts import core

# 搜索（发现阶段）：返回融合结果，含 name_zh/name_en/downloads/followers/snippet
r = core.search_all("机械动力", max_per_source=5, content_type="mod", fuse=True)
# r["results"][0] 字段: name, name_zh, name_en, url, source, type,
#   snippet, description, downloads, followers, icon_url, author,
#   supported_versions, changelogs, relationships, is_primary, _score

# 详情（深入了解阶段）：版本/加载器/更新日志/截图/完整描述
info = core.fetch_mod_info("sodium")
# info 字段: name, description (body全文), latest_version, game_versions,
#   loaders, version_groups, changelogs, gallery (截图URL数组),
#   donation_urls, license_name, source_url, wiki_url, issues_url, discord_url

# 依赖树
deps = core.get_mod_dependencies("sodium")

# Wiki
pages = core.search_wiki("enchanting", max_results=5)
article = core.read_wiki("https://minecraft.wiki/w/Diamond_Sword", include_infobox=True)
```

**结果解读**：

1. 优先取 `is_primary: true` 的条目回答用户——四级联判别已保证准确性
2. 多个 `is_primary: true` 时全部列出（互不依赖的独立模组）
3. 无 `is_primary` 时按 `_score` 降序取第一个
4. `source` 含 `|` 的融合条目字段来自多平台，质量更高

**API 选择指南**：

| 场景 | 用哪个 |
|------|--------|
| 用户问"有没有XX模组" | `search_all` |
| 用户问"支持什么版本/加载器" | `fetch_mod_info` |
| 用户问"有什么更新/截图" | `fetch_mod_info` |
| 用户问"依赖什么模组" | `get_mod_dependencies` |
| 用户问原版机制/合成/附魔 | `search_wiki` / `read_wiki` |

> **Token 注意**：`fetch_mod_info` 的 `body` 字段是完整 Markdown 描述，可能很大。搜索结果不含 body。
> `content_type` 可选：`mod` / `item` / `modpack` / `shader` / `resourcepack` / `vanilla` / `entity` / `biome` / `dimension`

## 搜索路由

| Content Type | 搜索平台 | 说明 |
|-------------|---------|------|
| `mod` / `modpack` | MC百科 + Modrinth | 不搜 wiki（无模组数据） |
| `item` | MC百科 + Modrinth + wiki | wiki 有原版物品数据 |
| `shader` / `resourcepack` | Modrinth | 视听内容 Modrinth 独占 |
| `vanilla` / `entity` / `biome` / `dimension` | minecraft.wiki (EN/ZH) | 原版内容仅 wiki 有数据 |

## 关键行为

- **跨语言桥接**：中文关键词自动从 MC百科 提取英文名去 Modrinth 补搜，并行执行
- **本体判别**：`is_primary: true` 标记本体模组（C→B→A→兜底 四级联）
- **字段级融合**：name_zh→MC百科，name_en→Modrinth，downloads→Modrinth，relationships→MC百科
- **WAF 自动回退**：MC百科 被拦截时降级到搜索页数据，不阻断搜索
- **CDN 绕过**：curl_cffi + Chrome124 TLS 指纹绕过 Cloudflare

## 错误处理

所有函数失败时用 `_error` 键（而非 None 或抛异常）。Agent 端统一判断：

```python
def _is_valid(result):
    return result is not None and "_error" not in result
```

| `_error` 值 | 含义 | 对策 |
|-------------|------|------|
| `not_found` | 资源不存在 | 告知用户，建议换关键词 |
| `api_failed` | API 请求失败/超时 | 可重试一次，仍然失败则告知用户 |
| `parse_failed` | 页面解析失败（正常降级） | 搜索页数据已返回，忽略此信号继续使用结果 |
| `rate_limited` | Modrinth API 429 | 等待后重试，或只用其他平台数据 |
| `no_content` | wiki 页面无内容 | 告知用户该页面无有效内容 |

> `parse_failed` 非致命——WAF 回退后搜索页基础数据（名称/URL/描述）仍可用。
> `search_all(fuse=True)` 返回 `{"results": [...]}` 不含 `_error`；各平台错误记录在 `_platform_errors` 中。

## 参考

详细故障排查和错误码参考：`references/troubleshooting.md`、`references/errors.md`
