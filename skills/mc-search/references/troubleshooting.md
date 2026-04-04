# 故障排查

## curl 不存在

**症状**：`/bin/curl: No such file or directory`

**解决**：
- Windows：安装 [curl for Windows](https://curl.se/windows/) 或使用 WSL
- Termux：curl 通常已预装；如不存在则 `pkg install curl`
- Linux/macOS：自带，无需安装

## MC百科返回空结果

**症状**：`四个平台均无 [关键词] 相关结果`，但网络正常

**排查**：
```bash
# 模组搜索（filter=0）
curl -s "https://search.mcmod.cn/s?key=关键词&filter=0" | head -c 500
# 物品搜索（filter=3）
curl -s "https://search.mcmod.cn/s?key=关键词&filter=3" | head -c 500
```

- 返回空 HTML 或 `<1000` 字符：被临时封禁
- 有结果但工具无返回：可能是请求格式变化

**解决**：
1. 稍后重试
2. 使用 `--cache` 利用缓存（TTL 1小时）

## 缓存清理

```bash
rm -rf ~/.cache/mc-search/
```

## Modrinth API 错误

**症状**：`[mod_id] 查询依赖时网络错误`

**排查**：
```bash
curl -s "https://api.modrinth.com/v2/project/sodium" -H "User-Agent: Mozilla/5.0"
```

- HTTP 429：触发了限速，等待 1 小时
- HTTP 403/500：Modrinth 服务端问题

## minecraft.wiki 搜索无结果

**症状**：`minecraft.wiki 无 [关键词] 相关结果`

**原因**：
1. minecraft.wiki 只有原版内容（不是 mod 的 wiki）
2. Termux 环境下 minecraft.wiki 间歇性不可达
3. MediaWiki API 端点无法访问

**验证**：
```bash
curl -s "https://minecraft.wiki/api.php?action=query&list=search&srsearch=关键词&format=json" | head -c 300
```

## MC百科 class ID 解析失败

**症状**：`无法解析模组 ID`

**原因**：`search_mcmod` 返回的 URL 与预期格式不符

**解决**：直接传入 class URL：
```bash
mc-search info https://www.mcmod.cn/class/18710.html
```

## 速度问题

- **四平台搜索** 默认超时 12 秒，每平台最多 3 结果
- **单平台搜索** (mr/wiki/author) 默认超时 12 秒
- **详情查询** (info/full/dep) 默认超时 12 秒
- **Modrinth API** 360 req/hr 限制，正常使用不会触发

## 调试模式

使用 `--json` 查看完整返回数据：
```bash
mc-search --json search 关键词
```
