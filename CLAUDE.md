# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

**mc-search** 是 AI Agent 优先的 Minecraft 内容搜索 Skill。AI Agent 通过 Python API 直接调用，不依赖 CLI。四平台并行：MC百科 / Modrinth / minecraft.wiki EN / minecraft.wiki ZH。

核心特性：
- **跨语言桥接**：中文关键词自动从 MC百科 提取 `name_en` 去 Modrinth 补搜，Agent 透明
- **本体判别**：`is_primary: true` C→B→A→兜底 四级联标记本体模组
- **字段级权威源融合**：`_merge_entry_fields()` 逐字段选源，不按单一平台优先
- **错误信号透明**：统一 `_error` 键区分 `not_found`/`api_failed`/`parse_failed`，不用 `None`

## 文件结构

```
mc-search-skill/
├── skills/mc-search/
│   ├── SKILL.md              # skill 定义（Agent 入口，触发短语/API/路由/错误处理）
│   ├── pyproject.toml        # 包配置 + CLI 入口点
│   ├── scripts/
│   │   ├── __init__.py       # 包入口，直接从子模块导入
│   │   ├── _http.py          # HTTP/工具层：curl, SearchError, CDN绕过, 常量, 全局状态 (~809 行)
│   │   ├── _mcmod_parse.py   # MC百科 HTML 解析：21个正则解析函数 (~770 行)
│   │   ├── _mcmod_search.py  # MC百科 搜索入口：搜索/作者/整合包 + 排名 (~399 行)
│   │   ├── _modrinth.py      # Modrinth：搜索/作者/详情/依赖 (~476 行)
│   │   ├── _wiki.py          # Wiki EN/ZH：搜索/阅读/Infobox解析 (~506 行)
│   │   ├── _fuse.py          # 融合管线：CJK桥接/评分/去重/合并/本体判别 (~698 行)
│   │   ├── core.py           # facade 薄壳：保留向后兼容，全部 re-export (~64 行)
│   │   └── cli.py            # argparse CLI（Agent 不使用），~1345 行
│   └── references/           # 人类参考文档（Agent 不加载）
│       ├── errors.md
│       ├── troubleshooting.md
│       ├── platform-comparison.md
│       └── result-schema.md
├── tests/
│   ├── validate_output.py    # 契约验证 + 内容深度检查（新代码入口）
│   └── regression_test.py    # 回归测试
├── CLAUDE.md
├── CONTEXT.md                # 领域模型解释
└── README.md
```

**依赖单向链**：`_http` → `_mcmod_parse` → `_mcmod_search`, `_http` → `_modrinth`, `_http` → `_wiki`, (all) → `_fuse` → `core.py`(facade)。修改时顺依赖方向自底向上。

## 关键架构图

```
Agent 调用 → core.py(facade) → _fuse.search_all() → 并行平台搜索(_mcmod_search/_modrinth/_wiki) → CJK桥接 → _fuse_results(6步) → 统一JSON
```

融合管线 6 步顺序：
1. `_score_and_filter` → 2. `_count_platform_hits` → 3. `_deduplicate_by_name`(调 `_merge_entry_fields`) → 4. `_sort_entries` → 5. `_build_fused_output` → 6. `_mark_primary`

每种 Content Type 的平台路由：
- `mod`/`modpack` → MC百科 + Modrinth
- `item` → MC百科 + Modrinth + wiki 补充
- `shader`/`resourcepack` → Modrinth 独占
- `vanilla`/`entity`/`biome`/`dimension` → wiki 为主

## 修改核心操作流程

### 第一步：建立全景认知

**先判断对象类型，再选工具：**

| 对象 | 工具 | 说明 |
|------|------|------|
| Python 代码（函数/类/变量） | codegraph MCP | `codegraph_context` / `codegraph_impact` / `codegraph_explore` |
| 文档/文本/配置文件 | Read / Grep 直接读 | codegraph 对 md/yaml/json/txt 无效 |
| 测试文件/验证脚本 | Read | 测试逻辑不在 codegraph 索引范围内 |

codegraph 只对代码符号有效。文档、配置、目录结构探索直接用 Read/Grep。

### 第二步：编辑前必须确认（禁止试错循环）

使用 Edit 工具前，必须完成以下校验：

1. **确认精确内容**：用 `cat -An` 看要替换的文本的精确空白符（空格/缩进/行尾），不要靠猜
2. **确认唯一性**：用 `grep -n` 搜索 old_string 在原文件中的出现次数。多于 1 处时必须提供足够的上下文使匹配唯一
3. **确认影响范围**：跨文件修改/重构先 `EnterPlanMode`

**禁止的行为：**
- 不确认空白符就反复尝试 Edit → 失败 → 调整 → 再试 的循环
- 在 Edit 返回 `Found 2 matches` 后不 grep 定位就调整 old_string 重试

### 第三步：高危修改必须备份

以下场景视为高危，修改前必须备份原文件：

| 场景 | 备份方式 |
|------|---------|
| 修改融合管线（`_fuse.py` 中 `_fuse_results` / `_merge_entry_fields` / `_mark_primary`） | `cp _fuse.py _fuse.py.bak` |
| 修改 MC百科 正则解析（`_mcmod_parse.py`） | `cp _mcmod_parse.py _mcmod_parse.py.bak` |
| 修改 Modrinth 解析/API（`_modrinth.py`） | `cp _modrinth.py _modrinth.py.bak` |
| 修改 Wiki 解析/API（`_wiki.py`） | `cp _wiki.py _wiki.py.bak` |
| 修改 CLI 解析逻辑（`cli.py` 中 `_build_parser` / `_print_*`） | `cp cli.py cli.py.bak` |

备份保留到修改验证通过（`python3 tests/validate_output.py` exit 0）后再清理。

### 第四步：验证

测试入口分两个层级：

**契约验证（必做）**：
```bash
python3 tests/validate_output.py
```
exit 0 为通过，WARN 可接受（数据本身问题），FAIL 必须修复。

**Python API 通路验证**：
```python
import sys; sys.path.insert(0, 'skills/mc-search')
import scripts.core as core

r = core.search_all("机械动力", max_per_source=1, content_type="mod", fuse=True)
assert len(r["results"]) > 0

info = core.fetch_mod_info("sodium")
assert info and info["name"] == "Sodium"

pages = core.search_wiki("enchanting", max_results=1)
assert len(pages) > 0
```

先测 Python API 通路，再考虑 CLI。不满足断言就修复，不得跳过。

## 安全规则

### HTML 解析（`_mcmod_parse.py`）
- 所有 MC百科 解析使用纯正则 + 字符串操作（无 BeautifulSoup）
- **正则修改后必须 `grep -rn` 整个代码库**：同一个正则可能在多个函数中重复出现
- MC百科 URL 三种模式互不相同：`/class/`（模组）、`/item/`（物品）、`/modpack/`（整合包）
- **WAF 回退路径**：`_build_mcmod_fallback_result`（在 `_mcmod_search.py`）字段比完整解析少，加新字段时同步加在这里

### 融合管线（`_fuse.py` 中 `_fuse_results`）
- 6 步顺序固定，改某一步时看它依赖上一步的哪些字段
- `_deduplicate_by_name` 调 `_merge_entry_fields` 做字段级覆盖。引入新字段时决定是否加入 `_MERGE_FIELD_RULES` 或 `_FIELD_PRIORITY`
- `_mark_primary` 的 C→B→A→兜底顺序固定，改判定逻辑时检查所有四级路径

### 全局变量并发安全（`_http.py`）
- `_platform_enabled`（`_PLATFORM_LOCK`）、`_MCMOD_SESSION`（`_MCMOD_LOCK`）
- 跨模块访问通过 facade re-export：`from scripts.core import set_platform_enabled`
- **修改全局变量必须在锁内读写**。新增全局状态时同步添加同名 `threading.Lock()`

## 提交

前缀与最近 commit 一致：`fix:` / `feat:` / `refactor:` / `docs:` / `chore:`
不写长标题，用短横线描述具体改动。例：`fix: 并发安全补全 + lambda提取具名函数 + CLI类型标注`

## 行为准则

- **极简主义**：不添加任务外的功能/重构/抽象
- **编辑前必确认**：cat -An 看空白符、grep -n 确认唯一性，禁止试错循环
- **高危必备份**：改融合管线/解析逻辑前 cp 备份
- **注释有目的**：写 WHY，不写 WHAT。正则意图、锁保护范围、回退路径触发条件必须写
- **codegraph 仅限代码**：改 Python 代码时先用 codegraph 建立符号认知；文档/配置/测试直接用 Read/Grep
- **验证后才报告完成**：validate_output.py exit 0 + Python API 通路断言
- **不留向后兼容包袱**：彻底删除无用代码，不做软废弃