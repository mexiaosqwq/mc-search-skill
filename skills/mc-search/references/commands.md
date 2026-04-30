# 命令参考

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（推荐） |
| `--cache` | 启用本地缓存（TTL 1 小时，需显式添加此参数） |
| `--no-mcmod` | 禁用 MC百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki（英文） |
| `--no-wiki-zh` | 禁用 minecraft.wiki/zh（中文） |
| `-o <file>` | 输出到文件 |

> **重要**：全局选项必须放在子命令**之前**。

---

## 1. search — 多平台搜索

**使用场景**：用户询问"帮我搜一下 xxx"，不确定具体要哪个平台。

```bash
mc-search --json search <关键词> [选项]
```

| 选项 | 说明 | 默认 |
|------|------|------|
| `--type` | 内容类型：mod/item/shader/resourcepack/modpack | mod |
| `--shader` | 快捷：搜光影包（= `--type shader`，仅 Modrinth） | - |
| `--modpack` | 快捷：搜整合包（= `--type modpack`） | - |
| `--resourcepack` | 快捷：搜材质包（= `--type resourcepack`，仅 Modrinth） | - |
| `--platform` | 平台：all/mcmod/modrinth/wiki/wiki-zh | all |
| `--author` | 按作者搜索（MC百科 + Modrinth 双平台并行） | - |
| `-n <数量>` | 每平台最多结果 | 5 |
| `--timeout <秒>` | 超时时间 | 15 |

**快捷标志等价关系**：
- `--shader` = `--type shader` + 自动限定仅 Modrinth
- `--modpack` = `--type modpack`
- `--resourcepack` = `--type resourcepack` + 自动限定仅 Modrinth

**`--type` 对平台的影响**：
- `mod`/`item`/`modpack`：MC百科 + Modrinth
- `shader`/`resourcepack`：仅 Modrinth（自动限定）
- 搜索结果也可能包含 minecraft.wiki 相关内容

**`--author` 双平台搜索**：
- 同时查询 MC百科 和 Modrinth
- 返回格式：`{"mcmod": [...], "modrinth": [...], "mcmod_count": N, "modrinth_count": N}`

---

## 2. show — 查看详情/依赖

**使用场景**：用户选中了一个项目，想看详细信息或依赖关系。

```bash
mc-search --json show <名称/URL/ID> [选项]
```

| 选项 | 说明 |
|------|------|
| `--full` | 完整信息（Modrinth 返回完整数据；MC百科详情页受限，回退到基础信息）|
| `--deps` | 依赖关系（走 Modrinth 数据源） |
| `--skip-dep` | 跳过依赖查询（加速，仅 --full） |
| `--skip-mr` | 跳过 Modrinth 查询（加速，仅 --full） |

**参数格式与路由规则**：
- 中文名称 → MC百科优先，失败回退 Modrinth（`mc-search show 钠`）
- 英文/slug → Modrinth 优先（`mc-search show sodium`）
- MC百科 URL → 直读 MC百科页面（`mc-search show https://www.mcmod.cn/class/23352.html`）
- Modrinth URL → 直读 Modrinth API（`mc-search show https://modrinth.com/mod/sodium`）
- 纯数字 ID → 按 MC百科 class ID 查询（`mc-search show 23352`）

> 注：`--skip-mr` 和全局 `--no-mr` 在 show 命令中等效，均可跳过 Modrinth。

**`--deps` 快捷路径**：
- 直接搜 Modrinth slug → 获取依赖

**`--full` 返回数据**：
- `mcmod`: MC百科基础信息（详情页受限时仅有搜索页数据）
- `modrinth`: Modrinth 详情（完整数据，无截断）
- `dependencies`: Modrinth 依赖树
- `saved_files`: 自动保存的长描述文件路径

**示例**：
```bash
mc-search --json show 钠                        # MC百科信息
mc-search --json show sodium                    # Modrinth详情
mc-search --json show 钠 --full                 # 双平台信息
mc-search --json show https://www.mcmod.cn/class/2785.html --full
mc-search --json show https://modrinth.com/mod/sodium --full
mc-search --json show 2785 --full               # MC百科 ID
mc-search --json show 钠 --deps                 # Modrinth 依赖
```

---

## 3. wiki — 原版 Wiki 搜索与阅读

**使用场景**：查原版游戏内容（附魔、合成、生物、方块等）。

```bash
mc-search --json wiki <关键词或URL> [选项]
```

| 选项 | 说明 | 默认 |
|------|------|------|
| `-r` | 搜索后读取第一个结果正文 | - |
| `-n <数量>` | 最多结果 | 5 |
| `-p <段落数>` | 读取页面时的最大段落数 | 20 |
| `--timeout <秒>` | 超时时间 | 15 |

**智能检测**：
- 参数以 `http` 开头 → 直接读取 wiki 页面（替代 wiki `read` 模式）
- 否则 → 搜索 wiki（仅搜索 minecraft.wiki 中英双站）

**示例**：
```bash
mc-search --json wiki 附魔台                    # 搜索 wiki
mc-search --json wiki 附魔台 -r                 # 搜索并读取正文
mc-search --json wiki https://minecraft.wiki/w/Diamond_Sword  # 直接读取
mc-search --json wiki https://minecraft.wiki/w/Diamond_Sword -p 8
```
