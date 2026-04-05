# mc-search

> 一个 Claude Code Skill，用于在四大平台搜索 Minecraft 模组、物品和 Wiki 内容。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[English Documentation →](README.en.md)

---

## 这是什么？

**mc-search** 是一个 **Claude Code Skill**，让 AI Agent 能够从四大平台搜索和检索 Minecraft 相关信息：

- **MC百科** (mcmod.cn) — 中文模组数据库
- **Modrinth** — 英文 mod/光影/材质包平台
- **minecraft.wiki** — 原版游戏内容 Wiki（英文）
- **minecraft.wiki/zh** — 原版游戏内容 Wiki（中文）

## 工作原理

当用户询问 Minecraft 模组、物品或游戏内容时，Claude 会通过 Bash 自动调用此 Skill 获取结构化 JSON 数据，然后以人类可读的格式呈现结果。

```
用户："帮我查一下 Sodium 模组"
  ↓
Claude: mc-search --json search sodium
  ↓
Claude 解析 JSON 响应 → 呈现格式化答案
```

## 快速开始

### 前置要求

- Python 3.8+
- 可用 `curl` 命令
- 无需 API key

### 安装

```bash
cd skills/mc-search
pip install -e .
```

### 测试 Skill

```bash
mc-search --help
mc-search --json search 钠
```

## 可用命令

| 命令 | 描述 | 示例 |
|------|------|------|
| `search` | 多平台搜索 | `mc-search --json search 钠` |
| `full` | 获取完整模组信息 | `mc-search --json full 钠` |
| `info` | MC百科模组详情 | `mc-search --json info 钠` |
| `dep` | Modrinth 依赖树 | `mc-search --json dep sodium` |
| `wiki` | 搜索 minecraft.wiki | `mc-search --json wiki 附魔` |
| `read` | 读取 Wiki 页面内容 | `mc-search --json read <url>` |
| `mr` | Modrinth 单平台搜索 | `mc-search --json mr sodium` |
| `author` | 按 Modrinth 作者搜索 | `mc-search --json author jellysquid_` |

> **重要**：`--json` 标志必须放在**子命令之前**。

## 主要特性

- **四平台并行搜索** — 同时搜索所有平台
- **智能相关性排序** — 精确匹配 > 前缀匹配 > 包含匹配
- **多平台融合** — 自动合并来自不同平台的结果
- **结构化 JSON 输出** — 便于 AI Agent 解析
- **本地缓存** — TTL 1 小时，减少 API 调用
- **无外部依赖** — 仅使用 Python 标准库 + curl

## 项目结构

```
mc-search-skill/
├── README.md                      # 本文件
├── SKILL.md                       # Claude Code Skill 定义
├── CLAUDE.md                      # Claude Code 项目指南
├── pyproject.toml                 # Python 包配置
├── scripts/
│   ├── cli.py                     # CLI 入口
│   └── core.py                    # 核心搜索逻辑
└── references/
    ├── result-schema.md           # JSON 响应字段文档
    ├── commands.md                # 命令参考（中文）
    └── troubleshooting.md         # 故障排查指南（中文）
```

## 文档

- **[SKILL.md](skills/mc-search/SKILL.md)** — Claude Code Skill 主要定义
- **[CLAUDE.md](skills/mc-search/CLAUDE.md)** — Claude Code 实例项目指南
- **[references/result-schema.md](skills/mc-search/references/result-schema.md)** — JSON 响应字段文档
- **[references/commands.md](skills/mc-search/references/commands.md)** — 详细命令参考
- **[references/troubleshooting.md](skills/mc-search/references/troubleshooting.md)** — 故障排查指南

## 仓库信息

- **名称**: `mc-search-skill`
- **URL**: https://github.com/mexiaosqwq/mc-search-skill
- **Issues**: https://github.com/mexiaosqwq/mc-search-skill/issues

## 许可证

MIT License — 详见 LICENSE 文件

## 致谢

本 Skill 利用了以下 API 和平台：
- [MC百科 API](https://www.mcmod.cn/) — 中文模组数据库
- [Modrinth API](https://docs.modrinth.com/) — 开放模组平台
- [minecraft.wiki API](https://minecraft.wiki/) — 原版游戏内容

感谢所有贡献者和 Minecraft 模组社区的支持。
