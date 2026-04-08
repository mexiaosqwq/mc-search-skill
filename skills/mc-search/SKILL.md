---
name: mc-search
version: "4.5.0"
description: "Minecraft 内容搜索 - 模组/整合包/光影/材质包/wiki 四平台聚合"
license: MIT
context: open
user-invocable: true
allowed-tools: [Bash]
triggers:
  - "搜索"
  - "查询"
  - "查找"
  - "模组"
  - "整合包"
  - "光影包"
  - "材质包"
  - "wiki"
---

# mc-search

Minecraft 内容搜索工具，支持四平台并行：
- **MC百科** (mcmod.cn) - 中文模组/整合包
- **Modrinth** - 英文 mod/光影/材质/整合包
- **minecraft.wiki** - 原版游戏内容（英文）
- **minecraft.wiki/zh** - 原版游戏内容（中文）

## 何时使用

当用户询问以下任何内容时**立即触发**：

### 模组/mod 相关
- "搜索机械动力"
- "钠模组信息"
- "Create mod 怎么样"
- "推荐几个科技模组"
- "有什么好玩的模组"

### 整合包相关
- "RLCraft 是什么"
- "搜索科技整合包"
- "推荐服务器整合包"

### 光影/材质相关
- "BSL 光影"
- "搜索高清材质包"
- "Complementary 光影怎么样"

### wiki/原版内容相关
- "wiki 附魔台"
- "下界合金怎么获得"
- "村民交易列表"

## 快速命令

```bash
# 模糊搜索 - 不确定具体名称时
mc-search --json search <关键词> [--type mod/item/modpack/shader/resourcepack]

# 获取详情 - 知道名称时（推荐首选）
mc-search --json details <模组名> --full

# wiki 查询 - 原版游戏内容
mc-search --json wiki <关键词>
```

## 决策表

| 用户需求 | 命令 | 示例 |
|----------|------|------|
| 知道名称，要详情 | `details` | `mc-search --json details create` |
| 不确定名称，模糊搜 | `search` | `mc-search --json search 钠` |
| 按平台搜索 | `search --platform` | `mc-search --json search sodium --platform modrinth` |
| 按类型过滤 | `search --type` | `mc-search --json search BSL --type shader` |
| 获取完整信息 | `details --full` | `mc-search --json details sodium --full` |
| 只看依赖 | `deps` | `mc-search --json deps sodium` |
| 查 wiki | `wiki` | `mc-search --json wiki 下界合金` |
| MC百科作者 | `search --author` | `mc-search --json search --author Notch` |
| Modrinth作者 | `author` | `mc-search --json author Notch` |

**注意**: `full` 命令已标记为[已废弃]，请改用 `details --full`。

## 返回数据结构

### search 命令（JSON 对象）

```json
{
  "results": [
    {
      "name": "机械动力",
      "name_en": "Create",
      "name_zh": "机械动力",
      "url": "https://www.mcmod.cn/class/2021.html",
      "source": "mcmod.cn",
      "type": "mod",
      "snippet": "简述...",
      "categories": ["科技Mod"],
      "downloads": 5000000
    }
  ],
  "platform_stats": {"mcmod": 1, "modrinth": 0}
}
```

### details 命令（JSON 对象，替代 full）

```json
{
  "mcmod": {
    "name_zh": "机械动力",
    "name_en": "Create",
    "status": "活跃",
    "author_team": [{"name": "Simibubi", "roles": ["程序"]}],
    "description": "简介...",
    "categories": ["科技Mod"],
    "tags": ["机械", "自动化"],
    "supported_versions": ["1.20.1", "1.18.2"],
    "relationships": {
      "requires": [{"name_zh": "飞轮", "url": "..."}],
      "integrates": [{"name_zh": "JEI", "url": "..."}]
    }
  },
  "modrinth": {
    "downloads": 14000000,
    "followers": 52000,
    "author": "simibubi",
    "client_side": "optional",
    "server_side": "optional",
    "license_name": "MIT",
    "latest_version": "6.0.9",
    "loaders": ["fabric", "neoforge"]
  },
  "dependencies": {
    "deps": {
      "flywheel": {"name": "Flywheel", "type": "required"}
    },
    "required_count": 1,
    "optional_count": 0
  },
  "saved_files": ["/path/to/output/Create_mod_full.md"]  // 仅在触发文件保存时存在
}
```

### 关键字段说明

| 字段 | 说明 |
|------|------|
| `name` / `name_en` / `name_zh` | 中英文名称 |
| `source` | 数据来源平台 |
| `type` | 项目类型 (mod/item/modpack/shader/resourcepack) |
| `status` | 模组状态 (活跃/半弃坑/弃坑) |
| `client_side` / `server_side` | 客户端/服务端需求 (required/optional/unsupported) |
| `relationships.requires` | 前置模组（必需依赖） |
| `relationships.integrates` | 联动模组（兼容） |

## 文件输出

当描述过长时**自动保存**到 `output/` 目录：

**触发条件**：
- Modrinth body > 3000 字符
- MC百科简介 > 5000 字符

**文件命名**：`{名称}_{类型}_full.md`

**JSON 响应**包含：
```json
{
  "saved_files": [
    "/path/to/skill/output/Create_mod_full.md"
  ]
}
```

AI 可直接读取或上传这些文件。

## 依赖显示规则

- **前置模组（必需依赖）**：优先显示 Modrinth 数据
- **联动模组**：使用 MC百科 数据
- 如果都没有：显示"无"

## 实用示例

### 1. 搜索模组
```bash
mc-search --json search 机械动力
```

### 2. 获取完整信息
```bash
mc-search --json full Create
```

### 3. 按类型搜索

```bash
mc-search --json search BSL --type shader           # 光影包
mc-search --json search Faithful --type resourcepack # 材质包
mc-search --json search RLCraft --type modpack       # 整合包
```

### 4. wiki 查询（原版内容）

```bash
mc-search --json wiki 下界合金
mc-search --json wiki "Villager Trading"  # 英文
```

**wiki 搜索特点**：
- 只搜索 minecraft.wiki（中英双站）
- 返回游戏机制、合成表等原版内容
- 不适用于模组内容

### 5. 依赖查询
```bash
mc-search --json dep sodium
```

## 注意事项

1. **`--json` 位置**：必须放在子命令**之前**
   ```bash
   mc-search --json search 钠   # ✓
   mc-search search --json 钠   # ✗
   ```

2. **类型过滤**：支持 `mod`/`item`/`modpack`/`shader`/`resourcepack`

3. **网络稳定性**：四平台并行，单个失败不影响其他结果

4. **缓存**：可使用 `--cache` 启用本地缓存（TTL 1小时）

## 平台特性

| 平台 | 优势 | 适用场景 |
|------|------|----------|
| MC百科 | 中文详细，联动信息全 | 中文用户、找联动模组 |
| Modrinth | 英文官方，依赖准确 | 依赖查询、版本信息、光影/材质包 |
| minecraft.wiki | 原版百科 | 合成表、游戏机制 |

## 不同类型内容的差异

### 模组 (mod)
- **搜索范围**: MC百科 + Modrinth
- **返回**: 中英文信息、依赖关系、支持版本

### 光影包 (shader)
- **搜索范围**: 仅 Modrinth
- **返回**: 英文信息、截图、下载量

### 材质包 (resourcepack)
- **搜索范围**: 仅 Modrinth
- **返回**: 英文信息、预览图

### 整合包 (modpack)
- **搜索范围**: MC百科 + Modrinth
- **返回**: 包含模组列表、下载链接

### wiki 内容
- **搜索范围**: minecraft.wiki (中英)
- **返回**: 游戏机制、合成表、生物信息
- **不适用**: --type 参数

## 错误处理

| 情况 | 处理 |
|------|------|
| 无结果 | 尝试其他关键词/平台 |
| 网络错误 | 自动重试 |
| 版本不一致 | 以 Modrinth 为准（官方发布） |
