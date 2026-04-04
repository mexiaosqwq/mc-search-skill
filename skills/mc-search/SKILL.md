---
name: mc-search
version: "0.4.0"
description: "Minecraft 聚合搜索工具。触发：用户询问模组信息、物品资料、mod 依赖、版本对比、原版游戏内容、作者作品。格式：`mc-search --json <子命令> <参数>`，如 `mc-search --json search 钠`。"
license: MIT
context: open
user-invocable: true
allowed-tools: [Bash, Read, Glob, Grep]
---

# mc-search

Minecraft 内容聚合搜索。四平台并行：MC百科、Modrinth、minecraft.wiki（英文/中文）。

> **格式**：`mc-search --json <子命令> <参数>`（`--json` 放最前）
> - 搜索：`mc-search --json search <关键词>`
> - 详情：`mc-search --json full <模组名>`
> - Wiki：`mc-search --json wiki <关键词>`

## 执行流程

```
用户提问 → 分析意图选命令 → Bash执行mc-search --json → 解析JSON呈现
```

> **重要**：所有命令都应加 `--json` 获取结构化输出，便于解析。

## 决策树

```
用户询问模组/游戏内容
├─ 知道模组名，要完整信息 ──────→ full <模组名>
├─ 只有个大概关键词 ──────────→ search <关键词>
├─ 想查原版游戏内容 ──────────→ wiki <关键词>
├─ 想查作者作品
│   ├─ MC百科作者 ────────────→ search --author <作者>
│   └─ Modrinth作者 ──────────→ author <用户名>
├─ 想查依赖
│   └─ 依赖树 ────────────────→ dep <slug>
├─ 已有页面链接
│   ├─ MC百科 class URL ─────→ info <URL>
│   ├─ Modrinth URL ─────────→ full <URL>  或 dep <slug>
│   └─ wiki URL ─────────────→ read <URL>
└─ 想直接读 wiki 正文 ──────────→ read <URL>
```

## 命令速查

| 意图 | 命令 | 说明 |
|------|------|------|
| **完整信息** | `mc-search --json full <模组名>` | **首选**：一次返回详情+依赖+版本 |
| 模组搜索 | `mc-search --json search <关键词>` | 四平台并行，每平台默认取前15个结果，智能排序 |
| 物品搜索 | `mc-search --json search <关键词> --type item` | 搜物品/方块 |
| 实体搜索 | `mc-search --json search <关键词> --type entity` | 搜实体/biome/dimension |
| 原版内容 | `mc-search --json wiki <关键词> -n <数量>` | minecraft.wiki，`-n` 限制结果数 |
| 读取wiki | `mc-search --json wiki <关键词> -r` | 搜索+读取正文 |
| 依赖树 | `mc-search --json dep <mod_slug>` | Modrinth 依赖 |
| MC百科作者 | `mc-search --json search --author <作者>` | 精确匹配作者名 |
| Modrinth作者 | `mc-search --json author <用户名> -n <数量>` | Modrinth 用户作品，`-n` 限制结果数 |

## full 命令详解

`full` 是最强大的命令，一次调用即可获取模组的全部信息：

```bash
mc-search --json full <模组名或URL>
```

**返回字段**：
| 字段 | 说明 |
|------|------|
| `mcmod` | MC百科详情（描述、版本、作者、截图、标签、状态等） |
| `modrinth` | Modrinth 详情（下载量、版本历史、更新日志、运行环境等） |
| `dependencies` | 依赖树（必需/可选依赖列表） |
| `content_list` | MC百科资料列表（物品/方块、生物/实体、附魔等） |
| `search_results` | 搜索结果摘要（用于确认匹配准确性） |
| `_mr_tentative` | Modrinth 模糊匹配提示（当精确匹配失败时） |

**使用场景**：
- 用户想深入了解某个模组
- 需要查看依赖关系
- 需要版本历史或更新日志
- 需要下载链接和外部链接

**示例**：
```bash
mc-search --json full 钠
mc-search --json full sodium
mc-search --json full https://www.mcmod.cn/class/2785.html
mc-search --json full https://modrinth.com/mod/sodium
```

## 返回字段要点

**search 返回**（主要字段，完整见 [result-schema.md](references/result-schema.md)）：
- **嵌套结构**: `{"results": [...], "platform_stats": {...}}` — 结果列表和平台统计
- `results[].name`, `results[].name_zh`, `results[].name_en` — 名称
- `results[].url`, `results[].source` — 链接和来源平台
- `results[].description` / `results[].snippet` — 描述摘要
- `results[]._truncated` — **数据截断元信息**（如有则表示数据不完整）

**排序规则**（智能相关性排序）：
1. **精确匹配优先**：名称完全等于搜索词 → 最高分
2. **短名称加权**：精确匹配时，名称越短越精确（"Spawn" > "Spawn Mod"）
3. **前缀匹配次之**：名称以搜索词开头
4. **多平台命中加权**：同时出现在多个平台的结果更可信
5. **平台权威度**：同分时 MC百科 > Modrinth > Wiki

**full 返回**：
- `mcmod` — MC百科详情（描述、版本、作者、截图等）
- `modrinth` — Modrinth 详情（下载量、版本历史、更新日志等，**完整数据无截断**）
- `dependencies` — 依赖树
- `content_list` — MC百科资料列表（物品/方块、生物/实体、附魔等，仅当有数据时返回）
- `search_results` — 搜索结果摘要
- `_mr_tentative` — Modrinth 模糊匹配结果（如有）

## 版本优先级

当 MC百科和 Modrinth 版本不一致时，**以 Modrinth 为准**（官方发布平台，更新及时）。

**示例场景**：
- MC百科显示最新版本 `0.5.0`，Modrinth 显示 `0.6.0` → 使用 Modrinth 的 `0.6.0`
- MC百科版本信息未更新时，Modrinth 提供最新发布版本

## 全局选项

放在子命令前：`--json`（推荐）、`--cache`、`--no-mcmod`、`--no-mr`、`--no-wiki`、`--no-wiki-zh`

## 初始化

```bash
pip install -e skills/mc-search
```

## 详细文档

- [result-schema.md](references/result-schema.md) — 返回字段完整定义
- [troubleshooting.md](references/troubleshooting.md) — 错误处理
