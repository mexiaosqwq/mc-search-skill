# Clean Code Review (代码状态审查)

**审查日期**: 2026-04-05
**审查文件**: `scripts/core.py`, `scripts/cli.py`
**审查范围**: 当前工作区所有变更

---

## Triage (自动分类)

- ** Docs-only**: no (有代码变更)
- ** React/Next perf review**: no (Python 项目)
- ** UI guidelines audit**: no (CLI 工具)
- ** Reason**: Python CLI 项目，另一 Claude Code 进行了深度修改

---

## 1. Naming Issues【有意义的命名】

### ✅ 良好：常量命名已优化

- **位置**: `core.py:78-80`
- **代码**:
  ```python
  _DEFAULT_RESULTS_PER_PLATFORM = 15  # 每平台默认结果数（所有类型统一）
  # 向后兼容别名
  _SOURCE_MAX = _DEFAULT_RESULTS_PER_PLATFORM
  ```
- **评价**: 命名清晰，且保留向后兼容别名

### ⚠️ 中等：部分变量名仍可改进

- **位置**: `core.py:103`
- **代码**: `_MOD_META_PAT = re.compile(r"^(?:\(\d+\)\s*)?Mod(?:讨论|教程)\s*\(\d+\)")`
- **问题**: `_MOD_META_PAT` 中的 `PAT` 冗余（正则变量本身就是 pattern）
- **建议**:
  ```python
  # 当前
  _MOD_META_PAT = re.compile(...)

  # 建议
  _MOD_META_RE = re.compile(...)  # RE 表示正则表达式
  ```
- **严重程度**: Low

---

## 2. Function Issues【小函数 + 单一职责】

### ✅ 良好：函数拆分合理

- **位置**: `cli.py`（另一个 Claude 的修改）
- **评价**: `_fetch_modrinth_info` 函数被拆分为多个子逻辑，符合 SRP 原则

### ⚠️ 中等：`_fetch_modrinth_info` 函数过长

- **位置**: `cli.py:522-597`
- **问题**: 函数 76 行，包含 slug 精确匹配、名称精确匹配、模糊匹配等多层逻辑
- **建议**: 可提取为独立的匹配函数
  ```python
  def _find_best_modrinth_match(hits: list, search_term: str) -> dict | None:
      """在搜索结果中找到最佳匹配的模组"""
      # 精确匹配逻辑
      # 名称匹配逻辑
      # 模糊匹配逻辑
  ```
- **严重程度**: Medium

---

## 3. Duplication Issues【DRY】

### ✅ 良好：无明显重复代码

- **评价**: 另一 Claude Code 的修改中，Modrinth 搜索逻辑已去重

---

## 4. Over-Engineering【YAGNI】

### ✅ 良好：无过度设计

- **评价**: 代码保持实用，无未使用的兼容性代码

---

## 5. Magic Numbers【避免硬编码】

### ✅ 良好：常量已提取

- **位置**: `core.py:51-81`
- **评价**: 所有魔法数字已提取为有意义的常量

### ⚠️ 低：部分魔法数字仍有遗漏

- **位置**: `cli.py:565-581`
- **代码**:
  ```python
  if hit_slug.lower() == norm_search or hit_slug.lower() == mr_search_name.lower():
      best_score = 200  # 硬编码分数
  ...
  if norm_hit == norm_search:
      best_score = 150  # 硬编码分数
  ...
  if norm_search in norm_hit or norm_hit in norm_search:
      score = 50  # 硬编码分数
  ```
- **建议**: 定义为常量
  ```python
  # 在文件顶部定义
  _MODRINTH_MATCH_SCORE_EXACT_SLUG = 200
  _MODRINTH_MATCH_SCORE_EXACT_NAME = 150
  _MODRINTH_MATCH_SCORE_FUZZY = 50
  _MODRINTH_MATCH_SCORE_PREFIX = 30
  _MODRINTH_MATCH_THRESHOLD = 50
  ```
- **严重程度**: Low

---

## 6. Structural Clarity【结构清晰度】

### ✅ 良好：嵌套条件减少

- **评价**: 另一 Claude Code 的修改中，使用了 early return 和函数提取

### ⚠️ 中等：`_fuse_results` 中的防御性编程可优化

- **位置**: `core.py:1723-1728`
- **代码**:
  ```python
  # 防御性编程：content_type 可能为 None（如果上游未正确传递）
  if content_type is None:
      content_type = "mod"  # 默认使用 mod 优先级
  prio_key = "default" if content_type in ("mod", "item") else "other"
  platform_prio = _CONTENT_PLATFORM_PRIORITY.get(prio_key, _CONTENT_PLATFORM_PRIORITY["default"])
  ```
- **问题**: `.get()` 的 fallback 永远不会触发（因为 `prio_key` 总是 "default" 或 "other"）
- **建议**: 简化为
  ```python
  if content_type is None:
      content_type = "mod"
  prio_key = "default" if content_type in ("mod", "item") else "other"
  platform_prio = _CONTENT_PLATFORM_PRIORITY[prio_key]  # 直接索引，无需 fallback
  ```
- **严重程度**: Low

---

## 7. Project Conventions【项目规范】

### ✅ 良好：导入顺序已优化

- **位置**: `core.py:7-17`
- **评价**: `concurrent.futures` 已按字母顺序排列

### ⚠️ 低：注释风格不一致

- **位置**: `core.py` 多处
- **问题**: 部分注释使用 `# === 标题 ===`，部分使用普通 `#`
- **建议**: 统一注释风格
- **严重程度**: Low

---

## 总结

### 问题统计
- **High**: 0
- **Medium**: 1 (函数过长)
- **Low**: 4 (命名、魔法数字、防御性编程、注释风格)

### 建议修复顺序
1. 提取 `_fetch_modrinth_info` 中的匹配逻辑为独立函数 (Medium)
2. 定义 Modrinth 匹配分数常量 (Low)
3. 简化 `_fuse_results` 中的防御性逻辑 (Low)
4. 统一注释风格 (Low)

---

**判定**: **Ready** (可合并，建议后续优化)

---

## 补充审查报告（由 Claude 执行）

### 📊 代码规模分析

| 指标 | 数值 |
|------|------|
| 总函数数 | 52 个 |
| 超长函数（>100行） | 5 个 |
| 常量定义 | 30+ 个 |

---

### 🔴 高优先级问题（新增）

#### 1. [函数过大] `get_mod_info` - 149 行

- **位置**: `core.py:1184`
- **说明**: 函数包含多个职责（获取数据、解析、截断、缓存）
- **建议拆分**:
  ```python
  def _fetch_modrinth_project(mod_id: str) -> dict | None: ...
  def _parse_modrinth_license(data: dict) -> str: ...
  def _parse_modrinth_body(data: dict, no_limit: bool) -> str: ...
  def _fetch_modrinth_members(project_id: str) -> str | None: ...
  def _fetch_modrinth_versions(project_id: str, no_limit: bool) -> tuple[list, dict]: ...
  ```
- **严重程度**: High

#### 2. [函数过大] `_read_wiki_impl` - 138 行

- **位置**: `core.py:1610`
- **说明**: 单一函数处理过多 HTML 解析逻辑
- **建议拆分**:
  ```python
  def _extract_wiki_title(html: str) -> str: ...
  def _extract_wiki_content(html: str, no_limit: bool) -> tuple[list, list]: ...
  ```
- **严重程度**: High

#### 3. [函数过大] `_parse_mcmod_item_result` - 122 行

- **位置**: `core.py:240`
- **说明**: 物品页面解析逻辑过长
- **建议拆分**:
  ```python
  def _parse_item_title(html: str) -> tuple[str, str]: ...
  def _parse_item_info_table(html: str) -> dict: ...
  def _parse_item_description(html: str) -> str: ...
  ```
- **严重程度**: High

---

### 🟡 中优先级问题（新增）

#### 4. [函数过大] `_extract_mcmod_external_links` - 108 行

- **位置**: `core.py:711`
- **建议**: 按链接类型提取子函数
- **严重程度**: Medium

#### 5. [函数过大] `search_mcmod` - 106 行

- **位置**: `core.py:975`
- **建议**: 提取去重、排序、截断逻辑为子函数
- **严重程度**: Medium

#### 6. [DRY] 重复的名称解析逻辑

- **位置**: 多处
- **说明**: `_parse_mcmod_result` 和 `_parse_mcmod_item_result` 中都有类似的名称解析代码
- **建议**: 提取通用函数
  ```python
  def _parse_display_name(raw_title: str, source: str) -> tuple[str, str]:
      """从原始标题解析中文名和英文名"""
      ...
  ```
- **严重程度**: Medium

---

### ✅ 做得好的地方（新增）

1. **常量集中定义** - 文件顶部的常量定义清晰（`core.py:51-81`）
2. **函数命名语义化** - 如 `_extract_mcmod_cover`, `_extract_mcmod_versions`
3. **文档字符串完整** - 所有主要函数都有 docstring
4. **错误处理完善** - 使用 `_SearchError` 区分错误类型
5. **模块化设计** - `core.py` 和 `cli.py` 职责分离
6. **作者团队抓取** - 新功能的实现清晰且健壮

---

### 📋 改进优先级（更新）

| 优先级 | 行动项 | 预估工作量 |
|--------|--------|------------|
| P0 | 拆分 `get_mod_info` (149行) | 2-3 小时 |
| P1 | 拆分 `_read_wiki_impl` (138行) | 1-2 小时 |
| P1 | 拆分 `_parse_mcmod_item_result` (122行) | 1-2 小时 |
| P2 | 拆分 `_extract_mcmod_external_links` (108行) | 1-2 小时 |
| P2 | 拆分 `search_mcmod` (106行) | 1-2 小时 |
| P3 | 提取名称解析通用函数 | 0.5 小时 |
| P3 | 定义 Modrinth 匹配分数常量 | 0.5 小时 |

---

### 🎯 最终判定

**代码质量**: **良好** (B+)

**主要优点**:
- 常量命名清晰
- 模块化设计良好
- 新功能（作者团队抓取）实现完善

**主要改进点**:
- 5个函数过长，需要拆分
- 部分代码重复可以提取

**建议**: 代码可以合并，但建议在后续迭代中优先处理 P0/P1 级别的函数拆分任务。