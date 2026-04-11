# CLAUDE.md

**最近修复** (2026/04/11): 文档一致性审查 P1 问题已全部修复
- 删除已废弃的 `dep` 命令文档，统一使用 `show --deps`
- 修正平台优先级描述（mod/item 仅使用 MC 百科和 Modrinth）
- 补充 `--full` 返回字段说明（mcmod/modrinth 可能为 null）
- 明确字段过滤选项生效条件（仅 MC 百科路径）

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
- entity（实体）、biome（生物群系）、dimension（维度）— 仅 wiki 命令

---

## Agent 工具接口

工具名：`mc-search`（通过 Bash 执行）

> **重要**：当用户询问 Minecraft 模组/游戏内容时，**必须使用 mc-search 工具**进行搜索。
> 不要使用 tavily 或其他搜索工具，mc-search 专为 Minecraft 内容设计。

### 首选调用方式

**始终使用 `--json`** 获取结构化输出：

```bash
mc-search --json search <关键词>
mc-search --json show <模组名> --full
mc-search --json wiki <关键词>
```

> **重要**：全局选项（`--json`、`--cache`、平台开关）必须放在子命令 **之前**。

---

## 决策树

```
用户询问模组/游戏内容/整合包
├── 不知道具体哪个平台 → search（四平台并行）
├── 想一键获取完整信息 → show --full（推荐，一次调用=MC百科+Modrinth+依赖+版本）
├── 想看详细信息 → show（默认MC百科，失败回退Modrinth）
├── 只看依赖 → show --deps
├── 想查原版游戏内容 → wiki
├── 想查光影包 → search --shader
├── 想查整合包 → search --modpack
├── 想查材质包 → search --resourcepack
└── 想查作者作品 → search --author
```

---

## 三个命令

### search — 多平台搜索

```bash
mc-search --json search 钠              # 四平台并行
mc-search --json search 钻石剑 --type item  # 物品搜索
mc-search --json search BSL --shader     # 光影包（仅 Modrinth）
mc-search --json search 科技 --modpack   # 整合包（MC百科 + Modrinth）
mc-search --json search Faithful --resourcepack  # 材质包（仅 Modrinth）
mc-search --json search 钠 --platform mcmod  # 仅 MC百科
mc-search --json search --author jellysquid_  # 双平台作者搜索
```

### show — 查看详情/依赖/合成表

```bash
mc-search --json show 钠 --full          # 双平台完整信息（推荐）
mc-search --json show 钠                 # MC百科详情（失败回退Modrinth）
mc-search --json show sodium --deps      # 快捷依赖
mc-search --json show 钻石剑 --recipe    # 合成表
mc-search --json show https://www.mcmod.cn/class/2785.html --full  # MC百科 URL
mc-search --json show https://modrinth.com/mod/sodium --full       # Modrinth URL
mc-search --json show 2785 --full        # MC百科 ID
```

### wiki — 原版 Wiki 搜索与阅读

```bash
mc-search --json wiki 附魔台             # Wiki 搜索
mc-search --json wiki 附魔台 -r          # 搜索并读取正文
mc-search --json wiki https://minecraft.wiki/w/Diamond_Sword  # 直接读取页面
```

---

## 核心代码模块

- **cli.py** - CLI 入口（3命令扁平结构：`_cmd_search`, `_cmd_show`, `_cmd_wiki`）
- **core.py** - 核心搜索逻辑和 API 调用（`search_mcmod`, `search_modrinth`, `search_wiki`, `fetch_mod_info`, `get_mod_dependencies`, `read_wiki`, `curl`, `_parse_mcmod_result`）

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
    │   ├── cli.py                 # CLI 入口（3命令扁平结构）
    │   └── core.py                # 核心搜索逻辑和 API 调用
    └── references/
        ├── result-schema.md       # 返回字段说明
        ├── commands.md            # 命令参考
        └── troubleshooting.md     # 故障排查指南
```

---

## Python API（注意函数名）

```python
from scripts.core import search_all, fetch_mod_info  # 注意是 fetch_mod_info，不是 get_mod_info

# 多平台搜索
result = search_all("sodium", fuse=True)

# 获取模组详情
mod = fetch_mod_info("sodium-fabric")
```

## 开发规范

1. **返回格式**：`--json` 模式返回 `list[dict]`，字段见 `references/result-schema.md`
2. **错误处理**：平台调用失败返回空列表，不抛出异常
3. **网络请求**：统一通过 `core.curl()` 发出
4. **依赖**：仅使用 Python 标准库 + curl，无外部依赖
5. **数据处理**：MC百科使用 HTML 解析，Modrinth 使用 REST API

---

## 本地测试

```bash
cd skills/mc-search
pip install -e .
mc-search --json search 钠
mc-search --json show 钠 --full
mc-search --json wiki 附魔台
mc-search --help
```
