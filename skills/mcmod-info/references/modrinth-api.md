# Modrinth API

## 搜索接口

**URL**: `https://api.modrinth.com/v2/search`

| 参数 | 说明 |
|------|------|
| `query` | 搜索关键词 |
| `index` | 排序：`relevance`（默认） |
| `limit` | 返回数量（API 默认 20；CLI `mr` 命令默认传入 5，由 `-n` 参数控制） |

**请求头**: `User-Agent: mcmod-search/1.0`（必须有）

**示例**:
```
https://api.modrinth.com/v2/search?query=sodium&index=relevance&limit=5
```

## 响应字段

```json
{
  "hits": [{
    "title": "Sodium",
    "slug": "sodium",
    "description": "The fastest and most compatible rendering optimization mod...",
    "project_type": "mod",
    "url": "https://modrinth.com/mod/sodium"
  }]
}
```

## 注意事项

- `project_type` 包含 `mod`、`shader`、`resourcepack` 等，需过滤 `mod`
- 不使用 facets 参数（URL encode 问题），在代码中过滤
- 支持匿名访问，无需 API key
- 限速：每小时 360 次（由 Modrinth API 强制，代码无本地限速）
