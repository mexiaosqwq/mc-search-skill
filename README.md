# mc-search

**Minecraft 模组 + 游戏内容信息查询工具**，专为 AI Agent 设计，同时搜索四大平台。

## 核心能力

- **MC百科** — 中文模组、物品、方块资料
- **Modrinth** — 英文 mod/光影/材质包搜索、依赖树、版本历史
- **minecraft.wiki** — 原版游戏内容（附魔、合成、生物等）
- **minecraft.wiki/zh** — 中文版 minecraft.wiki

## 安装

```bash
cd skills/mc-search
pip install -e .
```

**依赖**: Python 3.8+ 和 curl。无需 API key。

## 使用方式

### 作为命令行工具使用

直接在终端运行：

```bash
mc-search --help
mc-search --json search 钠
```

### 作为 Agent Skill 使用

mc-search 是一个 Claude Code Skill，Agent 会通过 Bash 自动调用 `mc-search` 命令。

支持的命令格式：`mc-search --json <子命令> <参数>`

> **注意**：`--json` 必须放在子命令**之前**

## 快速参考

| 场景 | 命令 |
|------|------|
| 四平台搜索 | `mc-search --json search <关键词>` |
| 物品搜索 | `mc-search --json search <关键词> --type item` |
| 作者搜索（MC百科） | `mc-search --json search --author <名>` |
| 作者搜索（Modrinth） | `mc-search --json author <用户名> -n 20` |
| Modrinth 搜索 | `mc-search --json mr <关键词>` |
| 依赖树 | `mc-search --json dep <mod_slug>` |
| 模组详情（MC百科） | `mc-search --json info <名称或URL>` |
| 一键完整信息 | `mc-search --json full <名称>` |
| wiki 搜索 | `mc-search --json wiki <关键词>` |
| wiki 正文读取 | `mc-search --json read <url>` |

## AI Agent 使用

**始终使用 `--json` 输出**便于程序解析：

```bash
# 搜索模组
mc-search --json search 钠

# 获取完整信息（推荐）
mc-search --json full 钠

# 查看依赖
mc-search --json dep sodium
```

### 返回字段说明

详见 [references/result-schema.md](skills/mc-search/references/result-schema.md)

### 故障排查

详见 [references/troubleshooting.md](skills/mc-search/references/troubleshooting.md)

## 项目结构

```
skills/mc-search/
├── SKILL.md              # Agent 接口定义（核心文档）
├── CLAUDE.md             # Claude Code 项目指南
├── pyproject.toml        # Python 包配置
├── scripts/
│   ├── cli.py            # CLI 入口
│   └── core.py           # 核心搜索逻辑
└── references/
    ├── result-schema.md  # 结果字段说明
    ├── commands.md       # 命令参考
    └── troubleshooting.md # 故障排查
```

## 许可证

MIT License
