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
用户询问模组/游戏内容/整合包
├── 不知道具体哪个平台 → search（四平台并行）
├── 想一键获取完整信息 → full（推荐，一次调用=搜索+详情+依赖+版本）
├── 想看详细信息 → info / dep / full
├── 想查原版游戏内容 → wiki / read
├── 想查整合包 → search --type modpack / full <整合包名>
├── 想查光影包/材质包 → search --type shader|resourcepack / full <URL>
└── 想查作者作品 → search --author（MC百科）/ author（Modrinth）
```

---

## 常用命令

### 搜索

```bash
mc-search --json search 钠              # 四平台并行
mc-search --json search 钻石剑 --type item  # 物品搜索
mc-search --json search 科技 --type modpack  # 整合包搜索（MC百科 + Modrinth）
mc-search --json search BSL --type shader  # 光影包（仅 Modrinth）
mc-search --json search Faithful --type resourcepack  # 材质包（仅 Modrinth）
mc-search --json search --author Notch  # MC百科作者
```

**说明**：
- 整合包搜索（`--type modpack`）仅在 **MC百科** 和 **Modrinth** 两个平台进行
- 光影包（`--type shader`）和材质包（`--type resourcepack`）**仅 Modrinth** 支持
- minecraft.wiki 不支持整合包/光影包/材质包搜索
- 整合包返回字段包含 `is_official`（是否为 MC百科官方收录）

### 详情

```bash
mc-search --json info 钠                # MC百科详情
mc-search --json info 钠 -m             # 同时查 Modrinth
mc-search --json dep sodium             # Modrinth 依赖树
mc-search --json full sodium            # 完整信息（含版本）
```

### 核心代码模块

- **cli.py** - CLI 入口和命令处理（`_cmd_search`, `_cmd_info`, `_cmd_full`, `_cmd_wiki`, `_cmd_read`, `_cmd_dep`, `_cmd_author`）
- **core.py** - 核心搜索逻辑和 API 调用（`search_mcmod`, `search_modrinth`, `search_wiki`, `get_mod_info`, `get_mod_dependencies`, `read_wiki`, `_curl`, `_parse_mcmod_result`）

### 一键全量（推荐）

```bash
mc-search --json full 钠                # 一次获取模组全部信息
mc-search --json full https://modrinth.com/shader/bsl  # 光影包
mc-search --json full https://modrinth.com/resourcepack/faithful  # 材质包
mc-search --json full https://modrinth.com/modpack/rl-craft  # 整合包
```

### Wiki

```bash
mc-search --json wiki 附魔台            # Wiki 搜索
mc-search --json read https://minecraft.wiki/w/Diamond_Sword  # 读取正文
```

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（推荐） |
| `--cache` | 启用本地缓存（TTL 1小时） |
| `--no-mcmod` | 禁用 MC百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki |
| `--no-wiki-zh` | 禁用中文 wiki |
| `-o <file>` | 输出到文件 |

---

## 项目结构

```
mc-search-skill/
├── .github/
│   └── workflows/
│       ├── claude-agent.yml      # Claude Agent CI/CD 工作流
│       └── claude-review.yml     # 代码审查工作流
├── .gitignore                     # Git 忽略配置
├── LICENSE                        # MIT 许可证
├── README.md                      # 中文说明文档
├── README.en.md                   # 英文说明文档
└── skills/mc-search/
    ├── SKILL.md                   # Agent Skill 定义（触发器+命令）
    ├── pyproject.toml             # Python 包配置（入口：mc-search = scripts.cli:main）
    ├── scripts/
    │   ├── __init__.py
    │   ├── cli.py                 # CLI 入口和命令处理
    │   └── core.py                # 核心搜索逻辑和 API 调用
    └── references/
        ├── result-schema.md       # 返回字段说明
        ├── commands.md            # 命令参考
        └── troubleshooting.md     # 故障排查指南
```

---

## 开发规范

1. **返回格式**：`--json` 模式返回 `list[dict]`，字段见 `references/result-schema.md`
2. **错误处理**：平台调用失败返回空列表，不抛出异常
3. **网络请求**：统一通过 `core._curl()` 发出
4. **依赖**：仅使用 Python 标准库 + curl，无外部依赖
5. **数据处理**：MC百科使用 HTML 解析，Modrinth 使用 REST API

---

## 本地测试

```bash
cd skills/mc-search
pip install -e .
mc-search search 钠
mc-search --json search 钠
mc-search --help
```
