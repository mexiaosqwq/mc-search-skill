# mc-search

AI Agent 优先的 Minecraft 内容聚合搜索工具。并行搜索多平台，返回融合后的统一结果。

## Language

**内容类型（Content Type）**:
搜索目标的内容分类。可选：`mod` / `item` / `modpack` / `shader` / `resourcepack` / `vanilla` / `entity` / `biome` / `dimension`。

**平台路由（Platform Routing）**:
每种 Content Type 只在匹配的平台上搜索：
- 模组（mod/modpack）→ MC百科 + Modrinth，不搜 wiki（无模组数据，会引入噪音）
- 物品（item）→ MC百科 + Modrinth + wiki 补充（wiki 有原版物品数据可参考）
- 视听内容（shader/resourcepack）→ Modrinth 独占
- 原版知识（vanilla/entity/biome/dimension）→ wiki 为主

_Avoid_: 所有类型全平台搜索，空耗网络请求。

**本体判别（Primary Detection）**:
融合结果自动标记 `is_primary: true`。C→B→A→兜底 四级联判断：
1. 前置关系（C）：被其他条目依赖且自身非自引用 → 本体
2. 精确名匹配 + 最高下载量（B）：名称与关键词完全一致中下载最高
3. 最高下载量（A）：下载最多的标记为本体
4. 最高分兜底（D）：前三关无人命中时，最高相关性分标记为本体

每融合组独立判断，可能有多条 `is_primary: true`（互不依赖的独立模组）。
跨平台去重合并。相同内容在不同平台的搜索结果合并为一条记录，标注 `_sources` 列出所有来源平台。

融合时按**字段级权威源**选取数据，不按单一平台优先：

| 字段 | 第一源 | 第二源 | 原因 |
|------|--------|--------|------|
| `name_zh` | MC百科 | — | 社区共识译名 |
| `name_en` | Modrinth | MC百科 | 官方 ID |
| `description` | Modrinth | MC百科 | API 稳定优先 |
| `dependencies` | Modrinth | — | 结构化依赖数据 |
| `relationships`（联动/前置） | MC百科 | — | 唯一有此数据的平台 |
| `downloads` / `followers` | Modrinth | — | 官方分发站计数 |
| `snippet` / `icon_url` / `changelogs` | Modrinth | — | 搜索摘要+图标+更新日志 |
| `supported_versions` / `author` | Modrinth | — | 版本支持+作者名 |
| `_sources` | 全部保留 | — | 不去掉任一来源 |

**平台优先级（Platform Priority）**:
去重时决定同名结果保留哪一个的权重。mod/item 类型下 mcmod.cn > modrinth > wiki；其余内容类型各平台平等。

**跨语言桥接（Cross-Language Bridge）**:
中文关键词搜索时，从 MC百科 结果提取 `name_en` 去 Modrinth 并行补搜。补搜结果去重后合并进融合管线。Agent 无感知。

**CDN 绕过（CDN Bypass）**:
MC百科 和 minecraft.wiki 使用 `curl_cffi` + Chrome124 TLS 指纹绕过 Cloudflare 等 CDN 防护。各子域名独立绕过状态。

**WAF 回退（WAF Fallback）**:
MC百科 详情页被防火墙拦截时，自动用搜索页已有数据构建最小结果，不阻断搜索流程。

## Relationships

- 一次 **Search** 产生多个平台的 **Hit**
- 融合（**Fuse**）将跨平台同类 **Hit** 合并为一条 **Result**
- **Hit** 属于一个 **Content Type**，决定搜索路由到哪些平台
- 每个 **Hit** 同时持有 `name_zh`（中文名）和 `name_en`（英文名），其中至少一个非空

## Example dialogue

> **Dev:** "搜索 `sodium` 时，MC百科 返回了 钠(Sodium) 的模组页，Modrinth 也返回了 Sodium，融合后是一条还是两条？"
> **Domain expert:** "一条。MC百科 现在从 `<title>` 稳定提取 `name_en=Sodium`，Modrinth 有 `name=Sodium`。多候选 key 匹配发现 `sodium` 这个 key 重叠，自动合并。MC百科 提供中文名 `钠`，Modrinth 提供英文名 `Sodium`。融合后 `_sources` 为 `['mcmod.cn', 'modrinth']`。"
> **Dev:** "那中文关键词 `机械动力` 呢？Modrinth 不支持中文搜索啊"
> **Domain expert:** "跨语言桥接自动处理。MC百科 搜到 `name_en=Create`，用 `Create` 去 Modrinth 并行补搜。补搜结果与 MC百科 结果在融合阶段自动合并为一条。`_sources` 最终为 `['mcmod.cn', 'modrinth']`，Modrinth 侧 downloads/dependencies/body 都在。Agent 看到的结果和英文搜索一样完整。"
> **Dev:** "冷门模组呢？比如 MC百科 有页面但没提取到英文名"
> **Domain expert:** "MC百科 没提取到英文名时桥接放弃，但不影响 MC百科 侧结果正常返回。"

## Flagged ambiguities

### 跨平台名称对齐（已修复）

`_entry_name_keys` 多候选 key 匹配：每个结果吐出所有可用名称，任一 key 命中即合并。MC百科 英文名从 `<title>` 稳定提取（98%+ 覆盖）。

### wiki.gg 新布局适配（已修复）

2024-2025 wiki.gg 迁移后，中文 wiki 的 infobox 从 `<table>` 改为 `<div class="infobox-rows">` 布局。新增 div 格式解析，4/5 中文页面类型 infobox 已恢复正常。首段 infobox rail 数据泄漏已切除。

### 描述截断与截图禁用（已修复）

描述在 500 字符处截断，`_truncated` 元信息通知 Agent 原始长度。截图/画廊默认禁用以节省 token，通过 `_truncated` 告诉 Agent 存在但未返回。

### 字段级权威源（已代码化）

`_merge_entry_fields()` 实现按字段逐源选取：name_zh → MC百科，name_en → Modrinth → MC百科，description → Modrinth → MC百科，downloads/followers → Modrinth，relationships → MC百科 唯一。

### MC百科 联动解析信号（已代码化）

`_extract_mcmod_relationships()` 返回 `_parse_attempted` 标志。HTML 中存在关系标签但未提取到数据时返回 `{"_error": "parse_failed"}`，确实无关系标签时返回 `None`。联动列表按 `id` 去重。

### 跨语言桥接（已代码化）

中文关键词从 MC百科 提取 `name_en` 去 Modrinth 并行补搜，补搜结果与原始结果融合。单向（中文→英文），英文关键词方向无需桥接。

### 本体判别（已代码化）

`_mark_primary()` C→B→A→兜底 四级联：前置关系链 → 精确名+下载 → 纯下载 → 最高分兜底。结果字段 `is_primary: true`，Agent 可一眼识别。

### 已知限制

- MC百科 CDN 盾偶发拦截（yxd_token + CC check），已有自动绕过，重试后通常恢复正常
