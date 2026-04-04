# mc-search 文档一致性审查报告

审查日期：2026-04-04（修复后最终报告）
审查范围：SKILL.md / CLAUDE.md / references/*.md / pyproject.toml / scripts/cli.py / scripts/core.py

---

## 审查结论

- **Verdict**: ✅ Pass
- **Summary**: P0:0 P1:0 P2:0 P3:0 Pending:0
- **Note**: 重命名后复查，已修复所有遗留问题

---

## 本次修复项

| ID | 文件 | 修改内容 |
|----|------|----------|
| 20 | troubleshooting.md:34 | `~/.cache/mcmod-info/` → `~/.cache/mc-search/` |
| 21 | troubleshooting.md:71,90,91 | `mcmod-search` → `mc-search` |
| 22 | troubleshooting.md:14,82 | "三个平台" → "四个平台" |
| 23 | modrinth-api.md:13 | User-Agent 说明更新为 `Mozilla/5.0` |
| 24 | SKILL.md:283 | 章节 wiki → `### 8.` |
| 25 | SKILL.md:305 | 章节 read → `### 9.` |

---

## 已修复项（历史）

- ✅ P1-1: CLAUDE.md `search_all()` 返回类型描述已更正
- ✅ P1-2: README.md 已添加 `full` 命令
- ✅ P1-3: README.md `update-check` 确认已存在
- ✅ P1-4: SKILL.md 已移除 `--type block/mechanic`
- ✅ P2-6: troubleshooting.md filter 示例已更正
- ✅ P2-11: result-schema.md body 截断描述已更正
- ✅ P2-12: SKILL.md dep --installed "仅 dep" 已补充
- ✅ P3-14: SKILL.md 章节编号已更正（dep/update-check/author）
- ✅ P3-15: README.md "三大平台" → "四大平台"
- ✅ P3-16: modrinth-api.md 限速描述已更正
- ✅ P2-7: `search --author` JSON 返回空键已移除
- ✅ P2-8: result-schema.md 已添加 `search_mcmod_author` 格式说明
- ✅ P3-13: core.py 重复函数定义已清理
- ✅ P3-17: SKILL.md `search_results` 说明已标注
- ✅ Pending-19: SKILL.md info 参数格式说明已添加提示

---

## 已验证一致

| 项目 | 状态 | 说明 |
|------|------|------|
| SKILL.md 命令格式 | ✅ | 所有命令示例使用 `mc-search` |
| CLAUDE.md 命令格式 | ✅ | 所有命令示例使用 `mc-search` |
| result-schema.md body 截断 | ✅ | `_MAX_BODY_CHARS = 5000` |
| result-schema.md version_groups | ✅ | `_MAX_VERSION_GROUPS = 5` |
| result-schema.md changelogs | ✅ | `_MAX_CHANGELOGS = 5` |
| core.py 缓存目录 | ✅ | `~/.cache/mc-search/` 与项目名称一致 |
| pyproject.toml 包名 | ✅ | `mc-search 0.3.0` |
| troubleshooting.md 缓存目录 | ✅ | `~/.cache/mc-search/` |
| troubleshooting.md 命令名 | ✅ | 使用 `mc-search` |
| troubleshooting.md 平台数量 | ✅ | 四个平台 |
| modrinth-api.md User-Agent | ✅ | `Mozilla/5.0` 模拟浏览器请求 |
| SKILL.md 章节编号 | ✅ | author=7, wiki=8, read=9 |
