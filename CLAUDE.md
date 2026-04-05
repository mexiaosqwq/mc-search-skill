# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# mc-search 项目指南

## 项目概述

Minecraft 聚合搜索工具，供 AI Agent 调用。

**四大平台：**
- MC百科 (mcmod.cn) — 中文模组/物品/整合包
- Modrinth — 英文 mod/光影/材质包/整合包
- minecraft.wiki — 原版游戏内容 wiki（英文）
- minecraft.wiki/zh — 原版游戏内容 wiki（中文）

**支持类型：**
- mod（模组）、item（物品）、modpack（整合包）
- shader（光影包）、resourcepack（材质包/资源包）
- entity（实体）、biome（生物群系）、dimension（维度）

---

## 代码结构

实际代码位于 `skills/mc-search/` 子目录中：

```
skills/mc-search/
├── SKILL.md              # Agent 接口定义（核心文档）
├── CLAUDE.md             # 项目指南（本文件）
├── pyproject.toml        # Python 包配置（定义入口 mc-search = scripts.cli:main）
├── scripts/
│   ├── cli.py            # CLI 入口和命令处理
│   └── core.py           # 核心搜索逻辑和 API 调用
└── references/
    ├── result-schema.md  # 结果字段说明
    ├── commands.md       # 命令参考
    └── troubleshooting.md # 故障排查指南
```

## Agent 调用方式

工具名：`mc-search`（通过 Bash 执行）

**始终使用 `--json`** 获取结构化输出：

```bash
mc-search --json search <关键词>
mc-search --json info <模组名>
mc-search --json full <模组名>
```

> **重要**：全局选项（`--json`、`--cache`、平台开关）必须放在子命令 **之前**。

## 核心功能模块

### 搜索功能 (cli.py:_cmd_search)
- 四平台并行搜索
- 支持类型过滤 (--type)
- 支持作者搜索 (--author)
- 支持结果融合 (--fuse)

### 项目详情 (cli.py:_cmd_info, _cmd_full)
- MC百科详情解析 (core.py:_parse_mcmod_result)
- Modrinth API 调用 (core.py:get_mod_info)
- 依赖关系查询 (core.py:get_mod_dependencies)

### Wiki 功能 (cli.py:_cmd_wiki, _cmd_read)
- minecraft.wiki 搜索
- 页面正文读取和解析

### 核心 API (core.py)
- `_curl()` - 统一 HTTP 请求
- `search_mcmod()` - MC百科搜索
- `search_modrinth()` - Modrinth 搜索
- `search_wiki()` / `search_wiki_zh()` - Wiki 搜索
- `get_mod_info()` - 获取 Modrinth 详情
- `_parse_mcmod_result()` - 解析 MC百科页面

## 常用命令

### 搜索

```bash
mc-search --json search 钠              # 四平台并行
mc-search --json search 钻石剑 --type item  # 物品搜索
mc-search --json search 科技 --type modpack  # 整合包搜索
mc-search --json search BSL --type shader  # 光影包（仅 Modrinth）
mc-search --json search --author Notch  # MC百科作者
```

### 详情

```bash
mc-search --json info 钠                # MC百科详情
mc-search --json full sodium            # 完整信息（推荐）
mc-search --json dep sodium             # Modrinth 依赖树
```

### Wiki

```bash
mc-search --json wiki 附魔台            # Wiki 搜索
mc-search --json read https://minecraft.wiki/w/Diamond_Sword  # 读取正文
```

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（推荐） |
| `--cache` | 启用本地缓存（TTL 1小时） |
| `--no-mcmod` | 禁用 MC百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki |
| `--no-wiki-zh` | 禁用中文 wiki |

## 开发规范

1. **返回格式**：`--json` 模式返回 `list[dict]`，字段见 `references/result-schema.md`
2. **错误处理**：平台调用失败返回空列表，不抛出异常
3. **网络请求**：统一通过 `core._curl()` 发出
4. **依赖**：仅使用 Python 标准库 + curl，无外部依赖
5. **数据处理**：MC百科使用 HTML 解析，Modrinth 使用 REST API

## 本地测试

```bash
cd skills/mc-search
pip install -e .
mc-search search 钠
mc-search --json search 钠
mc-search --help
```
