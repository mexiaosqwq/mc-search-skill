# mc-search

Minecraft content aggregation search tool with four-platform parallel search.

[![Version](https://img.shields.io/github/v/release/mexiaosqwq/mc-search-skill)](https://github.com/mexiaosqwq/mc-search-skill/releases)
[![License](https://img.shields.io/github/license/mexiaosqwq/mc-search-skill)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange)](skills/mc-search/SKILL.md)

[中文文档 →](README.md)

## Project Overview

mc-search is a Minecraft content search **Skill for Claude Code**, capable of searching four platforms in parallel:

- **MC 百科** (mcmod.cn) — Chinese mods/items/modpacks
- **Modrinth** — English mods/shaders/resourcepacks/modpacks
- **minecraft.wiki** — Vanilla game wiki (English)
- **minecraft.wiki/zh** — Vanilla game wiki (Chinese)

Supports searching for mods, modpacks, shaders, resourcepacks, items, entities, biomes, dimensions, and other game content.

## Install to Claude Code

Place the `skills/mc-search` directory in Claude Code's `skills` directory:

```bash
# Method 1: Clone and install
git clone https://github.com/mexiaosqwq/mc-search-skill.git
cp -r mc-search-skill/skills/mc-search ~/.claude/skills/

# Method 2: Clone directly to skills
cd ~/.claude/skills
git clone https://github.com/mexiaosqwq/mc-search-skill.git temp
cp -r temp/skills/mc-search .
rm -rf temp
```

## Features

- **Four Platforms**: MC 百科，Modrinth, minecraft.wiki (English/Chinese)
- **Multiple Types**: mods, modpacks, shaders, resourcepacks, items, entities, biomes, dimensions
- **Result Fusion**: Cross-platform results auto-sorted and merged
- **Dependency Query**: Automatic mod dependency retrieval
- **Recipe Query**: Item crafting recipe lookup
- **Local Cache**: Optional caching mechanism to reduce network requests

## Quick Usage

**Claude Code will automatically detect and invoke this skill** when users ask about:

```
"搜索机械动力"
"钠模组信息"
"BSL 光影怎么样"
"wiki 附魔台"
"RLCraft 整合包"
```

### Manual Testing

```bash
cd ~/.claude/skills/mc-search
mc-search --json search sodium
mc-search --json show sodium --full
mc-search --json wiki enchanting
```

## Commands

### search — Multi-platform search

```bash
mc-search --json search <keyword> [options]
```

| Option | Description |
|--------|-------------|
| `--shader` | Shader pack search (Modrinth only) |
| `--modpack` | Modpack search |
| `--resourcepack` | Resource pack search (Modrinth only) |
| `--type` | Content type: mod/item/shader/resourcepack/modpack |
| `--platform` | Platform: all/mcmod/modrinth/wiki/wiki-zh |
| `--author` | Search by author (dual platform) |
| `-n <count>` | Max results per platform (default 15) |
| `--timeout <sec>` | Timeout in seconds (default 12) |

### show — View details/deps/recipes

```bash
mc-search --json show <name/URL/ID> [options]
```

| Option | Description |
|--------|-------------|
| `--full` | Full dual-platform info |
| `--deps` | Dependencies |
| `--recipe` | Crafting recipe (items only) |
| `--skip-dep` | Skip dependency lookup (speed up, only with `--full`) |
| `--skip-mr` | Skip Modrinth query (speed up, only with `--full`) |

### wiki — Vanilla Wiki search & read

```bash
mc-search --json wiki <keyword or URL> [options]
```

| Option | Description |
|--------|-------------|
| `-r` | Read first result after search |
| `-n` | Max results |
| `-p` | Paragraphs to read |

## Global Options

| Option | Description |
|--------|-------------|
| `--json` | JSON format output (recommended) |
| `-o, --output` | Output to file |
| `--cache` | Enable local cache (TTL 1 hour) |
| `--no-mcmod` | Disable MC 百科 |
| `--no-mr` | Disable Modrinth |
| `--no-wiki` | Disable English wiki |
| `--no-wiki-zh` | Disable Chinese wiki |
| `--screenshots <count>` | Screenshot count (show command only, default 0) |

## Project Structure

```
mc-search-skill/
├── skills/
│   └── mc-search/              # Skill directory (for Claude Code)
│       ├── SKILL.md            # Claude Code Skill definition
│       ├── pyproject.toml      # Python package config
│       ├── scripts/
│       │   ├── core.py         # Core search logic
│       │   └── cli.py          # CLI entry
│       └── references/         # Detailed documentation
└── README.md
```

## License

MIT License

## Acknowledgments

Thanks to the following platforms for providing data support:

- [MC 百科](https://www.mcmod.cn/)
- [Modrinth](https://modrinth.com/)
- [Minecraft Wiki](https://minecraft.wiki/)
