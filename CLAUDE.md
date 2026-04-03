# mcmod-info 项目指南

## 项目概述

Minecraft 模组 + 游戏内容信息查询工具，三平台并行搜索：
- **MC百科** (mcmod.cn) — 中文模组/物品
- **Modrinth** — 英文 mod/光影/材质包
- **minecraft.wiki** — 原版游戏内容

## 技术栈

- Python 3.8+，无外部依赖（仅使用 curl）
- Claude Code Skill 格式

## 目录结构

```
skills/mcmod-info/
├── SKILL.md              # Claude Code Skill 定义
├── pyproject.toml        # Python 包配置
├── scripts/
│   ├── cli.py            # CLI 入口
│   └── core.py           # 核心搜索逻辑
└── references/           # API 文档
```

## 常用命令

```bash
# 安装
pip install -e .

# 测试
mcmod-search search 钠

# CLI 帮助
mcmod-search --help
```

## 开发规范

- 搜索函数统一返回 `list[dict]`，格式见 `references/result-schema.md`
- 平台调用失败时返回空列表，不抛出异常
- 所有网络请求通过 `core._curl()` 统一发出
