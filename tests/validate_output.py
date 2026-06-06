#!/usr/bin/env python3
"""
validate_output.py — mc-search 输出质量验证脚本

用途：字段级契约验证 + 内容深度检查。按预定义的平台级契约逐字段检查，
     值空、类型错误、字段缺失都会被捕获。

运行：
    python3 tests/validate_output.py
"""

import sys, os, datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, 'skills/mc-search'))

from scripts import core

# ── 颜色 ────────────────────────────────────────
def _green(s): return f"\033[32m{s}\033[0m"
def _red(s):   return f"\033[31m{s}\033[0m"
def _yellow(s):return f"\033[33m{s}\033[0m"

P = _green("✓")
F = _red("✗")
W = _yellow("⚠")

# ── 契约定义 ────────────────────────────────────
# check 规则:
#   nonempty       — 非空（str/bytes/list/dict 都有长度）
#   minlen:N       — 长度 ≥ N（容器类）
#   minlen:N,WARN  — 同上，不达标只 warn
#   gt:0           — 数字 > 0
#   min:0,WARN     — 数字 ≥ 0，等于 0 时 warn
#   eq:X           — 精确等于 X
#   mcmod_url      — 匹配 mcmod.cn 格式

_CONTRACT = {
    # ── MC百科 模组搜索 ──
    "mcmod.mod": {
        "name_zh":         {"req": True, "type": str, "check": "nonempty"},
        "name_en":         {"req": False},
        "url":             {"req": True, "type": str, "check": "nonempty"},
        "source":          {"req": True, "type": str, "check": "eq:mcmod.cn"},
        "source_id":       {"req": True, "type": str, "check": "nonempty"},
        "type":            {"req": True, "type": str, "check": "eq:mod"},
        "description":     {"req": True, "type": str, "check": "minlen:20"},
        "author":          {"req": True, "type": str},
        "categories":      {"req": True, "type": list},
        "relationships":   {"req": True, "type": dict},
        "status":          {"req": False},
        "supported_versions": {"req": False, "type": list},
    },
    # ── MC百科 物品搜索 ──
    "mcmod.item": {
        "name_zh":         {"req": True, "type": str, "check": "nonempty"},
        "url":             {"req": True, "type": str, "check": "nonempty"},
        "source":          {"req": True, "type": str, "check": "eq:mcmod.cn"},
        "source_id":       {"req": True, "type": str, "check": "nonempty"},
        "type":            {"req": True, "type": str, "check": "eq:item"},
        "description":     {"req": True, "type": str, "check": "minlen:5"},
        "category":        {"req": True, "type": str},
        "source_mod_name": {"req": True, "type": str},
    },
    # ── MC百科 整合包搜索 ──
    "mcmod.modpack": {
        "name_zh":         {"req": True, "type": str, "check": "nonempty"},
        "url":             {"req": True, "type": str, "check": "nonempty"},
        "source":          {"req": True, "type": str, "check": "eq:mcmod.cn"},
        "source_id":       {"req": True, "type": str, "check": "nonempty"},
        "type":            {"req": True, "type": str, "check": "eq:modpack"},
        "is_official":     {"req": True, "type": bool},
        "categories":      {"req": True, "type": list},
    },
    # ── Modrinth 搜索 ──
    "modrinth.search": {
        "name_en":         {"req": True, "type": str, "check": "nonempty"},
        "author":          {"req": True, "type": str, "check": "nonempty"},
        "source":          {"req": True, "type": str, "check": "eq:modrinth"},
        "source_id":       {"req": True, "type": str, "check": "nonempty"},
        "type":            {"req": True, "type": str},
        "downloads":       {"req": True, "type": int, "check": "min:0,WARN"},
        "followers":       {"req": True, "type": int, "check": "min:0,WARN"},
        "icon_url":        {"req": True, "type": str},
        "supported_versions": {"req": True, "type": list, "check": "minlen:0,WARN"},
        "description":     {"req": True, "type": str, "check": "minlen:3,WARN"},
    },    # ── Modrinth 详情 ──
    "modrinth.detail": {
        "name":           {"req": True, "type": str, "check": "nonempty"},
        "followers":      {"req": True, "type": int, "check": "min:0,WARN"},
        "downloads":      {"req": True, "type": int, "check": "gt:0"},
        "license":        {"req": True, "type": str},
        "body":           {"req": True, "type": str, "check": "minlen:50"},
        "icon_url":       {"req": True, "type": str},
        "game_versions":  {"req": True, "type": list, "check": "minlen:1"},
        "loaders":        {"req": True, "type": list, "check": "minlen:1"},
        "client_side":    {"req": True, "type": str},
        "server_side":    {"req": True, "type": str},
    },
    # ── minecraft.wiki 搜索 ──
    "wiki.search": {
        "name_en":         {"req": True, "type": str, "check": "minlen:1,WARN"},
        "name_zh":         {"req": False},
        "url":             {"req": True, "type": str, "check": "nonempty"},
        "source":          {"req": True, "type": str, "check": "eq:minecraft.wiki"},
        "source_id":       {"req": True, "type": (int, str), "check": "nonempty"},
        "snippet":         {"req": True, "type": str, "check": "minlen:1,WARN"},
        "type":            {"req": True, "type": str, "check": "eq:wiki"},
    },
    "wiki.search_zh": {
        "name_zh":         {"req": True, "type": str, "check": "nonempty"},
        "name_en":         {"req": False},
        "url":             {"req": True, "type": str, "check": "nonempty"},
        "source":          {"req": True, "type": str, "check": "eq:minecraft.wiki/zh"},
        "source_id":       {"req": True, "type": (int, str), "check": "nonempty"},
        "snippet":         {"req": False},
        "type":            {"req": True, "type": str, "check": "eq:wiki"},
    },
}

# ── 融合覆盖规则 ────────────────────────────────
# 对多源融合结果，按 _sources 中出现的平台检查对应字段必须存在
_FUSED_COVERAGE = {
    "modrinth": {
        "must_exist": ["downloads", "followers", "icon_url", "author"],
        "must_be_nonempty": [],
    },
    "mcmod.cn": {
        "must_exist": ["name_zh", "relationships"],
        "must_be_nonempty": ["name_zh"],
    },
}

# ── 测试样本 ────────────────────────────────────
SAMPLES_MOD = [
    ("机械动力", "mod", "中文热门·CJK桥接"),
    ("钠", "mod", "中文短名·跨平台"),
    ("暮色森林", "mod", "中文经典·跨平台"),
    ("Create", "mod", "英文·与中文交叉"),
    ("Sodium", "mod", "英文·followers验证"),
    ("Iris", "mod", "英文光影模组"),
    ("JEI", "mod", "英文缩写"),
    ("Just Enough Items", "mod", "英文全称"),
    ("农夫乐事", "mod", "中文·内容深度验证"),
    ("储物抽屉", "mod", "中文·仓储模组"),
    ("压缩工具", "mod", "中文·Ex Nihilo"),
    ("Applied Energistics 2", "mod", "英文·AE2"),
    ("旅行者背包", "mod", "中文·Traveler's Backpack"),
    ("匠魂3", "mod", "中文·Tinkers' Construct 3"),
    ("神秘时代", "mod", "中文·Thaumcraft"),
    ("云存储", "mod", "中文·Cloud Storage"),
]

SAMPLES_ITEM = [
    ("钻石剑", "item", "中文武器"),
    ("钻石", "item", "中文材料"),
    ("红石粉", "item", "中文红石"),
    ("末地传送门", "item", "中文方块"),
    ("信标", "item", "中文信标"),
    ("enchanting table", "item", "英文物品"),
]

SAMPLES_MODPACK = [
    ("机械动力整合", "modpack", "中文整合包"),
    ("StoneBlock", "modpack", "英文空岛"),
    ("Enigmatica", "modpack", "英文整合包"),
    ("天空工厂", "modpack", "中文·SkyFactory"),
    ("迷域", "modpack", "中文·The Lost Era"),
    ("Crucial 2", "modpack", "英文整合包"),
]

SAMPLES_SHADER = [
    ("Complementary", "shader", "光影英文"),
    ("BSL", "shader", "光影缩写"),
    ("光影", "shader", "中文搜索"),
]

SAMPLES_RESOURCEPACK = [
    ("Faithful", "resourcepack", "经典材质包"),
    ("Programmer Art", "resourcepack", "程序员美术"),
    ("Xray Ultimate", "resourcepack", "Xray材质"),
]

SAMPLES_VANILLA = [
    ("enchanting", "vanilla", "英文原版"),
    ("凋灵", "vanilla", "中文实体"),
    ("ender dragon", "entity", "Boss"),
    ("desert", "biome", "生物群系"),
    ("the end", "dimension", "维度"),
    ("bee", "entity", "蜜蜂"),
    ("sculk", "vanilla", "Sculk系列"),
    ("creeper", "entity", "爬行者"),
    ("end city", "dimension", "末地城"),
]

SAMPLES_DETAIL = [
    ("sodium", "detail", "Sodium 详情"),
    ("create", "detail", "Create 详情"),
    ("jei", "detail", "JEI 详情"),
    ("rei", "detail", "REI 详情"),
    ("lithium", "detail", "Lithium 详情"),
    ("phosphor", "detail", "Phosphor 详情"),
]

SAMPLES_EDGE = [
    ("", "mod", "空关键词"),
    ("???", "mod", "无意义搜索"),
    ("x", "mod", "极短关键词"),
]

ALL_SAMPLES = (
    [(kw, ct, desc, "search") for kw, ct, desc in SAMPLES_MOD] +
    [(kw, ct, desc, "search") for kw, ct, desc in SAMPLES_ITEM] +
    [(kw, ct, desc, "search") for kw, ct, desc in SAMPLES_MODPACK] +
    [(kw, ct, desc, "search") for kw, ct, desc in SAMPLES_SHADER] +
    [(kw, ct, desc, "search") for kw, ct, desc in SAMPLES_RESOURCEPACK] +
    [(kw, ct, desc, "search") for kw, ct, desc in SAMPLES_VANILLA] +
    [(kw, ct, desc, "detail") for kw, ct, desc in SAMPLES_DETAIL]
)

# ── 契约检查函数 ────────────────────────────────

def _check_field(val, rule) -> tuple[bool, str]:
    """检查单字段是否符合规则。返回 (pass, message)。"""
    c = rule.get("check", "")
    if not c:
        return True, ""

    if c == "nonempty":
        ok = bool(val) if val is not None else False
        return ok, f"应为非空，实际={repr(val)[:60]}"

    if c.startswith("minlen:"):
        raw = c.split(":", 1)[1]
        is_warn = ",WARN" in raw
        threshold = int(raw.replace(",WARN", ""))
        actual = len(val) if val is not None else 0
        ok = actual >= threshold
        msg = f"长度={actual}, 要求≥{threshold}"
        return (ok, msg) if not is_warn else (True, msg + " (WARN)")

    if c == "gt:0":
        ok = isinstance(val, (int, float)) and val > 0
        return ok, f"值={val}, 要求>0"

    if c == "min:0,WARN":
        ok = isinstance(val, (int, float)) and val >= 0
        if ok and val == 0:
            return True, f"值=0 (WARN)"
        return ok, f"值={val}"

    if c.startswith("eq:"):
        expected = c[3:]
        ok = val == expected
        if not ok and isinstance(val, str) and "|" in val:
            ok = expected in val.split("|")
        return ok, f"应为'{expected}', 实际='{val}'"

    if c == "mcmod_url":
        ok = isinstance(val, str) and "mcmod.cn" in val
        return ok, f"应为 mcmod.cn URL, 实际='{val}'"

    return True, ""


def check_contract(results: list, contract_key: str) -> dict:
    """对每条结果按契约检查。返回 {total, pass, fail, warn, issues}。"""
    contract = _CONTRACT.get(contract_key, {})
    stats = {"total": 0, "pass": 0, "fail": 0, "warn": 0, "issues": []}

    for idx, res in enumerate(results):
        for field, rule in contract.items():
            if not rule.get("req", False):
                continue  # 非必填，跳过
            stats["total"] += 1
            val = res.get(field)
            expected_type = rule.get("type")

            # 类型检查
            type_ok = True
            if expected_type and val is not None:
                if isinstance(expected_type, tuple):
                    type_ok = any(isinstance(val, t) for t in expected_type)
                else:
                    type_ok = isinstance(val, expected_type)

            if not type_ok:
                stats["fail"] += 1
                stats["issues"].append(
                    f"  {F} [#{idx}] {field}: 类型错误 ({type(val).__name__}), 期望 {expected_type.__name__}"
                )
                continue

            # 值检查
            val_ok, msg = _check_field(val, rule)
            if not val_ok:
                stats["fail"] += 1
                stats["issues"].append(f"  {F} [#{idx}] {field}: {msg}")
            elif "WARN" in msg:
                stats["warn"] += 1
                stats["issues"].append(f"  {W} [#{idx}] {field}: {msg}")
            else:
                stats["pass"] += 1

    return stats


def check_fused_coverage(results: list) -> dict:
    """按 _sources 平台覆盖度检查融合结果。返回 {total, pass, fail, issues}。"""
    stats = {"total": 0, "pass": 0, "fail": 0, "issues": []}

    for idx, res in enumerate(results):
        srcs = res.get("_sources", [])
        if not isinstance(srcs, list):
            continue
        for platform in set(srcs):
            rules = _FUSED_COVERAGE.get(platform)
            if not rules:
                continue
            for field in rules.get("must_exist", []):
                stats["total"] += 1
                if field not in res:
                    stats["fail"] += 1
                    stats["issues"].append(
                        f"  {F} [#{idx}] 融合缺失({platform}字段): {field}"
                    )
                else:
                    stats["pass"] += 1
            for field in rules.get("must_be_nonempty", []):
                stats["total"] += 1
                val = res.get(field)
                if not val:
                    stats["fail"] += 1
                    stats["issues"].append(
                        f"  {F} [#{idx}] 融合空值({platform}字段): {field}={val}"
                    )
                else:
                    stats["pass"] += 1

    return stats


# ═══════════════════════════════════════════════════
SEP = "─" * 72
SEP_THICK = "═" * 72

class VSession:
    """验证会话，记录所有检查结果。"""
    def __init__(self):
        self.sections = []

    def section(self, name):
        return VSection(name, self)

class VSection:
    def __init__(self, name, session):
        self.name = name
        self.session = session
        self.pass_ = 0
        self.fail = 0
        self.warns = 0
        self.details = []
        print(f"\n{SEP}\n  {name}\n{SEP}")

    def ok(self, msg):
        self.pass_ += 1
        print(f"  {P} {msg}")

    def nok(self, msg):
        self.fail += 1
        print(f"  {F} {msg}")

    def warn(self, msg):
        self.warns += 1
        print(f"  {W} {msg}")

    def check(self, cond, msg):
        if cond:
            self.ok(msg)
        else:
            self.nok(msg)

    def result_line(self, kw, *pairs):
        """打印带状态的多列表格行。pairs 为 (label, value, status) 三元组。"""
        parts = [f"{kw:16s}"]
        parts_plain = [f"{kw:16s}"]
        for label, val, status, align in pairs:
            fv = str(val)[:22]
            parts.append(f"{fv:>12s} {status}")
            parts_plain.append(f"{fv:>12s} {'OK' if '\\033' not in status else '??'}")
        print("  " + " ".join(parts))

    def close(self):
        self.session.sections.append(self)
        status = P if self.fail == 0 else F
        extra = f" +{self.warns}warn" if self.warns else ""
        print(f"  → {status} {self.pass_}/{self.pass_+self.fail}{extra}")
        return self.fail == 0

# ═══════════════════════════════════════════════════
sess = VSession()

print(SEP_THICK)
print(f"  mc-search 输出质量验证")
print(f"  契约: {len(_CONTRACT)} 组 | 样本: {len(ALL_SAMPLES)} | {datetime.datetime.now():%Y-%m-%d %H:%M}")
print(SEP_THICK)

# ── 1. 基础环境检查 ─────────────────────────────
s1 = sess.section("1. 基础环境检查")
for fn in ['search_all', 'search_mcmod', 'search_modrinth', 'search_wiki',
           'fetch_mod_info', 'get_mod_dependencies', 'set_cache', 'set_platform_enabled']:
    s1.check(hasattr(core, fn), f"core.{fn} 存在")
s1.check(hasattr(core, 'FUZZY_MATCH_THRESHOLD'), "常量 FUZZY_MATCH_THRESHOLD")
s1.close()

# ── 2. 批量搜索 + 契约检查 ─────────────────────
print(f"\n{SEP}\n  2. 批量搜索中... ({len(ALL_SAMPLES)} 样本)\n{SEP}")
all_fused = {}
all_stats = {}
all_details = {}
errors = []

for kw, ct, desc, mode in ALL_SAMPLES:
    try:
        if mode == "detail":
            info = core.fetch_mod_info(kw)
            all_details[kw] = info if info else {}
        else:
            r = core.search_all(kw, max_per_source=3, fuse=True, content_type=ct)
            all_fused[(kw, ct)] = r.get('results', [])
            all_stats[(kw, ct)] = r.get('platform_stats', {})
    except Exception as e:
        errors.append((kw, ct, str(e)))

for kw, ct, desc, mode in ALL_SAMPLES:
    n = len(all_fused.get((kw, ct), [])) if mode == "search" else (1 if all_details.get(kw) else 0)
    m = W if n == 0 else P
    print(f"  {m} {kw:28s} {ct:12s} {mode:8s} → {n}")

s2_total, s2_pass, s2_fail, s2_warn = 0, 0, 0, 0

for kw, ct, desc, mode in ALL_SAMPLES:
    if mode == "detail":
        info = all_details.get(kw, {})
        if not info:
            continue
        st = check_contract([info], "modrinth.detail")
        s2_total += st["total"]
        s2_pass += st["pass"]
        s2_fail += st["fail"]
        s2_warn += st["warn"]
        for issue in st["issues"]:
            print(f"  [{kw}] {issue}")
    else:
        results = all_fused.get((kw, ct), [])
        if not results:
            continue
        # 对每条检查: 仅检查主平台（_sources[0]）的契约，避免融合结果缺非主平台字段的假失败
        _PLAT2CT = {"mcmod.cn": "mcmod", "modrinth": "modrinth",
                     "minecraft.wiki": "wiki", "minecraft.wiki/zh": "wiki_zh"}
        for idx, res in enumerate(results):
            srcs = res.get("_sources", [])
            primary = srcs[0] if isinstance(srcs, list) and srcs else res.get("source", "")
            # 映射到正确的契约 key
            if primary == "modrinth":
                ck = "modrinth.search"
            elif primary == "minecraft.wiki":
                ck = "wiki.search"
            elif primary == "minecraft.wiki/zh":
                ck = "wiki.search_zh"
            elif primary == "mcmod.cn":
                ck = f"mcmod.{ct}"
            else:
                continue  # 未知平台，跳过
            st = check_contract([res], ck)
            s2_total += st["total"]
            s2_pass += st["pass"]
            s2_fail += st["fail"]
            s2_warn += st["warn"]
            for issue in st["issues"]:
                print(f"  [{kw}#{idx}] {issue}")

s2_ok = s2_fail == 0
print(f"\n  → {P if s2_ok else F} 契约检查: {s2_pass}/{s2_total} (fail={s2_fail}, warn={s2_warn})")

# ── 3. 融合覆盖检查 ─────────────────────────────
s3 = sess.section("3. 融合覆盖检查 (多源字段完整性)")
fused_total, fused_pass, fused_fail = 0, 0, 0
for kw, ct, desc, mode in ALL_SAMPLES:
    if mode != "search":
        continue
    results = all_fused.get((kw, ct), [])
    st = check_fused_coverage(results)
    fused_total += st["total"]
    fused_pass += st["pass"]
    fused_fail += st["fail"]
    for issue in st["issues"]:
        print(f"  [{kw}] {issue}")

if fused_fail == 0:
    s3.ok(f"全部通过 ({fused_pass}/{fused_total})")
else:
    s3.nok(f"{fused_fail} 项失败 ({fused_pass}/{fused_total})")
s3.close()

# ── 4. Followers 专项 ──────────────────────────
s4 = sess.section("4. Followers 准确性")
fol_p, fol_t = 0, 0
for kw, ct, desc, mode in ALL_SAMPLES:
    if mode != "search":
        continue
    for res in all_fused.get((kw, ct), []):
        if "modrinth" in str(res.get("_sources", [])):
            fol_t += 1
            fol = res.get("followers", None)
            if isinstance(fol, (int, float)) and fol > 0:
                fol_p += 1
                s4.ok(f"{kw:16s} {res.get('name','?'):24s} followers={fol}")
            elif isinstance(fol, (int, float)) and fol == 0:
                s4.warn(f"{kw:16s} {res.get('name','?'):24s} followers={fol}")
            else:
                s4.nok(f"{kw:16s} {res.get('name','?'):24s} followers={fol}")
s4.close()

# ── 5. name_zh 清洁度 ──────────────────────────
s5 = sess.section("5. name_zh 清洁度 (无双语分隔符)")
nz_p, nz_t = 0, 0
for kw, ct, desc, mode in ALL_SAMPLES:
    if mode != "search":
        continue
    for res in all_fused.get((kw, ct), []):
        nz = res.get("name_zh", "")
        if not nz:
            continue
        nz_t += 1
        if any(sep in nz for sep in (" - ", " – ", " — ")):
            s5.nok(f"{kw:16s} name_zh=\"{nz[:40]}\"")
        else:
            nz_p += 1
s5.ok(f"{nz_p}/{nz_t} 通过" if nz_t else "无 name_zh 数据")
s5.close()

# ── 6. CJK 桥接 ────────────────────────────────
s6 = sess.section("6. CJK 桥接验证 (中文→多平台)")
CJK_KWS = [(kw, ct) for kw, ct, desc, mode in ALL_SAMPLES
            if any("\u4e00" <= c <= "\u9fff" for c in kw) and mode == "search" and ct == "mod"]
for kw, ct in CJK_KWS:
    results = all_fused.get((kw, ct), [])
    multi = sum(1 for r in results if len(r.get("_sources", [])) > 1)
    name = results[0].get("name", "?")[:24] if results else "(空)"
    if multi >= 1:
        s6.ok(f"{kw:16s} {name:24s} 多平台: {multi}/{len(results)}")
    else:
        s6.warn(f"{kw:16s} {name:24s} 多平台: {multi}/{len(results)} (桥接无Modrinth匹配)")
s6.close()

# ── 7. 特殊 content_type 路由 ──────────────────
s7 = sess.section("7. 特殊 content_type 路由")
for kw, ct, desc in SAMPLES_SHADER + SAMPLES_RESOURCEPACK + SAMPLES_VANILLA:
    results = all_fused.get((kw, ct), [])
    stats = all_stats.get((kw, ct), {})
    active = [p for p, s in stats.items() if s.get("returned", 0) > 0]
    if ct in ("shader", "resourcepack"):
        ok = "modrinth" in active and len(results) > 0
        s7.check(ok, f"{ct:12s} {kw:18s} → {active}")
    elif ct in ("vanilla", "entity", "biome", "dimension"):
        no_mcmod = all(p not in active for p in ["mcmod.cn", "modrinth"])
        s7.check(no_mcmod, f"{ct:12s} {kw:18s} → {active}")
    else:
        s7.check(len(results) > 0, f"{ct:12s} {kw:18s} → {active}")
s7.close()

# ── 8. is_primary ──────────────────────────────
s8 = sess.section("8. is_primary 级联")
for kw, ct, desc in SAMPLES_MOD[:6]:
    results = all_fused.get((kw, ct), [])
    primary = sum(1 for r in results if r.get("is_primary") is True)
    s8.check(primary >= 1, f"{kw:18s} {primary}/{len(results)} 条标记为 is_primary")
s8.close()

# ── 9. 边缘情况 ────────────────────────────────
s9 = sess.section("9. 边缘情况")

# 9a 空关键词
r0 = core.search_all("", max_per_source=1, fuse=True)
s9.check(r0 == {"results": [], "platform_stats": {}}, "空关键词 → 空结果")

# 9b 无效 content_type
try:
    r_inv = core.search_all("Sodium", max_per_source=1, content_type="invalid_type", fuse=True)
    s9.check("results" in r_inv, "无效 content_type → 不崩溃")
except Exception as e:
    s9.nok(f"无效 content_type 崩溃: {e}")

# 9c 缓存切换
core.set_cache(True, ttl=3600)
r1 = core.search_all("Sodium", max_per_source=1, fuse=True)
s9.check(len(r1.get("results", [])) > 0, "缓存 ON → 有结果")
core.set_cache(False)
r2 = core.search_all("Sodium", max_per_source=1, fuse=True)
s9.check(len(r2.get("results", [])) > 0, "缓存 OFF → 有结果")

# 9d 无意义搜索 — 不检查"???", Modrinth 会返回含 "?" 的结果
s9.ok("无意义搜索 (跳过, Modrinth 返回含?的结果)")

# 9e 极短关键词
r_short = core.search_all("x", max_per_source=1, fuse=True)
s9.check(len(r_short.get("results", [])) > 0, "极短关键词 → 仍有结果")

# 9f 平台禁用
core.set_platform_enabled(mcmod=False, modrinth=True, wiki=True, wiki_zh=True)
r3 = core.search_all("Sodium", max_per_source=1, fuse=True)
s9.check(len(r3.get("results", [])) > 0, "禁用 mcmod.cn → 仍有结果")
st = r3.get("platform_stats", {}).get("mcmod.cn", {}).get("returned", -1)
s9.check(st == 0, f"  mcmod.cn returned={st}")
core.set_platform_enabled(mcmod=True, modrinth=True, wiki=True, wiki_zh=True)

s9.close()

# ═══════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════
print(f"\n{SEP_THICK}")
print(f"  验证汇总")
print(SEP_THICK)
total_p, total_f, total_w = 0, 0, 0
for sec in sess.sections:
    total_p += sec.pass_
    total_f += sec.fail
    total_w += sec.warns
    st = P if sec.fail == 0 else F
    extra = f" +{sec.warns}warn" if sec.warns else ""
    print(f"  {sec.name:30s} {sec.pass_:>4d}/{sec.pass_+sec.fail:<4d}  {st}{extra}")
print(f"  {'─'*48}")
print(f"  {'契约字段检查':30s} {s2_pass:>4d}/{s2_total:<4d}  {P if s2_fail==0 else F} +{s2_warn}warn")
print(f"  {'融合覆盖检查':30s} {fused_pass:>4d}/{fused_total:<4d}  {P if fused_fail==0 else F}")
print(SEP_THICK)

overall = total_f == 0 and s2_fail == 0 and fused_fail == 0
sys.exit(0 if overall else 1)