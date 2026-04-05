# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**mc-search** - Minecraft 聚合搜索工具，支持四平台并行搜索（MC百科、Modrinth、minecraft.wiki 中英双站）。

## 常用命令

### 安装
```bash
pip install -e .
```

### 运行搜索
```bash
# 基本格式（--json 必须在最前面）
mc-search --json <子命令> <参数>

# 搜索模组
mc-search --json search 钠

# 获取完整信息
mc-search --json full 钠

# Wiki 搜索
mc-search --json wiki 钻石剑

# 按类型搜索
mc-search --json search RLCraft --type modpack
mc-search --json search BSL --type shader
mc-search --json search Faithful --type resourcepack

# 测试命令
python3 -m py_compile scripts/core.py scripts/cli.py  # 语法检查
```

### 开发模式
```bash
# 直接运行 Python 脚本
python3 -m scripts.cli search 测试

# 或
python3 scripts/cli.py search 测试
```

## 代码架构

### 核心模块

**scripts/core.py** (~2700 行)
- 核心搜索逻辑和数据处理
- 四大平台适配器：
  - `search_mcmod()` - MC百科搜索
  - `search_modrinth()` - Modrinth 搜索
  - `search_wiki()` / `search_wiki_zh()` - minecraft.wiki 中英搜索
- 统一结果格式和智能路由
- 缓存系统（TTL 1小时）
- 平台开关控制

**scripts/cli.py** (~650 行)
- CLI 入口点，基于 argparse
- 命令定义：`search`, `full`, `info`, `wiki`, `read`, `dep`, `author`, `mr`
- 结果输出（JSON/纯文本）
- 全局选项：`--json`, `--cache`, `--no-*`, `-o`

### 关键函数

```
search_all()              # 四平台并行搜索 + 结果融合
get_mod_info()            # 获取模组完整信息
_extract_wiki_infobox()   # Wiki Infobox 提取（拆分为 6 个辅助函数）
_fuse_results()           # 跨平台结果融合（拆分为 5 个辅助函数）
_score_relevance()        # 相关性评分（使用常量配置）
```

### 数据流

```
CLI 命令 → search_all() / get_mod_info() → 平台搜索函数 → _curl() → 结果融合 → 输出
```

### 常量配置

关键常量在 `scripts/core.py` 顶部（~100+ 个）：
- `_MAX_*` / `_MIN_*` - 数据提取限制
- `_SCORE_*` - 评分系统常量
- `_WIKI_*` - Wiki 解析配置
- `_MCMOD_*` - MC百科过滤器

## 支持的项目类型

| 类型 | 平台 | 说明 |
|------|------|------|
| `mod` | MC百科 + Modrinth | 模组搜索 |
| `item` | MC百科 | 物品/方块 |
| `modpack` | MC百科 + Modrinth | 整合包 |
| `shader` | Modrinth | 光影包 |
| `resourcepack` | Modrinth | 材质包 |
| `entity` | minecraft.wiki | 实体/生物 |
| `biome` | minecraft.wiki | 生物群系 |
| `dimension` | minecraft.wiki | 维度 |

## 已知限制

1. **JavaScript 渲染内容** - 使用 curl 获取静态 HTML，无法获取 JS 动态内容（评论、懒加载版本列表等）
2. **懒加载图片** - 仅支持 `data-src`, `data-lazy-src`, `data-original` 属性

## 开发规范

1. **返回格式** - `--json` 模式返回 `list[dict]`，字段见 `SKILL.md`
2. **错误处理** - 平台调用失败返回空列表，不抛出异常
3. **网络请求** - 统一通过 `core._curl()` 发出
4. **依赖** - 仅使用 Python 标准库 + curl，无外部依赖
5. **Agent 调用** - 优先使用 `--json` 便于解析

## 测试

目前没有自动化测试框架。手动测试建议：

```bash
# 语法检查
python3 -m py_compile scripts/core.py scripts/cli.py

# 功能测试
mc-search --json search 钠
mc-search --json full sodium
mc-search --json wiki 钻石剑

# 性能测试
time mc-search --json search sodium
```

## 文档

- `SKILL.md` - Agent 接口定义（核心文档）
- `RELEASE-v4.0.md` - 发布说明
- `plans/clean-code-fixes.md` - Clean Code 修复计划（已完成）

## 代码质量改进（2026-04-05 完成）

**已完成的改进**:
- 3 个大函数拆分为 17 个小函数（最大从 220→60 行）
- 17 个评分/配置常量消除魔法数字
- 嵌套层级从 4 层降至 2 层
- 改进懒加载图片检测（支持 3 种属性）
- 修复 3 个实际 bug：
  1. 生物群系类型判断错误
  2. 中文正则不兼容
  3. CLI 重复函数定义
- 清理：删除 ISSUES.md，合并报告文件

**当前状态**: 95/95 测试通过，0 失败
