# 故障排查

## 快速诊断流程

```
调用失败
│
├─ 返回空或无结果
│   ├─ 检查关键词拼写 → 尝试其他关键词
│   ├─ 检查 content_type → 模组用 "mod"，物品用 "item"
│   └─ 检查平台路由 → core.set_platform_enabled(False, ["mcmod"]) 禁用了平台？
│
├─ 网络错误
│   ├─ MC百科 服务不可用 → 自动降级，搜索页数据已返回
│   └─ Modrinth API 错误 → 检查 _error 字段，可能 rate_limited
│
└─ 解析错误
    ├─ _error: parse_failed → 正常降级，搜索页数据已返回
    └─ 空字段 → 检查 MC百科 HTML 结构是否变化
```

> **手动调试 CLI**：`mc-search --json search 关键词 2>&1 | python3 -m json.tool`

---

## MC百科返回空结果

**症状**：`所有平台均无 [关键词] 相关结果`，但确认关键词存在

**排查步骤**：

1. **检查网络连接**：
   ```bash
   curl -s -H "User-Agent: Mozilla/5.0" "https://search.mcmod.cn/s?key=test&filter=0" | head -c 500
   ```

2. **判断是否被限流**：
   - 返回空 HTML 或 `<1000` 字符：被临时封禁
   - HTTP 429/503：服务器限流或维护

3. **检查搜索类型**：
   - 模组搜索：`core.search_all("<关键词>", content_type="mod")`
   - 物品搜索：`core.search_all("<关键词>", content_type="item")`

**解决方案**：
1. 稍后重试（限流通常持续 5-15 分钟）
2. 更换搜索关键词（尝试中英文、缩写）

## Modrinth API 错误

**症状**：`[mod_id] 查询依赖时网络错误` 或 `Modrinth API 请求失败`

**排查步骤**：

1. **检查网络连接**：
   ```bash
   curl -s "https://api.modrinth.com/v2/project/sodium" | python -m json.tool
   ```

2. **检查限流状态**：
   - HTTP 429：触发了速率限流
   - API 限制：360 请求/小时
   - 等待 1 小时自动重置

3. **检查返回内容**：
   - HTTP 403/500：服务端问题，稍后重试；wiki 403 请检查 `curl_cffi>=0.15.0` 是否安装
   - 返回空或 JSON 错误：检查网络或 User-Agent

**解决方案**：
1. 稍后重试（等待 5-15 分钟）
2. 减少频繁请求（特别是 `core.fetch_mod_info()` 的完整详情查询）

## minecraft.wiki 搜索无结果

**症状**：`minecraft.wiki 无 [关键词] 相关结果`

**原因分析**：
1. minecraft.wiki **只收录原版内容**（方块、物品、生物、机制），不包含模组
2. Termux 环境下 minecraft.wiki 间歇性不可达
3. MediaWiki API 端点被防火墙阻止

**验证网络**：
```bash
curl -s -H "User-Agent: mc-search/5.4.0-dev" "https://minecraft.wiki/api.php?action=query&list=search&srsearch=Diamond&format=json" | head -c 300
```

**建议**：
- 模组相关 → 用 `core.search_all()` 或 `core.fetch_mod_info()`（走 MC百科/Modrinth）
- 原版内容 → 用 `core.search_wiki()`（minecraft.wiki 只收录原版游戏内容）

## MC百科 class ID 解析失败

**症状**：`无法解析模组 ID` 或 `MC百科 搜索结果结构变化`

**原因**：
- MC百科搜索页面 HTML 结构变化
- 网络超时导致 HTML 截断
- 关键词在 MC百科 无结果

**解决方案**：
1. 直接使用 MC百科 URL：
   ```python
   core.fetch_mod_info("https://www.mcmod.cn/class/18710.html")
   ```
2. 改用 Modrinth 搜索：
   ```python
   core.fetch_mod_info("<slug>")  # e.g., "sodium"
   ```

## 速度问题

**性能基准**：
| 操作 | API | 预期耗时 |
|------|-----|----------|
| 搜索（四平台并行） | `search_all()` | 2-5 秒 |
| 详情查询 | `fetch_mod_info()` | 3-8 秒 |
| 依赖查询 | `get_mod_dependencies()` | 1-3 秒 |
| Wiki 搜索 | `search_wiki()` | 1-3 秒 |

**优化建议**：
- 设置 `max_per_source` 限制每个平台的返回数量
- 尽量避免循环中重复调用 `fetch_mod_info()`

## Modrinth 搜索结果不准确

**症状**：搜索 "Spawn" 但返回 "Spawn Animations" 作为第 1 结果

**原因**：
- Modrinth API 使用自己的相关性排序（考虑下载量、热度等）
- 工具的搜索排序只在**融合结果**时生效

**解决方案**：
1. 使用 `core.fetch_mod_info("spawn")` 精确匹配 slug
2. 使用更具体的关键词（如 "Spawn mod" 而非 "spawn"）
3. 检查融合结果中的 `source` 字段，确认是否来自正确平台

## 调试模式

### Agent 用法：查看完整返回

```python
import sys; sys.path.insert(0, 'skills/mc-search')
from scripts import core

r = core.search_all("关键词", fuse=True)
for entry in r["results"]:
    print(entry["name"], entry["source"], entry.get("_score"))
```

### Agent 用法：查看平台统计

```python
r = core.search_all("关键词", fuse=False)
for platform, data in r.items():
    if platform == "platform_stats": continue
    print(f"{platform}: {len(data)} results")
print(r.get("platform_stats"))
```

### Agent 用法：检查相关性评分

```python
from scripts.core import _calc_name_score

query = "spawn"
names = ["spawn", "spawn animations", "orespawn"]
for name in names:
    score = _calc_name_score(name.lower(), query.lower())
    print(f"{name:30s} → score={score}")
```

### 手动调试：CLI

```bash
mc-search --json search 关键词 2>&1 | python3 -m json.tool
mc-search --json search 关键词 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(json.dumps(d.get('platform_stats', {}), indent=2))
"
```

## 常见问题 FAQ

### Q1: 为什么搜索结果不准确？

**A**: Modrinth/MC百科 API 使用热度排序（下载量、关注度）。建议：
- 用 `core.fetch_mod_info()` 通过 slug 精确匹配
- 在 `search_all` 结果中检查 `is_primary: true` 标记

### Q2: 如何查看完整版本历史？

**A**: 使用 `core.fetch_mod_info()`：
```python
info = core.fetch_mod_info("sodium")
print(info["version_groups"])   # 最多 5 组
print(info["version_history"])  # 完整版本列表
print(info["changelogs"])        # 最近 5 条
```

### Q3: 如何判断数据是否完整？

**A**: 检查 `_truncated` 字段，详见 [result-schema.md](result-schema.md#_truncated-元数据字段)。

### Q5: 如何按作者搜索？

**A**: 使用 `core.search_mcmod_author()`：
```python
results = core.search_mcmod_author("jellysquid_")
```

---

## 详细错误码参考

完整的错误码定义和解决方案，请查看 **[errors.md](errors.md)**。
