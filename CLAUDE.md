# mcmod-info 项目指南

## 项目概述

Minecraft 模组 + 游戏内容信息查询工具，供 AI Agent 调用。

**四大平台：**
- MC百科 (mcmod.cn) — 中文模组/物品
- Modrinth — 英文 mod/光影/材质包
- minecraft.wiki — 原版游戏内容 wiki
- minecraft.wiki/zh — 原版游戏内容 wiki（中文）

## Agent 工具接口

工具名：`mcmod-search`（通过 Bash 执行）

**常用调用：**
```bash
# 搜索
mcmod-search search <关键词>          # 四平台并行
mcmod-search search <词> --type item  # 物品
mcmod-search mr <关键词>              # 仅 Modrinth

# 信息查询
mcmod-search info <模组>              # MC百科详情
mcmod-search dep <mod_slug>           # Modrinth 依赖树
mcmod-search update-check <mod> --installed <版本>  # 版本对比
mcmod-search author <用户名>          # Modrinth 作者作品

# wiki
mcmod-search wiki <关键词>            # minecraft.wiki 搜索
mcmod-search read <url>               # 读取正文

# 全局选项（所有命令共享）
mcmod-search <cmd> --json            # JSON 输出（Agent 推荐）
mcmod-search <cmd> --cache           # 启用本地缓存（TTL 1小时）
mcmod-search <cmd> --no-mcmod        # 禁用 MC百科
mcmod-search <cmd> --no-mr           # 禁用 Modrinth
mcmod-search <cmd> --no-wiki         # 禁用 minecraft.wiki
mcmod-search <cmd> --no-wiki-zh      # 禁用 minecraft.wiki/zh
mcmod-search <cmd> -o <file>         # 输出到文件

# info 子选项
mcmod-search info <模组> -T          # 仅名称/别名
mcmod-search info <模组> -a          # 仅作者
mcmod-search info <模组> -d          # 仅前置/联动模组
mcmod-search info <模组> -v          # 仅支持版本
mcmod-search info <模组> -g          # 仅截图/封面
mcmod-search info <模组> -c          # 仅分类/标签
mcmod-search info <模组> -s          # 仅来源链接
mcmod-search info <模组> -S          # 仅状态/开源属性
mcmod-search info <模组> -m          # 同时查询 Modrinth
mcmod-search info <模组> -r          # 显示物品合成表（仅 item 类型）

# 输出格式（Agent 推荐）
mcmod-search <command> --json
```

## 目录结构

```
skills/mcmod-info/
├── SKILL.md              # Agent 接口定义（核心文档）
├── pyproject.toml        # Python 包配置
├── scripts/
│   ├── cli.py            # CLI 入口
│   └── core.py           # 核心搜索逻辑
└── references/
    ├── result-schema.md  # 结果字段说明
    ├── mcmod-api.md      # MC百科 API
    ├── modrinth-api.md   # Modrinth API
    └── troubleshooting.md
```

## 开发规范

- `search_all()` 在 `--json` 模式下返回融合后的 `list[dict]`，否则返回 `{platform: [results]}`；其余搜索函数统一返回 `list[dict]`，格式见 `references/result-schema.md`
- 平台调用失败时返回空列表，不抛出异常
- 所有网络请求通过 `core._curl()` 统一发出
- 无外部依赖，仅使用 Python 标准库 + curl
- Agent 调用优先使用 `--json` 便于解析

## 本地测试

```bash
# 安装
pip install -e .

# 测试搜索
mcmod-search search 钠

# 测试 JSON 输出
mcmod-search search 钠 --json

# 查看帮助
mcmod-search --help
```
