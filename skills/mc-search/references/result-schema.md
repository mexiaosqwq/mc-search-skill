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
| `external_links` | 外部平台链接字典（无时为 null）：`curseforge` / `modrinth` / `github` / `discord` |

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

## MC百科 — `search_mcmod_author` 作者搜索结果

与 `search_mcmod`（模组）返回字段相同，包含完整详情页字段：name / name_en / name_zh / url / source / source_id / type / description / status / source_type / author / categories / tags / supported_versions / cover_image / screenshots / relationships / has_changelog / is_vanilla。

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
| `_sources` | list[str] | 融合来源平台列表（所有来源，**始终存在**） |
| 其余字段 | | 来自优先级最高平台的结果 |

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
