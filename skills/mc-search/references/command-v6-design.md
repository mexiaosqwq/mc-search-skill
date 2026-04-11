# 命令职责划分 - v6.0 设计方案

## 设计理念

**三层信息粒度**，满足不同场景需求：

| 命令 | 场景 | 数据范围 | 网络请求 |
|------|------|----------|----------|
| `search` | 快速浏览、列表筛选 | 基本信息（名称、简介） | 仅搜索 API |
| `info` | 了解模组详情 | 单平台完整信息 + 依赖 | 搜索 + 详情页面 |
| `detail` | 深度研究、跨平台对比 | 跨平台聚合 + 版本历史 + 统计 | 搜索 + 详情 + 版本 + 依赖 |

---

## 命令定义

### 1. `search` - 快速浏览

**场景**：搜索多个模组、快速浏览列表、初步筛选

**数据粒度**：
- 仅基本信息（名称、类型、简介）
- 每平台最多 3 个结果
- 描述截断至 200 字符
- 不包含依赖、版本历史、详细统计

**示例**：
```bash
mc-search --json search 光影           # 快速浏览光影包列表
mc-search --json search 科技 --modpack # 快速浏览整合包
mc-search --json search sodium         # 快速浏览钠相关信息
```

---

### 2. `info` - 中等详情（新增）

**场景**：了解某个模组的基本信息、快速查阅

**数据粒度**：
- 单平台完整信息（默认 MC 百科）
- 包含：名称、作者、版本、分类、简介
- 包含：前置/联动依赖（MC 百科数据）
- 不包含：Modrinth 数据、详细统计、版本历史

**示例**：
```bash
mc-search --json info 钠                    # 默认 MC 百科
mc-search --json info 钠 --platform modrinth # Modrinth 平台
mc-search --json info 钠 --no-deps           # 不包含依赖
```

**选项**：
| 选项 | 说明 | 默认 |
|------|------|------|
| `--platform` | 指定平台：mcmod/modrinth | mcmod |
| `--deps` | 包含依赖关系 | true |
| `--no-deps` | 不包含依赖 | false |

---

### 3. `detail` - 深度查询（新增）

**场景**：深入研究、跨平台对比、完整数据收集

**数据粒度**：
- 跨平台完整信息（MC 百科 + Modrinth）
- 包含：双平台所有字段
- 包含：Modrinth 依赖关系
- 包含：版本历史、更新日志
- 包含：下载统计、社区数据
- 包含：截图画廊、相关链接

**示例**：
```bash
mc-search --json detail 钠              # 默认双平台
mc-search --json detail 钠 --versions   # 包含版本历史
mc-search --json detail 钠 --stats      # 包含社区统计
mc-search --json detail 钠 --gallery    # 包含截图画廊
```

**选项**：
| 选项 | 说明 | 默认 |
|------|------|------|
| `--platforms` | 平台列表：mcmod,modrinth,all | all |
| `--versions` | 包含版本历史 | false |
| `--stats` | 包含社区统计 | false |
| `--gallery` | 包含截图画廊 | false |

---

## 向后兼容方案

### 方案：保留 `show` 作为 `info` 的别名

```
search  → search (保持不变)
show    → info (默认行为，别名)
show --full → detail (等价)
```

**实现方式**：
```python
# CLI 解析时自动映射
if args.cmd == "show":
    if args.full:
        args.cmd = "detail"
    else:
        args.cmd = "info"
```

**优点**：
- 现有用户无感知
- 文档只需说明别名关系
- 平滑迁移

---

## 对比表

| 字段 | search | info | detail |
|------|--------|------|--------|
| 名称 | ✓ | ✓ | ✓ |
| 简介 | ✓(截断) | ✓(完整) | ✓(完整) |
| 作者 | ✓ | ✓ | ✓ |
| 版本 | ✗ | ✓ | ✓ |
| 分类/标签 | ✓ | ✓ | ✓ |
| 依赖 | ✗ | ✓(MC 百科) | ✓(双平台) |
| Modrinth 数据 | ✗ | ✗ | ✓ |
| 版本历史 | ✗ | ✗ | ✓ |
| 下载统计 | ✗ | ✗ | ✓ |
| 截图画廊 | ✗ | ✗ | ✓ |
| 更新日志 | ✗ | ✗ | ✓ |

---

## 决策树

```
用户询问模组信息
│
├── "搜索/查找/看看有哪些" → search
├── "X 模组怎么样/信息/作者" → info
└── "完整信息/详细/对比" → detail
```

---

## 实现优先级

### Phase 1: 添加 `info` 命令（核心）
1. 新增 `info` 子命令
2. 实现单平台完整信息抓取
3. 默认 MC 百科，支持 `--platform modrinth`

### Phase 2: 添加 `detail` 命令（增强）
1. 新增 `detail` 子命令
2. 实现跨平台聚合
3. 支持版本历史、统计等扩展字段

### Phase 3: 别名映射（兼容）
1. `show` → `info` 别名
2. `show --full` → `detail` 别名
3. 更新文档

---

## 优势

1. **语义清晰**：search/info/detail 职责明确
2. **性能优化**：轻量级命令不浪费网络请求
3. **用户体验**：按需获取信息，避免过度查询
4. **可扩展性**：每个命令可独立增强
