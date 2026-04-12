---
name: mc-search
version: "5.0.0"
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
- **MC 百科** (mcmod.cn) - 中文模组/整合包
- **Modrinth** - 英文 mod/光影/材质/整合包
- **minecraft.wiki** - 原版游戏内容（英文）
- **minecraft.wiki/zh** - 原版游戏内容（中文）

## 快速参考

### 最常用命令

```bash
# 搜索模组/物品/整合包
mc-search --json search <关键词>

# 查看模组详情（双平台）
mc-search --json show <模组名> --full

# 查看依赖关系
mc-search --json show <模组名> --deps

# 搜索原版游戏内容
mc-search --json wiki <关键词>
```

### 场景速查

| 场景 | 命令 |
|------|------|
| 快速搜索 | `mc-search --json search 钠` |
| 查看详情 | `mc-search --json show 钠 --full` |
| 只看依赖 | `mc-search --json show 钠 --deps` |
| 搜光影包 | `mc-search --json search BSL --shader` |
| 搜整合包 | `mc-search --json search 科技 --modpack` |
| 查 wiki | `mc-search --json wiki 附魔台` |

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

## 三个命令

### 1. `search` — 多平台搜索

```bash
mc-search --json search <关键词> [选项]
```

| 选项 | 说明 | 默认 |
|------|------|------|
| `--shader` | 快捷：搜光影包（仅 Modrinth） | - |
| `--modpack` | 快捷：搜整合包（MC百科+Modrinth） | - |
| `--resourcepack` | 快捷：搜材质包（仅 Modrinth） | - |
| `--type` | 完整类型：mod/item/shader/resourcepack/modpack | mod |
| `--platform` | 平台：all/mcmod/modrinth/wiki/wiki-zh | all |
| `--author` | 按作者搜索（MC百科+Modrinth双平台） | - |
| `--cache` | 启用本地缓存（TTL 1 小时） | - |
| `--screenshots <num>` | 返回截图数量（默认 0，即不返回） | 0 |
| `-n` | 每平台最多结果 | 3 |

**快捷标志等价关系**：
- `--shader` = `--type shader` + 自动限定仅 Modrinth
- `--modpack` = `--type modpack`
- `--resourcepack` = `--type resourcepack` + 自动限定仅 Modrinth

**示例**：
```bash
# 基础搜索
mc-search --json search 钠                      # 四平台并行搜索
mc-search --json search 机械动力                # 中文模组搜索
mc-search --json search Create                  # 英文模组搜索

# 按类型搜索
mc-search --json search 钻石剑 --type item      # 物品搜索
mc-search --json search 科技 --modpack          # 整合包搜索
mc-search --json search BSL --shader            # 光影包（仅 Modrinth）
mc-search --json search Faithful --resourcepack # 材质包（仅 Modrinth）

# 按平台限定
mc-search --json search 钠 --platform mcmod     # 仅 MC 百科
mc-search --json search sodium --platform modrinth  # 仅 Modrinth
mc-search --json search 附魔台 --platform wiki  # 仅英文 wiki
mc-search --json search 附魔台 --platform wiki-zh  # 仅中文 wiki

# 特殊搜索
mc-search --json search --author jellysquid_    # 按作者搜索（双平台）
mc-search --json search 钠 -n 5                 # 每平台 5 个结果
mc-search --json search 钠 --no-mr              # 禁用 Modrinth
```

### 2. `show` — 查看详情/依赖/合成表

```bash
mc-search --json show <名称/URL/ID> [选项]
```

| 选项 | 说明 |
|------|------|
| `--full` | 双平台完整信息（MC百科+Modrinth+依赖+版本） |
| `--deps` | 快捷：仅依赖关系（走 Modrinth 快速路径） |
| `--recipe` | 合成表（仅 item） |
| `--skip-dep` | 跳过依赖查询（加速，仅 --full） |
| `--skip-mr` | 跳过 Modrinth 查询（加速，仅 --full） |
| `-T` | 仅名称/别名（仅 MC 百科路径生效） |
| `-a` | 仅作者（仅 MC 百科路径生效） |
| `-d` | 仅前置/联动（仅 MC 百科路径生效） |
| `-v` | 仅版本（仅 MC 百科路径生效） |
| `-g` | 仅截图（仅 MC 百科路径生效） |
| `-c` | 仅分类/标签（仅 MC 百科路径生效） |
| `-s` | 仅来源链接（仅 MC 百科路径生效） |
| `-S` | 仅状态/开源属性（仅 MC 百科路径生效） |

**默认行为（无 --full）**：
- MC百科 URL/ID/中文名 → 查 MC百科，失败回退 Modrinth
- Modrinth URL/slug → 查 Modrinth

**`--deps` 快捷路径**：
- 不爬全页，直接搜 Modrinth slug → 获取依赖
- 和旧 `deps` 命令一样快

**示例**：
```bash
# 基础查询
mc-search --json show 钠                        # MC 百科详情
mc-search --json show sodium                    # Modrinth 详情（自动回退）
mc-search --json show 机械动力                  # 中文模组

# 双平台完整信息
mc-search --json show 钠 --full                 # 双平台完整信息
mc-search --json show Create --full             # 英文模组双平台
mc-search --json show 2785 --full               # 用 MC 百科 ID 查询

# URL 查询
mc-search --json show https://www.mcmod.cn/class/2785.html --full
mc-search --json show https://modrinth.com/mod/sodium --full

# 快捷查询
mc-search --json show 钠 --deps                 # 仅依赖关系
mc-search --json show 机械动力 --deps           # 依赖查询
mc-search --json show 钻石剑 --recipe           # 合成表

# 字段过滤（精简输出）
mc-search --json show 钠 -a                     # 仅作者
mc-search --json show 钠 -v                     # 仅版本
mc-search --json show 钠 -c                     # 仅分类/标签
mc-search --json show 钠 -T -a                  # 仅名称 + 作者
```

### 3. `wiki` — 原版 Wiki 搜索与阅读

```bash
mc-search --json wiki <关键词或URL> [选项]
```

| 选项 | 说明 | 默认 |
|------|------|------|
| `-r` | 搜索后读取第一个结果正文 | - |
| `-n` | 最多结果 | 5 |
| `-p` | 段落数（URL读取时生效） | 20 |

**智能检测**：
- 参数以 `http` 开头 → 直接读取 wiki 页面
- 否则 → 搜索 wiki

**示例**：
```bash
# 基础搜索
mc-search --json wiki 附魔台                    # 搜索 wiki
mc-search --json wiki 下界合金                  # 原版物品搜索
mc-search --json wiki 村民交易                  # 游戏机制搜索

# 搜索并读取正文
mc-search --json wiki 附魔台 -r                 # 搜索并读取第一个结果
mc-search --json wiki 下界合金 -r               # 搜索并读取

# 直接读取页面
mc-search --json wiki https://minecraft.wiki/w/Diamond_Sword  # 英文页面
mc-search --json wiki https://minecraft.wiki/w/钻石剑 -p 10   # 中文页面，10 段落

# 限定结果数量
mc-search --json wiki 合成 -n 3                 # 最多 3 个结果
```

## 决策表

| 用户需求 | 命令 | 示例 |
|----------|------|------|
| 知道名称，要详情 | `show --full` | `mc-search --json show create --full` |
| 不确定名称，模糊搜 | `search` | `mc-search --json search 钠` |
| 搜光影包 | `search --shader` | `mc-search --json search BSL --shader` |
| 搜整合包 | `search --modpack` | `mc-search --json search 科技 --modpack` |
| 搜材质包 | `search --resourcepack` | `mc-search --json search Faithful --resourcepack` |
| 搜物品 | `search --type item` | `mc-search --json search 钻石剑 --type item` |
| 按平台搜索 | `search --platform` | `mc-search --json search sodium --platform modrinth` |
| 仅 MC 百科 | `search --platform mcmod` | `mc-search --json search 钠 --platform mcmod` |
| 仅 Modrinth | `search --platform modrinth` | `mc-search --json search sodium --platform modrinth` |
| 禁用某平台 | `--no-mr` / `--no-mcmod` | `mc-search --json search 钠 --no-mr` |
| 只看依赖 | `show --deps` | `mc-search --json show sodium --deps` |
| 查 wiki | `wiki` | `mc-search --json wiki 下界合金` |
| 读取 wiki 页面 | `wiki <url>` | `mc-search --json wiki https://minecraft.wiki/w/Diamond_Sword` |
| 按作者搜索 | `search --author` | `mc-search --json search --author jellysquid_` |
| 精简结果 | `-n <num>` | `mc-search --json search 钠 -n 1` |
| 查看作者信息 | `show -a` | `mc-search --json show 钠 -a` |
| 查看版本信息 | `show -v` | `mc-search --json show 钠 -v` |
| 查看合成表 | `show --recipe` | `mc-search --json show 钻石剑 --recipe` |

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

### show --full 命令（JSON 对象，双平台全量输出）

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
  "saved_files": ["/path/to/output/Create_mod_full.md"]
}
```

> **注意**：`mcmod` 和 `modrinth` 字段可能为 `null`（当对应平台查询失败时）。`saved_files` 仅在触发文件保存时存在。

### 关键字段说明

| 字段 | 说明 |
|------|------|
| `name` / `name_en` / `name_zh` | 中英文名称 |
| `source` | 数据来源平台 |
| `_sources` | 融合来源平台列表（仅融合模式下存在） |
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

## 环境变量

- `MC_SEARCH_OUTPUT_DIR`：自定义输出目录（默认：`output/`）

## 依赖显示规则

- **前置模组（必需依赖）**：优先显示 Modrinth 数据
- **联动模组**：使用 MC百科 数据
- 如果都没有：显示"无"

## 注意事项

1. **`--json` 位置**：放在子命令之前或之后都可以
   ```bash
   mc-search --json search 钠   # 两种写法都可以
   mc-search search --json 钠   
   ```

2. **类型过滤**：支持 `mod`/`item`/`modpack`/`shader`/`resourcepack`


3. **网络稳定性**：四平台并行，单个失败不影响其他结果

4. **缓存**：可使用 `--cache` 启用本地缓存（TTL 1 小时）

5. **截图控制**：默认不返回截图（节省带宽），可使用 `--screenshots <num>` 调整
   ```bash
   mc-search --json search 钠 --screenshots 3   # 返回 3 张截图
   mc-search --json show 钠 --full --screenshots 5   # full 模式也受控制
   ```

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

## 错误处理

| 情况 | 处理 |
|------|------|
| 无结果 | 尝试其他关键词/平台 |
| 网络错误 | 自动重试 |
| 版本不一致 | 以 Modrinth 为准（官方发布） |
