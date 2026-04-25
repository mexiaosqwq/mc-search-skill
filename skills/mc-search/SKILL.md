---
name: mc-search
version: "5.1.0"
description: "Minecraft 内容搜索 - 模组/整合包/光影/材质包/wiki 四平台聚合"
license: MIT
context: open
user-invocable: true
allowed-tools: [Bash]
triggers:
  - "模组"
  - "整合包"
  - "光影包"
  - "材质包"
  - "Minecraft 模组"
  - "MC 模组"
  - "原版 wiki"
---

# mc-search

Minecraft 内容搜索 Skill。当用户询问 Minecraft 模组、整合包、光影、材质包或原版游戏内容时，使用此工具获取信息。

## 使用规则

**必须使用 `--json`** 获取结构化输出：

```bash
mc-search --json search <关键词>      # 模糊搜索
mc-search --json show <名称> --full   # 查看详情
mc-search --json wiki <关键词>        # 查原版内容
```

## 命令

### search — 多平台搜索

```bash
mc-search --json search <关键词> [--shader|--modpack|--resourcepack] [--author <作者>]
```

### show — 查看详情

```bash
mc-search --json show <名称/URL/ID> [--full|--deps|--recipe] [--skip-dep] [--skip-mr]
```

### wiki — 原版 Wiki

```bash
mc-search --json wiki <关键词> [-r]
```

## 返回格式

所有命令返回 JSON。成功时返回数据对象，失败时返回：

```json
{"error": "错误码", "message": "错误信息"}
```

字段定义见 [result-schema.md](references/result-schema.md)。

## 平台说明

- **MC 百科** — 中文模组，联动信息全
- **Modrinth** — 英文模组，依赖准确，光影/材质包唯一来源
- **minecraft.wiki** — 原版游戏内容（方块、物品、机制）

详见 [platform-comparison.md](references/platform-comparison.md)。
