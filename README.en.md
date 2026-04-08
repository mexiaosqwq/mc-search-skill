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
- **MC百科** (mcmod.cn) — Chinese mod database
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

# Get full info (recommended)
mc-search --json details sodium --full

# Get mod details
mc-search --json details sodium

# Search wiki
mc-search --json wiki diamond sword

# Search by type
mc-search --json search BSL --type shader
mc-search --json search RLCraft --type modpack

# Quick dependencies
mc-search --json deps sodium
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

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `search` | Multi-platform search | `mc-search --json search sodium` |
| `search --platform` | Search specific platform | `mc-search --json search sodium --platform modrinth` |
| `details` | Get mod details | `mc-search --json details sodium` |
| `details --full` | Full info (deps+versions) | `mc-search --json details sodium --full` |
| `deps` | Quick dependencies | `mc-search --json deps sodium` |
| `info` | MC百科 details | `mc-search --json info 钠` |
| `full` | [Deprecated] Full info | `mc-search --json full sodium` |
| `wiki` | Search minecraft.wiki | `mc-search --json wiki enchanting` |
| `read` | Read wiki page | `mc-search --json read <url>` |
| `dep` | Modrinth dependencies | `mc-search --json dep sodium` |
| `author` | Search by author | `mc-search --json author jellysquid_` |

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
│   └── cli.py        # CLI entry point
├── references/       # Detailed documentation
└── pyproject.toml    # Python package config
```

---

## v4.5.0 Improvements

- Clean Code refactoring (15 issues fixed)
- Hardcoded constants extracted
- Data completeness enhanced (Modrinth fields)
- Tests: 95/95 passing, 0 failures

## License

MIT License

## Acknowledgments

- [MC百科](https://www.mcmod.cn/) — Chinese mod database
- [Modrinth](https://modrinth.com/) — Modern mod platform
- [Minecraft Wiki](https://minecraft.wiki/) — Game wiki
