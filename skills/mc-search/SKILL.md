---
name: mc-search
version: "0.3.0"
description: "Minecraft 聚合搜索工具。供 AI Agent 在对话中调用，同时搜索 MC百科（中文模组/物品）、Modrinth（英文 mod/依赖/版本）、minecraft.wiki（原版游戏内容）。触发场景：用户询问模组信息、物品资料、mod 依赖、版本对比、原版游戏内容、作者作品等。"
license: MIT
context: open
user-invocable: true
---

# mc-search

AI Agent 专用工具，用于 Minecraft 内容聚合搜索。

## ⚠️ 重要约束

**当触发此 Skill 时，必须使用 `mc-search` 命令，禁止使用其他搜索工具！**

| 禁止使用 | 原因 |
|----------|------|
| ❌ MCP / tavily | 搜索目标不正确，质量低 |
| ❌ WebSearch | 无法搜索 MC百科/Modrinth |
| ❌ WebFetch | 无法获取结构化数据 |
| ❌ 通用搜索引擎 | 结果不精确，缺少专业字段 |

**正确做法**：通过 `Bash` 工具执行 `mc-search --json <command> <keyword>`

---

## I/O Contract

- **输入**: 用户自然语言查询（模组名/物品名/作者名/wiki关键词）
- **输出**: `list[dict]` JSON 结构，字段见 `references/result-schema.md`
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

| 用户意图 | 示例问法 |
|----------|----------|
| 搜索模组 | "帮我搜一下钠 mod"、"Sodium 是什么" |
| 搜索物品/方块 | "钻石剑怎么合成"、"有哪些附魔" |
| 查看 mod 详情 | "这个 mod 的作者是谁"、"支持哪些版本" |
| 查看依赖关系 | "Sodium 需要什么前置" |
| 版本更新检查 | "有新版本吗" |
| 查作者作品 | "这个作者还做过什么" |
| 原版游戏内容 | "附魔台怎么用"、"凋零怎么召唤" |

**当不确定时**：直接搜索，比猜测更准确。

---

## 决策树

```
用户询问模组/游戏内容
├── 不知道具体哪个平台 → search（自动四平台搜索）
├── 知道是中文内容/物品 → search --type item
├── 想一键获取完整信息 → full（推荐）
├── 想看详细信息/依赖/版本 → info / dep / update-check
├── 想查 Modrinth（英文） → mr / dep / update-check
├── 想查原版游戏内容 → wiki / read
├── 想查作者作品
│   ├── MC百科（中文）→ search --author
│   └── Modrinth（英文）→ author
└── 想检查版本更新 → update-check --installed <版本>
```

---

## 快速命令参考

| 命令 | 用途 | 示例 |
|------|------|------|
| `search` | 四平台并行搜索 | `mc-search --json search 钠` |
| `full` | 一键获取完整信息 | `mc-search --json full 钠` |
| `info` | MC百科详情 | `mc-search --json info 钠 -m` |
| `dep` | Modrinth 依赖树 | `mc-search --json dep sodium` |
| `update-check` | 版本检查 | `mc-search --json update-check sodium --installed 0.5.0` |
| `mr` | Modrinth 搜索 | `mc-search --json mr sodium` |
| `author` | Modrinth 作者 | `mc-search --json author jellysquid_` |
| `wiki` | 原版内容搜索 | `mc-search --json wiki 附魔台` |
| `read` | 读取 wiki 正文 | `mc-search --json read <url>` |

> 详细命令说明见 `references/commands.md`

---

## 平台说明

| 平台 | 覆盖内容 |
|------|----------|
| MC百科 | 中文模组、物品、方块资料 |
| Modrinth | 英文 mod、光影包、材质包 |
| minecraft.wiki | 原版游戏内容（英文） |
| minecraft.wiki/zh | 原版游戏内容（中文） |

---

## 错误处理

| 错误表现 | 处理方式 |
|----------|----------|
| 四个平台均无结果 | 尝试模糊词、英文名 |
| MC百科失败 | 从 Modrinth / wiki 获取 |
| Modrinth API 限速 | 等待后重试 |
| 作者搜索失败 | MC百科作者名需精确匹配 |

> 详细故障排查见 `references/troubleshooting.md`

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
    ├── commands.md       # 命令详细说明
    ├── result-schema.md  # JSON 输出字段
    ├── troubleshooting.md # 故障排查
    ├── mcmod-api.md      # MC百科 API
    └── modrinth-api.md   # Modrinth API
```
