# 故障排查

## 快速诊断流程

```
命令执行失败
│
├─ 返回 "无相关结果"
│   ├─ 检查关键词拼写 → 尝试其他关键词
│   ├─ 检查搜索类型 → 搜模组用 search，搜物品用 --type item
│   └─ 检查平台过滤 → 是否使用了 --no-mcmod/--no-mr
│
├─ 网络错误
│   ├─curl: command not found → 安装 curl
│   ├─ MC百科 响应过短 → 被限流，使用 --cache 或稍后重试
│   └─ Modrinth API 错误 → 检查网络或稍后重试
│
└─ 解析错误
    ├─ 无法解析模组 ID → 使用 URL 直接查询
    └─ JSON 解析失败 → 检查 stderr 输出
```

---

## curl 不存在

**症状**：`/bin/curl: No such file or directory` 或 `command not found: curl`

**解决**：
- **Windows**：安装 [curl for Windows](https://curl.se/windows/) 或使用 WSL
- **Termux**：curl 通常已预装；如不存在则 `pkg install curl`
- **Linux/macOS**：系统自带，无需安装
- **验证安装**：运行 `curl --version`

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
   - 模组搜索：`search <关键词>`
   - 物品搜索：`search <关键词> --type item`

**解决方案**：
1. 稍后重试（限流通常持续 5-15 分钟）
2. 使用 `--cache` 利用缓存（TTL 1小时）
3. 更换搜索关键词（尝试中英文、缩写）

## 缓存管理

**查看缓存状态**：
```bash
ls -lh ~/.cache/mc-search/
```

**清理缓存**：
```bash
rm -rf ~/.cache/mc-search/
```

**缓存 TTL**：1 小时（搜索）、1 天（详情）

**适用场景**：
- 缓存中有正确结果，可立即响应
- 网络不稳定或被限流时
- 需要快速测试而不等待网络请求

## Modrinth API 错误

**症状**：`[mod_id] 查询依赖时网络错误` 或 `Modrinth API 请求失败`

**排查步骤**：

1. **检查网络连接**：
   ```bash
   curl -s -H "User-Agent: mc-search/0.4.0" "https://api.modrinth.com/v2/project/sodium" | python -m json.tool
   ```

2. **检查限流状态**：
   - HTTP 429：触发了速率限流
   - API 限制：360 请求/小时
   - 等待 1 小时自动重置

3. **检查返回内容**：
   - HTTP 403/500：服务端问题，稍后重试
   - 返回空或 JSON 错误：检查网络或 User-Agent

**解决方案**：
1. 稍后重试（等待 5-15 分钟）
2. 使用 `--cache` 利用缓存数据
3. 减少频繁请求（特别是 `full` 命令）

## minecraft.wiki 搜索无结果

**症状**：`minecraft.wiki 无 [关键词] 相关结果`

**原因分析**：
1. minecraft.wiki **只收录原版内容**（方块、物品、生物、机制），不包含模组
2. Termux 环境下 minecraft.wiki 间歇性不可达
3. MediaWiki API 端点被防火墙阻止

**验证网络**：
```bash
curl -s -H "User-Agent: mc-search/0.4.0" "https://minecraft.wiki/api.php?action=query&list=search&srsearch=Diamond&format=json" | head -c 300
```

**建议**：
- 模组相关 → 用 `search` 或 `full`（走 MC百科/Modrinth）
- 原版内容 → 用 `wiki`

## MC百科 class ID 解析失败

**症状**：`无法解析模组 ID` 或 `MC百科 搜索结果结构变化`

**原因**：
- MC百科搜索页面 HTML 结构变化
- 网络超时导致 HTML 截断
- 关键词在 MC百科 无结果

**解决方案**：
1. 直接使用 MC百科 URL：
   ```bash
   mc-search info https://www.mcmod.cn/class/18710.html
   ```
2. 改用 Modrinth 搜索：
   ```bash
   mc-search --json full <模组名>
   ```

## 速度问题

**性能基准**：
| 操作 | 预期耗时 | 说明 |
|------|----------|------|
| 搜索（四平台并行） | 2-5 秒 | 取决于最慢平台 |
| 详情查询（full） | 3-8 秒 | 需多次 API 请求 |
| 依赖查询（dep） | 1-3 秒 | 单次 API 请求 |
| Wiki 搜索 | 1-3 秒 | MediaWiki API |

**优化建议**：
- 使用 `--cache` 减少网络请求
- 避免频繁重复请求
- 超时时间：默认 12 秒，可适当调整

## Modrinth 搜索结果不准确

**症状**：搜索 "Spawn" 但返回 "Spawn Animations" 作为第 1 结果

**原因**：
- Modrinth API 使用自己的相关性排序（考虑下载量、热度等）
- 工具的搜索排序只在**融合结果**时生效

**解决方案**：
1. 使用 `full` 命令，它会先用原始关键词直搜 Modrinth 并精确匹配 slug
2. 使用更具体的关键词（如 "Spawn mod" 而非 "spawn"）
3. 检查融合结果中的 `source` 字段，确认是否来自正确平台

## 调试模式

**使用 `--json` 查看完整返回**：
```bash
mc-search --json search 关键词 2>&1 | python3 -m json.tool
```

**查看平台统计**：
```bash
mc-search --json search 关键词 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(json.dumps(d.get('platform_stats', {}), indent=2))
"
```

**检查相关性评分**（内部使用）：
```python
# 在 Python 中测试评分逻辑
import sys
sys.path.insert(0, 'skills/mc-search/scripts')
from core import _calc_name_score

query = "spawn"
names = ["spawn", "spawn animations", "orespawn"]
for name in names:
    score = _calc_name_score(name.lower(), query.lower())
    print(f"{name:30s} → score={score}")
```

## 常见问题 FAQ

### Q1: 为什么 "Spawn" 模组有时排第 1，有时排后面？

**A**: 取决于使用的命令：
- `search` 命令：使用智能排序，"Spawn"（精确匹配）排第 1
- `full` 命令：先用原始关键词直搜 Modrinth，精确匹配 slug 时排第 1

**如果仍然遇到问题**：
1. 使用更具体的关键词（如 "Spawn mod" 而非 "spawn"）
2. 直接使用 Modrinth slug：`full spawn-mod`
3. 使用 MC百科 class URL：`info https://www.mcmod.cn/class/14900.html`

### Q2: 为什么小众模组排名靠后？

**A**: 因为 Modrinth/MC百科 的 API 使用热度排序（下载量、关注度等）。工具的排序逻辑已在改善：
- 精确匹配优先（第 0 层）
- 前缀匹配次之（第 1 层）
- 包含匹配再次之（第 2 层）

但仍无法完全克服热度因素。**建议**：使用精确模组名或 slug。

### Q3: 如何查看模组的完整版本历史？

**A**: 使用 `full` 命令，它会获取 Modrinth 的完整版本列表：
```bash
mc-search --json full sodium
```

返回的 `version_groups` 字段包含所有版本分组。

### Q4: 如何判断返回数据是否完整？

**A**: 检查 `_truncated` 字段：
```json
{
  "_truncated": {
    "version_groups": {"returned": 5, "total": 62}
  }
}
```

如有 `_truncated`，表示数据不完整。可使用 `full` 命令获取完整数据（仅 Modrinth 部分）。

### Q5: 缓存是否会导致数据过时？

**A**: 缓存 TTL 为 1 小时，超过后自动失效。对于版本检查等实时性要求高的场景，建议：
1. 不使用 `--cache`
2. 直接使用 Modrinth API
3. 使用 `update-check` 命令专门检查版本
