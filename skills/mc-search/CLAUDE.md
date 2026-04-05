# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# mc-search 项目指南

## 项目概述

Minecraft 聚合搜索工具，供 AI Agent 调用。

**四大平台：**
- MC百科 (mcmod.cn) — 中文模组/物品
- Modrinth — 英文 mod/光影/材质包
- minecraft.wiki — 原版游戏内容 wiki（英文）
- minecraft.wiki/zh — 原版游戏内容 wiki（中文）

---

## Agent 工具接口

工具名：`mc-search`（通过 Bash 执行）

### 首选调用方式

**始终使用 `--json`** 获取结构化输出：

```bash
mc-search --json search <关键词>
mc-search --json info <模组名>
mc-search --json full <模组名>
```

> **重要**：全局选项（`--json`、`--cache`、平台开关）必须放在子命令 **之前**。

---

## 决策树

```
用户询问模组/游戏内容
├── 不知道具体哪个平台 → search（四平台并行）
├── 想一键获取完整信息 → full（推荐，一次调用=搜索+详情+依赖+版本）
├── 想看详细信息 → info / dep / full
├── 想查原版游戏内容 → wiki / read
└── 想查作者作品 → search --author（MC百科）/ author（Modrinth）
```

---

## 常用命令

### 搜索

```bash
mc-search --json search 钠              # 四平台并行
mc-search --json search 钻石剑 --type item  # 物品搜索
mc-search --json search --author Notch  # MC百科作者
```

### 详情

```bash
mc-search --json info 钠                # MC百科详情
mc-search --json info 钠 -m             # 同时查 Modrinth
mc-search --json dep sodium             # Modrinth 依赖树
mc-search --json full sodium            # 完整信息（含版本）
```

### 一键全量（推荐）

```bash
mc-search --json full 钠                # 一次获取全部信息
mc-search --json full 钠 --installed 0.5.0  # 带版本检查
```

### Wiki

```bash
mc-search --json wiki 附魔台            # 原版内容搜索
mc-search --json read https://minecraft.wiki/w/Diamond_Sword  # 读取正文
```

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（Agent 推荐） |
| `--cache` | 启用本地缓存（TTL 1小时） |
| `--no-mcmod` | 禁用 MC百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki |
| `--no-wiki-zh` | 禁用中文 wiki |
| `-o <file>` | 输出到文件 |

---

## 目录结构

```
skills/mc-search/
├── SKILL.md              # Agent 接口定义（核心文档）
├── pyproject.toml        # Python 包配置
├── scripts/
│   ├── cli.py            # CLI 入口
│   └── core.py           # 核心搜索逻辑
└── references/
    ├── result-schema.md  # 结果字段说明
    ├── mcmod-api.md      # MC百科 API
    └── modrinth-api.md   # Modrinth API
```

---

## 开发规范

1. **返回格式**：`--json` 模式返回 `list[dict]`，字段见 `references/result-schema.md`
2. **错误处理**：平台调用失败返回空列表，不抛出异常
3. **网络请求**：统一通过 `core._curl()` 发出
4. **依赖**：仅使用 Python 标准库 + curl，无外部依赖
5. **Agent 调用**：优先使用 `--json` 便于解析

---

## 本地测试

```bash
pip install -e .
mc-search search 钠
mc-search --help
```
