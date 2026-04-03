# Changelog

## [Unreleased]

## [0.2.0] — 2026-04-03

### Added
- Claude Code Skill 完整定义（SKILL.md）
- 三平台并行搜索：`search` 命令
- MC百科搜索：模组 (`--type mod`) 和物品 (`--type item`)
- MC百科作者搜索：`search --author`
- minecraft.wiki 搜索 + 正文读取
- Modrinth 搜索（mod / shader / resourcepack）
- Modrinth 依赖树查询：`dep`
- Modrinth 版本更新检查：`update-check`
- Modrinth 作者搜索：`author`
- MC百科模组详情：`info`（支持 `-T/-a/-d/-v/-g/-c/-s/-S` 字段过滤）
- `--mr` 联动查询 Modrinth 信息
- 本地缓存系统（TTL 1小时）
- `--json` 全局输出格式
- `--output` 文件输出
- 平台开关：`--no-mcmod` / `--no-mr` / `--no-wiki`

### Documentation
- API 参考文档（references/mcmod-api.md, modrinth-api.md）
- 统一结果 Schema 文档（references/result-schema.md）
- 故障排查指南（references/troubleshooting.md）
