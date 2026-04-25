# 错误码参考

本文件列出 `mc-search` 返回的错误码及其含义。

## 错误码列表

| 错误码 | HTTP 状态 | 说明 | 解决方案 |
|--------|----------|------|----------|
| `NO_RESULTS` | 200 | 无搜索结果 | 尝试其他关键词或平台 |
| `FETCH_FAILED` | 200 | 网络请求失败 | 检查网络或稍后重试 |
| `NOT_FOUND` | 404 | 资源不存在 | 检查 URL 或 ID 是否正确 |
| `EMPTY_AUTHOR` | 404 | 作者无结果 | 检查作者名拼写 |
| `PARSE_ERROR` | 500 | 页面解析失败 | 页面结构变化，等待修复 |
| `RATE_LIMITED` | 429 | 触发限流 | 等待 5-15 分钟后重试 |
| `NETWORK_ERROR` | 0 | 网络连接失败 | 检查网络连接 |
| `TIMEOUT` | 0 | 请求超时 | 增加 `--timeout` 值 |

## 错误输出示例

```json
{
  "error": "NO_RESULTS",
  "message": "未找到与 'xyzabc123' 相关的结果"
}
```

```json
{
  "error": "RATE_LIMITED",
  "message": "MC 百科 API 限流，请稍后重试"
}
```

## 调试技巧

### 查看详细错误信息

```bash
mc-search --json search 关键词 2>&1 | python3 -m json.tool
```

### 检查平台状态

```bash
# 检查 MC 百科
curl -s -I "https://www.mcmod.cn" | head -1

# 检查 Modrinth
curl -s -I "https://api.modrinth.com/v2/project/sodium" | head -1

# 检查 wiki
curl -s -I "https://minecraft.wiki/api.php" | head -1
```

## 常见错误场景

### 1. "所有平台均无相关结果"

**原因**: 关键词不存在或拼写错误

**解决**: 
- 检查拼写
- 尝试英文关键词
- 使用 `--platform` 限制搜索范围

### 2. "MC百科 服务不可用（可能维护中）"

**原因**: MC百科 服务器限流或维护

**解决**:
- 等待 5-15 分钟
- 使用 `--cache` 利用缓存
- 改用 `--platform modrinth` 搜索

### 3. "Modrinth API 请求失败"

**原因**: 网络问题或 API 限流（360 请求/小时）

**解决**:
- 检查网络连接
- 等待 1 小时自动重置
- 使用 `--cache`

### 4. "无法解析模组 ID"

**原因**: MC 百科页面结构变化或 HTML 截断

**解决**:
- 直接使用 MC 百科 URL
- 改用 Modrinth slug 搜索
