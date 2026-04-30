# 错误码参考

本文件列出 `mc-search` 返回的错误码及其含义。

## 错误码列表

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| `NO_RESULTS` | 无搜索结果 | 尝试其他关键词或平台 |
| `EMPTY_KEYWORD` | 搜索关键词为空 | 输入有效的搜索关键词 |
| `EMPTY_AUTHOR` | 作者名为空 | 输入有效的作者名 |
| `FETCH_FAILED` | 网络请求失败 | 检查网络或稍后重试 |
| `NOT_FOUND` | 资源不存在 | 检查 URL 或 ID 是否正确 |
| `URL_NOT_FOUND` | URL 指向的资源不存在 | 检查 URL 是否正确 |
| `READ_ERROR` | wiki 页面读取失败 | 检查 URL 或稍后重试 |
| `CAPTCHA` | MC百科触发验证码 | 稍后重试或使用 Modrinth |
| `DISABLED` | 请求的平台已禁用 | 启用对应平台或更换平台 |
| `INVALID_INPUT` | 输入参数不合法 | 检查命令参数格式 |

> 注：所有错误码均在 HTTP 200 下以 JSON 格式返回（`{"error": "...", "message": "..."}`），
> 与 shell exit code 0 配合，确保 Agent 能正确解析错误信息而不被非零退出码中断。

### 内部/嵌套错误码

以下错误码出现在子字段中（如 `dependencies.error`），而非顶层 `error` 字段：

| 错误码 | 说明 | 出现位置 |
|--------|------|----------|
| `PROJECT_NOT_FOUND` | Modrinth 项目不存在 | `get_mod_dependencies()` → `dependencies.error` |
| `API_ERROR` | Modrinth API 请求失败 | `get_mod_dependencies()` → `dependencies.error` |
| `NO_CONTENT` | wiki 页面无内容可读 | `read_wiki()` → 顶层 `error` |

## 错误输出示例

```json
{
  "error": "NO_RESULTS",
  "message": "未找到与 'xyzabc123' 相关的结果"
}
```

```json
{
  "error": "FETCH_FAILED",
  "message": "MC百科 服务不可用（可能维护中）"
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
