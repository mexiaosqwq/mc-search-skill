---
name: mc-search
version: "4.0.0"
description: "Minecraft 聚合搜索工具。支持 MC百科、Modrinth、minecraft.wiki 中英双站。搜索模组/整合包/光影包/材质包/物品/实体，JSON 结构化输出。"
license: MIT
context: open
user-invocable: true
allowed-tools: [Bash]
triggers:
  - "搜索.*模组"
  - "搜索.*整合包"
  - "搜索.*光影"
  - "搜索.*材质包"
  - "搜索.*生物群系"
  - "搜索.*维度"
  - "搜索.*实体"
  - "查询.*mod"
  - "mod.*依赖"
  - "wiki.*搜索"
  - "Modrinth.*搜索"
---

# mc-search

Minecraft 内容聚合搜索工具，支持 **四平台并行搜索**：
- **MC百科** (mcmod.cn) — 中文模组/物品/整合包
- **Modrinth** — 英文 mod/光影包/材质包/整合包
- **minecraft.wiki** — 原版游戏内容 wiki（英文）
- **minecraft.wiki/zh** — 原版游戏内容 wiki（中文）

## 支持的项目类型

| 类型 | 说明 | 支持平台 | 典型用途 |
|------|------|----------|----------|
| `mod` | 模组 | MC百科 + Modrinth | 搜索 Fabric/Forge 模组 |
| `item` | 物品/方块 | MC百科 | 查询物品属性、合成表 |
| `modpack` | 整合包 | MC百科 + Modrinth | 搜索整合包（如 RLCraft） |
| `shader` | 光影包 | Modrinth | 搜索着色器（如 BSL、Complementary） |
| `resourcepack` | 材质包/资源包 | Modrinth | 搜索材质包（如 Faithful） |
| `entity` | 实体/生物 | minecraft.wiki | 查询原版生物信息 |
| `biome` | 生物群系 | minecraft.wiki | 查询群系信息 |
| `dimension` | 维度 | minecraft.wiki | 查询维度信息（下界/末地） |

---

## 快速开始

**执行格式**：
```bash
mc-search --json <子命令> <参数>
```

> ⚠️ **`--json` 必须放在最前面**（全局选项优先）

### 快速决策表

| 用户意图 | 推荐命令 | 示例 |
|----------|----------|------|
| 知道名称，要完整信息 | `full <名称>` | `mc-search --json full 钠` |
| 不确定名称，模糊搜索 | `search <关键词>` | `mc-search --json search 钠` |
| 搜索整合包 | `search --type modpack` | `mc-search --json search RLCraft --type modpack` |
| 搜索光影包 | `search --type shader` | `mc-search --json search BSL --type shader` |
| 搜索材质包 | `search --type resourcepack` | `mc-search --json search Faithful --type resourcepack` |
| 查原版游戏内容 | `wiki <关键词>` | `mc-search --json wiki 附魔台` |
| 查 Modrinth 依赖 | `dep <slug>` | `mc-search --json dep sodium` |
| 查作者作品 | `search --author` | `mc-search --json search --author Notch` |

---

## 命令参考

### 1. search — 多平台并行搜索

**用途**：不确定具体模组名时的模糊搜索，支持类型过滤。

```bash
mc-search --json search <关键词> [选项]
```

**选项**：
| 选项 | 说明 | 默认 |
|------|------|------|
| `--type <类型>` | 类型过滤：`mod`/`item`/`modpack`/`shader`/`resourcepack`/`entity` | `mod` |
| `-n <数量>` | 每平台最多结果数 | `3` |
| `-t <秒>` | 超时时间 | `12` |
| `--author <作者>` | MC百科作者搜索 | - |
| `--fuse` | 融合四平台结果去重 | - |

**示例**：
```bash
# 通用搜索
mc-search --json search 钠

# 类型过滤
mc-search --json search 钻石剑 --type item
mc-search --json search 科技 --type modpack
mc-search --json search BSL --type shader

# 作者搜索
mc-search --json search --author Notch
```

**返回字段**（JSON）：
```json
[
  {
    "name": "钠",
    "name_en": "Sodium",
    "name_zh": "钠",
    "url": "https://www.mcmod.cn/class/2785.html",
    "source": "mcmod.cn",
    "type": "mod",
    "snippet": "现代化优化模组...",
    "categories": ["优化Mod"]
  }
]
```

### 2. full — 一键获取完整信息

**用途**：知道模组/整合包名称或 URL，获取所有详细信息（推荐首选）。

```bash
mc-search --json full <名称或URL> [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `--skip-dep` | 跳过依赖查询（加速） |
| `--skip-mr` | 跳过 Modrinth 查询（加速） |

**示例**：
```bash
# 模组
mc-search --json full 钠

# 整合包
mc-search --json full RLCraft
mc-search --json full https://www.mcmod.cn/modpack/339.html

# 光影包
mc-search --json full https://modrinth.com/shader/complementary-reimagined

# 材质包
mc-search --json full https://modrinth.com/resourcepack/faithful
```

**返回字段**（JSON 对象）：
```json
{
  "mcmod": {
    "name_zh": "钠",
    "name_en": "Sodium",
    "status": "活跃",
    "author": "JellySquid",
    "categories": ["优化Mod"],
    "supported_versions": ["1.20.1", "1.19.4"]
  },
  "modrinth": {
    "downloads": 25000000,
    "followers": 50000,
    "latest_version": "0.6.0",
    "loaders": ["fabric", "neoforge"],
    "client_side": "required",
    "server_side": "optional"
  },
  "dependencies": {
    "deps": {},
    "required_count": 0,
    "optional_count": 0
  }
}
```

### 3. info — MC百科详情

**用途**：查看 MC百科 模组/物品的详细信息。

```bash
mc-search --json info <名称或URL或ID> [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `-T` | 仅名称/别名 |
| `-a` | 仅作者 |
| `-d` | 仅前置/联动模组 |
| `-v` | 仅支持版本 |
| `-g` | 仅截图/封面 |
| `-c` | 仅分类/标签 |
| `-s` | 仅来源链接 |
| `-S` | 仅状态/开源属性 |
| `-m` | 同时查 Modrinth |
| `-r` | 显示物品合成表（仅 item） |

**示例**：
```bash
mc-search --json info 钠
mc-search --json info 钠 -m
mc-search --json info 钻石剑 -r
```

### 4. wiki — minecraft.wiki 搜索

**用途**：搜索原版游戏内容（附魔、合成、生物、方块等）。

```bash
mc-search --json wiki <关键词> [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `-n <数量>` | 最多结果数 | `5` |
| `-r` | 搜索后直接读取第一个页面 |

**示例**：
```bash
mc-search --json wiki 附魔台
mc-search --json wiki 凋灵 -r
```

### 5. read — 读取 wiki 页面正文

**用途**：已知 wiki URL，读取完整内容。

```bash
mc-search --json read <URL> [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `-p <段落数>` | 最多段落数 | `5` |

**示例**：
```bash
mc-search --json read https://minecraft.wiki/w/Diamond_Sword -p 8
```

### 6. dep — Modrinth 依赖树

**用途**：查看 Modrinth 模组的依赖关系。

```bash
mc-search --json dep <mod_slug>
```

**示例**：
```bash
mc-search --json dep sodium
```

### 7. author — Modrinth 作者搜索

**用途**：查看某作者在 Modrinth 上的作品。

```bash
mc-search --json author <用户名> [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `-n <数量>` | 最多结果数 | `10` |

**示例**：
```bash
mc-search --json author jellysquid_ -n 20
```

### 8. mr — Modrinth 单平台搜索

**用途**：直接在 Modrinth 上搜索（支持光影/材质包），比 `search` 更快。

```bash
mc-search --json mr <关键词> [选项]
```

**选项**：
| 选项 | 说明 | 默认 |
|------|------|------|
| `-t <类型>` | 项目类型：`mod`/`shader`/`resourcepack` | `mod` |
| `-n <数量>` | 最多结果数 | `5` |

**示例**：
```bash
# 搜索模组
mc-search --json mr sodium

# 搜索光影包
mc-search --json mr shaders -t shader

# 搜索材质包
mc-search --json mr faithful -t resourcepack
```

---

## 特殊搜索场景

### 搜索生物群系 (biome)

```bash
# 搜索生物群系（minecraft.wiki）
mc-search --json search " Plains" --type biome
mc-search --json search "Nether" --type biome
```

### 搜索维度 (dimension)

```bash
# 搜索维度（minecraft.wiki）
mc-search --json search "Overworld" --type dimension
mc-search --json search "End" --type dimension
```

### 搜索实体 (entity)

```bash
# 搜索实体/生物（minecraft.wiki）
mc-search --json search "Creeper" --type entity
mc-search --json search "Villager" --type entity
```

### 融合搜索结果

```bash
# 融合四平台结果，去重后返回
mc-search --json search sodium --fuse
```

> **`--fuse` 说明**：将四平台结果合并，按相关性排序并去重同名项目，返回最多 15 条结果。

---

## 全局选项

> ⚠️ **位置**：必须放在子命令**之前**

```bash
mc-search --json search 钠          # ✓ 正确
mc-search search --json 钠          # ✗ 错误
```

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（Agent 推荐） |
| `--cache` | 启用本地缓存（TTL 1小时） |
| `--no-mcmod` | 禁用 MC百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用 minecraft.wiki（英文） |
| `--no-wiki-zh` | 禁用中文 wiki |
| `-o <文件>` | 输出到文件 |

---

## 智能排序逻辑

### 搜索排序规则

`search` 命令使用相关性排序，优先级从高到低：

| 优先级 | 条件 | 示例 |
|--------|------|------|
| 1️⃣ 精确匹配 | 名称完全等于搜索词 | 搜 "spawn" → "Spawn" 排第 1 |
| 2️⃣ 前缀匹配 | 名称以搜索词开头 | 搜 "sod" → "Sodium" 排前 |
| 3️⃣ 包含匹配 | 名称包含搜索词 | 搜 "spawn" → "OreSpawn" 排后 |
| 4️⃣ 多平台加权 | 同时出现在多个平台 | 跨平台结果排名提升 |
| 5️⃣ 平台权威度 | 同分时优先级 | MC百科 > Modrinth > Wiki |

### 版本优先级

当 MC百科 和 Modrinth 版本不一致时，**以 Modrinth 为准**：
- Modrinth 是官方发布平台，更新更及时
- MC百科 可能存在版本信息延迟

---

## 使用示例

### 示例 1：搜索模组

```bash
# 搜索并获取完整信息
mc-search --json search 钠
mc-search --json full 钠
```

### 示例 2：搜索光影包

```bash
# 搜索光影包（仅 Modrinth）
mc-search --json search Complementary --type shader

# 获取完整信息
mc-search --json full https://modrinth.com/shader/complementary-reimagined
```

### 示例 3：搜索整合包

```bash
# 搜索整合包（MC百科 + Modrinth）
mc-search --json search RLCraft --type modpack

# 获取完整信息
mc-search --json full RLCraft
```

---

## 错误处理

| 错误信息 | 原因 | 解决方法 |
|----------|------|----------|
| `四个平台均无 [关键词] 相关结果` | 关键词不存在或拼写错误 | 尝试其他关键词 |
| `无法解析模组 ID` | URL 格式问题 | 直接使用 URL：`info <URL>` |
| `mod_id 查询依赖时网络错误` | API 限流（360次/小时） | 稍后重试 |

**调试技巧**：
```bash
mc-search --json search 关键词 2>&1 | python3 -m json.tool
```

---

## 相关文档

- [commands.md](references/commands.md) — 完整命令参考
- [result-schema.md](references/result-schema.md) — 返回字段定义
- [troubleshooting.md](references/troubleshooting.md) — 故障排查指南
