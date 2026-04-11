# mc-search

> Skill for Minecraft content search

[![Version](https://img.shields.io/github/v/release/mexiaosqwq/mc-search-skill)](https://github.com/mexiaosqwq/mc-search-skill/releases)
[![License](https://img.shields.io/github/license/mexiaosqwq/mc-search-skill)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange)](skills/mc-search/SKILL.md)

[中文文档 →](README.md)

---

## What is this?

**mc-search** is a **Claude Code Skill** that enables AI agents to search Minecraft content across four platforms simultaneously.

**Supported Platforms**:
- **MC 百科 (mcmod.cn)** — Chinese mod database
- **Modrinth** — Modern mod platform
- **minecraft.wiki** — Game wiki (English)
- **minecraft.wiki/zh** — Game wiki (Chinese)

**Supported Types**: mods, items, modpacks, shaders, resourcepacks, entities, biomes, dimensions

---

## Quick Start

### Method 1: Clone and use (Recommended)

```bash
# Clone repository
git clone https://github.com/mexiaosqwq/mc-search-skill.git
cd mc-search-skill/skills/mc-search

# Install
pip install -e .
```

After installation, use anywhere:
```bash
mc-search --json search sodium
```

### Method 2: Copy to Claude Code Skills directory

To let Claude Code automatically use this Skill:

```bash
# 1. Clone or download repository
git clone https://github.com/mexiaosqwq/mc-search-skill.git

# 2. Copy skill to Claude Code directory
cp -r mc-search-skill/skills/mc-search ~/.claude/skills/

# 3. Install in skill directory
cd ~/.claude/skills/mc-search
pip install -e .
```

> **Important**: Must run `pip install -e .` in the `skills/mc-search/` directory, because that's where `pyproject.toml` is located.

### Standalone CLI

```bash
# Search mods
mc-search --json search sodium

# Search shaders (shortcut flag)
mc-search --json search BSL --shader

# Search modpacks
mc-search --json search tech --modpack

# Get full info (recommended)
mc-search --json show sodium --full

# Quick dependencies
mc-search --json show sodium --deps

# Wiki search
mc-search --json wiki enchanting

# Wiki read page
mc-search --json wiki https://minecraft.wiki/w/Diamond_Sword
```

### Python API

```python
from scripts.core import search_all, fetch_mod_info  # Note: fetch_mod_info, not get_mod_info

# Multi-platform search
result = search_all("sodium", fuse=True)

# Get mod details
mod = fetch_mod_info("sodium-fabric")
```

---

## What can it search?

| Type | Platforms | Description |
|------|-----------|-------------|
| `mod` | MC百科 + Modrinth | Mods (Fabric/Forge/NeoForge) |
| `item` | MC百科 | Items/blocks |
| `modpack` | MC百科 + Modrinth | Modpacks |
| `shader` | Modrinth | Shader packs |
| `resourcepack` | Modrinth | Resource/texture packs |
| `entity` | minecraft.wiki | Entities/mobs |
| `biome` | minecraft.wiki | Biomes |
| `dimension` | minecraft.wiki | Dimensions |

---

## Three Commands

### search — Multi-platform search

```bash
mc-search --json search <keyword> [options]
```

| Option | Description |
|--------|-------------|
| `--shader` | Shortcut: search shaders (Modrinth only) |
| `--modpack` | Shortcut: search modpacks |
| `--resourcepack` | Shortcut: search resource packs (Modrinth only) |
| `--type` | Full type: mod/item/shader/resourcepack/modpack |
| `--platform` | Platform: all/mcmod/modrinth/wiki/wiki-zh |
| `--author` | Search by author (dual platform) |
| `-n` | Max results per platform |

### show — View details/deps/recipes

```bash
mc-search --json show <name/URL/ID> [options]
```

| Option | Description |
|--------|-------------|
| `--full` | Full dual-platform info (MC百科+Modrinth+deps+versions) |
| `--deps` | Shortcut: dependencies only |
| `--recipe` | Show recipe (item only) |
| `-T/-a/-d/-v/-g/-c/-s/-S` | Field filters |

### wiki — Vanilla Wiki search & read

```bash
mc-search --json wiki <keyword or URL> [options]
```

| Option | Description |
|--------|-------------|
| `-r` | Read first result after search |
| `-n` | Max results |
| `-p` | Max paragraphs (for URL reading) |

> **Note**: `--json` flag must come **before** the subcommand.

---

## Global Options

| Option | Description |
|--------|-------------|
| `--json` | JSON format output (recommended) |
| `-o, --output` | Output to file |
| `--cache` | Enable local cache (TTL 1 hour) |
| `--no-mcmod` | Disable MC百科 |
| `--no-mr` | Disable Modrinth |
| `--no-wiki` | Disable minecraft.wiki (English) |
| `--no-wiki-zh` | Disable Chinese wiki |

---

## Architecture

```
skills/mc-search/
├── SKILL.md          # Claude Code Skill definition (user guide)
├── scripts/
│   ├── core.py       # Core search logic
│   └── cli.py        # CLI entry (3-command flat structure)
├── references/       # Detailed documentation
└── pyproject.toml    # Python package config
```

---

## v5.0.0 Improvements

- Command merge: 8 commands → 3 flat commands (search/show/wiki)
- Shortcut flags: `--shader`/`--modpack`/`--resourcepack`
- MC百科 fallback to Modrinth on failure
- Wiki search fix (no longer filters out vanilla content)
- Unified error handling

## License

MIT License

## Acknowledgments

- [MC百科](https://www.mcmod.cn/) — Chinese mod database
- [Modrinth](https://modrinth.com/) — Modern mod platform
- [Minecraft Wiki](https://minecraft.wiki/) — Game wiki
