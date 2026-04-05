# 命令参考

## 1. search — 多平台并行搜索

**使用场景**：用户询问"帮我搜一下 xxx"，不知道具体要哪个平台。

**平台**：MC百科 + Modrinth + minecraft.wiki + minecraft.wiki/zh

```bash
mc-search search <关键词> [options]
```

| 选项 | 说明 |
|------|------|
| `--type item` | 搜索物品/方块（仅对 MC百科 有效），默认搜索模组 |
| `--type mod` | 搜索模组（默认） |
| `--type entity` | 融合时 wiki 权威结果优先（biome/dimension 同） |
| `--author <作者名>` | MC百科作者搜索（作者名需精确匹配） |
| `-n <数量>` | 每平台最多结果（默认3，`--fuse` 时最多15） |
| `-t <秒数>` | 超时时间（默认12秒） |
| `--json` | JSON 输出（Agent 解析首选） |

> **重要**：`--type` 选项只对 MC百科 搜索有效，用于区分模组和物品搜索。Modrinth 和 wiki 搜索不受此选项影响。

**示例**：
```bash
mc-search --json search 钠
mc-search --json search 钻石剑 --type item
mc-search --json search --author Notch
```

---

## 2. mr — Modrinth 单平台搜索

**使用场景**：明确要查英文 mod/光影包/纹理包。

```bash
mc-search mr <关键词> [options]
```

| 选项 | 说明 |
|------|------|
| `-n <数量>` | 最多结果（默认5） |
| `-t mod` | 项目类型：mod / shader / resourcepack（默认 mod） |
| `--json` | JSON 输出 |

> **注**：mr 命令的默认超时时间为 12 秒（继承自全局默认值）。

**示例**：
```bash
mc-search --json mr sodium
mc-search --json mr shaders -t shader
```

---

## 3. info — MC百科模组/物品详情

**使用场景**：用户选中了一个模组，想看详细信息。

```bash
mc-search --json info <模组名或URL或ID> [options]
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
| `-r` | 显示物品合成表（仅 item 类型） |

**参数格式**：
- 模组名称：`mc-search info 钠`
- MC百科 URL：`mc-search info https://www.mcmod.cn/class/23352.html`
- 纯数字 ID：`mc-search info 23352`

> **注意**：info 命令不支持 Modrinth URL。如需查询 Modrinth 模组详情，请使用 `full` 命令。

**示例**：
```bash
mc-search --json info 钠
mc-search --json info Sodium -m
mc-search --json info 钻石剑 -r
```

---

## 4. full — 一键获取完整信息（推荐）

**使用场景**：需要模组的全部信息，只需**一次调用**。无数据截断，返回完整信息。

```bash
mc-search --json full <模组名或URL或slug> [options]
```

| 选项 | 说明 |
|------|------|
| `--skip-dep` | 跳过依赖查询（加速） |
| `--skip-mr` | 跳过 Modrinth 查询（加速） |

**一次返回**：
- `mcmod`: MC百科完整详情
- `modrinth`: Modrinth 详情（完整数据，无截断）
- `dependencies`: 依赖树

**示例**：
```bash
mc-search --json full 钠
mc-search --json full https://modrinth.com/mod/sodium
```

---

## 5. dep — Modrinth 依赖树

**使用场景**：想知道一个 mod 需要哪些前置。

```bash
mc-search dep <mod_slug或project_id> [options]
```

| 选项 | 说明 |
|------|------|
| `--json` | JSON 输出 |

**示例**：
```bash
mc-search --json dep sodium
```

---

## 6. author — Modrinth 作者搜索

**使用场景**：想知道某作者在 Modrinth 上发布了哪些作品。

```bash
mc-search author <用户名> [options]
```

| 选项 | 说明 |
|------|------|
| `-n <数量>` | 最多结果（默认10） |
| `--json` | JSON 输出 |

> **注**：author 命令的默认超时时间为 12 秒（继承自全局默认值）。

**示例**：
```bash
mc-search --json author jellysquid_
```

---

## 7. wiki — minecraft.wiki 搜索

**使用场景**：查原版游戏内容（附魔、合成、生物、方块等）。

```bash
mc-search wiki <关键词> [options]
```

| 选项 | 说明 |
|------|------|
| `-n <数量>` | 最多结果（默认5） |
| `-r` | 搜索后直接读取第一个页面正文 |
| `--json` | JSON 输出 |

> **注**：wiki 命令的默认超时时间为 12 秒（继承自全局默认值）。

**示例**：
```bash
mc-search --json wiki 附魔台
mc-search --json wiki 凋灵 -r
```

---

## 8. read — 读取 wiki 页面正文

**使用场景**：用户选中了一个 wiki 页面，想看完整内容。

```bash
mc-search read <url> [options]
```

| 选项 | 说明 |
|------|------|
| `-p <段落数>` | 最多段落数（默认5） |
| `--json` | JSON 输出 |

> **注**：read 命令的默认超时时间为 12 秒（继承自全局默认值）。

**示例**：
```bash
mc-search --json read https://minecraft.wiki/w/Diamond_Sword -p 8
```

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（Agent 调用推荐） |
| `--cache` | 启用本地缓存（TTL 1小时） |
| `--no-mcmod` | 禁用 MC百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki（英文） |
| `--no-wiki-zh` | 禁用 minecraft.wiki/zh（中文） |
| `-o <file>` | 输出到文件 |
