# MC百科 搜索 API

## 搜索接口

**URL**: `https://search.mcmod.cn/s`

| 参数 | 值 | 说明 |
|------|---|------|
| `key` | 关键词 | URL encode，中文关键词直接可用 |
| `filter=0` | 模组 | 其他：2=整合包（代码未用），3=资料（物品/方块） |
| `mold=1` | 列表格式 | ⚠️ 代码未使用，加此参数会改变排名算法，不推荐 |
| `page=N` | 分页 | 第 N 页 |

**示例**:
```
https://search.mcmod.cn/s?key=alex洞穴&filter=0
https://search.mcmod.cn/s?key=矿工乐事&filter=0
```

## 响应结构

结果在 `<div class="search-result-list">` 区块内：

```html
<div class="result-item">
  <div class="head">
    <a href="https://www.mcmod.cn/class/23352.html">Alexs Caves Delight</a>
  </div>
  <div class="body">...描述...</div>
</div>
```

## 提取规则

1. 用 `search-result-list` 定位结果区块
2. 正则提取：`href="(https://www\.mcmod\.cn/class/\d+\.html)">([^<]+)</a>`
3. 去掉 `<em>` 高亮标签再提取名称
4. 页面标题：从 `<title>` 取 `- MC百科` 前的部分

## class 页面

**URL**: `https://www.mcmod.cn/class/{id}.html`

提取 `<title>` 即为模组完整名称。

## 限速

每次请求间隔 **0.3s** 以上，被封返回空 HTML。
