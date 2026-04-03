# mcmod-info

**Minecraft 模组 + 游戏内容信息查询Skills工具**，专为 AI Agent 设计，同时搜索四大平台。

## 核心能力

- **MC百科** — 中文模组、物品、方块资料
- **Modrinth** — 英文 mod 搜索、依赖树、版本历史、作者作品
- **minecraft.wiki** — 原版游戏内容（附魔、合成、生物等）

## 安装

```bash
pip install mcmod-info
```

依赖：**Python 3.8+** 和 **curl**。无需 API key。

## 快速参考

| 场景 | 命令 |
|------|------|
| 四平台搜索 | `mcmod-search search <关键词>` |
| 物品搜索 | `mcmod-search search <关键词> --type item` |
| 作者搜索 | `mcmod-search search --author <名>` |
| Modrinth 搜索 | `mcmod-search mr <关键词>` |
| 依赖树 | `mcmod-search dep <mod_slug>` |
| 版本检查 | `mcmod-search update-check <mod> --installed <版本>` |
| 作者作品 | `mcmod-search author <用户名>` |
| 模组详情 | `mcmod-search info <名称或URL>` |
| 一键完整信息 | `mcmod-search full <名称>` |
| wiki 搜索 | `mcmod-search wiki <关键词>` |
| wiki 正文 | `mcmod-search read <url>` |

## AI Agent 使用

将 `skills/mcmod-info/` 放入 Agent 的 skills 目录，Agent 即可通过工具调用接口执行 `mcmod-search`。

推荐使用 `--json` 输出便于程序解析。

## 文档

- [SKILL.md](skills/mcmod-info/SKILL.md) — Agent 专用接口文档
- [references/result-schema.md](skills/mcmod-info/references/result-schema.md) — 结果字段说明
- [references/troubleshooting.md](skills/mcmod-info/references/troubleshooting.md) — 故障排查

## 许可证

MIT License
