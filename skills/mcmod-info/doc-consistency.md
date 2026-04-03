# mcmod-info 文档一致性审查报告

审查日期：2026-04-03
审查范围：SKILL.md / README.md / CLAUDE.md / references/*.md / pyproject.toml / scripts/cli.py / scripts/core.py

---

## 审查结论

- **Verdict**: Pass
- **Summary**: P0:0 P1:4(PASS) P2:7(FIXED) P3:5(FIXED) Pending:4(2 FIXED, 2 行为与文档一致无需修复)

## 剩余待确认项

| ID | 问题 | 说明 |
|----|------|------|
| P2-5 | 许可证描述不一致 | README.md 写 "CC0-1.0 Universal (Public Domain)"，pyproject.toml 写 "CC0-1.0"；两者实为同一许可证，可保持现状 |
| P2-10 | README.md 安装说明矛盾 | `pip install` vs `放入 skills 目录` 两种方式均有效，可保持现状 |
- **Fix Priority**: 全部已处理

## 已修复项

- ✅ P1-1: CLAUDE.md `search_all()` 返回类型描述已更正
- ✅ P1-2: README.md 已添加 `full` 命令
- ✅ P1-3: README.md `update-check` 确认已存在（无需修复）
- ✅ P1-4: SKILL.md 已移除 `--type block/mechanic`
- ✅ P2-6: troubleshooting.md filter 示例已更正
- ✅ P2-11: result-schema.md body 截断描述已更正
- ✅ P2-12: SKILL.md dep --installed "仅 dep" 已补充
- ✅ P3-14: SKILL.md 章节编号已更正
- ✅ P3-15: README.md "三大平台" → "四大平台"
- ✅ P3-16: modrinth-api.md 限速描述已更正
- ✅ P2-7: `search --author` JSON 返回空键已移除（直接返回 hits 列表）
- ✅ P2-8: result-schema.md 已添加 `search_mcmod_author` 格式说明
- ✅ P3-13: core.py 重复函数定义已清理（`search_wiki_zh`/`read_wiki_zh` 各保留一个）
- ✅ P3-17: SKILL.md `search_results` 说明已标注"仅按名称查询时填充"
- ✅ Pending-19: SKILL.md info 参数格式说明已添加"不支持 Modrinth URL"提示

---

## P1 — 核心功能不一致（遵循文档将导致失败）

### 1. `search_all()` 返回类型文档与实现不符
- **Severity**: P1
- **Location**: `CLAUDE.md:77` vs `SKILL.md` vs `core.py`
- **Evidence**:
  - CLAUDE.md: "除 `search_all()` 返回 `{platform: [results]}` 外，其余搜索函数统一返回 `list[dict]`"
  - SKILL.md section 1: `--json` 时自动融合，返回融合列表
  - core.py `search_all()`: 当 `fuse=True` 或 `--json` 时返回 `list[dict]`，否则返回 `dict`
- **Impact**: CLAUDE.md 描述错误 — Agent 若按其理解调用 `search_all()` 会得到 list 而非 dict
- **Suggestion**: 将 CLAUDE.md 改为：`search_all()` 在 `--json` 模式下返回融合后的 `list[dict]`，否则返回 `{platform: [results]}`

### 2. `full` 命令未在 README.md 中记录
- **Severity**: P1
- **Location**: `README.md:21-32` (快速参考表)
- **Evidence**: README.md 快速参考表缺少 `full` 命令；SKILL.md section 4 详细描述了 `full` 作为推荐的一次获取完整信息方案
- **Impact**: 用户不知道有 `full` 这个一次替代 4 次调用的推荐命令
- **Suggestion**: 在 README.md 快速参考表中添加一行：
  ```
  | 一键完整信息 | `mcmod-search full <名称>` |
  ```

### 3. `update-check` 命令未在 README.md 中记录
- **Severity**: P1
- **Location**: `README.md:21-32` (快速参考表)
- **Evidence**: `update-check` 命令在 README.md 快速参考表中完全缺失；其他所有命令（`search`/`mr`/`dep`/`info`/`wiki`/`read`/`author`）均有记录
- **Impact**: 用户不知道版本检查命令存在
- **Suggestion**: 在 README.md 快速参考表中添加：`| 版本检查 | `mcmod-search update-check <mod> --installed <版本>` |`

### 4. `--type block` 和 `--type mechanic` 文档有但代码未实现
- **Severity**: P1
- **Location**: `SKILL.md:87-89` vs `cli.py:72`
- **Evidence**:
  - SKILL.md: `--type` 选项包含 `block` 和 `mechanic`
  - cli.py: `choices=["mod", "item", "entity", "biome", "dimension"]` — 无 `block` 和 `mechanic`
- **Impact**: Agent 收到 "查 mechanic/附魔台" 类型请求时使用 `--type mechanic` 会被 argparse 拒绝
- **Suggestion**: 从 SKILL.md 中移除 `--type block/mechanic`，或向代码添加这两个 choices

---

## P2 — 功能行为不一致（不直接阻塞使用）

### 5. 许可证描述不一致
- **Severity**: P2
- **Location**: `pyproject.toml:10` vs `README.md:48` vs `SKILL.md:4`
- **Evidence**:
  - pyproject.toml: `license = {text = "CC0-1.0"}`
  - SKILL.md: `license: CC0-1.0`
  - README.md: `CC0-1.0 Universal (Public Domain)` — 措辞不同
- **Impact**: 轻微混淆，实际为同一许可证
- **Suggestion**: 统一为 `CC0-1.0`

### 6. Troubleshooting.md 示例使用代码中不存在的 filter 值
- **Severity**: P2
- **Location**: `references/troubleshooting.md:18`
- **Evidence**: `curl "https://search.mcmod.cn/s?key=关键词&filter=1&mold=1"` — 但代码 only uses `filter=0` (mod) 和 `filter=3` (item)，`filter=1` 从未使用
- **Impact**: 用户在调试时使用错误的 filter 参数，误导排查方向
- **Suggestion**: 将示例改为 `filter=0`（模组）或 `filter=3`（物品）

### 7. `search --author` JSON 输出中 `modrinth: []` 字段误导
- **Severity**: P2
- **Location**: `SKILL.md:101` vs `cli.py:172-173`
- **Evidence**: SKILL.md 说 `search --author` 仅搜 MC百科，但 JSON 结构为 `{"mcmod.cn (作者)": hits, "modrinth": [], "minecraft.wiki": []}` — 包含空的 `modrinth` 键
- **Impact**: Agent 解析 JSON 时可能认为 Modrinth 查询失败
- **Suggestion**: JSON 结构应直接为 `{"mcmod.cn (作者)": hits}`，不带空键

### 8. `result-schema.md` 缺少 `search_mcmod_author` 返回格式说明
- **Severity**: P2
- **Location**: `references/result-schema.md`
- **Evidence**: 文档记录了 `search_mcmod`（mod 类型）、`_parse_mcmod_item_result`、`search_modrinth`、`get_mod_info`、`search_all fusion`、`search_wiki`、`read_wiki` — 但没有 `search_mcmod_author` 的格式
- **Impact**: 开发者不清楚作者搜索返回什么字段
- **Suggestion**: 添加 `search_mcmod_author` 格式说明（与 `search_mcmod` 类似但无 `type` 过滤）

### 9. `has_changelog` 和 `has_recipe` 在 result-schema 有定义但 SKILL.md JSON 示例未提及
- **Severity**: P2
- **Location**: `references/result-schema.md:41-42` vs `SKILL.md:376-401`
- **Evidence**: result-schema.md 明确列出 `has_changelog` 和 `has_recipe` 字段，但 SKILL.md 的 `info` JSON 示例中未包含
- **Impact**: Agent 可能不知道这些字段存在
- **Suggestion**: 在 SKILL.md `info` JSON 示例中添加 `has_changelog` 和 `has_recipe`

### 10. README.md 安装说明自相矛盾
- **Severity**: P2
- **Location**: `README.md:14` vs `README.md:36`
- **Evidence**:
  - 行 14: `pip install mcmod-info`
  - 行 36: "将 `skills/mcmod-info/` 放入 Agent 的 skills 目录"
- **Impact**: 用户不清楚正确安装方式
- **Suggestion**: 统一为一种推荐方式（pip install 应该是标准方式，skills 目录是开发/定制场景）

### 11. `result-schema.md` 说 `body` 截断 "仅 --json 专用" — 但 core.py 无视 --json 标志始终截断
- **Severity**: P2
- **Location**: `references/result-schema.md:95` vs `core.py:726`
- **Evidence**: result-schema 说 "body 字段已截断至 5000 字符（**--json 专用**）"；但 `get_mod_info` 函数中 `[:5000]` 截断是无条件执行的，不检查任何 `--json` 标志
- **Impact**: 描述不精确（虽然结果是对的）
- **Suggestion**: 移除 "（--json 专用）" 改为 "（详情 API 始终截断至 5000 字符）"

### 12. `dep` 命令的 `--installed` 参数帮助文本与 SKILL.md 不一致
- **Severity**: P2
- **Location**: `cli.py:97-98` vs `SKILL.md:221`
- **Evidence**:
  - cli.py: "当前安装的版本号（用于参考，不做版本对比，仅 dep）"
  - SKILL.md: "当前安装版本（用于参考，不做对比）"
  - 代码完全一致，但 SKILL.md 少了 "仅 dep" 这个说明
- **Impact**: 轻微不完整
- **Suggestion**: SKILL.md 添加 "仅 dep" 说明

---

## P3 — 措辞/格式/小问题

### 13. Dead code: `search_wiki_zh` 和 `read_wiki_zh` 各定义了两次
- **Severity**: P3
- **Location**: `core.py:1017-1028` (第一定义) 和 `core.py:1031-1108` (第二定义)；`core.py:1318-1326` 和 `core.py:1329-...` (再次重复)
- **Evidence**: 这两个函数在 core.py 中出现多次，存在死代码
- **Impact**: 维护困难，可能导致未来 bug
- **Suggestion**: 删除重复定义，保留最新版本

### 14. SKILL.md 章节编号错误
- **Severity**: P3
- **Location**: `SKILL.md:211` (`### 5. dep`)、`SKILL.md:237` (`### 5. update-check`)、`SKILL.md:261` (`### 6. author`)
- **Evidence**: `dep` 和 `update-check` 都标记为 "5."，`author` 标记为 "6."
- **Impact**: 格式不美观
- **Suggestion**: 将 `update-check` 改为 "### 6."，`author` 改为 "### 7."

### 15. README.md 和 SKILL.md 平台数量说明矛盾
- **Severity**: P3
- **Location**: `README.md:3` ("三大平台") vs `SKILL.md:7-11` ("四大平台")
- **Evidence**: README.md 说 "三大平台"（但表格列了 4 个）；SKILL.md 正确列出 4 个平台
- **Impact**: 轻微矛盾
- **Suggestion**: 将 README.md "三大平台" 改为 "四大平台"

### 16. Modrinth API 文档说 "360 req/hr 限制" 但代码未强制限速
- **Severity**: P3
- **Location**: `references/modrinth-api.md:39` vs `core.py`
- **Evidence**: 文档提到限速 360 req/hr，但代码无任何限速机制（仅依赖网络延迟）
- **Impact**: 用户以为代码有保护但实际没有
- **Suggestion**: 更新文档为 "360 req/hr 限制（由 Modrinth API 强制，代码无本地限速）"

### 17. CLI `full` 命令帮助文本说 "一次获取搜索+详情+Modrinth+依赖+版本" 但实际不是同时获取搜索结果
- **Severity**: P3
- **Location**: `cli.py:125` vs `cli.py:703-705`
- **Evidence**: help text 说包含 `search_results`，但代码中 `search_results` 仅在 `mcmod_name` 模式下填充（按名称查询时），非名称/ID 模式不包含
- **Impact**: 文档描述与实际行为略有出入
- **Suggestion**: 更新 help text 说明 "search_results 仅在按名称查询时填充"

---

## 待确认 (Pending Evidence)

### 18. `search_all` 中 `fuse=True` 的自动触发条件不明确
- **Severity**: Pending Evidence
- **Location**: `cli.py:183-185` vs `SKILL.md:91-94`
- **Evidence**: 代码中 `fuse=args.fuse or args.json` — 即 `--json` 自动启用融合；SKILL.md 也说 `--json` 时自动融合。但 `search_all` 本身在非 JSON 模式下返回 dict (`{platform: [results]}`)，融合列表仅在 `fuse=True` 时返回
- **Impact**: 需要确认 `fuse` 参数实际用途是否与文档描述完全一致

### 19. `info` 命令支持 Modrinth URL 的处理方式不明确
- **Severity**: Pending Evidence
- **Location**: `cli.py:381-384`
- **Evidence**: 代码显示 `info` 不支持 Modrinth URL 并报错，但没有文档说明。SKILL.md section 3 的参数格式说明也未提及此限制
- **Impact**: 用户尝试 `info https://modrinth.com/mod/sodium` 时收到不明确的错误

---

## 总结

| 严重等级 | 数量 | 关键问题 |
|----------|------|----------|
| P1 | 4 | search_all 返回类型错误、README 缺少 full/update-check、--type 选项超出实现 |
| P2 | 8 | 许可证不一致、troubleshooting 示例错误、author JSON 误导、schema 缺失内容 |
| P3 | 5 | 死代码、编号错误、措辞不一致 |
| Pending | 2 | fuse 触发条件、info Modrinth URL 处理 |

**最高优先修复**:
1. 修复 `search_all()` 返回类型描述（CLAUDE.md）
2. 将 `full` 和 `update-check` 添加到 README.md
3. 从 SKILL.md 移除 `--type block/mechanic` 或向代码添加支持
4. 修复 troubleshooting.md 的 filter 示例
