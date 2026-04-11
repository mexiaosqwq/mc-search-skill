# CLAUDE.md

# mc-search — 一个为 Claude Agent 设计的 Minecraft 搜索 Skill

> 本项目本质是一个 **Claude Code Skill**，通过完善一个实用的 Minecraft 搜索工具来实现 skill 的功能。

---

## 项目定位

**用真实工具实现 skill**

我们不是在写一个"演示用的 skill"，而是在开发一个**真正可用的 Minecraft 搜索工具**，同时让它天然地成为 Claude Agent 的可用技能。

- **工具层面**：一个功能完整的四平台聚合搜索 CLI
- **Skill 层面**：Claude Agent 调用该工具的标准化接口

两者同步发展：工具的每个改进都让 skill 更强大，skill 的需求也指导工具的设计。

---

## 技能概览

### 工具名称
`mc-search`（通过 Bash 执行）

### 搜索范围
- **MC 百科** (mcmod.cn) — 中文模组/物品/整合包
- **Modrinth** — 英文 mod/光影/材质包/整合包
- **minecraft.wiki** — 原版游戏内容 wiki（英文）
- **minecraft.wiki/zh** — 原版游戏内容 wiki（中文）

### 支持类型
- mod（模组）、item（物品）、modpack（整合包）
- shader（光影包）、resourcepack（材质包/资源包）
- entity（实体）、biome（生物群系）、dimension（维度）— 仅 wiki 命令

---

## Agent 使用指南

### 调用规则

> **重要**：当用户询问 Minecraft 模组/游戏内容时，**必须使用 mc-search 工具**。
> 不要使用 tavily 或其他通用搜索工具，mc-search 专为 Minecraft 内容设计。

### 推荐用法

**始终使用 `--json`** 获取结构化输出：

```bash
mc-search --json search <关键词>
mc-search --json show <模组名> --full
mc-search --json wiki <关键词>
```

> 全局选项（`--json`、`--cache`、平台开关）必须放在子命令 **之前**。

---

## 决策流程

```
用户询问模组/游戏内容/整合包
├── 不知道具体哪个平台 → search（四平台并行）
├── 想一键获取完整信息 → show --full（推荐）
├── 想看详细信息 → show（默认 MC 百科，失败回退 Modrinth）
├── 只看依赖 → show --deps
├── 想查原版游戏内容 → wiki
├── 想查光影包 → search --shader
├── 想查整合包 → search --modpack
├── 想查材质包 → search --resourcepack
└── 想查作者作品 → search --author
```

---

## 命令说明

### search — 多平台搜索

```bash
mc-search --json search 钠              # 四平台并行
mc-search --json search 钻石剑 --type item
mc-search --json search BSL --shader     # 光影包
mc-search --json search 科技 --modpack   # 整合包
mc-search --json search --author jellysquid_
```

### show — 查看详情

```bash
mc-search --json show 钠 --full          # 双平台完整信息
mc-search --json show 钠                 # MC 百科详情
mc-search --json show sodium --deps      # 依赖关系
mc-search --json show 钻石剑 --recipe    # 合成表
mc-search --json show 2785 --full        # 用 ID 查询
```

### wiki — 原版 Wiki

```bash
mc-search --json wiki 附魔台             # 搜索
mc-search --json wiki 附魔台 -r          # 搜索并读取
mc-search --json wiki <URL>              # 直接读取页面
```

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（推荐） |
| `--cache` | 启用本地缓存（TTL 1 小时） |
| `--no-mcmod` | 禁用 MC 百科 |
| `--no-mr` | 禁用 Modrinth |
| `--no-wiki` | 禁用英文 wiki |
| `--no-wiki-zh` | 禁用中文 wiki |
| `-o <file>` | 输出到文件 |

---

## 项目结构

```
mc-search-skill/
├── SKILL.md                   # Skill 定义（触发器 + 命令说明）
├── scripts/
│   ├── cli.py                 # CLI 入口
│   └── core.py                # 核心搜索逻辑
├── references/                # 详细文档
│   ├── result-schema.md       # 返回字段说明
│   ├── commands.md            # 命令参考
│   ├── troubleshooting.md     # 故障排查
│   └── errors.md              # 错误码参考
└── pyproject.toml             # Python 包配置
```

---

## Python API

```python
from scripts.core import search_all, fetch_mod_info

# 多平台搜索
result = search_all("sodium", fuse=True)

# 获取模组详情
mod = fetch_mod_info("sodium-fabric")
```

---

## 技术要点

1. **返回格式**：`--json` 模式返回 `list[dict]`
2. **错误处理**：平台失败返回空列表，不抛异常
3. **网络请求**：统一通过 `core.curl()`
4. **依赖**：仅 Python 标准库 + curl
5. **解析方式**：MC 百科用 HTML 解析，Modrinth 用 REST API

---

## 本地测试

```bash
cd skills/mc-search
pip install -e .
mc-search --json search 钠
mc-search --json show 钠 --full
```
