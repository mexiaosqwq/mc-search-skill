#!/usr/bin/env python3
"""mc-search 融合管线 — 多平台编排 + CJK桥接 + 评分/去重/排序"""

import re
import time
from concurrent import futures as futures_module

from ._http import (
    logger, SearchError,
    _platform_enabled, _PLATFORM_LOCK,
    _DEFAULT_RESULTS_PER_PLATFORM,
    _TEXT_CONTENT_TYPES, _CONTENT_PLATFORM_PRIORITY,
    _VISUAL_CONTENT_TYPES, _MODRINTH_CONTENT_TYPES,
    _MAX_FETCH_WORKERS, _EMPTY_MODRINTH_RESULT,
    MatchScore,
    FUZZY_MATCH_THRESHOLD, FUZZY_MIN_LEN,
)
from ._mcmod_search import search_mcmod, _parallel_fetch_with_fallback
from ._modrinth import search_modrinth
from ._wiki import search_wiki, search_wiki_zh


def search_all(keyword: str, max_per_source: int | None = None, timeout: int = 15,
               content_type: str = "mod", fuse: bool = True) -> dict:
    """
    四平台并行搜索，返回统一格式。
    timeout: 整体超时秒数
    content_type: "mod" | "item" | "modpack" | "vanilla" | "entity" | "biome" | "dimension" | "shader" | "resourcepack"
      - 同时决定每平台最大结果数（_DEFAULT_RESULTS_PER_PLATFORM）
      - shader/resourcepack 仅搜索 Modrinth
      - modpack 仅搜索 MC百科 + Modrinth
    fuse: True 时返回 {"results": [...融合列表...], "platform_stats": {platform: {total, returned}}}
         False 时返回 {platform: [results]}（向后兼容）
    """
    if not keyword or not keyword.strip():
        return {"results": [], "platform_stats": {}}

    per_source = max_per_source if max_per_source is not None else _DEFAULT_RESULTS_PER_PLATFORM

    # 1. 并行调度各平台搜索
    results, stats = _dispatch_platform_search(keyword, per_source, content_type, timeout)

    # 2. CJK 跨语言桥接（中文关键词 → MC百科 name_en → Modrinth 补搜）
    if fuse and _is_cjk(keyword):
        _apply_cjk_bridge(results, stats, keyword, per_source)

    # 3. 结果融合或原样返回
    if fuse:
        fused = _fuse_results(results, content_type=content_type, query_keyword=keyword)
        return {"results": fused, "platform_stats": stats}
    return results


def _dispatch_platform_search(keyword: str, per_source: int, content_type: str, timeout: int
                              ) -> tuple[dict, dict]:
    """并行调度各平台搜索，返回 (results, stats)。"""
    results = {"mcmod.cn": [], "modrinth": [], "minecraft.wiki": [], "minecraft.wiki/zh": []}
    stats = {p: {"total": 0, "returned": 0} for p in results}

    pe = _platform_enabled.copy()
    if content_type in _VISUAL_CONTENT_TYPES:
        pe["mcmod.cn"] = pe["minecraft.wiki"] = pe["minecraft.wiki/zh"] = False
    elif content_type in ("mod", "modpack"):
        pe["minecraft.wiki"] = pe["minecraft.wiki/zh"] = False
    else:
        # vanilla / entity / biome / dimension → 仅 wiki
        pe["mcmod.cn"] = pe["modrinth"] = False

    def _wrap_mcmod():
        try:
            ct = content_type if content_type in _TEXT_CONTENT_TYPES else "mod"
            if content_type not in _TEXT_CONTENT_TYPES:
                logger.debug(f"MC百科不支持 content_type={content_type}，降级为 mod")
            return search_mcmod(keyword, per_source, content_type=ct)
        except (SearchError, OSError) as e:
            logger.warning(f"MC百科搜索失败: {e}")
            return []

    def _wrap_modrinth():
        try:
            mr_type = content_type if content_type in _MODRINTH_CONTENT_TYPES else "mod"
            return search_modrinth(keyword, per_source, project_type=mr_type)
        except (SearchError, OSError) as e:
            logger.warning(f"Modrinth搜索失败: {e}")
            return _EMPTY_MODRINTH_RESULT, True  # (data, is_error)

    def _wrap_wiki():
        try:
            return search_wiki(keyword, per_source)
        except (SearchError, OSError) as e:
            logger.warning(f"Wiki搜索失败: {e}")
            return []

    def _wrap_wiki_zh():
        try:
            return search_wiki_zh(keyword, per_source)
        except (SearchError, OSError) as e:
            logger.warning(f"中文Wiki搜索失败: {e}")
            return []

    workers = []
    futures_map = {}
    with futures_module.ThreadPoolExecutor(max_workers=_MAX_FETCH_WORKERS) as ex:
        if pe.get("mcmod.cn", False):
            f = ex.submit(_wrap_mcmod)
            futures_map[f] = "mcmod.cn"
            workers.append(f)
        if pe.get("modrinth", False):
            f = ex.submit(_wrap_modrinth)
            futures_map[f] = "modrinth"
            workers.append(f)
        if pe.get("minecraft.wiki", False):
            f = ex.submit(_wrap_wiki)
            futures_map[f] = "minecraft.wiki"
            workers.append(f)
        if pe.get("minecraft.wiki/zh", False):
            f = ex.submit(_wrap_wiki_zh)
            futures_map[f] = "minecraft.wiki/zh"
            workers.append(f)

        for future in futures_module.as_completed(workers):
            key = futures_map[future]
            try:
                raw = future.result(timeout=timeout)
            except (futures_module.TimeoutError, OSError, SearchError) as e:
                logger.warning(f"平台 {key} 获取结果失败: {e}")
                if key == "modrinth":
                    raw = (_EMPTY_MODRINTH_RESULT, True)
                else:
                    raw = []

            if key == "modrinth":
                is_error = False
                if isinstance(raw, tuple) and len(raw) == 2:
                    raw, is_error = raw
                if isinstance(raw, dict) and not is_error:
                    results[key] = raw.get("results", [])
                    stats[key] = {"total": raw.get("total", 0), "returned": raw.get("returned", 0)}
                else:
                    results[key] = []
                    stats[key] = {"total": 0, "returned": 0, "error": "search_failed"}
            else:
                results[key] = raw if isinstance(raw, list) else []
                stats[key] = {"total": len(results[key]), "returned": len(results[key])}

        for f in workers:
            f.cancel()

    return results, stats


def _apply_cjk_bridge(results: dict, stats: dict, keyword: str, per_source: int):
    """中文关键词用 MC百科 name_en 补搜 Modrinth，去重后合并。"""
    bridge_hits = _cross_language_bridge(results["mcmod.cn"], keyword, per_source)
    if bridge_hits:
        existing_slugs = {h.get("source_id", "") for h in results["modrinth"]}
        new_hits = [h for h in bridge_hits if h.get("source_id", "") not in existing_slugs]
        results["modrinth"].extend(new_hits)
        stats["modrinth"]["total"] = stats["modrinth"]["returned"] = len(results["modrinth"])


def _is_cjk(text: str) -> bool:
    """检测文本是否包含 CJK 字符。"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def _cross_language_bridge(mcmod_hits: list, keyword: str, per_source: int) -> list:
    """从 MC百科 结果提取英文名去 Modrinth 补搜。"""
    if not mcmod_hits:
        return []

    # 提取英文名候选（去重，最多 per_source 个）
    en_names = set()
    # MC百科 name_en
    for hit in mcmod_hits:
        en = (hit.get("name_en") or "").strip()
        if en:
            en_names.add(en.lower())
    if not en_names:
        logger.debug("Cross-language bridge: no English names extracted")
        return []

    # 并行搜索 Modrinth（每个英文名独立搜，限 2 结果/名）
    all_hits = {}
    mr_limit = min(per_source, 2)

    def _search_one(en_name: str):
        try:
            return search_modrinth(en_name, max_results=mr_limit, project_type="mod")
        except (SearchError, OSError) as e:
            logger.debug(f"Bridge Modrinth search failed for {en_name}: {e}")
            return {"results": []}

    en_list = list(en_names)[:per_source]
    if en_list:
        with futures_module.ThreadPoolExecutor(max_workers=min(len(en_list), _MAX_FETCH_WORKERS)) as ex:
            futs = [ex.submit(_search_one, en) for en in en_list]
            for future in futures_module.as_completed(futs):
                mr_result = future.result()
                for hit in mr_result.get("results", []):
                    slug = hit.get("source_id", "")
                    if slug and slug not in all_hits:
                        all_hits[slug] = hit

    if all_hits:
        logger.debug(f"Cross-language bridge: {len(en_names)} en names -> {len(all_hits)} Modrinth hits")
    return list(all_hits.values())


def _calc_name_score(name_lc: str, query_lc: str) -> int:
    """
    计算单个名称字段的相关性分数（使用常量）。

    评分逻辑:
    - 精确匹配: 100 + 短名称奖励
    - 前缀匹配: 60 + 短名称奖励（ASCII 查询需词边界，防止 "spawn" 匹配 "spawning"）
    - 全词匹配: 45（仅 ASCII，防止 "OreSpawn" 匹配 "spawn"）
    - 包含查询词: 30 + 位置奖励
    - 名称被包含: 20
    """
    if not name_lc or not query_lc:
        return 0

    # 连字符归一化：将 - 替换为空格，使 "fabric-api" 能匹配 "Fabric API"
    name_norm = name_lc.replace("-", " ")
    query_norm = query_lc.replace("-", " ")

    # 1. 精确匹配（同时检查原始和归一化版本）
    if name_lc == query_lc or name_norm == query_norm:
        bonus = max(0, MatchScore.EXACT_MATCH_MAX_BONUS - len(name_lc) * MatchScore.EXACT_MATCH_BONUS_FACTOR)
        return MatchScore.EXACT_MATCH_BASE + bonus

    # 词边界检查仅对纯 ASCII 查询生效（CJK 无空格分界概念）
    _ascii = query_lc.isascii()

    # 2. 前缀匹配（归一化版本：连字符→空格）
    if name_norm.startswith(query_norm):
        if not _ascii or len(query_norm) >= len(name_norm) or not name_norm[len(query_norm)].isalnum():
            bonus = max(0, MatchScore.PREFIX_MAX_BONUS - len(query_lc) * MatchScore.PREFIX_BONUS_FACTOR)
            return MatchScore.PREFIX_BASE + bonus

    # 2.5 全词匹配（归一化版本）
    if _ascii:
        word_pat = re.compile(r'(?<![a-z0-9])' + re.escape(query_norm) + r'(?![a-z0-9])')
        if word_pat.search(name_norm):
            return MatchScore.WHOLE_WORD_BASE

    # 3. 包含查询词（归一化版本）
    pos = name_norm.find(query_norm)
    if pos >= 0:
        if not _ascii or (
            (pos == 0 or not name_norm[pos - 1].isalnum()) and
            (pos + len(query_norm) >= len(name_norm) or not name_norm[pos + len(query_norm)].isalnum())
        ):
            pos_bonus = max(0, MatchScore.CONTAINS_MAX_POS_BONUS - pos)
            return MatchScore.CONTAINS_BASE + pos_bonus

    # 4. 名称被包含
    if len(name_lc) >= MatchScore.MIN_LENGTH_FOR_CONTAINED and name_lc in query_lc:
        return MatchScore.CONTAINED_IN_QUERY

    return 0


def _score_relevance(query: str, hit: dict, content_type: str = "mod") -> float:
    """
    计算单条搜索结果与查询词的相关性分数（优化版，0-150+）。

    评分规则:
      - 主字段精确匹配: 100 + 短名称奖励(最多+20)
      - 主字段前缀匹配: 60 + 短名称奖励(最多+15)
      - 主字段包含查询词: 30 + 位置奖励(最多+10)
      - 主字段被包含于查询词: 20 (适合缩写搜索)
      - 次字段匹配: 同级别 -10 分
      - Snippet 包含查询词: +5
      - Wiki item 来源: +5
      - 多平台命中: 每多一个平台 +10 (在 _fuse_results 中计算)
    """
    if not query or not hit:
        return 0.0

    # 直接命中的 wiki 页面（通过 go=Go 跳转），给予高基础分
    if hit.get("_direct_match"):
        return MatchScore.EXACT_MATCH_BASE

    name_zh = (hit.get("name_zh") or "").lower()
    name_en = (hit.get("name_en") or "").lower()
    q = query.strip().lower()
    if not q:
        return 0.0

    # 1. 选择主要/次要评分字段
    primary = name_zh if _is_cjk(q) else name_en
    secondary = name_en if primary == name_zh else name_zh
    if not primary:
        primary, secondary = secondary, ""

    # 2. 计算名称分数
    score = _calc_name_score(primary, q)
    if score == 0 and secondary:
        score = _calc_name_score(secondary, q)
        if score > 0:
            score = max(score - MatchScore.SECONDARY_PENALTY, MatchScore.SECONDARY_MIN)

    # 3. Snippet 加分
    snippet = (hit.get("snippet") or "").lower()
    if snippet and q in snippet:
        score += MatchScore.SNIPPET_BONUS

    # 4. Wiki item 来源加分
    platform = hit.get("_platform", hit.get("source", ""))
    if content_type == "item" and platform in ("minecraft.wiki", "minecraft.wiki/zh"):
        score += MatchScore.WIKI_ITEM_BONUS

    # 5. MC百科 类别加权：冒险/装饰类常因名字巧合匹配，降低权重
    cats = hit.get("categories", [])
    if cats:
        for cat in cats:
            if cat in ("冒险Mod", "装饰Mod"):
                score -= 10
                break

    return score


def _fuse_results(results: dict, content_type: str = "mod", query_keyword: str = "") -> list[dict]:
    """
    跨平台去重合并，按相关性分数排序。

    排序规则：相关性分数 DESC → 多平台命中加权 → 平台优先级 ASC（tiebreaker）
    content_type 用于调整不同类型内容的平台优先级。
    """
    if content_type is None:
        content_type = "mod"

    # 步骤1: 打分并过滤
    scored = _score_and_filter(results, content_type, query_keyword)

    # 步骤2: 统计平台命中
    name_platform_count = _count_platform_hits(scored)

    # 步骤3: 去重
    by_name = _deduplicate_by_name(scored, name_platform_count)

    # 步骤4: 排序
    sorted_entries = _sort_entries(by_name)

    # 步骤5: 构建输出
    fused = _build_fused_output(sorted_entries, scored)

    # 步骤6: 标记本体（C→B→A 级联）
    fused = _mark_primary(fused, query_keyword)

    return fused


def _score_and_filter(results: dict, content_type: str, query_keyword: str) -> list[dict]:
    """步骤1: 给所有结果打分，同时过滤无关结果。"""
    prio_key = "default" if content_type in ("mod", "item") else "other"
    platform_prio = _CONTENT_PLATFORM_PRIORITY[prio_key]

    scored = []
    for platform, hits in results.items():
        for h in hits:
            # 过滤 MC百科 安全验证/限流空数据
            h_name = h.get("name_zh") or h.get("name") or ""
            if platform == "mcmod.cn" and h_name in ("安全验证", "安全验证中", "访问间隔过短，请稍后再试"):
                continue

            score = _score_relevance(query_keyword, h, content_type=content_type)
            # 过滤 wiki 无匹配结果（分数为 0）
            if content_type == "mod" and platform in ("minecraft.wiki", "minecraft.wiki/zh"):
                if score == 0:
                    continue

            priority = platform_prio.get(platform, 99)
            scored.append({**h, "_platform": platform, "_score": score, "_priority": priority})

    return scored


def _entry_name_keys(entry: dict) -> set[str]:
    """返回所有可用名称的标准化 key 集合（多候选，跨语言匹配）。

    对每个名称生成 hyphen 和 space 两种变体，解决 "EnderIO" vs "Ender-IO"
    等连字符差异导致的跨平台去重失败问题。
    """
    keys = set()
    for field in ('name_zh', 'name_en', 'name', '_name_zh_cn'):
        v = entry.get(field)
        if v and isinstance(v, str) and v.strip():
            norm = v.strip().lower()
            keys.add(norm)
            # Hyphen/space 归一化：同时生成连字符和空格两种变体
            if '-' in norm:
                keys.add(norm.replace('-', ' '))
            elif ' ' in norm:
                keys.add(norm.replace(' ', '-'))
    return keys


def _count_platform_hits(scored: list[dict]) -> dict[frozenset, set]:
    """步骤2: 统计每个名称组在多少个平台出现。"""
    name_platform_count = {}
    for entry in scored:
        keys = _entry_name_keys(entry)
        if not keys:
            continue
        frozen = frozenset(keys)
        if frozen not in name_platform_count:
            name_platform_count[frozen] = set()
        name_platform_count[frozen].add(entry["_platform"])
    return name_platform_count


def _merge_entry_fields(entries: list[dict]) -> dict:
    """按字段级权威源合并同一实体的多个平台条目。"""
    if len(entries) == 1:
        entry = entries[0]
        if entry.get("relationships") is None:
            entry["relationships"] = {}
        entry.setdefault("downloads", 0)
        entry.setdefault("followers", 0)
        entry.setdefault("icon_url", "")
        return entry

    by_platform = {}
    for e in entries:
        src = e.get("_platform") or e.get("source", "")
        by_platform[src] = e

    def _field_from(primary_src, fallback_src, field):
        v = (by_platform.get(primary_src) or {}).get(field) or ""
        if field == "name_en" and _is_cjk(v):
            v = ""  # 拒绝含 CJK 的 name_en，回退到备选源
        return v or (by_platform.get(fallback_src) or {}).get(field) or ""

    # 以最高分条目为基础，覆盖权威字段
    base = max(entries, key=lambda e: e.get("_score", 0))
    merged = {
        "name_zh": _field_from("mcmod.cn", "modrinth", "name_zh"),
        "name_en": _field_from("modrinth", "mcmod.cn", "name_en"),
        "description": _field_from("modrinth", "mcmod.cn", "description"),
        "downloads": (by_platform.get("modrinth") or {}).get("downloads",
                     (by_platform.get("mcmod.cn") or {}).get("downloads", 0)),
        "followers": (by_platform.get("modrinth") or {}).get("followers",
                      (by_platform.get("mcmod.cn") or {}).get("followers", 0)),
        "relationships": (by_platform.get("mcmod.cn") or {}).get("relationships") or {},
        "snippet": _field_from("modrinth", "mcmod.cn", "snippet"),
        "icon_url": _field_from("modrinth", "mcmod.cn", "icon_url"),
        "changelogs": (by_platform.get("modrinth") or {}).get("changelogs")
                       or (by_platform.get("mcmod.cn") or {}).get("changelogs") or [],
        "supported_versions": _field_from("modrinth", "mcmod.cn", "supported_versions"),
        "author": _field_from("modrinth", "mcmod.cn", "author"),
    }
    return {**base, **merged}


def _cross_platform_consistent(new_entry: dict, group_entries: list[dict]) -> bool:
    """验证新 entry 与已有组是否存在跨平台 ID 冲突。

    MC百科 的 external_links.cross_platform_ids.modrinth_slug 标识对应 Modrinth 项，
    Modrinth 的 source_id 是自身 slug。两者都非空但不一致时阻止合并（同名不同模组）。
    """
    new_src = new_entry.get("_platform") or new_entry.get("source", "")
    new_slug = (new_entry.get("source_id") or "").strip().lower()

    if new_src == "modrinth" and new_slug:
        for e in group_entries:
            e_src = e.get("_platform") or e.get("source", "")
            if e_src == "mcmod.cn":
                ext = e.get("external_links")
                if isinstance(ext, dict):
                    cpi = ext.get("cross_platform_ids")
                    if isinstance(cpi, dict):
                        mcmod_slug = (cpi.get("modrinth_slug") or "").strip().lower()
                        if mcmod_slug and mcmod_slug != new_slug:
                            return False

    if new_src == "mcmod.cn":
        ext = new_entry.get("external_links")
        if isinstance(ext, dict):
            cpi = ext.get("cross_platform_ids")
            if isinstance(cpi, dict):
                new_mr_slug = (cpi.get("modrinth_slug") or "").strip().lower()
                if new_mr_slug:
                    for e in group_entries:
                        e_src = e.get("_platform") or e.get("source", "")
                        if e_src == "modrinth":
                            e_slug = (e.get("source_id") or "").strip().lower()
                            if e_slug and e_slug != new_mr_slug:
                                return False

    return True


def _deduplicate_by_name(scored: list[dict], name_platform_count: dict) -> dict[str, dict]:
    """步骤3: 多候选 key 去重。两结果任一 key 命中即视为同一内容。按字段级权威源合并。

    匹配策略（按优先级）：
    1. 精确匹配：entry 的任一 key 与已有 canonical 组的 key 完全相等
    2. 模糊匹配：精确匹配失败后，对 entry 的每个 key 与组内所有 key 做 SequenceMatcher，
       相似度 ≥ FUZZY_MATCH_THRESHOLD 且 key 长度 ≥ FUZZY_MIN_LEN 视为同一实体
    合并前通过 _cross_platform_consistent 验证跨平台 ID 不冲突。
    """
    key_to_canonical = {}         # individual key → canonical key
    entries_by_canonical = {}     # canonical_key → [entry, ...]
    from difflib import SequenceMatcher

    for entry in scored:
        entry_keys = _entry_name_keys(entry)
        if not entry_keys:
            continue

        canonical_key = None
        for k in entry_keys:
            if k in key_to_canonical:
                canonical_key = key_to_canonical[k]
                break

        if canonical_key is None:
            # 精确匹配失败，尝试模糊匹配到已有组
            matched_canonical = None
            for ck, c_entries in entries_by_canonical.items():
                # 获取该组的所有 key
                group_keys = set()
                for ce in c_entries:
                    group_keys.update(_entry_name_keys(ce))
                for ek in entry_keys:
                    if len(ek) < FUZZY_MIN_LEN:
                        continue
                    for gk in group_keys:
                        if len(gk) < FUZZY_MIN_LEN:
                            continue
                        ratio = SequenceMatcher(None, ek, gk).ratio()
                        if ratio >= FUZZY_MATCH_THRESHOLD:
                            if _cross_platform_consistent(entry, c_entries):
                                matched_canonical = ck
                            break
                    if matched_canonical:
                        break
                if matched_canonical:
                    break

            if matched_canonical is not None:
                canonical_key = matched_canonical
                entries_by_canonical[canonical_key].append(entry)
                for k in entry_keys:
                    if k not in key_to_canonical:
                        key_to_canonical[k] = canonical_key
            else:
                # 精确和模糊都失败，创建新组
                canonical_key = min(entry_keys)
                entries_by_canonical[canonical_key] = [entry]
                for k in entry_keys:
                    key_to_canonical[k] = canonical_key
            continue

        if _cross_platform_consistent(entry, entries_by_canonical[canonical_key]):
            entries_by_canonical[canonical_key].append(entry)
            for k in entry_keys:
                if k not in key_to_canonical:
                    key_to_canonical[k] = canonical_key
        else:
            # 跨平台 ID 冲突：创建新组，用唯一 key 避免覆盖已有组
            base = min(entry_keys)
            canonical_key = base
            n = 2
            while canonical_key in entries_by_canonical:
                canonical_key = f"{base}_{n}"
                n += 1
            entries_by_canonical[canonical_key] = [entry]
            for k in entry_keys:
                key_to_canonical[k] = canonical_key

    # 多平台命中加权 + 字段级权威源合并
    by_name = {}
    for canonical_key, entries in entries_by_canonical.items():
        # 多平台统计：直接从组内 entries 收集平台（比 name_platform_count 更可靠，
        # 因为模糊匹配后 key 的 frozenset 分组已不适用）
        all_platforms = set()
        for e in entries:
            platform = e.get("_platform") or e.get("source", "")
            if platform:
                all_platforms.add(platform)
        platform_count = len(all_platforms)

        merged = _merge_entry_fields(entries)
        if platform_count > 1:
            merged["_score"] += (platform_count - 1) * MatchScore.MULTI_PLATFORM_BONUS
        # 直接设置 _sources，避免 _build_fused_output 的精确集合交集在模糊匹配场景下失效
        merged["_sources"] = sorted(all_platforms)
        by_name[canonical_key] = merged

    return by_name


def _sort_entries(by_name: dict[str, dict]) -> list[dict]:
    """步骤4: 排序（分数 DESC，同分时 priority ASC 即高优先级在前）。"""
    return sorted(by_name.values(), key=lambda e: (e["_score"], -e["_priority"]), reverse=True)


def _build_fused_output(sorted_entries: list[dict], scored: list[dict]) -> list[dict]:
    """步骤5: 构建融合结果输出。"""
    fused = []
    for entry in sorted_entries:
        # 保留分数 + 截断元信息，移除其他 _ 字段
        merged = {k: v for k, v in entry.items()
                  if not k.startswith("_") or k in ("_score", "_sources", "_truncated")}

        # 收集所有 key 重叠结果的平台（多候选 key 交集匹配）
        # 如果 entry 已有 _sources（来自 _deduplicate_by_name 的模糊匹配结果），则保留
        if "_sources" not in merged:
            entry_keys = _entry_name_keys(entry)
            platforms = [e["_platform"] for e in scored
                         if _entry_name_keys(e) & entry_keys]
            merged["_sources"] = list(dict.fromkeys(platforms))

        if len(merged["_sources"]) > 1:
            # 多平台同名结果：组合 source 字段（如 "mcmod.cn|modrinth"）
            merged["source"] = "|".join(merged["_sources"])

        fused.append(merged)
    return fused


def _mark_primary(fused: list[dict], query_keyword: str) -> list[dict]:
    """标记融合结果中的本体模组（C→B→A 级联判断）。

    为所有结果设置 is_primary 字段：True 表示本体，False 表示非本体。
    """
    if not fused:
        return fused

    q = (query_keyword or "").strip().lower()
    if not q:
        # 无查询词时，所有结果标记为非本体
        for hit in fused:
            hit["is_primary"] = False
        return fused

    # 初始化：所有结果默认 is_primary = False
    for hit in fused:
        hit["is_primary"] = False

    # ── 级联 C: 前置关系 ──
    required_by_others = set()   # name → 被其他条目依赖（name_zh / name_en）
    for hit in fused:
        rel = hit.get("relationships", {})
        if isinstance(rel, dict) and not rel.get("_error"):
            for req in rel.get("requires", []):
                req_name = (req.get("name_zh") or req.get("name_en") or "").strip().lower()
                if req_name:
                    required_by_others.add(req_name)
    if required_by_others:
        for hit in fused:
            hit_name = (hit.get("name_zh") or hit.get("name") or "").strip().lower()
            hit_en = (hit.get("name_en") or "").strip().lower()
            if hit_name in required_by_others or hit_en in required_by_others:
                # 同时检查自身不是仅被自己依赖（排除 requires 列表指向自己的循环引用）
                requires_self = False
                rel = hit.get("relationships", {})
                if isinstance(rel, dict) and not rel.get("_error"):
                    for req in rel.get("requires", []):
                        rn = (req.get("name_zh") or req.get("name_en") or "").strip().lower()
                        if rn == hit_name or rn == hit_en:
                            requires_self = True
                            break
                if not requires_self:
                    hit["is_primary"] = True
        if any(h.get("is_primary") for h in fused):
            return fused

    # ── 级联 B: 精确名匹配 + 最高下载量 ──
    exact_matches = [h for h in fused
                     if (h.get("name_zh") or h.get("name") or "").strip().lower() == q
                     or (h.get("name_en") or "").strip().lower() == q]
    if exact_matches:
        max_dl = max((h.get("downloads", 0) for h in exact_matches), default=0)
        if max_dl > 0:
            for h in exact_matches:
                if h.get("downloads", 0) == max_dl:
                    h["is_primary"] = True
            return fused

    # ── 级联 A: 最高下载量 ──
    max_dl = max((h.get("downloads", 0) for h in fused), default=0)
    if max_dl > 0:
        for h in fused:
            if h.get("downloads", 0) == max_dl:
                h["is_primary"] = True

    # ── 兜底: 无人命中则最高分 ──
    if not any(h.get("is_primary") for h in fused):
        best = max(fused, key=lambda h: h.get("_score", 0))
        best["is_primary"] = True

    return fused
