---
name: mc-search
version: "0.4.0"
description: "Minecraft 聚合搜索工具。触发：用户询问模组信息、物品资料、mod 依赖、版本对比、原版游戏内容、作者作品。格式：`mc-search --json <子命令> <参数>`，如 `mc-search --json search 钠`。"
license: MIT
context: open
user-invocable: true
allowed-tools: [Bash]
---

# mc-search

Minecraft 内容聚合搜索工具，支持 **四平台并行搜索**（MC百科、Modrinth、minecraft.wiki 中英双站）。

> **注意**：整合包搜索（`--type modpack`）仅在 MC百科 和 Modrinth 两个平台进行。

> **执行格式**：`mc-search --json <子命令> <参数>`
> - **`--json` 必须放在最前面**（全局选项优先）
> - 所有命令优先使用 `--json` 获取结构化输出
>
> **执行流程**：
> ```
> 用户提问 → 判断意图 → 选择命令 → Bash 执行 → 解析 JSON → 呈现结果
> ```

## 快速决策

| 用户意图 | 推荐命令 | 成功率 |
|----------|----------|--------|
| **知道模组/整合包名，要完整信息** | `full <模组名或整合包名>` | ⭐⭐⭐⭐⭐ |
| **不确定模组名，模糊搜索** | `search <关键词>` | ⭐⭐⭐⭐ |
| **搜索整合包** | `search <关键词> --type modpack` | ⭐⭐⭐⭐ |
| 查原版游戏内容 | `wiki <关键词>` | ⭐⭐⭐⭐⭐ |
| 查 Modrinth 依赖 | `dep <slug>` | ⭐⭐⭐⭐⭐ |
| 查作者作品 | `search --author <作者>` | ⭐⭐⭐ |

---

## 命令分类

### 1️⃣ 搜索类（发现内容）

```bash
# 通用搜索（四平台并行，智能排序）
mc-search --json search <关键词>

# 指定类型搜索
mc-search --json search <关键词> --type modpack      # 整合包（MC百科 + Modrinth）
mc-search --json search <关键词> --type shader       # 光影包（仅 Modrinth）
mc-search --json search <关键词> --type resourcepack # 材质包（仅 Modrinth）
mc-search --json search <关键词> --type item         # 物品/方块
mc-search --json search <关键词> --type entity       # 实体/生物

# 作者搜索
mc-search --json search --author "<作者名>"        # MC百科作者
mc-search --json author "<用户名>" -n 20           # Modrinth作者
```

**特点**：
- 四平台并行搜索（MC百科、Modrinth、Minecraft.wiki 中英）
- 智能排序：精确匹配 > 前缀匹配 > 包含匹配
- 多平台融合：同名模组/整合包自动合并，跨平台加权

> **注意**：
> - 整合包搜索（`--type modpack`）仅在 **MC百科** 和 **Modrinth** 两个平台进行
> - 光影包（`--type shader`）和材质包（`--type resourcepack`）**仅 Modrinth** 支持
> - minecraft.wiki 不支持整合包/光影包/材质包搜索
> - 整合包返回字段包含 `is_official`（仅 MC百科 整合包包含此字段）

### 2️⃣ 详情类（完整信息）

```bash
# 一键全量信息（推荐首选）
mc-search --json full <模组名或URL>

# 支持所有项目类型（模组/光影/材质/整合包）
mc-search --json full https://modrinth.com/shader/complementary-reimagined
mc-search --json full https://modrinth.com/resourcepack/faithful
mc-search --json full https://modrinth.com/modpack/rl-craft

# 单平台详情
mc-search --json info <模组名>           # MC百科详情
mc-search --json info <模组名> -m        # 同时查 Modrinth
```

**`full` 返回内容**：
- `mcmod`: MC百科详情（模组/整合包：中文名、分类、状态、作者、截图、标签）
- `modrinth`: Modrinth 详情（下载量、版本历史、运行环境、更新日志）
- `dependencies`: 依赖树（必需/可选依赖）
- `search_results`: 搜索结果摘要（用于确认匹配准确性）
- `_mr_tentative`: Modrinth 模糊匹配提示（当精确匹配失败时）
- `author_team`: 作者团队列表（含分工信息，仅 MC百科）
- `community_stats`: 社区统计数据（评级、浏览量等，仅 MC百科）

> 注：
> - `full` 命令返回的是 JSON 对象，以上字段均为顶级键
> - 支持模组（mod）、光影包（shader）、材质包（resourcepack）、整合包（modpack）
> - MC百科 不支持光影包和材质包，此类项目仅返回 Modrinth 数据

### 3️⃣ Wiki 类（原版内容）

```bash
# 搜索原版内容
mc-search --json wiki <关键词>

# 搜索 + 读取正文
mc-search --json wiki <关键词> -r

# 读取指定 URL
mc-search --json read https://minecraft.wiki/w/Diamond_Sword
```

### 4️⃣ 依赖类（Modrinth）

```bash
# 查看依赖树
mc-search --json dep <mod_slug>
```

> 注：`update-check` 命令已移除，如需检查版本，请使用 Modrinth API 或 `full` 命令获取最新版本信息。

## 决策树（详细版）

```
用户询问模组/游戏内容/整合包
│
├─ 1. 想快速获取完整信息（推荐）
│   └─ 知道模组/整合包名 → full <模组名或整合包名或URL>  ← 首选
│       ├─ 模组名：full 钠
│       ├─ 整合包名：full RLCraft
│       ├─ 光影包：full https://modrinth.com/shader/bsl
│       ├─ 材质包：full https://modrinth.com/resourcepack/faithful
│       ├─ MC百科URL：full https://www.mcmod.cn/class/2785.html
│       ├─ MC百科整合包URL：full https://www.mcmod.cn/modpack/123.html
│       └─ Modrinth URL：full https://modrinth.com/mod/sodium
│
├─ 2. 不确定模组名，需要搜索
│   └─ 模糊关键词 → search <关键词>
│       ├─ 筛类型：search 钻石剑 --type item
│       ├─ 搜整合包：search 科技 --type modpack  # 仅限 MC百科 + Modrinth
│       ├─ 搜光影包：search Complementary --type shader  # 仅 Modrinth
│       ├─ 搜材质包：search Faithful --type resourcepack  # 仅 Modrinth
│       └─ 筛作者：search --author Notch
│
├─ 3. 查原版游戏内容（wiki）
│   └─ wiki <关键词>
│       ├─ 仅搜索：wiki 附魔台
│       └─ 搜索+读取：wiki 附魔台 -r
│
├─ 4. 查 Modrinth 依赖
│   └─ dep <slug>  ← 需要知道模组 slug
│
├─ 5. 查作者作品
│   ├─ MC百科：search --author <作者名>
│   └─ Modrinth：author <用户名> -n 20
│
└─ 6. 已有 URL，直接读取
    ├─ MC百科模组：info <URL>
    ├─ MC百科整合包：full <URL>
    ├─ Modrinth模组/整合包/光影/材质：full <URL> 或 dep <slug>
    ├─ Wiki：read <URL>
```

## 全局选项

> **位置**：必须放在子命令**之前**

```bash
mc-search --json search 钠          # ✓ 正确
mc-search search --json 钠          # ✗ 错误
```

| 选项 | 说明 | 示例 |
|------|------|------|
| `--json` | JSON 格式输出（Agent 推荐） | `mc-search --json search 钠` |
| `--cache` | 启用本地缓存（TTL 1小时） | `mc-search --cache search 钠` |
| `--no-mcmod` | 禁用 MC百科 | `mc-search --no-mcmod search sodium` |
| `--no-mr` | 禁用 Modrinth | `mc-search --no-mr search 钠` |
| `--no-wiki` | 禁用 minecraft.wiki | `mc-search --no-wiki search 钠` |
| `--no-wiki-zh` | 禁用中文 wiki | `mc-search --no-wiki-zh search 钠` |
| `-o <文件>` | 输出到文件 | `mc-search --json search 钠 -o result.json` |

## 常用参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--type <类型>` | 搜索类型过滤 | `--type mod` / `--type item` / `--type modpack` / `--type shader` / `--type resourcepack` / `--type entity` |
| `-n <数量>` | 限制结果数量 | `-n 10` |
| `-m` | 同时查 Modrinth | `info 钠 -m` |
| `-r` | 读取 wiki 正文 | `wiki 附魔台 -r` |

## 智能排序逻辑

### 搜索排序规则

`search` 命令使用**智能相关性排序**，优先级从高到低：

| 优先级 | 条件 | 示例 |
|--------|------|------|
| 1️⃣ 精确匹配 | 名称完全等于搜索词 | 搜 "spawn" → "Spawn" 排第 1 |
| 2️⃣ 前缀匹配 | 名称以搜索词开头 | 搜 "sod" → "Sodium" 排前 |
| 3️⃣ 包含匹配 | 名称包含搜索词 | 搜 "spawn" → "OreSpawn" 排后 |
| 4️⃣ 多平台加权 | 同时出现在多个平台 | "Spawn" 在 MC百科+Modrinth → 排名提升 |
| 5️⃣ 平台权威度 | 同分时优先级 | MC百科 > Modrinth > Wiki |

**实际效果**：
```bash
# "Spawn" 精确匹配排第 1（而非 "OreSpawn"）
mc-search --json search spawn

# "钠" 精确匹配排第 1（而非 "Sodium Extra"）
mc-search --json search 钠
```

### 版本优先级

当 MC百科和 Modrinth 版本不一致时，**以 Modrinth 为准**：
- Modrinth 是官方发布平台，更新更及时
- MC百科可能存在版本信息延迟

**示例**：
- MC百科：`0.5.0`（可能过时）
- Modrinth：`0.6.0`（最新）
- 结论：使用 `0.6.0`

---

## 使用示例

### 示例 1：搜索 "钠" 模组

```bash
# 快速搜索（四平台并行）
mc-search --json search 钠

# 获取完整信息（推荐）
mc-search --json full 钠

# 输出示例（JSON 解析后）：
# {
#   "mcmod": {
#     "name_zh": "钠",
#     "name_en": "Sodium",
#     "status": "活跃",
#     "author": "JellySquid",
#     "categories": ["优化Mod"]
#   },
#   "modrinth": {
#     "downloads": 25000000,
#     "latest_version": "0.6.0",
#     "loaders": ["fabric", "neoforge"]
#   }
# }
```

### 示例 2：搜索 "spawn" 模组

```bash
# 模糊搜索
mc-search --json search spawn

# 结果排序：
# 1. Spawn（精确匹配）← 第 1
# 2. Spawn Animations（前缀匹配）
# 3. OreSpawn（包含匹配，排后）
```

### 示例 3：查看依赖

```bash
# 查看 Sodium 的依赖
mc-search --json dep sodium

# 输出：
# {
#   "deps": {},
#   "required_count": 0,
#   "optional_count": 0
# }
# → Sodium 无依赖
```

### 示例 4：获取版本信息

```bash
# 使用 full 命令获取完整信息（包含最新版本）
mc-search --json full 钠

# Modrinth 返回中包含最新版本信息：
# {
#   "modrinth": {
#     "latest_version": "0.6.0",
#     "version_groups": [...]
#   }
# }
```

### 示例 5：搜索整合包

```bash
# 搜索整合包（MC百科 + Modrinth）
mc-search --json search RLCraft --type modpack
mc-search --json search 科技 --type modpack      # 中文关键词

# 获取整合包完整信息
mc-search --json full RLCraft
mc-search --json full https://www.mcmod.cn/modpack/339.html  # MC百科URL
mc-search --json full https://modrinth.com/modpack/rl-craft  # Modrinth URL

# 输出示例（JSON 解析后）：
# {
#   "name": "RLCraft",
#   "name_en": "RLCraft",
#   "type": "modpack",
#   "source": "mcmod.cn|modrinth",
#   "is_official": true,
#   "description": "硬核生存整合包...",
#   "categories": ["冒险", "魔法"]
# }
```

### 示例 6：搜索光影包/材质包

```bash
# 搜索光影包（仅 Modrinth）
mc-search --json search Complementary --type shader
mc-search --json search BSL --type shader

# 搜索材质包（仅 Modrinth）
mc-search --json search Faithful --type resourcepack
mc-search --json search Mizuno --type resourcepack

# 获取光影包完整信息
mc-search --json full https://modrinth.com/shader/complementary-reimagined

# 获取材质包完整信息
mc-search --json full https://modrinth.com/resourcepack/faithful

# 输出示例（光影包 JSON）：
# {
#   "mcmod": null,                        # MC百科 不支持光影包
#   "modrinth": {
#     "name": "Complementary Shaders - Reimagined",
#     "type": "shader",
#     "client_side": "required",          # 光影仅客户端需要
#     "server_side": "unsupported",
#     "downloads": 5000000,
#     "latest_version": "r5.2.2",
#     "categories": ["optimization"]
#   },
#   "dependencies": null                  # 光影通常无依赖
# }
```

---

## 错误处理

| 错误信息 | 原因 | 解决方法 |
|----------|------|----------|
| `四个平台均无 [关键词] 相关结果` | 关键词不存在或拼写错误 | 尝试其他关键词或检查拼写 |
| `无法解析模组 ID` | MC百科 URL 格式变化 | 直接使用 URL：`info <URL>` |
| `mod_id 查询依赖时网络错误` | Modrinth API 限流或网络问题 | 稍后重试（限流：360次/小时） |
| `MC百科 响应过短` | 被 MC百科 临时封禁 | 使用 `--cache` 或稍后重试 |

**调试技巧**：使用 `--json` 查看完整返回数据

```bash
mc-search --json search 关键词 2>&1 | python3 -m json.tool
```

## 详细文档

- [result-schema.md](references/result-schema.md) — 返回字段完整定义
- [troubleshooting.md](references/troubleshooting.md) — 故障排查指南

## 初始化

```bash
# 安装为 Python 包（推荐）
cd skills/mc-search
pip install -e .

# 测试安装
mc-search --help
mc-search --json search 钠
```
