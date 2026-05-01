# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供本代码库的工作指导。

## 项目定位

**mc-search** 是 AI Agent 优先的 Minecraft 内容搜索 Skill。AI Agent 通过 Python API 直接调用，不依赖 CLI。

并行搜索四个平台：
- **MC 百科** (mcmod.cn) — 中文模组/物品/整合包（HTML 解析，脆弱）
- **Modrinth** — 英文模组/光影/材质包/整合包（REST API，稳定）
- **minecraft.wiki** — 原版游戏 wiki 英文/中文（MediaWiki API）

## 架构

```
Agent 调用 → core.py API → 并行平台搜索 → 结果融合(_fuse_results) → 统一 JSON
```

两个文件：
- `scripts/core.py` — 全部搜索逻辑（API 调用、HTML 解析、结果融合、缓存）
- `scripts/cli.py` — argparse 薄壳（Agent 不使用，仅人类调试用）

## Agent 使用方式

Agent 应直接 `import` core 模块，不通过 CLI。

### 搜索：`search_all()`

```python
from scripts import core

# 多平台搜索（推荐）
result = core.search_all("机械动力", max_per_source=5, content_type="mod", fuse=True)
# → {"results": [...], "platform_stats": {"mcmod.cn": {...}, "modrinth": {...}, ...}}

# 单平台搜索
core.set_platform_enabled(mcmod=False, modrinth=True, wiki=False, wiki_zh=False)
result = core.search_all("sodium", max_per_source=5, content_type="mod", fuse=True)
```

`content_type` 可选：`mod` / `item` / `modpack` / `shader` / `resourcepack` / `vanilla`（原版 wiki）。

返回的每个 hit 关键字段：`name`、`name_zh`、`name_en`、`url`、`source`、`_score`（相关性 0-120）、`_sources`（来源平台列表）、`snippet`/`description`。

### 详情：`fetch_mod_info()` / `get_mod_dependencies()`

```python
# Modrinth 模组详情
info = core.fetch_mod_info("sodium")  # slug 或 project_id
# → dict 含 name, description, body(Markdown), downloads, author, supported_versions, changelogs...

# 依赖树
deps = core.get_mod_dependencies("sodium")
# → {"deps": {slug: {name, slug, client_side, server_side, url}}}
```

### MC百科：`search_mcmod()` / `parse_mcmod_result()`

```python
hits = core.search_mcmod("机械动力", max_results=3, content_type="mod")
# → list[dict]，每项含 name_zh, name_en, description, author, supported_versions, relationships...
```

MC百科 详情页可能被 WAF 拦截，此时自动回退到搜索页数据构建最小结果。

### Wiki：`search_wiki()` / `search_wiki_zh()` / `read_wiki()`

```python
pages = core.search_wiki("enchanting", max_results=5)
# → list[dict]，每项含 name, url, snippet, sections

article = core.read_wiki("https://minecraft.wiki/w/Enchanting", max_paragraphs=-1)
# → dict 含 name, url, content([段落]), infobox(结构化数据), main_image
```

### 作者搜索：`search_mcmod_author()` / `search_modrinth_author()`

```python
mcmod_works = core.search_mcmod_author("Simibubi", max_mods=10)
mr_works = core.search_modrinth_author("jellysquid3", max_results=10)
```

### 缓存

```python
core.set_cache(True)  # 启用，TTL 1 小时
# 缓存位置：~/.cache/mc-search/
# 详情页 HTML 缓存可显著加速 MC百科 二次访问
```

### 平台开关

```python
core.set_platform_enabled(mcmod=True, modrinth=True, wiki=True, wiki_zh=True)
# Agent 不应裸调 set_platform_enabled，应通过 search_all 的 content_type 自动路由
```

## JSON 返回格式（统一信封）

所有结果均为 `{"results": ..., ...}` 结构。错误为 `{"error": "CODE", "message": "..."}`。

| 函数 | `results` 类型 | 附加字段 |
|------|---------------|---------|
| `search_all(fuse=True)` | `[{hit}]` | `platform_stats` |
| `fetch_mod_info()` | `{dict}` | — |
| `get_mod_dependencies()` | `{deps: {...}}` | — |
| `search_wiki()` | `[{hit}]` | — |
| `read_wiki()` | `{dict}` | — |
| `search_mcmod()` | `[{hit}]` | — |

## 重要实现细节

### 网络层
- MC百科 + minecraft.wiki：`curl_cffi` + Chrome124 TLS 指纹绕过 CDN/反爬
- Modrinth API：标准 `urllib.request` HTTP
- MC百科 各子域名 (www + search) 需独立 CDN 绕过
- WAF 检测：短页面 (<1000B) 含 AIWAFCDN/防火墙拦截 等签名视为被阻断

### MC百科 解析
- 纯正则 + 字符串操作，无 BeautifulSoup
- HTML 结构可能变化，解析较脆弱
- 详情页被 WAF 拦截时自动回退到搜索页数据（`_build_mcmod_fallback_result`）
- 物品页 (`/item/`) 与模组页 (`/class/`) 结构完全不同，分别解析

### 结果融合（`_fuse_results`）
1. 评分：精确匹配 100+ → 前缀 60+ → 包含 30+ → snippet 加分 +5 → 多平台 +10
2. 去重：同名按 score 保留最高分
3. 排序：分数 DESC

### 缓存
- 装饰器 `@_cached(lambda params: (cache_type, cache_key))` 管理所有缓存
- MC百科 详情页 HTML 额外缓存（最贵请求，绕过 CDN 前先查）
- 缓存 key 包含完整参数，修改任何参数自动分离缓存

## 性能注意事项

- `search_modrinth()` 内部对每个搜索结果并行获取详情（`_parallel_fetch_with_fallback`，最多 4 workers）
- `search_all()` 并行提交 4 平台任务
- Modrinth API 速率限制：360 请求/小时
- MC百科 无速率限制但 CDN 可能限流

## 测试（Python API 方式）

修改代码后，在 Python 中验证：

```python
import scripts.core as core

# 搜索
r = core.search_all("机械动力", max_per_source=1, content_type="mod", fuse=True)
assert len(r["results"]) > 0

# 详情
info = core.fetch_mod_info("sodium")
assert info and info["name"] == "Sodium"

# Wiki
pages = core.search_wiki("enchanting", max_results=1)
assert len(pages) > 0

# 缓存
core.set_cache(True)
r2 = core.search_all("sodium", max_per_source=1, fuse=True)
assert len(r2["results"]) > 0
```

## 依赖

- Python 3.8+
- `curl_cffi>=0.15.0`（MC百科 + wiki 必需）
- 其余标准库

## 修改准则

- **不改 CLI**：Agent 不经过 CLI，功能迭代优先考虑 core.py API
- **复杂任务先规划**：走 `workflow-execute-plans`，分批执行 + 验证 + 暂停反馈
- **保持 AI 优先**：所有设计决策以 AI Agent 调用体验为第一位
