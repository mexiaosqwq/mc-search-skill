# mc-search - Minecraft 聚合搜索工具

[![Version](https://img.shields.io/github/v/release/mexiaosqwq/mc-search-skill)](https://github.com/mexiaosqwq/mc-search-skill/releases)
[![License](https://img.shields.io/github/license/mexiaosqwq/mc-search-skill)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)

> Minecraft 内容聚合搜索工具，支持 **四平台并行搜索**：MC百科、Modrinth、minecraft.wiki（中英双站）

## ✨ 特性

- 🌐 **四平台并行**: MC百科、Modrinth、minecraft.wiki 英文/中文
- 📦 **多类型支持**: 模组/整合包/光影包/材质包/物品/实体/生物群系/维度
- 🔍 **智能搜索**: 相关性评分、多平台融合、去重排序
- 📊 **完整数据**: Infobox 提取、版本历史、依赖关系、截图画廊
- 🚀 **高性能**: 并发搜索、本地缓存（TTL 1小时）
- 📝 **CLI 友好**: JSON 输出、Agent 集成

## 🚀 快速开始

### 安装

```bash
pip install mc-search
```

### 基本用法

```bash
# 搜索模组
mc-search --json search 钠

# 获取完整信息
mc-search --json full sodium

# Wiki 搜索
mc-search --json wiki 钻石剑

# 按类型搜索
mc-search --json search BSL --type shader
mc-search --json search RLCraft --type modpack
```

### Python API

```python
from scripts.core import search_all, get_mod_info, read_wiki

# 多平台搜索
result = search_all("sodium", fuse=True)

# 获取模组详情
mod = get_mod_info("sodium-fabric")

# 读取 Wiki 页面
wiki = read_wiki("https://minecraft.wiki/w/Diamond_Sword")
```

## 📊 支持的项目类型

| 类型 | 说明 | 支持平台 |
|------|------|----------|
| `mod` | 模组 | MC百科 + Modrinth |
| `item` | 物品/方块 | MC百科 |
| `modpack` | 整合包 | MC百科 + Modrinth |
| `shader` | 光影包 | Modrinth |
| `resourcepack` | 材质包 | Modrinth |
| `entity` | 实体/生物 | minecraft.wiki |
| `biome` | 生物群系 | minecraft.wiki |
| `dimension` | 维度 | minecraft.wiki |

## 🏗️ 架构

```
skills/mc-search/
├── scripts/
│   ├── core.py       # 核心搜索逻辑 (~2800 行)
│   └── cli.py        # CLI 入口 (~1000 行)
├── SKILL.md          # Agent 接口定义
├── CLAUDE.md         # 开发者指南
└── RELEASE-v4.5.md   # 发布说明
```

## 📈 代码质量

**v4.5.0 改进**:
- ✅ Clean Code 重构 (15 个问题修复)
- ✅ 硬编码清理 (类型常量提取)
- ✅ 数据完整性增强 (Modrinth 字段)
- ✅ 测试: 95/95 通过，0 失败

## 📖 文档

- **[SKILL.md](SKILL.md)** - Agent 接口定义（用户使用指南）
- **[CLAUDE.md](CLAUDE.md)** - 开发者指南（代码架构）
- **[RELEASE-v4.5.md](RELEASE-v4.5.md)** - 发布说明

## 🔧 开发

```bash
# 克隆仓库
git clone https://github.com/mexiaosqwq/mc-search-skill.git
cd mc-search-skill

# 安装依赖
pip install -e .

# 运行测试
python3 -m py_compile scripts/core.py scripts/cli.py
```

## 📄 许可证

MIT License

## 🙏 致谢

- [MC百科](https://www.mcmod.cn/) - 中文模组百科
- [Modrinth](https://modrinth.com/) - 现代化模组平台
- [Minecraft Wiki](https://minecraft.wiki/) - 原版游戏Wiki
