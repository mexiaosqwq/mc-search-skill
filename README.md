# mc-search

Minecraft 内容聚合搜索工具，支持四平台并行搜索。

[![Version](https://img.shields.io/github/v/release/mexiaosqwq/mc-search-skill)](https://github.com/mexiaosqwq/mc-search-skill/releases)
[![License](https://img.shields.io/github/license/mexiaosqwq/mc-search-skill)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange)](SKILL.md)

[English Documentation →](README.en.md)

## 项目简介

mc-search 是一个为 **Claude Code** 设计的 Minecraft 内容搜索 Skill，可以并行搜索四个平台：

- **MC 百科** (mcmod.cn) — 中文模组/物品/整合包
- **Modrinth** — 英文 mod/光影/材质包/整合包
- **minecraft.wiki** — 原版游戏内容 wiki（英文）
- **minecraft.wiki/zh** — 原版游戏内容 wiki（中文）

支持搜索模组、整合包、光影包、材质包、物品，以及实体、生物群系、维度等游戏内容。

## 安装到 Claude Code

将 `skills/mc-search` 目录复制到 Claude Code 的 `skills` 目录：

```bash
# 方式 1：克隆后安装
git clone https://github.com/mexiaosqwq/mc-search-skill.git
cp -r mc-search-skill/skills/mc-search ~/.claude/skills/

# 方式 2：直接从仓库复制
cd ~/.claude/skills
git clone https://github.com/mexiaosqwq/mc-search-skill.git temp
cp -r temp/skills/mc-search .
rm -rf temp
```

## 主要功能

- **四平台搜索**：MC 百科、Modrinth、minecraft.wiki（英文/中文）
- **多类型支持**：模组、整合包、光影包、材质包、物品、实体、生物群系、维度
- **结果融合**：跨平台结果自动排序和合并
- **依赖查询**：自动获取模组依赖关系
- **合成表查询**：物品合成配方查询
- **本地缓存**：可选缓存机制，减少网络请求

## 快速使用

**Claude Code 会自动识别并调用此 skill**，当用户询问以下任何内容时：

```
"搜索机械动力"
"钠模组信息"
"BSL 光影怎么样"
"wiki 附魔台"
"RLCraft 整合包"
```

### 手动测试

```bash
cd ~/.claude/skills/mc-search
mc-search --json search 钠
mc-search --json show 钠 --full
mc-search --json wiki 附魔台
```

## 命令说明

### search — 多平台搜索

```bash
mc-search --json search <关键词> [选项]
```

| 选项 | 说明 |
|------|------|
| `--shader` | 光影包搜索（仅 Modrinth） |
| `--modpack` | 整合包搜索 |
| `--resourcepack` | 材质包搜索（仅 Modrinth） |
| `--type` | 内容类型：mod/item/shader/resourcepack/modpack |
| `--platform` | 平台：all/mcmod/modrinth/wiki/wiki-zh |
| `--author` | 按作者搜索（双平台） |
| `-n` | 每平台最多结果数 |
| `--timeout <秒>` | 超时时间（默认 12 秒） |

### show — 查看详情/依赖/合成表

```bash
mc-search --json show <名称/URL/ID> [选项]
```

| 选项 | 说明 |
|------|------|
| `--full` | 双平台完整信息 |
| `--deps` | 依赖关系 |
| `--recipe` | 合成表（仅物品） |

### wiki — 原版 Wiki 搜索与阅读

```bash
mc-search --json wiki <关键词或 URL> [选项]
```

| 选项 | 说明 |
|------|------|
| `-r` | 搜索后读取正文 |
| `-n` | 最多结果数 |
| `-p` | 读取段落数 |

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（推荐） |
| `-o, --output` | 输出到文件 |
| `--cache` | 启用本地缓存（TTL 1 小时） |
| `--no-mcmod` | 禁用 MC 百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用英文 wiki |
| `--no-wiki-zh` | 禁用中文 wiki |

## 项目结构

```
mc-search-skill/
├── SKILL.md                    # Skill 定义（根目录）
├── skills/
│   └── mc-search/              # Skill 目录（放入 Claude Code）
│       ├── SKILL.md            # Claude Code Skill 定义
│       ├── pyproject.toml      # Python 包配置
│       ├── scripts/
│       │   ├── core.py         # 核心搜索逻辑
│       │   └── cli.py          # CLI 入口
│       └── references/         # 详细文档
└── README.md
```

## 许可证

MIT License

## 致谢

感谢以下平台提供的数据支持：

- [MC 百科](https://www.mcmod.cn/)
- [Modrinth](https://modrinth.com/)
- [Minecraft Wiki](https://minecraft.wiki/)
