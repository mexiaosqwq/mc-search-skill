---
name: mc-search
version: "5.3.0-dev"
description: "Minecraft 内容搜索 - 模组/整合包/光影/材质包/wiki 五平台聚合"
license: MIT
context: open
user-invocable: true
allowed-tools: [Bash]
triggers:
  - "模组"
  - "整合包"
  - "光影包"
  - "材质包"
  - "资源包"
  - "Minecraft 模组"
  - "MC 模组"
  - "原版 wiki"
  - "Minecraft Wiki"
  - "MC百科"
  - "Modrinth"
  - "我的世界"
  - "我的世界模组"
  - "mc模组"
  - "minecraft 攻略"
---

# mc-search

Minecraft 聚合搜索 Skill。五平台并行（MC百科 / Modrinth / bbsmc / wiki EN / wiki ZH），返回融合结果。所有操作通过 CLI 单行命令。

## 搜索

```bash
mcsearch search 机械动力 --json -n 2
mcsearch search sodium --json -n 3 --type mod
mcsearch search 光影 --json --type shader
mcsearch search 整合包 --json --type modpack
```

`--type`: `mod`(默认) / `item` / `modpack` / `shader` / `resourcepack` / `vanilla`
`-n`: 每平台最大结果数（默认 5）
`--platform`: 限定平台 `all`(默认) / `mcmod` / `modrinth` / `wiki` / `wiki-zh`

## 详情 / 依赖

```bash
mcsearch show sodium --json              # 默认：按名查 Modrinth
mcsearch show sodium --deps --json       # 仅依赖
mcsearch show sodium --full --json       # 双平台全量
```

## Wiki

```bash
mcsearch wiki 附魔 --json                          # 搜索
mcsearch wiki "https://zh.minecraft.wiki/w/铁砧" --json  # URL 直接读
mcsearch wiki 红石 -r --json                       # 搜+读正文
```

## 平台 / 缓存

```bash
mcsearch --cache search ...               # 全局缓存（TTL 1h）
mcsearch --no-mcmod search ...            # 禁用 MC百科
mcsearch search ... --platform modrinth   # 限单平台
```

## 返回字段

`--json` 输出 `{"results": [{hit}], "platform_stats": {...}}`。
Hit 字段：`name`, `name_zh`, `name_en`, `url`, `source`, `source_id`, `_score`, `_sources`, `snippet`, `description`。
失败信号：`{"_error": "not_found"}` / `{"_error": "parse_failed"}`。

## 错误处理

| 现象 | 对策 |
|------|------|
| 无结果 | 换更短关键词 或 `--platform modrinth` 限单平台 |
| MC百科 被拦 | 自动降级，`_error: parse_failed` 标记 |
| 结果太多 | `-n 3` 限制 |
