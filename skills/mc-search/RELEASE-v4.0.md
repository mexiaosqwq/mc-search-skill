# Release Notes - v4.0.0

**发布日期**: 2026-04-05

## 核心功能变更

### ✨ 新增项目类型支持

1. **光影包 (Shader) 搜索**
   - `search --type shader` - 仅 Modrinth 平台
   - `full` 命令支持光影包 URL
   - `mr -t shader` 单平台搜索

2. **材质包 (Resourcepack) 搜索**
   - `search --type resourcepack` - 仅 Modrinth 平台
   - `full` 命令支持材质包 URL
   - `mr -t resourcepack` 单平台搜索

3. **整合包 (Modpack) 搜索增强**
   - MC百科整合包多 filter 策略（2, 0, 20, 10）
   - Modrinth 整合包完全支持（type="modpack"）
   - `search --type modpack` 跨 MC百科 + Modrinth 搜索
   - `full` 命令支持整合包 URL

### 🔧 智能平台过滤

- **shader/resourcepack**: 自动仅搜索 Modrinth
- **modpack**: 自动搜索 MC百科 + Modrinth
- **entity/biome/dimension**: 优先 minecraft.wiki

### 🛠️ 代码质量改进

1. **函数提取**
   - `_search_modrinth_exact()` - Modrinth 精确搜索
   - `_parse_project_identifier()` - 通用 URL 解析

2. **常量提取**
   - `_PROJECT_TYPE_LABELS` - 项目类型标签
   - `_MCMOD_MODPACK_FILTERS` - 整合包 filter 列表

3. **Bug 修复**
   - 移除重复的 `_MCMOD_FILTER_MOD` 常量
   - 修复 Modrinth type 和 URL 返回

### 📚 文档重构

1. **SKILL.md 精简**
   - 删除冗余内容
   - 保留核心命令参考
   - 补充类型说明

2. **CLAUDE.md 更新**
   - 同步最新功能
   - 更新目录结构

3. **清理工作**
   - 删除审查报告文件
   - 清理 API 文档

## 文件变更统计

| 文件 | 变更行数 | 说明 |
|------|---------|------|
| `SKILL.md` | +548/-XXX | 重构精简 |
| `CLAUDE.md` (根目录) | +37/-XXX | 更新功能 |
| `scripts/cli.py` | +245/-XXX | 功能增强 |
| `scripts/core.py` | +130/-XXX | 平台过滤 |
| `references/` | -87 | 清理文档 |

## 版本升级

- **SKILL.md**: `0.5.0` → `4.0.0`（主要版本）
- **pyproject.toml**: `0.3.0` → `4.0.0`（主要版本）

---

**提交历史** (v3.x → v4.0.0): 15+ 次提交
