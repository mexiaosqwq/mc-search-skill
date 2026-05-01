---
name: mc-search
version: "5.1.0"
description: "Minecraft 内容搜索 - 模组/整合包/光影/材质包/wiki 四平台聚合"
license: MIT
context: open
user-invocable: true
allowed-tools: [Bash]
triggers:
  - "模组"
  - "整合包"
  - "光影包"
  - "材质包"
  - "资源包"
  - "Minecraft 模组"
  - "MC 模组"
  - "原版 wiki"
  - "Minecraft Wiki"
  - "MC百科"
  - "Modrinth"
  - "我的世界"
  - "我的世界模组"
  - "mc模组"
  - "minecraft 攻略"
---

# mc-search

Minecraft 内容搜索 Skill。Agent 通过 Python API 直接调用 `scripts.core`，不经过 CLI。

**使用方式**：

```bash
python -c "
import sys
sys.path.insert(0, 'skills/mc-search')
from scripts import core
import json

result = core.search_all('机械动力', max_per_source=5, fuse=True)
print(json.dumps(result, ensure_ascii=False))
"
```

用 `set_platform_enabled` 控制平台，用 `set_cache(True)` 启用缓存（TTL 1h）。

---

## API 速查

### 搜索：`search_all()`

```python
core.search_all(keyword, max_per_source=5, content_type="mod", fuse=True)
# → {"results": [{hit}], "platform_stats": {...}}

core.search_all(keyword, max_per_source=5, content_type="vanilla", fuse=True)
# → 仅 wiki 平台（原版内容）

core.search_all(keyword, max_per_source=5, content_type="shader", fuse=True)
# → 仅 Modrinth（光影/材质包）
```

`content_type`: `mod`(默认) / `item` / `modpack` / `shader` / `resourcepack` / `vanilla`

每个 hit 关键字段：`name`, `name_zh`, `name_en`, `url`, `source`, `_score`(0-120), `_sources`([平台]), `snippet`/`description`

### 详情：`fetch_mod_info()` / `get_mod_dependencies()`

```python
core.fetch_mod_info("sodium")  # slug 或 project_id
# → {name, description, body(Markdown), downloads, author, supported_versions, changelogs...}

core.get_mod_dependencies("sodium")
# → {"deps": {slug: {name, slug, client_side, server_side, url}}}
```

### MC百科：`search_mcmod()`

```python
core.search_mcmod("机械动力", max_results=3, content_type="mod")
# → [{name_zh, name_en, description, author, supported_versions, relationships...}]
```

MC百科 详情页可能被 WAF 拦截 → 自动回退到搜索页数据。解析依赖 HTML 结构，不稳定。

### Wiki：`search_wiki()` / `search_wiki_zh()` / `read_wiki()`

```python
core.search_wiki("enchanting", max_results=5)       # 英文
core.search_wiki_zh("附魔", max_results=5)           # 中文
# → [{name, url, snippet, sections, type: "wiki"}]

core.read_wiki("https://minecraft.wiki/w/Enchanting", max_paragraphs=-1)
# → {name, url, content([段落]), infobox(结构化数据), main_image}
```

Agent 提示：`read_wiki` 的 `content` 是段落列表，按需展示。`infobox` 含稀有度/耐久/攻击等结构化属性。

### 作者搜索

```python
core.search_mcmod_author("Simibubi", max_mods=10)
core.search_modrinth_author("jellysquid3", max_results=10)
```

### 平台控制

```python
core.set_platform_enabled(mcmod=True, modrinth=True, wiki=True, wiki_zh=True)
core.set_cache(True)  # TTL 1h, ~/.cache/mc-search/
```

---

## 返回格式

所有函数返回 Python dict/list。失败调 `search_all` 等可能抛出 `SearchError`。

| 函数 | 返回类型 | 说明 |
|------|---------|------|
| `search_all(fuse=True)` | `{results: [{hit}], platform_stats: {...}}` | 融合+去重+评分 |
| `search_mcmod()` | `[{hit}]` | MC百科 搜索结果列表 |
| `fetch_mod_info()` | `{dict}` 或 `None` | Modrinth 模组详情 |
| `get_mod_dependencies()` | `{deps: {...}}` | 依赖树 |
| `search_wiki()` | `[{hit}]` | wiki 搜索结果 |
| `read_wiki()` | `{name, content, infobox...}` | wiki 文章正文 |

hit 通用字段：`name`, `name_zh`, `name_en`, `url`, `source`, `_score`, `_sources`, `snippet`。平台特有字段见 [result-schema.md](references/result-schema.md)。

---

## 调用策略

| 用户意图 | API 调用 |
|---------|---------|
| 模糊搜索模组/整合包/光影 | `search_all(keyword, content_type="mod"/"shader"/etc, fuse=True)` |
| 看某个模组的详细信息 | `fetch_mod_info("slug")` |
| 查中文模组信息 | `search_mcmod("中文名")` |
| 查某个模组的依赖 | `get_mod_dependencies("slug")` |
| 查原版内容 | `search_wiki("关键词")` 或 `read_wiki(url)` |
| 搜索英文模组 | `set_platform_enabled(mcmod=False)` + `search_all(keyword, fuse=True)` |

## 平台选择

- 中文模组 → **MC百科**（中文描述+联动关系）
- 英文模组/光影/材质包 → **Modrinth**（API 稳定，依赖准确）
- 原版内容 → **minecraft.wiki**（中英文自动选择）
- 英文搜索加 `set_platform_enabled(mcmod=False)` 避免中文噪音

## 错误处理

| 现象 | 对策 |
|------|------|
| 搜索无结果 | 换更短关键词，或限定单平台 `set_platform_enabled(mcmod=False, ...)` |
| MC百科 WAF 拦截 | 自动降级到搜索页数据，无需干预 |
| Modrinth 超时 | 只影响 Modrinth 结果，MC百科/wiki 照常返回 |
| 结果太多 | `max_per_source=3` 限制数量 |

详见 [troubleshooting.md](references/troubleshooting.md) 和 [errors.md](references/errors.md)。
