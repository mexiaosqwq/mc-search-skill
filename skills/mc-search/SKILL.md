---
name: mc-search
version: "0.3.0"
description: "Minecraft 聚合搜索工具。【禁止使用 MCP/WebSearch/tavily】触发后必须通过 Bash 执行 mc-search 命令。触发场景：用户询问模组信息、物品资料、mod 依赖、版本对比、原版游戏内容、作者作品等。"
license: MIT
context: open
user-invocable: true
---

# mc-search

AI Agent 专用工具，用于 Minecraft 内容聚合搜索。

---

## 🚨 强制约束（触发后必须遵守）

**触发此 Skill 后，必须立即执行 `mc-search` 命令。**

### ❌ 绝对禁止使用的工具

| 禁止工具 | 禁止原因 |
|----------|----------|
| MCP / tavily_search | 搜索目标不正确，无法搜索 MC百科/Modrinth |
| WebSearch | 无法搜索 MC百科/Modrinth，结果不相关 |
| WebFetch | 无法获取结构化数据，效率低 |
| 任何通用搜索引擎 | 结果不精确，缺少专业字段 |

### ✅ 唯一正确的做法

**立即通过 Bash 工具执行：**

```bash
mc-search --json search <关键词>
```

### 触发后执行流程

```
1. 识别用户意图 → 选择合适的 mc-search 子命令
2. 调用 Bash 执行 mc-search --json <command> <keyword>
3. 解析 JSON 结果 → 向用户呈现信息
4. 如需更多信息 → 再次调用 mc-search（不要切换到其他搜索工具）
```

---

## I/O Contract

- **输入**: 用户自然语言查询（模组名/物品名/作者名/wiki关键词）
- **输出**: JSON 结构，包含 `results` 数组
- **调用方式**: `mc-search --json <command> <keyword>`

---

## 初始化

**首次使用前必须安装**：

```bash
cd skills/mc-search && bash setup.sh
```

或手动安装：`pip install mc-search`

验证安装：`mc-search --help`

---

## 触发判断

**当用户询问以下内容时，应调用此工具：**

| 用户意图 | 示例问法 | 使用命令 |
|----------|----------|----------|
| 搜索模组 | "帮我搜一下钠 mod" | `search` |
| 搜索物品/方块 | "钻石剑怎么合成" | `search --type item` |
| 一键获取完整信息 | "给我钠的全部信息" | `full` |
| 查看 mod 详情 | "这个 mod 的作者是谁" | `info` |
| 查看依赖关系 | "Sodium 需要什么前置" | `dep` |
| 版本更新检查 | "有新版本吗" | `update-check` |
| 查作者作品 | "这个作者还做过什么" | `search --author` 或 `author` |
| 原版游戏内容 | "附魔台怎么用" | `wiki` |

**当不确定时**：直接用 `search`，比猜测更准确。

---

## 核心命令详解

### 1. search — 四平台并行搜索（最常用）

**何时使用**：用户询问模组/物品，不确定要哪个平台。

```bash
mc-search --json search <关键词>
mc-search --json search <关键词> --type item   # 搜索物品
mc-search --json search --author <作者名>       # 搜索作者作品
```

**返回字段**：
- `name` / `name_zh` / `name_en` — 名称
- `url` — 页面链接
- `source` — 来源平台（mcmod.cn / modrinth / minecraft.wiki）
- `description` — 描述
- `author` — 作者（MC百科）
- `status` — 状态（活跃/停更）

**示例**：
```bash
mc-search --json search 钠
mc-search --json search 钻石剑 --type item
mc-search --json search --author CaffeineMC
```

---

### 2. full — 一键获取完整信息（推荐）

**何时使用**：需要模组的全部信息，只需一次调用。

```bash
mc-search --json full <模组名>
mc-search --json full <模组名> --installed <当前版本>  # 检查更新
```

**一次返回**：
- `mcmod` — MC百科完整详情（名称/作者/版本/前置/截图/描述）
- `modrinth` — Modrinth 详情（下载量/版本/许可证）
- `dependencies` — 依赖树（必需+可选）
- `update_check` — 版本对比（是否有新版本）

**示例**：
```bash
mc-search --json full 钠
mc-search --json full Sodium --installed 0.5.0
```

**对比传统方式**：
```bash
# 旧方式需要 4 次调用
mc-search --json search 钠
mc-search --json info 钠
mc-search --json dep sodium
mc-search --json update-check sodium --installed 0.5.0

# 新方式只需 1 次
mc-search --json full 钠 --installed 0.5.0
```

---

### 3. info — MC百科模组详情

**何时使用**：用户选中了一个模组，想看详细信息。

```bash
mc-search --json info <模组名或URL或ID>
mc-search --json info <模组名> -m   # 同时查 Modrinth
```

**常用选项**：
- `-m` — 同时查询 Modrinth 信息
- `-d` — 仅前置/联动模组
- `-v` — 仅支持版本
- `-g` — 仅截图/封面

**示例**：
```bash
mc-search --json info 钠
mc-search --json info 钠 -m          # 同时查 Modrinth
mc-search --json info 2785           # 用 MC百科 ID
mc-search --json info https://www.mcmod.cn/class/2785.html
```

---

### 4. dep — Modrinth 依赖树

**何时使用**：想知道一个 mod 需要哪些前置。

```bash
mc-search --json dep <mod_slug>
```

**返回字段**：
- `deps` — 依赖列表（必需+可选）
- `required_count` — 必需依赖数量
- `optional_count` — 可选依赖数量

**示例**：
```bash
mc-search --json dep sodium
mc-search --json dep fabric-api
```

---

### 5. update-check — 版本检查

**何时使用**：想知道安装的 mod 是否有新版本。

```bash
mc-search --json update-check <mod_slug> --installed <当前版本>
```

**返回字段**：
- `is_latest` — 是否最新（true/false）
- `latest_version` — 最新版本号
- `changelogs` — 最近更新日志

**示例**：
```bash
mc-search --json update-check sodium --installed 0.5.0
```

---

### 6. wiki — 原版游戏内容搜索

**何时使用**：查原版内容（附魔、合成、生物、方块等）。

```bash
mc-search --json wiki <关键词>
mc-search --json wiki <关键词> -r   # 搜索后直接读取正文
```

**示例**：
```bash
mc-search --json wiki 附魔台
mc-search --json wiki 凋灵 -r        # 直接读取正文
```

---

### 7. read — 读取 wiki 页面正文

**何时使用**：用户想看 wiki 页面的完整内容。

```bash
mc-search --json read <wiki_url>
mc-search --json read <wiki_url> -p <段落数>
```

**示例**：
```bash
mc-search --json read https://minecraft.wiki/w/Diamond_Sword
mc-search --json read https://minecraft.wiki/w/Enchanting -p 10
```

---

### 8. mr — Modrinth 单平台搜索

**何时使用**：明确要查英文 mod/光影包/材质包。

```bash
mc-search --json mr <关键词>
mc-search --json mr <关键词> -t shader        # 搜索光影
mc-search --json mr <关键词> -t resourcepack   # 搜索材质包
```

**示例**：
```bash
mc-search --json mr sodium
mc-search --json mr SEUS -t shader
```

---

### 9. author — Modrinth 作者搜索

**何时使用**：想知道某作者在 Modrinth 上发布了哪些作品。

```bash
mc-search --json author <用户名>
```

**示例**：
```bash
mc-search --json author jellysquid_
```

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（Agent 必须使用） |
| `--cache` | 启用本地缓存（TTL 1小时） |
| `--no-mcmod` | 禁用 MC百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki |

> 注意：全局选项必须放在子命令**之前**，如 `mc-search --json search 钠`

---

## 平台说明

| 平台 | 覆盖内容 | 特点 |
|------|----------|------|
| MC百科 | 中文模组、物品、方块 | 中文最全，有前置/联动信息 |
| Modrinth | 英文 mod、光影、材质包 | 有依赖树、版本历史 |
| minecraft.wiki | 原版游戏内容（英文） | 官方 wiki，权威 |
| minecraft.wiki/zh | 原版游戏内容（中文） | 中文翻译 |

---

## 典型场景调用示例

### 场景 1：用户问"帮我查一下钠 mod"

```bash
# 一次获取全部信息
mc-search --json full 钠
```

### 场景 2：用户问"钻石剑怎么合成"

```bash
# 搜索物品
mc-search --json search 钻石剑 --type item
# 如果需要更多信息，读取 wiki
mc-search --json wiki 钻石剑 -r
```

### 场景 3：用户问"Sodium 需要什么前置"

```bash
mc-search --json dep sodium
```

### 场景 4：用户问"我装的 Sodium 0.5.0 有新版本吗"

```bash
mc-search --json update-check sodium --installed 0.5.0
```

### 场景 5：用户问"这个作者还做过什么 mod"

```bash
# MC百科作者搜索
mc-search --json search --author CaffeineMC
# 或 Modrinth 作者搜索
mc-search --json author jellysquid_
```

### 场景 6：用户问"附魔台怎么用"

```bash
mc-search --json wiki 附魔台 -r
```

---

## JSON 输出关键字段

### search 结果

```json
{
  "results": [
    {
      "name": "钠",
      "name_en": "Sodium",
      "url": "https://www.mcmod.cn/class/2785.html",
      "source": "mcmod.cn",
      "author": "CaffeineMC",
      "status": "活跃",
      "description": "强大的渲染优化模组..."
    }
  ],
  "platform_stats": {
    "mcmod.cn": {"total": 1, "returned": 1},
    "modrinth": {"total": 2, "returned": 2}
  }
}
```

### full 结果

```json
{
  "mcmod": {
    "name": "钠",
    "author": "CaffeineMC",
    "supported_versions": ["1.20.1", "1.19.4"],
    "relationships": {
      "requires": [{"name_zh": "Fabric API", "url": "..."}]
    }
  },
  "modrinth": {
    "downloads": 5000000,
    "latest_version": "0.5.8"
  },
  "update_check": {
    "is_latest": false,
    "latest_version": "0.5.8"
  }
}
```

---

## 错误处理

| 错误表现 | 处理方式 |
|----------|----------|
| 四个平台均无结果 | 尝试英文名或模糊词 |
| MC百科失败 | 使用 Modrinth/wiki 结果 |
| Modrinth API 限速 | 等待后重试，或用 `--cache` |
| 作者搜索无结果 | MC百科需精确匹配作者名 |

**降级策略**：四个平台独立并行，任一失败不影响其他平台。

---

## 文件结构

```
mc-search/
├── SKILL.md              # 本文件
├── setup.sh              # 初始化脚本
├── pyproject.toml        # 包配置
├── scripts/              # 核心代码
│   ├── cli.py            # CLI 入口
│   └── core.py           # 搜索逻辑
└── references/           # 参考文档
    ├── commands.md       # 命令补充说明
    ├── result-schema.md  # JSON 字段详细说明
    └── troubleshooting.md # 故障排查
```
