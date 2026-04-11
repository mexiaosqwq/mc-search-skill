# mc-search

> Skill for Minecraft content search

[![Version](https://img.shields.io/github/v/release/mexiaosqwq/mc-search-skill)](https://github.com/mexiaosqwq/mc-search-skill/releases)
[![License](https://img.shields.io/github/license/mexiaosqwq/mc-search-skill)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange)](skills/mc-search/SKILL.md)

[English Documentation →](README.en.md)

---

## 这是什么？

**mc-search** 是一个 **Agent Skill**，让 AI Agent 能够从四大平台搜索和检索 Minecraft 相关内容。

**支持平台**：
- **MC百科** (mcmod.cn) — 中文模组数据库
- **Modrinth** — 现代化模组平台
- **minecraft.wiki** — 原版游戏 Wiki（英文）
- **minecraft.wiki/zh** — 原版游戏 Wiki（中文）

**支持类型**：模组、整合包、光影包、材质包、物品、实体、生物群系、维度

---

## 快速开始

### 方法1：克隆即用（推荐）

```bashbash
# 克隆仓库
git clone https://github.com/mexiaosqwq/mc-search-skill.git
cd mc-search-skill/skills/mc-search

# 安装
pip install -e .
```

安装后，在任何地方都可以使用：
```bashbash
mc-search --json search 钠
```

### 方法2：复制到 Claude Code Skills 目录

如果你想让 Claude Code 自动使用此 Skill：

```bashbash
# 1. 克隆或下载仓库
git clone https://github.com/mexiaosqwq/mc-search-skill.git

# 2. 复制 skill 到 Claude Code 目录
cp -r mc-search-skill/skills/mc-search ~/.claude/skills/

# 3. 在 skill 目录中安装
cd ~/.claude/skills/mc-search
pip install -e .
```

> **重要**：必须在 `skills/mc-search/` 目录中执行 `pip install -e .`，因为 `pyproject.toml` 在那里。

### 独立 CLI 使用

```bashbash
# 搜索模组
mc-search --json search 钠

# 搜光影包（快捷标志）
mc-search --json search BSL --shader

# 搜整合包
mc-search --json search 科技 --modpack

# 获取完整信息（推荐）
mc-search --json show 钠 --full

# 快捷依赖查询
mc-search --json show sodium --deps

# Wiki 搜索
mc-search --json wiki 附魔台

# Wiki 读取页面
mc-search --json wiki https://minecraft.wiki/w/Diamond_Sword
```

### Python API

```bashpython
from scripts.core import search_all, fetch_mod_info  # 注意：是 fetch_mod_info

# 多平台搜索
result = search_all("sodium", fuse=True)

# 获取模组详情
mod = fetch_mod_info("sodium-fabric")
```

---

## 支持的项目类型

| 类型 | 支持平台 | 说明 |
|------|----------|------|
| `mod` | MC百科 + Modrinth | 模组（Fabric/Forge/NeoForge） |
| `item` | MC百科 | 物品/方块 |
| `modpack` | MC百科 + Modrinth | 整合包 |
| `shader` | Modrinth | 光影包 |
| `resourcepack` | Modrinth | 材质包/资源包 |
| `entity` | minecraft.wiki | 实体/生物（仅 wiki 命令） |
| `biome` | minecraft.wiki | 生物群系（仅 wiki 命令） |
| `dimension` | minecraft.wiki | 维度（仅 wiki 命令） |

---

## 三个命令

### search — 多平台搜索

```bashbash
mc-search --json search <关键词> [选项]
```

| 选项 | 说明 |
|------|------|
| `--shader` | 快捷：搜光影包（仅 Modrinth） |
| `--modpack` | 快捷：搜整合包 |
| `--resourcepack` | 快捷：搜材质包（仅 Modrinth） |
| `--type` | 完整类型：mod/item/shader/resourcepack/modpack |
| `--platform` | 平台：all/mcmod/modrinth/wiki/wiki-zh |
| `--author` | 按作者搜索（双平台） |
| `-n` | 每平台最多结果 |

### show — 查看详情/依赖/合成表

```bashbash
mc-search --json show <名称/URL/ID> [选项]
```

| 选项 | 说明 |
|------|------|
| `--full` | 双平台完整信息（MC百科+Modrinth+依赖+版本） |
| `--deps` | 快捷：仅依赖关系 |
| `--recipe` | 合成表（仅 item） |
| `-T/-a/-d/-v/-g/-c/-s/-S` | 字段过滤 |

### wiki — 原版 Wiki 搜索与阅读

```bashbash
mc-search --json wiki <关键词或URL> [选项]
```

| 选项 | 说明 |
|------|------|
| `-r` | 搜索后读取第一个结果正文 |
| `-n` | 最多结果 |
| `-p` | 段落数（URL读取时生效） |

> **注意**：`--json` 标志必须放在子命令**之前**。

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（推荐） |
| `-o, --output` | 输出到文件 |
| `--cache` | 启用本地缓存（TTL 1 小时，需显式添加此参数） |
| `--no-mcmod` | 禁用 MC百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki（英文） |
| `--no-wiki-zh` | 禁用中文 wiki |

---

## 架构

```
skills/mc-search/
├── SKILL.md          # Claude Code Skill 定义（用户指南）
├── scripts/
│   ├── core.py       # 核心搜索逻辑
│   └── cli.py        # CLI 入口（3命令扁平结构）
├── references/       # 详细文档
└── pyproject.toml    # Python 包配置
```

---

## v5.0.0 改进

- 命令合并：8 命令 → 3 扁平命令（search/show/wiki）
- 快捷标志：`--shader`/`--modpack`/`--resourcepack`
- MC百科失败自动回退 Modrinth
- Wiki 搜索修复（不再误过滤原版内容）
- 统一错误处理

## 许可证

MIT License

## 致谢

- [MC百科](https://www.mcmod.cn/) — 中文模组数据库
- [Modrinth](https://modrinth.com/) — 现代化模组平台
- [Minecraft Wiki](https://minecraft.wiki/) — 原版游戏 Wiki
