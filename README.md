# mc-search

AI Agent 优先的 Minecraft 聚合搜索 Skill，四平台并行。

[![Version](https://img.shields.io/github/v/release/mexiaosqwq/mc-search-skill)](https://github.com/mexiaosqwq/mc-search-skill/releases)
[![License](https://img.shields.io/github/license/mexiaosqwq/mc-search-skill)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange)](skills/mc-search/SKILL.md)

[English Documentation →](README.en.md)

## 项目简介

mc-search 是为 **Claude Code Agent** 设计的 Minecraft 内容搜索 Skill，并行搜索四个平台：

- **MC 百科** (mcmod.cn) — 中文模组/物品/整合包，搜索+详情完整可用
- **Modrinth** — 英文 mod/光影/材质包/整合包，API 完整
- **minecraft.wiki** — 原版游戏 wiki（英文）
- **minecraft.wiki/zh** — 原版游戏 wiki（中文）

默认值针对 AI Agent 场景优化（少量结果、合理超时）。

> **MC百科 说明**：MC百科 (mcmod.cn) 使用 `curl_cffi` + Chrome TLS 指纹绕过 CDN 盾（各子域名独立绕过）。搜索+详情均可正常使用，需安装 `curl_cffi>=0.15.0`。

## 安装到 Claude Code

一条命令完成克隆 + 安装依赖 + 注册 Skill：

```bash
git clone https://github.com/mexiaosqwq/mc-search-skill.git && \
  cp -r mc-search-skill/skills/mc-search ~/.claude/skills/ && \
  cd ~/.claude/skills/mc-search && pip install -e . && \
  cd ~ && rm -rf mc-search-skill
```

安装后验证：

```bash
mc-search --json search JEI -n 1 --platform mcmod
```

## 主要功能

- **四平台并行搜索**：MC百科 + Modrinth + minecraft.wiki 中/英文
- **全量详情**：`show --full` 获取双平台完整数据（描述、版本、作者、依赖、外部链接）
- **依赖查询**：Modrinth 依赖树 + MC百科联动/前置关系
- **结果融合**：跨平台去重、评分、排序
- **多层缓存**：搜索结果 + 详情页 HTML + wiki 页面，`--cache` 开启

## 快速使用

Claude Code Agent 自动识别触发词（模组、MC百科、wiki 等）调用此 Skill。

### 手动测试

```bash
mc-search --json search 钠
mc-search --json show 钠 --full       # 双平台全量
mc-search --json show sodium --deps   # 依赖查询
mc-search --json wiki 附魔台 -r       # wiki 搜索+读取
mc-search --json search --author Simibubi -n 3
```

## 命令概览

| 命令 | 用途 | 默认值 |
|------|------|--------|
| `search` | 多平台搜索 | `-n 5`, `--timeout 15` |
| `show` | 详情/依赖 | `--full` 双平台 |
| `wiki` | wiki 搜索与阅读 | `-n 5`, `-r` 一步搜索+读取 |

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 输出（Agent 必须） |
| `--cache` | 启用缓存（TTL 1h，含 HTML 页面缓存） |
| `--no-mcmod` / `--no-mr` | 禁用指定平台 |
| `--no-wiki` / `--no-wiki-zh` | 禁用 wiki |

## 项目结构

```
mc-search-skill/
├── skills/mc-search/          # Skill 目录
│   ├── SKILL.md               # Agent 调用定义
│   ├── scripts/
│   │   ├── core.py             # 搜索/解析/缓存 (~3300 行)
│   │   └── cli.py              # CLI 入口 (~1200 行)
│   └── references/            # 命令/错误码/平台对比文档
├── README.md
└── README.en.md
```

## 许可证

MIT License

## 致谢

- [MC 百科](https://www.mcmod.cn/) — 中文 Minecraft 模组百科
- [Modrinth](https://modrinth.com/) — Minecraft 模组平台
- [Minecraft Wiki](https://minecraft.wiki/) — 原版游戏 wiki
