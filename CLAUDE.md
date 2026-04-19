# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供本代码库的工作指导。

## 项目概述

**mc-search** 是一个 Minecraft 内容聚合搜索工具，同时也是 Claude Code 的 Skill。它并行搜索四个平台：

- **MC 百科** (mcmod.cn) — 中文模组/物品/整合包
- **Modrinth** — 英文模组/光影/材质包/整合包
- **minecraft.wiki** — 原版游戏 wiki（英文）
- **minecraft.wiki/zh** — 原版游戏 wiki（中文）

项目具有双重用途：
- **工具层面**：功能完整的 Minecraft 内容搜索 CLI
- **Skill 层面**：Claude Agent 可调用的标准化接口

## 项目结构

```
mc-search-skill/
├── skills/mc-search/ # Claude Code Skill 目录
│ ├── SKILL.md # Skill 定义（触发器、命令说明）
│ ├── pyproject.toml # Python 包配置
│ ├── scripts/
│ │ ├── __init__.py
│ │ ├── core.py # 核心搜索逻辑（~110KB）
│ │ └── cli.py # CLI 入口（~51KB）
│ └── references/ # 详细文档
│ ├── commands.md # 命令语法参考
│ ├── result-schema.md # 返回字段定义
│ ├── platform-comparison.md # 平台差异对比
│ ├── troubleshooting.md # 故障诊断
│ └── errors.md # 错误码字典
├── README.md # 用户文档（中文）
├── README.en.md # 用户文档（英文）
└── .github/ # GitHub 工作流
```

## 架构说明

### 核心组件

**scripts/core.py** — 搜索实现：
- `search_mcmod()` — mcmod.cn HTML 解析
- `search_modrinth()` — modrinth.com REST API
- `search_wiki()` / `search_wiki_zh()` — MediaWiki API
- `search_all()` — 并行搜索与结果融合
- `fetch_mod_info()` — Modrinth 模组详情
- `get_mod_dependencies()` — 依赖树解析
- `curl()` — 统一 HTTP 请求封装（urllib.request）

**scripts/cli.py** — CLI 接口：
- 三个子命令：`search`、`show`、`wiki`
- 使用 argparse 解析参数
- 支持 JSON/文本两种输出格式
- 字段过滤（`-T`、`-a`、`-d`、`-v` 等）
- 长描述自动保存到文件

### 数据流

```
用户查询 → CLI 解析器 → 平台路由 → 并行获取 → 结果融合 → 输出
```

**平台选择逻辑**：
- `mod`/`item`/`modpack`：MC百科 + Modrinth
- `shader`/`resourcepack`：仅 Modrinth
- `entity`/`biome`/`block`：minecraft.wiki 优先

## 常用开发命令

### 安装与设置

```bash
# 开发模式安装
cd skills/mc-search
pip install -e .

# 验证安装
mc-search --version
```

### 测试命令

```bash
# 测试 search 命令
mc-search --json search 钠
mc-search --json search sodium --platform modrinth
mc-search --json search BSL --shader

# 测试 show 命令
mc-search --json show 钠 --full
mc-search --json show sodium --deps
mc-search --json show 钻石剑 --recipe

# 测试 wiki 命令
mc-search --json wiki 附魔台
mc-search --json wiki enchanting -r

# 测试缓存
mc-search --json --cache search 机械动力

# 测试字段过滤
mc-search --json show 钠 -a -v # 仅作者和版本
```

### 平台特定测试

```bash
# 禁用特定平台
mc-search --json search 钠 --no-mr # 跳过 Modrinth
mc-search --json search 钠 --no-mcmod # 跳过 MC百科
mc-search --json search 钠 --no-wiki # 跳过英文 wiki
mc-search --json search 钠 --no-wiki-zh # 跳过中文 wiki
```

### 输出与调试

```bash
# 输出到文件
mc-search --json search 钠 -o output.json

# 美化 JSON 输出
mc-search --json search 钠 | python -m json.tool

# 仅查看平台统计
mc-search --json search 钠 2>/dev/null | python -c "
import sys, json
d = json.load(sys.stdin)
print(json.dumps(d.get('platform_stats', {}), indent=2))
"
```

## 关键实现细节

### 网络层

所有 HTTP 请求通过 `core.curl()` 完成：
- 使用 `urllib.request` 发起 HTTP 请求（无外部系统依赖）
- 处理超时和编码
- 返回原始 HTML/JSON 供解析

### HTML 解析（MC 百科）

- 使用正则表达式 + 字符串操作（无 BeautifulSoup 依赖）
- 处理中文编码（GBK/UTF-8）
- 解析搜索结果页和详情页
- 提取：名称、描述、版本、依赖、截图

### API 集成（Modrinth）

- REST API v2：`api.modrinth.com/v2/`
- 端点：`/search`、`/project/{slug}`、`/project/{id}/dependencies`
- 速率限制：360 请求/小时
- 返回结构化 JSON

### 结果融合

`search_all()` 配合 `fuse=True`：
1. 使用 ThreadPoolExecutor 并行执行平台搜索
2. 按名称相关性评分（精确 > 前缀 > 包含）
3. 跨平台合并重复项
4. 按相关性排序

### 缓存机制

- 位置：`~/.cache/mc-search/`
- TTL：1 小时
- 使用 `--cache` 参数启用
- 键：URL/查询的 MD5

## 代码修改指南

### 添加新平台

1. 在 `core.py` 添加搜索函数
2. 在 `cli.py` 添加平台开关（`--no-<平台>`）
3. 更新 `_PLATFORM_FLAGS` 映射
4. 添加到 `search_all()` 平台列表

### 添加新命令

1. 在 `cli.py` 的 `main()` 中添加子解析器
2. 实现处理函数
3. 添加到 `commands` 分发字典
4. 更新 `SKILL.md` 和 `references/commands.md`

### 修改输出格式

- JSON 输出：修改处理函数中的字典结构
- 文本输出：修改 `cli.py` 中的 `_print_*` 函数
- 显示限制常量位于 `cli.py` 顶部

## 测试清单

修改代码后，请验证：

- [ ] `mc-search --json search <关键词>` 返回有效 JSON
- [ ] `mc-search --json show <名称> --full` 包含双平台数据
- [ ] `mc-search --json wiki <关键词>` 原版内容搜索正常
- [ ] 字段过滤（`-a`、`-v` 等）工作正常
- [ ] `--cache` 参数正确存储和读取数据
- [ ] 错误情况返回带 `error` 字段的 JSON
- [ ] 非 JSON 模式产生可读的文本输出

## 依赖项

- Python 3.8+
- 无外部依赖（仅使用标准库，HTTP 请求使用 `urllib.request`）

## 重要提示

- **始终使用 `--json`** 进行程序化访问
- MC 百科解析较脆弱（HTML 结构可能变化）
- Modrinth API 有速率限制（360/小时）
- minecraft.wiki 在某些环境（Termux）可能无法访问
- 缓存目录在使用 `--cache` 时自动创建
