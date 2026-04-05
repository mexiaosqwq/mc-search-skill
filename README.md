# mc-search

> Claude Code Skill for Minecraft content search

[![Version](https://img.shields.io/github/v/release/mexiaosqwq/mc-search-skill)](https://github.com/mexiaosqwq/mc-search-skill/releases)
[![License](https://img.shields.io/github/license/mexiaosqwq/mc-search-skill)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange)](skills/mc-search/SKILL.md)

---

## 这是什么？

**mc-search** 是一个 **Claude Code Skill**，让 AI Agent 能够从四大平台搜索和检索 Minecraft 相关内容。

**支持平台**：
- **MC百科** (mcmod.cn) — 中文模组数据库
- **Modrinth** — 现代化模组平台
- **minecraft.wiki** — 原版游戏 Wiki（英文）
- **minecraft.wiki/zh** — 原版游戏 Wiki（中文）

**支持类型**：模组、整合包、光影包、材质包、物品、实体、生物群系、维度

---

## 快速开始

### 安装

```bash
cd skills/mc-search
pip install -e .
```

### 在 Claude Code 中使用

当你询问 Minecraft 相关内容时，Claude Code 会自动调用此 Skill：

- "帮我查一下 Sodium 模组"
- "搜索钻石剑的 Wiki 信息"
- "查找 RLCraft 整合包"

或者手动触发：
```
/mc-search search 钠
```

### 独立 CLI 使用

```bash
# 搜索模组
mc-search --json search 钠

# 获取完整信息
mc-search --json full sodium

# 搜索 Wiki
mc-search --json wiki 钻石剑

# 按类型搜索
mc-search --json search BSL --type shader
mc-search --json search RLCraft --type modpack
```

### Python API

```python
from scripts.core import search_all, get_mod_info

# 多平台搜索
result = search_all("sodium", fuse=True)

# 获取模组详情
mod = get_mod_info("sodium-fabric")
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
| `entity` | minecraft.wiki | 实体/生物 |
| `biome` | minecraft.wiki | 生物群系 |
| `dimension` | minecraft.wiki | 维度 |

---

## 常用命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `search` | 多平台搜索 | `mc-search --json search 钠` |
| `full` | 获取完整模组信息 | `mc-search --json full sodium` |
| `info` | MC百科详情 | `mc-search --json info 钠` |
| `wiki` | 搜索 minecraft.wiki | `mc-search --json wiki 附魔` |
| `read` | 读取 Wiki 页面 | `mc-search --json read <url>` |
| `dep` | Modrinth 依赖关系 | `mc-search --json dep sodium` |
| `author` | 按作者搜索 | `mc-search --json author jellysquid_` |

> **注意**：`--json` 标志必须放在子命令**之前**。

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（推荐） |
| `--cache` | 启用本地缓存（TTL 1小时） |
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
│   └── cli.py        # CLI 入口
├── references/       # 详细文档
└── pyproject.toml    # Python 包配置
```

---

## v4.5.0 改进

- Clean Code 重构（15 个问题修复）
- 硬编码清理（类型常量提取）
- 数据完整性增强（Modrinth 字段）
- 测试：95/95 通过，0 失败

详见 [RELEASE-v4.5.md](skills/mc-search/RELEASE-v4.5.md)

---

## 开发

```bash
git clone https://github.com/mexiaosqwq/mc-search-skill.git
cd mc-search-skill
pip install -e .

# 运行测试
python3 -m py_compile scripts/core.py scripts/cli.py
```

---

## 许可证

MIT License

## 致谢

- [MC百科](https://www.mcmod.cn/) — 中文模组数据库
- [Modrinth](https://modrinth.com/) — 现代化模组平台
- [Minecraft Wiki](https://minecraft.wiki/) — 原版游戏 Wiki
