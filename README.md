# mc-search

**Minecraft 模组 + 游戏内容信息查询工具**，专为 AI Agent 设计，同时搜索四大平台。

## 核心能力

- **MC百科** — 中文模组、物品、方块资料
- **Modrinth** — 英文 mod 搜索、依赖树、版本历史、作者作品
- **minecraft.wiki** — 原版游戏内容（附魔、合成、生物等）

## 使用方式

### 作为 Agent Skill 使用

将 `skills/mc-search/` 文件夹复制到 Agent 的 skills 目录即可，无需安装。

### 作为命令行工具使用

```bash
pip install mc-search
mc-search --help
```

**依赖**: Python 3.8+ 和 curl。无需 API key。

## 快速参考

| 场景 | 命令 |
|------|------|
| 四平台搜索 | `mc-search search <关键词>` |
| 物品搜索 | `mc-search search <关键词> --type item` |
| 作者搜索 | `mc-search search --author <名>` |
| Modrinth 搜索 | `mc-search mr <关键词>` |
| 依赖树 | `mc-search dep <mod_slug>` |
| 版本检查 | `mc-search update-check <mod> --installed <版本>` |
| 作者作品 | `mc-search author <用户名>` |
| 模组详情 | `mc-search info <名称或URL>` |
| 一键完整信息 | `mc-search full <名称>` |
| wiki 搜索 | `mc-search wiki <关键词>` |
| wiki 正文 | `mc-search read <url>` |

## AI Agent 使用

推荐使用 `--json` 输出便于程序解析：

```bash
mc-search --json search <关键词>
mc-search --json info <模组名>
mc-search --json full <模组名>
```

## 文档

- [SKILL.md](skills/mc-search/SKILL.md) — Agent 专用接口文档
- [references/result-schema.md](skills/mc-search/references/result-schema.md) — 结果字段说明
- [references/troubleshooting.md](skills/mc-search/references/troubleshooting.md) — 故障排查

## 许可证

MIT License
