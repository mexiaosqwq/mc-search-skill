# Result Schema — 返回字段说明

所有搜索函数返回 `list[dict]`。注意区分**搜索结果**（轻量）和**详情结果**（完整元数据）。

---

## 通用字段（所有平台）

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 显示名称 |
| `name_en` | str | 英文名称 |
| `name_zh` | str | 中文名称 |
| `url` | str | 页面链接 |
| `source` | str | 来源平台：`mcmod.cn` / `modrinth` / `minecraft.wiki` / `minecraft.wiki/zh`；融合模式下为 `\|` 分隔的多平台字符串 |
| `source_id` | str | 平台内 ID（如 class ID、slug、pageid） |
| `type` | str | 项目类型：`mod` / `item` / `shader` / `resourcepack` / `block` / `entity` / `mechanic` / `other` |

---

## MC百科 — `search_mcmod` 搜索结果

| 字段 | 说明 |
|------|------|
| `name` / `name_en` / `name_zh` | 模组名称 |
| `url` | `https://www.mcmod.cn/class/{id}.html` |
| `source` | `mcmod.cn` |
| `source_id` | class ID（如 `2655`） |
| `type` | `mod` 或 `item` |
| `description` | 模组描述（已清洗，去除 "介绍"/"概述" 等残留） |
| `status` | 状态（如 `活跃`） |
| `source_type` | `open_source` / `closed_source` |
| `author` | 作者名 |
| `categories` | 分类列表 |
| `tags` | 标签列表 |
| `supported_versions` | 支持的版本列表（MC百科 detail 才有，搜索结果不含） |
| `cover_image` | 封面图 URL |
| `screenshots` | 截图 URL 列表 |
| `relationships.requires` | 前置 Mod 列表（MC百科 detail 才有；无时为 null） |
| `relationships.integrates` | 联动 Mod 列表（MC百科 detail 才有；无时为 null） |
| `has_changelog` | 是否有更新日志布尔值（MC百科 detail 才有） |
| `is_vanilla` | 是否为 MC百科原版内容分类（URL 含 `/class/1.html`） |
| `external_links` | 外部平台链接字典（无时为 null）：`official` / `curseforge` / `modrinth` / `github` / `wiki` / `discord` / `jenkins` / `mcbbs` |
| `content_list` | MC百科资料列表（无时为 null），见下方说明 |

### `content_list` 字段结构

当模组在 MC百科 有资料列表时，返回如下结构：

```json
{
  "content_list": {
    "1": {"label": "物品/方块", "count": 1016, "url": "https://www.mcmod.cn/item/list/2021-1.html"},
    "4": {"label": "生物/实体", "count": 2, "url": "https://www.mcmod.cn/item/list/2021-4.html"},
    "5": {"label": "附魔/魔咒", "count": 2, "url": "https://www.mcmod.cn/item/list/2021-5.html"}
  }
}
```

| type_id | 类型 |
|---------|------|
| `1` | 物品/方块 |
| `4` | 生物/实体 |
| `5` | 附魔/魔咒 |
| `6` | BUFF/DEBUFF |
| `7` | 多方块结构 |
| `8` | 自然生成 |
| `9` | 绑定热键 |
| `10` | 游戏设定 |

> 注：type_id 可能还有其他值，具体以页面实际返回为准。代码会动态提取标题。

---

## `_truncated` 元数据字段（可选）

当返回数据被截断时，`_truncated` 字段描述截断情况。AI Agent 可据此判断是否需要调用 `full` 命令获取完整数据。

### 结构

```json
{
  "_truncated": {
    "{field_name}": {
      "returned": 5,
      "total": 62
    }
  }
}
```

### 可能被截断的字段

| 平台 | 字段 | 默认限制 | 说明 |
|------|------|----------|------|
| MC百科 | `screenshots` | 6 张 | 详情页截图 |
| Modrinth | `body` | 5000 字符 | 项目描述正文 |
| Modrinth | `gallery` | 10 张 | 项目截图 |
| Modrinth | `version_groups` | 5 组 | 版本分组 |
| Modrinth | `changelogs` | 5 条 | 更新日志 |

### 使用示例

**普通搜索（有截断）**：
```json
{
  "name": "sodium",
  "version_groups": [["0.6.0", {...}, ...]],
  "_truncated": {
    "version_groups": {"returned": 5, "total": 62},
    "changelogs": {"returned": 5, "total": 144}
  }
}
```

**`full` 命令（无截断）**：
```json
{
  "name": "sodium",
  "version_groups": [["0.6.0", {...}], ["0.5.0", {...}], ...]
  // Modrinth 数据无 _truncated 字段，完整返回
  // MC百科 screenshots 仍有默认限制（6张）
}
```

> **注意**：`full` 命令仅 Modrinth 数据无截断，MC百科截图仍有默认限制。

### AI Agent 决策逻辑

```
if result._truncated exists:
    # 数据不完整，告知用户或调用 full 命令
    truncated_fields = list(result._truncated.keys())
    # 可提示：部分数据已截断，如需完整信息请使用 full 命令
```

---

## MC百科 — item 搜索结果（`_parse_mcmod_item_result`）

| 字段 | 说明 |
|------|------|
| `name` / `name_en` / `name_zh` | 物品名称 |
| `url` | MC百科物品页面 URL |
| `source` | `mcmod.cn` |
| `source_id` | item ID |
| `type` | `item` |
| `max_durability` | 最大耐久值（无则为 null） |
| `max_stack` | 最大堆叠数（无则为 null） |
| `category` | 资料分类 |
| `source_mod_name` | 所属模组名称 |
| `source_mod_url` | 所属模组页面链接 |
| `description` | 物品描述 |
| `has_recipe` | 是否有合成表（通过 `info -r` 查看） |

---

## MC百科 — 作者搜索 `search_mcmod_author`

与模组搜索返回字段相同，包含完整详情页字段：

| 字段 | 说明 |
|------|------|
| `name` / `name_en` / `name_zh` | 模组名称 |
| `url` | MC百科页面 URL |
| `source` | `mcmod.cn` |
| `source_id` | class ID |
| `type` | `mod` |
| `description` | 模组描述 |
| `status` | 状态 |
| `source_type` | `open_source` / `closed_source` |
| `author` | 作者名（与搜索参数一致） |
| `categories` | 分类列表 |
| `tags` | 标签列表 |
| `supported_versions` | 支持的版本列表 |
| `cover_image` | 封面图 URL |
| `screenshots` | 截图 URL 列表 |
| `relationships` | 前置/联动模组 |
| `has_changelog` | 是否有更新日志 |
| `is_vanilla` | 是否为原版内容 |

---

## Modrinth — `search_modrinth` 搜索结果（轻量）

`search_modrinth` 仅返回以下 8 个字段：

| 字段 | 说明 |
|------|------|
| `name` / `name_en` | 项目名称 |
| `name_zh` | 空字符串 |
| `url` | `https://modrinth.com/mod/{slug}` |
| `source` | `modrinth` |
| `source_id` | slug |
| `type` | `mod` / `shader` / `resourcepack` |
| `snippet` | 简短描述（来自搜索摘要，非完整描述） |

---

## Modrinth — `get_mod_info` 详情（完整元数据）

通过 `get_mod_info(mod_id)` 或 `info -m`（即 `info --modrinth`）获取：

| 字段 | 说明 |
|------|------|
| `name` / `name_en` | 项目名称 |
| `name_zh` | 空字符串 |
| `slug` | URL slug |
| `id` | project_id |
| `url` | `https://modrinth.com/mod/{slug}` |
| `source` | `modrinth` |
| `source_id` | slug |
| `description` | 项目完整描述（来自详情 API，非搜索摘要） |
| `body` | 完整 Markdown 描述（**已截断至 5000 字符**，详情 API 始终截断） |
| `type` | `mod` / `shader` / `resourcepack` |
| `author` | 作者用户名 |
| `license` | 许可证 ID |
| `categories` | 分类列表 |
| `client_side` | 客户端支持：`required` / `optional` / `unsupported` |
| `server_side` | 服务端支持：`required` / `optional` / `unsupported` |
| `source_url` | GitHub 仓库链接（可无） |
| `issues_url` | Issues 链接（可无） |
| `discord_url` | Discord 链接（可无） |
| `updated` | ISO 更新时间 |
| `published` | 发布时间 |
| `followers` | 关注数 |
| `icon_url` | 图标 URL |
| `gallery` | 截图 URL 列表（**最多 10 张**） |
| `latest_version` | 最新版本号 |
| `game_versions` | 最新版本支持的游戏版本列表 |
| `loaders` | 最新版本支持的加载器（fabric / forge / neoforge / quilt） |
| `downloads` | 总下载量 |
| `version_groups` | 版本分组列表（**最多 5 组**，已聚合去重） |
| `changelogs` | 最近更新日志（**最多 5 条**，--json 专用） |

---

## 融合结果 — `search_all(..., fuse=True)` 或 `--json` 模式

当 `fuse=True` 或使用 `--json` 时，`search_all` 返回跨平台融合后的列表（按 content_type 调整平台优先级）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | str | 来源平台，多平台时为 `\|` 分隔（如 `mcmod.cn\|modrinth`） |
| `_sources` | list[str] | 融合来源平台列表（**仅融合模式下存在**） |
| 其余字段 | | 来自优先级最高平台的结果 |

**融合示例**：
```json
{
  "name": "钠",
  "name_en": "Sodium",
  "url": "https://www.mcmod.cn/class/2655.html",
  "source": "mcmod.cn|modrinth",
  "_sources": ["mcmod.cn", "modrinth"],
  "description": "现代渲染引擎和客户端优化模组...",
  "type": "mod"
}
```

**平台优先级**：
- entity/biome/block/mechanic/dimension → `minecraft.wiki` > `minecraft.wiki/zh` > `mcmod.cn` > `modrinth`
- mod/item → `mcmod.cn` > `modrinth` > `minecraft.wiki` > `minecraft.wiki/zh`

---

## minecraft.wiki — `search_wiki` 搜索结果

| 字段 | 说明 |
|------|------|
| `name` / `name_en` | 页面标题 |
| `name_zh` | 空字符串 |
| `url` | 页面 URL |
| `source` | `minecraft.wiki` |
| `source_id` | pageid |
| `type` | `block` / `item` / `entity` / `mechanic` / `other`（从 URL 和名称推断） |
| `sections` | 章节标题列表（直接访问文章时从 h3 提取；MediaWiki API 降级路径返回空列表） |

---

## minecraft.wiki — `read_wiki` 读取正文

| 字段 | 说明 |
|------|------|
| `name` | 页面标题 |
| `url` | 页面 URL |
| `source` | `minecraft.wiki` |
| `content` | 正文段落列表（兼容旧接口；过滤 infobox、JSON-LD、CSS 片段后的纯文本） |
| `_sections` | 层级 section 列表（新版结构）：`{"heading", "parent", "content"}`，parent 为 null 表示顶级 h2，子节点为 h3/h4 |
