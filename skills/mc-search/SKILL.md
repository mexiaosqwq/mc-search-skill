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

Minecraft 内容搜索 Skill。当用户询问 Minecraft 模组、整合包、光影、材质包、原版游戏内容或攻略时，使用此工具获取信息。

> **MC百科 现状**：详情页受 AIWAFCDN 防火墙保护。**搜索功能正常**，可获取名称/描述/分类。
> 详情字段（作者/版本/截图/依赖/合成表）暂不可用，Modrinth 和 wiki 不受影响。

**所有命令必须使用 `--json`**，全局选项必须放在子命令**之前**。

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（所有命令必须使用） |
| `--cache` | 启用本地缓存（TTL 1 小时，减少重复查询等待） |
| `--no-mcmod` | 禁用 MC百科（搜英文模组时建议加，避免中文结果干扰） |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki（英文） |
| `--no-wiki-zh` | 禁用 minecraft.wiki/zh（中文） |
| `-o <file>` | 输出到文件 |

---

## 命令

### search — 多平台搜索

```bash
mc-search --json search <关键词> [选项]
```

| 选项 | 说明 | 默认 |
|------|------|------|
| `--type` | 内容类型：mod/item/shader/resourcepack/modpack | mod |
| `--shader` | 快捷：搜光影（= `--type shader`，仅 Modrinth） | - |
| `--modpack` | 快捷：搜整合包（= `--type modpack`） | - |
| `--resourcepack` | 快捷：搜材质包（= `--type resourcepack`，仅 Modrinth） | - |
| `--platform` | 平台：all/mcmod/modrinth/wiki/wiki-zh | all |
| `--author` | 按作者搜索（Modrinth 可用；MC百科侧受防火墙限制可能失败） | - |
| `-n <数量>` | 每平台最多结果（Agent 建议设 3-5，避免输出过长） | 15 |
| `--timeout <秒>` | 超时时间 | 12 |

> Agent 提示：搜索结果包含多平台融合数据。默认 15 条/平台可能过多，建议设 `-n 3` 或 `-n 5` 只取 top 结果。如需精确匹配，加 `--platform mcmod` 或 `--platform modrinth` 限定单平台。如需保存结果到文件，追加 `-o result.json`。

---

### show — 查看详情/依赖

```bash
mc-search --json show <名称/URL/ID> [选项]
```

| 选项 | 说明 |
|------|------|
| `--full` | 完整信息（Modrinth 返回完整数据；MC百科详情页受限，回退到基础信息）|
| `--deps` | 依赖关系（走 Modrinth 数据源） |
| `--skip-dep` | 跳过依赖查询（加速，仅 `--full`） |
| `--skip-mr` | 跳过 Modrinth 查询（加速，仅 `--full`） |

**参数格式**：
- 模组名称：`show 钠` / `show sodium`
- MC百科 URL：`show https://www.mcmod.cn/class/23352.html`
- 纯数字 ID：`show 23352`
- Modrinth URL：`show https://modrinth.com/mod/sodium`

> Agent 提示：`show` 默认返回轻量信息。需要完整信息（描述、版本、依赖）时用 `--full`（Modrinth 侧完整，MC百科侧回退到基础信息）。仅查依赖用 `--deps` 更快。返回的 `body` 字段是长 Markdown 描述（已截断至 5000 字符）——不要直接输出全部，提取关键段落即可。

---

### wiki — 原版 Wiki 搜索与阅读

```bash
mc-search --json wiki <关键词或URL> [选项]
```

| 选项 | 说明 | 默认 |
|------|------|------|
| `-r` | 搜索后自动读取第一个结果的正文 | - |
| `-n <数量>` | 最多返回多少条搜索结果 | 5 |
| `-p <段落数>` | 读取页面时的最大段落数 | 20 |
| `--timeout <秒>` | 超时时间 | 12 |

**智能检测**：
- 参数以 `http` 开头 → 直接读取 wiki 页面
- 否则 → 搜索 wiki（中英双站）

> Agent 提示：用户问原版合成表、附魔、生物等用此命令。`-r` 可一步完成"搜索+读取"，省去二次调用。返回的 `content` 是段落列表，按需展示即可。

---

## Agent 使用指南

### 命令选择策略

| 用户意图 | 命令 |
|---------|------|
| 模糊搜索模组/整合包/光影 | `search <关键词> -n 5` |
| 看某个模组的详细信息（Modrinth） | `show <名称> --full` |
| 查某个模组的依赖关系 | `show <名称> --deps` |
| 查原版内容（附魔/方块/生物） | `wiki <关键词>` 或 `wiki <关键词> -r` |
| 搜索英文模组 | `search <英文名> --no-mcmod -n 5` |
| 搜光影/材质包 | `search <关键词> --shader` / `--resourcepack` |

### 处理返回结果

- **搜索成功**：返回 `list[dict]`，每项包含 `name`、`url`、`source`、`description` 等字段
- **详情成功**：返回字典，MC百科数据在 `mcmod` 键，Modrinth 在 `modrinth` 键
- **失败**：返回 `{"error": "错误码", "message": "错误信息"}` — 向用户说明错误原因，建议换个关键词或平台
- **长文本处理**：`body` 字段可能很长，不要直接全部输出。提取用户关心的部分（如功能简介、安装要求）即可
- **融合结果**：`source` 字段可能包含多平台（如 `mcmod.cn|modrinth`），说明时告知用户信息来源

### 平台选择建议

- 中文模组搜索 → **MC百科**（搜索正常，可获取名称/描述/分类）
- 模组详情/依赖 → **Modrinth**（详情页完整，依赖准确，版本明确）
- 英文模组/光影/材质包 → **Modrinth**（功能完整）
- 原版内容 → **minecraft.wiki**（中英文自动选择）
- 搜英文模组时加 `--no-mcmod` 避免中文结果干扰

### 常见错误处理

| 现象 | 对策 |
|------|------|
| 搜索无结果 | 换更短的关键词，或换平台（如 `--platform modrinth`） |
| MC百科详情页被拦截 | 加 `--no-mcmod` 跳过，或使用 `--platform modrinth` |
| MC百科搜索不可用 | 加 `--no-mcmod` 跳过，搜索页通常正常 |
| 超时 | 加 `--timeout 20` 增加超时，或缩小搜索范围 |
| 结果太多 | 加 `-n 3` 限制返回数量 |

---

## 返回格式

所有命令返回 JSON。字段定义见 [result-schema.md](references/result-schema.md)。

```
搜索成功 → list[dict]  每个元素是一个结果项
详情成功 → dict         包含 mcmod / modrinth / dependencies 等键
失败     → {"error": "错误码", "message": "错误信息"}
```

## 平台说明

- **MC 百科** — 中文模组为主，联动信息全，中文搜索效果好。注意：详情页可能受防火墙保护，此时仅返回搜索页基本信息（名称+描述+分类），缺失作者/版本/依赖等详情
- **Modrinth** — 英文模组，依赖准确，光影/材质包唯一来源
- **minecraft.wiki** — 原版游戏内容（方块、物品、机制），中英文自动匹配

详见 [platform-comparison.md](references/platform-comparison.md)。
