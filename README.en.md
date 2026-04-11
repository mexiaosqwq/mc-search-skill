# mc-search

Minecraft content aggregation search tool with four-platform parallel search.

[![Version](https://img.shields.io/github/v/release/mexiaosqwq/mc-search-skill)](https://github.com/mexiaosqwq/mc-search-skill/releases)
[![License](https://img.shields.io/github/license/mexiaosqwq/mc-search-skill)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange)](skills/mc-search/SKILL.md)

[中文文档 →](README.md)

## Project Overview

mc-search is a Minecraft content search tool designed for AI Agents, capable of searching four platforms in parallel:

- **MC 百科** (mcmod.cn) — Chinese mods/items/modpacks
- **Modrinth** — English mods/shaders/resourcepacks/modpacks
- **minecraft.wiki** — Vanilla game wiki (English)
- **minecraft.wiki/zh** — Vanilla game wiki (Chinese)

Supports searching for mods, modpacks, shaders, resourcepacks, items, entities, biomes, dimensions, and other game content.

## Features

- **Four Platforms**: MC 百科，Modrinth, minecraft.wiki (English/Chinese)
- **Multiple Types**: mods, modpacks, shaders, resourcepacks, items, entities, biomes, dimensions
- **Result Fusion**: Cross-platform results auto-sorted and merged
- **Dependency Query**: Automatic mod dependency retrieval
- **Recipe Query**: Item crafting recipe lookup
- **Local Cache**: Optional caching mechanism to reduce network requests

## Quick Start

```bash
# Install
git clone https://github.com/mexiaosqwq/mc-search-skill.git
cd mc-search-skill/skills/mc-search
pip install -e .

# Usage
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
| `-n` | Max results per platform |

### show — View details/deps/recipes

```bash
mc-search --json show <name/URL/ID> [options]
```

| Option | Description |
|--------|-------------|
| `--full` | Full dual-platform info |
| `--deps` | Dependencies |
| `--recipe` | Crafting recipe (items only) |
| `-T/-a/-d/-v/-g/-c/-s/-S` | Field filters |

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

## Python API

```python
from scripts.core import search_all, fetch_mod_info

# Multi-platform search
result = search_all("sodium", fuse=True)

# Get mod details
mod = fetch_mod_info("sodium-fabric")
```

## Project Structure

```
mc-search-skill/
├── SKILL.md          # Claude Code Skill definition
├── scripts/
│   ├── core.py       # Core search logic
│   └── cli.py        # CLI entry
├── references/       # Detailed documentation
└── pyproject.toml    # Python package config
```

## License

MIT License

## Acknowledgments

Thanks to the following platforms for providing data support:

- [MC 百科](https://www.mcmod.cn/)
- [Modrinth](https://modrinth.com/)
- [Minecraft Wiki](https://minecraft.wiki/)
