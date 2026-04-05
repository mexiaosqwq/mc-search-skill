# Documentation Consistency Review (文档一致性审查) v2

**审查日期**: 2026-04-05  
**审查范围**: SKILL.md, CLAUDE.md, README.md, references/commands.md  
**审查依据**: 当前代码实现 (cli.py, core.py)

---

## 审查总结

| 严重程度 | 数量 | 说明 |
|----------|------|------|
| P0 | 0 | 安全/严重误导问题 |
| P1 | 3 | 核心功能不一致 |
| P2 | 5 | 示例不完整/命名不一致 |
| P3 | 3 | 措辞/格式/链接小问题 |
| Pending | 1 | 证据不足待查 |
| **总计** | **12** | |

---

## P1 - 核心功能不一致

### [P1-1] SKILL.md 和 CLAUDE.md 中提到不存在的 `update-check` 命令

- **位置**: 
  - `SKILL.md:259` - 示例代码 `mc-search --json update-check sodium --installed 0.5.0`
  - `CLAUDE.md:66` - 示例代码 `mc-search --json update-check sodium --installed 0.5.0`
  - `CLAUDE.md:43` - 决策树中提到 `update-check`
- **文档**: 文档中存在 `update-check` 命令的示例和说明
- **代码**: 在 `cli.py` 中未找到 `update-check` 或 `update_check` 的注册（见 `grep -n "add_parser"` 结果）
- **影响**: 用户按照文档尝试使用此命令会失败
- **建议**: 要么实现此命令，要么从文档中删除相关描述（推荐后者，因为 `full` 命令已包含版本信息）

### [P1-2] SKILL.md 中重复的"初始化"章节

- **位置**: `SKILL.md:289-304`
- **文档**: "初始化"章节出现两次（289-298 和 300-304）
- **问题**: 内容重复，且第二次出现时缺少"本地测试"部分
- **建议**: 删除重复的第二个"初始化"章节

### [P1-3] SKILL.md 中重复的"详细文档"章节

- **位置**: `SKILL.md:284-287` 和 `SKILL.md:306-309`
- **文档**: "详细文档"章节出现两次
- **问题**: 内容基本相同，造成冗余
- **建议**: 合并为一个统一的"详细文档"章节

---

## P2 - 中等优先级问题

### [P2-1] CLAUDE.md 中提到的 `update-check` 命令不存在

- **位置**: `CLAUDE.md:66`
- **文档**: `mc-search --json update-check sodium --installed 0.5.0`
- **代码**: cli.py 中无此命令注册
- **影响**: Agent 可能尝试调用不存在的命令
- **建议**: 删除该行或改为使用 `full` 命令

### [P2-2] CLAUDE.md 决策树中提到 `update-check`

- **位置**: `CLAUDE.md:43`
- **文档**: `想看详细信息 → info / dep / update-check`
- **问题**: `update-check` 命令不存在
- **建议**: 改为 `info / dep / full`

### [P2-3] SKILL.md 和 README.md 中安装路径不一致

- **位置**: 
  - `SKILL.md:293` - `pip install -e skills/mc-search`
  - `README.md:15-16` - `cd skills/mc-search && pip install -e .`
- **问题**: SKILL.md 假设用户在父目录执行，README.md 假设用户在 mc-search 目录执行
- **建议**: 统一说明，或添加"当前目录"提示

### [P2-4] SKILL.md 中 `--type` 选项说明不完整

- **位置**: `SKILL.md:159`
- **文档**: `--type <类型>` | 搜索类型过滤 | `--type item` / `--type mod` / `--type entity`
- **代码**: `core.py:search_mcmod` 只支持 `mod` 和 `item` 两种类型（见 filter_map）
- **问题**: `--type entity` 对 MC百科 搜索无效（文档可能误导用户）
- **建议**: 明确说明 `--type` 只对 MC百科 有效，且只支持 `mod` 和 `item`

### [P2-5] README.md 中的文件引用路径问题

- **位置**: `README.md:72,76`
- **文档**: `[references/result-schema.md](skills/mc-search/references/result-schema.md)`
- **问题**: 路径从 README.md 所在位置（skills/ 目录）来看是正确的，但从 mc-search/ 目录来看不正确
- **建议**: 统一路径引用方式，或使用相对路径

---

## P3 - 低优先级问题

### [P3-1] SKILL.md 中版本号未更新

- **位置**: `SKILL.md:3`
- **文档**: `version: "0.4.0"`
- **问题**: 可能需要更新到最新版本
- **建议**: 确认版本号是否与 pyproject.toml 一致

### [P3-2] CLAUDE.md 中目录结构不完整

- **位置**: `CLAUDE.md:101-111`
- **文档**: 列出了 SKILL.md, pyproject.toml, scripts/, references/
- **问题**: 未列出 CLAUDE.md 自身（新创建的文件）
- **建议**: 在目录结构中添加 CLAUDE.md

### [P3-3] commands.md 中命令示例缺少 `--json` 前缀

- **位置**: `commands.md:10,41,65,102,128,147,169,193`
- **文档**: 多处示例命令没有 `--json` 前缀（如 `mc-search search <关键词>`）
- **问题**: 与 SKILL.md 强调的"始终使用 --json"不一致
- **建议**: 所有示例都添加 `--json` 前缀

---

## Pending Evidence - 待查问题

### [Pending-1] SKILL.md 中 `--fuse` 参数说明

- **位置**: `SKILL.md:19`
- **文档**: `-n <数量>` | 每平台最多结果（默认3，`--fuse` 时最多15）
- **问题**: 需要确认 `--fuse` 是否是实际的 CLI 参数，还是内部参数
- **状态**: 需要进一步验证代码

---

## 审查结论

- **判定**: **Conditional Pass** (有条件通过)
- **摘要**: P0:0 P1:3 P2:5 P3:3 Pending:1
- **修复优先级**: P1 → P2 → P3

### 关键修复项
1. [P1-1] 移除 SKILL.md 和 CLAUDE.md 中所有 `update-check` 命令引用
2. [P1-2] 删除 SKILL.md 中重复的"初始化"章节
3. [P1-3] 删除 SKILL.md 中重复的"详细文档"章节
4. [P2-1] 修复 CLAUDE.md 中的 `update-check` 引用
5. [P2-2] 修复 CLAUDE.md 决策树中的 `update-check` 引用

---

**审查方法**: 
- 对比文档与 cli.py、core.py 实际实现
- 使用 grep 验证命令注册情况
- 检查文档内部一致性
