# 命令职责划分设计方案

## 设计理念

**三层信息粒度**，满足不同场景需求：

1. **search** - 快速浏览（轻量级）
2. **info** - 中等详情（单平台完整）
3. **detail** - 深度查询（跨平台聚合）

---

## 命令定义

### 1. `search` - 快速浏览

**场景**：搜索多个模组、快速浏览列表、初步筛选

**数据粒度**：
- 仅基本信息（名称、类型、简介）
- 每平台最多 3 个结果
- 描述截断至 200 字符
- 不包含依赖、版本历史、详细统计

**适用**：
- "搜索几个光影包"
- "看看有哪些科技模组"
- "快速浏览钠的替代品"

**命令示例**：
```bash
mc-search --json search 光影
mc-search --json search 科技 --modpack
mc-search --json search sodium
```

---

### 2. `info` - 中等详情（新增）

**场景**：了解某个模组的基本信息、快速查阅

**数据粒度**：
- 单平台完整信息（默认 MC 百科）
- 包含：名称、作者、版本、分类、简介
- 包含：前置/联动依赖（MC 百科数据）
- 不包含：Modrinth 数据、详细统计、版本历史

**适用**：
- "钠模组怎么样"
- "机械动力的作者是谁"
- "查看某个模组的依赖"

**命令示例**：
```bash
mc-search --json info 钠
mc-search --json info https://www.mcmod.cn/class/2785.html
mc-search --json info sodium --platform modrinth
```

**新增选项**：
| 选项 | 说明 |
|------|------|
| `--platform` | 指定平台：mcmod/modrinth |
| `--deps` | 包含依赖关系（默认开启） |
| `--no-deps` | 不包含依赖（加速） |

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

**适用**：
- "研究钠模组的完整信息"
- "对比 MC 百科和 Modrinth 的数据"
- "收集模组的完整元数据"

**命令示例**：
```bash
mc-search --json detail 钠
mc-search --json detail sodium --platforms all
mc-search --json detail 机械动力 --versions
```

**新增选项**：
| 选项 | 说明 |
|------|------|
| `--platforms` | 平台列表：mcmod,modrinth,all（默认 all） |
| `--versions` | 包含版本历史 |
| `--stats` | 包含社区统计 |
| `--gallery` | 包含截图画廊 |

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

## 向后兼容方案

### 方案 A：保留 `show` 作为 `info` 的别名

```python
# CLI 解析时
if args.cmd == "show":
    args.cmd = "info"
```

**优点**：
- 现有用户无感知
- 文档只需说明别名关系

**缺点**：
- `show` 语义不够清晰

### 方案 B：保留 `show --full` 作为 `detail` 的别名

```python
# CLI 解析时
if args.cmd == "show" and args.full:
    args.cmd = "detail"
```

**优点**：
- `show --full` → `detail` 语义自然
- `show` 默认行为保持不变

**缺点**：
- 需要处理 `show --full` 的迁移

### 推荐方案：**方案 B**

```
search  → search (保持不变)
show    → info (默认行为)
show --full → detail
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

## 决策树

```
用户询问模组信息
│
├── "搜索/查找/看看有哪些" → search
├── "X 模组怎么样/信息/作者" → info
└── "完整信息/详细/对比" → detail
```

---

## 示例场景

### 场景 1：快速浏览光影包
```bash
mc-search --json search BSL --shader
# 返回：BSL Shaders, Complementary, 等 3 个光影的基本信息
```

### 场景 2：了解钠模组
```bash
mc-search --json info 钠
# 返回：MC 百科完整信息，包含依赖关系
```

### 场景 3：深入研究钠模组
```bash
mc-search --json detail 钠
# 返回：MC 百科 + Modrinth 完整信息，包含版本历史、统计、截图
```

---

## 优势

1. **语义清晰**：search/info/detail 职责明确
2. **性能优化**：轻量级命令不浪费网络请求
3. **用户体验**：按需获取信息，避免过度查询
4. **可扩展性**：每个命令可独立增强
