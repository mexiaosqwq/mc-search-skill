# mcmod-info

Minecraft 模组 + 游戏内容信息查询工具，三平台并行搜索。

**同时搜索**：MC百科（中文模组）+ Modrinth（英文 mod）+ minecraft.wiki（原版内容）。

## 安装

```bash
pip install mcmod-info
```

或使用 [pipx](https://pypa.github.io/pipx/) 安装（推荐）：

```bash
pipx install mcmod-info
```

依赖：**Python 3.8+** 和 **curl**（系统自带，无需 API key）。

## 快速开始

```bash
# 三平台并行搜索
mcmod-search search 钠

# MC百科物品搜索
mcmod-search search 钻石剑 --type item

# MC百科作者搜索
mcmod-search search --author Notch

# minecraft.wiki 搜索
mcmod-search wiki 附魔

# 读取 wiki 页面正文
mcmod-search read https://minecraft.wiki/w/Diamond_Sword

# Modrinth 搜索
mcmod-search mr sodium

# 查看 mod 依赖树
mcmod-search dep sodium

# 检查更新
mcmod-search update-check sodium --installed 0.4.1

# 按作者搜索（Modrinth）
mcmod-search author jellysquid_

# MC百科模组详情
mcmod-search info https://www.mcmod.cn/class/23352.html
```

## 全局选项

| 选项 | 说明 |
|------|------|
| `--cache` | 启用本地缓存（TTL 1小时） |
| `--no-mcmod` | 禁用 MC百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki |
| `--json` | 以 JSON 格式输出 |
| `-o <file>` | 输出到文件而非 stdout |

## Claude Code Skill

将此目录放入 Claude Code 的 `~/.claude/skills/` 目录，即可在对话中调用。

```bash
# 查看完整命令列表
mcmod-search --help
```

## 详细文档

- [SKILL.md](skills/mcmod-info/SKILL.md) — Claude Code Skill 完整定义
- [references/](skills/mcmod-info/references/) — API 参考和故障排查

## 支持的平台

| 平台 | 说明 | 限制 |
|------|------|------|
| MC百科 (mcmod.cn) | 中文模组/物品搜索 | 每请求间隔 0.3s |
| Modrinth | 英文 mod/光影/材质包搜索 | 360 req/hr |
| minecraft.wiki | 原版游戏内容 wiki | 无 |

## 许可证

CC0-1.0 Universal (Public Domain）
