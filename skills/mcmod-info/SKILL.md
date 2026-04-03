---
name: mcmod-info
description: Minecraft 模组和游戏内容信息查询 CLI，同时从 MC百科、Modrinth、minecraft.wiki 三平台返回结果。触发场景：搜模组、搜物品、搜 wiki、查依赖、查版本更新。
license: Complete terms in LICENSE
context: open
user-invocable: true
---

# mcmod-info

三平台并行搜索：MC百科（中文模组）+ Modrinth（英文 mod）+ minecraft.wiki（原版内容）。

## 命令

| 命令 | 说明 |
|------|------|
| `search <关键词>` | 三平台并行搜索 |
| `search <关键词> --type item` | MC百科物品搜索 |
| `search <关键词> --author <名>` | MC百科作者搜索 |
| `wiki <关键词>` | minecraft.wiki 搜索 |
| `wiki <关键词> -r` | 搜索并读取前 4 段正文 |
| `read <url>` | 读取 wiki 页面正文（`-p N` 段落数） |
| `mr <关键词>` | Modrinth 单搜 |
| `dep <mod_id>` | Modrinth 依赖树 |
| `update-check <mod_id> --installed <ver>` | 版本对比 |
| `author <username>` | Modrinth 作者搜索 |
| `info <mod>` | MC百科模组详情 |

## 全局选项

`--cache` 缓存 / `--no-mr` / `--no-mcmod` / `--no-wiki` 禁用平台 / `--json` 输出 / `-o <file>` 写入文件

## 环境

Python 3.8+、curl 命令，无 API key 要求。

## 详细文档

- `README.md` — 完整使用指南
- `references/` — API 参考文档
