---
name: mcmod-info
description: "Minecraft 模组 + 游戏内容信息查询工具。供 AI Agent 在对话中调用，同时搜索 MC百科（中文模组/物品）、Modrinth（英文 mod/依赖/版本）、minecraft.wiki（原版游戏内容）。触发场景：用户询问模组信息、物品资料、mod 依赖、版本对比、原版游戏内容、作者作品等。"
license: MIT
context: open
user-invocable: true
---

# mcmod-info

AI Agent 专用工具，用于 Minecraft 模组和游戏内容信息查询。

## 触发判断

**当用户询问以下内容时，应调用此工具：**

| 用户意图 | 示例问法 |
|----------|----------|
| 搜索模组 | "帮我搜一下钠 mod"、"Sodium 是什么"、"查一下这个模组" |
| 搜索物品/方块 | "钻石剑怎么合成"、"有哪些附魔"、"这个东西的耐久" |
| 查看 mod 详情 | "这个 mod 的作者是谁"、"支持哪些版本" |
| 查看依赖关系 | "Sodium 需要什么前置"、"这个 mod 依赖哪些" |
| 版本更新检查 | "有新版本吗"、"当前版本是不是最新的" |
| 查作者作品 | "这个作者还做过什么"、"xx 的其他作品" |
| 原版游戏内容 | "附魔台怎么用"、"凋零怎么召唤" |

**当不确定时**：直接搜索，比猜测更准确。

---

## 工具调用

通过 `Bash` 工具执行 `mcmod-search` 命令。

### 通用格式

```bash
mcmod-search <command> [options]
```

### Agent 首选用法

**始终使用 `--json`** 获取结构化输出，便于解析：

```bash
mcmod-search --json search <关键词>
mcmod-search --json info <模组名>
mcmod-search --json dep <mod_slug>
```

> 注意：全局选项（`--json`、`--cache`、平台开关）必须放在子命令 **之前**。

---

## 决策树

```
用户询问模组/游戏内容
├── 不知道具体哪个平台 → search（自动四平台搜索）
├── 知道是中文内容/物品 → search --type item
├── 想一键获取完整信息 → full（推荐，一次=search+info+dep+update-check）
├── 想看详细信息/依赖/版本 → info / dep / update-check
├── 想查 Modrinth（英文） → mr / dep / update-check
├── 想查原版游戏内容 → wiki / read
├── 想查作者作品
│   ├── MC百科（中文）→ search --author
│   └── Modrinth（英文）→ author
└── 想检查版本更新 → update-check --installed <版本>
```

---

## 命令参考

### 1. search — 四平台并行搜索

**使用场景**：用户询问"帮我搜一下 xxx"，不知道具体要哪个平台。

```bash
mcmod-search search <关键词> [options]
```

| 选项 | 说明 |
|------|------|
| `--type item` | 搜索物品/方块（MC百科），默认搜索模组 |
| `--type mod` | 搜索模组（默认） |
| `--type entity` | 融合时 wiki 权威结果优先（biome/dimension 同） |
| `--type biome` | 融合时 wiki 权威结果优先 |
| `--type dimension` | 融合时 wiki 权威结果优先 |
| `--author <作者名>` | MC百科作者搜索（作者名需精确匹配） |
| `--fuse` | 融合四平台结果去重（`--json` 时自动启用） |
| `-n <数量>` | 每平台最多结果（默认3） |
| `-t <秒数>` | 超时秒数（默认12） |
| `--json` | JSON 输出（Agent 解析首选），`--json` 时自动融合 |

**示例**：
```bash
mcmod-search --json search 钠
mcmod-search --json search 钻石剑 --type item
mcmod-search --json search --author Notch
```

---

### 2. mr — Modrinth 单平台搜索

**使用场景**：明确要查英文 mod/光影包/材质包。

```bash
mcmod-search mr <关键词> [options]
```

| 选项 | 说明 |
|------|------|
| `-n <数量>` | 最多结果（默认5） |
| `-t mod` | 项目类型：mod / shader / resourcepack（默认 mod） |
| `--json` | JSON 输出 |

**示例**：
```bash
mcmod-search --json mr sodium
mcmod-search --json mr shaders -t shader
```

---

### 3. info — MC百科模组/物品详情

**使用场景**：用户选中了一个模组，想看详细信息。

```bash
mcmod-search info <模组名或URL或ID> [options]
```

| 选项 | 说明 |
|------|------|
| `-T` | 仅名称/别名 |
| `-a` | 仅作者 |
| `-d` | 仅前置/联动模组 |
| `-v` | 仅支持版本 |
| `-g` | 仅截图/封面 |
| `-c` | 仅分类/标签 |
| `-s` | 仅来源链接 |
| `-S` | 仅状态/开源属性 |
| `-m` | 同时查询 Modrinth |
| `-r` | 显示物品/方块合成表（仅 item 类型有效） |
| `--json` | JSON 输出（全字段） |

**参数格式**（`info` 接受三种输入）：
- 模组名称：`mcmod-search info 钠`
- MC百科 URL：`mcmod-search info https://www.mcmod.cn/class/23352.html`
- 纯数字 ID：`mcmod-search info 23352`

> **不支持 Modrinth URL**，如需查询 Modrinth 信息请使用 `full` 命令。

**示例**：
```bash
mcmod-search --json info 钠
mcmod-search --json info Sodium -m
mcmod-search --json info https://www.mcmod.cn/class/23352.html -d -v
```

---

### 4. full — 一键获取完整信息（推荐）

**使用场景**：需要模组的全部信息（MC百科 + Modrinth + 依赖 + 版本），只需**一次调用**。

```bash
mcmod-search full <模组名或URL或slug> [options]
```

| 选项 | 说明 |
|------|------|
| `--installed <版本>` | 当前安装版本，用于判断是否有更新 |
| `--skip-dep` | 跳过依赖查询（加速） |
| `--skip-mr` | 跳过 Modrinth 查询（加速） |
| `--json` | JSON 输出（默认启用） |

**一次返回**：
- `mcmod`: MC百科完整详情（名称/作者/版本/前置/截图）
- `modrinth`: Modrinth 详情（下载量/版本/许可证）
- `dependencies`: 依赖树（必需+可选）
- `update_check`: 版本对比（是否有新版本）
- `search_results`: 原始搜索结果列表（**仅按名称查询时填充**，按 ID/URL 查询时为空）

**示例**：
```bash
# 推荐：一次获取所有信息
mcmod-search --json full 钠

# 已知版本，检查是否有更新
mcmod-search --json full Sodium --installed 0.5.0

# 加速：不查依赖
mcmod-search --json full 钠 --skip-dep
```

**对比传统调用链**（需要 4 次调用）：
```bash
# 旧方式（4次调用）
mcmod-search --json search 钠
mcmod-search --json info 钠
mcmod-search --json dep sodium
mcmod-search --json update-check sodium --installed 0.5.0

# 新方式（1次调用）
mcmod-search --json full 钠 --installed 0.5.0
```

---

### 5. dep — Modrinth 依赖树

**使用场景**：想知道一个 mod 需要哪些前置/被哪些 mod 需要。

```bash
mcmod-search dep <mod_slug或project_id> [options]
```

| 选项 | 说明 |
|------|------|
| `--installed <版本>` | 当前安装版本（用于参考，不做对比，仅 dep） |
| `--json` | JSON 输出 |

**示例**：
```bash
mcmod-search --json dep sodium
mcmod-search --json dep fabric-api --installed 0.15.0
```

**JSON 返回字段**：
- `deps`: {slug: {name, slug, type, client_side, server_side, url}}
- `required_count`: 必需依赖数量
- `optional_count`: 可选依赖数量

---

### 6. update-check — Modrinth 版本检查

**使用场景**：想知道安装的 mod 是否有新版本。

```bash
mcmod-search update-check <mod_slug> --installed <版本>  (必填)
```

| 字段 | 说明 |
|------|------|
| `is_latest` | true = 已是最新 |
| `latest_version` | 最新版本号 |
| `version_groups` | 版本历史分组 |
| `changelogs` | 最近更新日志（最多5条） |
| `downloads` | 总下载量 |
| `followers` | 关注数 |

**示例**：
```bash
mcmod-search --json update-check sodium --installed 0.5.0
```

---

### 7. author — Modrinth 作者搜索

**使用场景**：想知道某作者在 Modrinth 上发布了哪些作品。

```bash
mcmod-search author <用户名> [options]
```

| 选项 | 说明 |
|------|------|
| `-n <数量>` | 最多结果（默认10） |
| `--json` | JSON 输出 |

**示例**：
```bash
mcmod-search --json author jellysquid_
```

---

### 7. wiki — minecraft.wiki 搜索

**使用场景**：查原版游戏内容（附魔、合成、生物、方块等）。

```bash
mcmod-search wiki <关键词> [options]
```

| 选项 | 说明 |
|------|------|
| `-n <数量>` | 最多结果（默认5） |
| `-r` | 搜索后直接读取第一个页面正文（前4段） |
| `--json` | JSON 输出 |

**示例**：
```bash
mcmod-search --json wiki 附魔台
mcmod-search --json wiki 凋灵 -r
```

---

### 8. read — 读取 wiki 页面正文

**使用场景**：用户选中了一个 wiki 页面，想看完整内容。

```bash
mcmod-search read <url> [options]
```

| 选项 | 说明 |
|------|------|
| `-p <段落数>` | 最多段落数（默认5） |
| `--json` | JSON 输出 |

**示例**：
```bash
mcmod-search --json read https://minecraft.wiki/w/Diamond_Sword -p 8
```

---

## 全局选项

所有命令共享以下选项：

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出 |
| `--cache` | 启用本地缓存（TTL 1小时，减少重复请求） |
| `--no-mcmod` | 禁用 MC百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki |
| `--no-wiki-zh` | 禁用 minecraft.wiki/zh 中文 wiki |
| `-o <file>` | 输出到文件而非 stdout |

---

## 平台说明

| 平台 | URL | 覆盖内容 | 限制 |
|------|-----|----------|------|
| MC百科 | mcmod.cn | 中文模组、物品、方块资料 | 每请求间隔 0.3s |
| Modrinth | modrinth.com | 英文 mod、光影包、材质包 | 360 req/hr |
| minecraft.wiki | minecraft.wiki | 原版游戏内容（英文） | 无 |
| minecraft.wiki/zh | minecraft.wiki | 原版游戏内容（中文） | 无 |

---

## JSON 输出结构

### search / mr / author 结果格式

```json
{
  "source": "mcmod.cn | modrinth | minecraft.wiki | minecraft.wiki/zh",
  "name": "显示名称",
  "name_en": "英文名",
  "name_zh": "中文名",
  "url": "页面链接",
  "source_id": "平台内ID",
  "type": "mod | item | shader | resourcepack | block | entity | mechanic",
  # 注：block / mechanic / dimension 由平台搜索结果自动推断，非 --type CLI 选项
  "description": "MC百科描述",
  "snippet": "Modrinth摘要",
  "status": "活跃 | 不活跃（仅mcmod）",
  "source_type": "open_source | closed_source",
  "author": "作者名（仅mcmod）",
  "categories": ["分类列表"],
  "tags": ["标签列表"]
}
```

### info 完整返回

```json
{
  "name": "...",
  "name_en": "...",
  "name_zh": "...",
  "url": "...",
  "source": "mcmod.cn",
  "source_id": "class ID",
  "type": "mod | item",
  "is_vanilla": false,
  "cover_image": "封面图URL",
  "screenshots": ["截图URL列表"],
  "supported_versions": ["1.20.1", "1.19.4"],
  "categories": ["分类"],
  "tags": ["标签"],
  "author": "作者",
  "status": "活跃",
  "source_type": "open_source",
  "description": "模组描述（最多8段）",
  "relationships": {
    "requires": [{"name_zh": "...", "name_en": "...", "url": "..."}],
    "integrates": [{"name_zh": "...", "name_en": "...", "url": "..."}]
  },
  "has_changelog": true,
  "has_recipe": true
}
```

### read wiki 返回

```json
{
  "name": "页面标题",
  "url": "页面URL",
  "source": "minecraft.wiki",
  "content": ["段落1", "段落2"],
  "_sections": [
    {"heading": "H3标题", "parent": "H2父标题", "content": ["内容"]}
  ]
}
```

---

## 错误处理

| 错误表现 | 原因 | 处理方式 |
|----------|------|----------|
| 四个平台均无结果 | 关键词无相关内容 | 尝试模糊词、英文名 |
| 无法获取模组页面 | MC百科被封禁 | 稍后重试或用 `--cache` |
| dep 查询网络错误 | Modrinth API 限速 | 等待后重试 |
| 作者名无结果 | MC百科作者名需精确匹配 | 尝试部分名、去空格 |

**降级策略**：
- 四个平台独立并行查询，任一平台失败不影响其他平台结果
- MC百科失败 → 仍可从 Modrinth / wiki 获取结果
- Modrinth 失败 → 仍可从 MC百科 / wiki 获取结果
- wiki 无结果 → 尝试 search（会自动融合四平台结果）
- 若全部无结果 → 尝试模糊词或英文名

---

## 典型调用链

```
用户: "帮我查一下 Sodium"
→ search sodium --json
→ 用户选中 → info Sodium -m --json（获取完整信息 + Modrinth 联动）
→ 用户想知道前置 → dep sodium --json
→ 用户想检查更新 → update-check sodium --installed <版本> --json

用户: "这个物品怎么获得"
→ search <物品名> --type item --json
→ 用户选中 → read <wiki_url> --json

用户: "这个作者还做过什么"
→ search --author <作者名> --json
或
→ author <用户名> --json（Modrinth）
```

---

## 安装与环境

- 依赖：**Python 3.8+**、**curl**
- 无需 API key
- 安装：`pip install mcmod-info`
- 命令入口：`mcmod-search`
- 缓存目录：`~/.cache/mcmod-info/`

---

## 故障排查

详见 `references/troubleshooting.md`。

常见问题：
- **无结果**：MC百科可能被临时封禁，稍后重试
- **速度慢**：减少 `-n` 值或禁用不需要的平台
- **依赖查询失败**：Modrinth API 限速，等待后重试
- **作者搜索失败**：MC百科作者名需精确匹配，可尝试部分匹配
