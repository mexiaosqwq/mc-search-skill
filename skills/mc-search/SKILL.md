---
name: mc-search
version: "0.3.0"
description: "Minecraft 聚合搜索工具。触发：用户询问模组信息、物品资料、mod 依赖、版本对比、原版游戏内容、作者作品。"
license: MIT
context: open
user-invocable: true
allowed-tools: [Bash, Read, Glob, Grep]
---

# mc-search

Minecraft 内容聚合搜索。四平台并行：MC百科、Modrinth、minecraft.wiki（英文/中文）。

## 执行流程

```
用户提问 → 分析意图选命令 → Bash执行mc-search → 解析JSON呈现
```

## 命令速查

| 意图 | 命令 | 说明 |
|------|------|------|
| 模组/物品搜索 | `mc-search --json search <关键词>` | 四平台并行，默认搜模组 |
| 物品搜索 | `mc-search --json search <关键词> --type item` | 搜物品/方块 |
| **完整信息** | `mc-search --json full <模组名>` | **推荐**：一次返回详情+依赖+版本 |
| 依赖树 | `mc-search --json dep <mod_slug>` | Modrinth 依赖 |
| 版本检查 | `mc-search --json update-check <slug> --installed <版本>` | 是否有更新 |
| 原版内容 | `mc-search --json wiki <关键词>` | minecraft.wiki |
| 读取wiki | `mc-search --json wiki <关键词> -r` | 搜索+读取正文 |
| 作者作品 | `mc-search --json search --author <作者>` | MC百科作者 |
| Modrinth作者 | `mc-search --json author <用户名>` | Modrinth 作者 |

## 关键字段

**search 返回**：`name`, `name_en`, `url`, `source`, `author`, `description`, `status`

**full 返回**：`mcmod`（详情）, `modrinth`（下载量/版本）, `dependencies`, `update_check`

## 版本优先级

当 MC百科和 Modrinth 版本不一致时，**以 Modrinth 为准**（官方发布平台，更新及时）。

## 全局选项

放在子命令前：`--json`（必须）、`--cache`、`--no-mcmod`、`--no-mr`、`--no-wiki`

## 初始化

```bash
pip install -e skills/mc-search
```

## 详细文档

- [result-schema.md](references/result-schema.md) — 返回字段完整定义
- [troubleshooting.md](references/troubleshooting.md) — 错误处理
