# mc-search 重构计划

## 现状诊断

- **core.py**: 2945 行，92 个函数，109KB
- **cli.py**: 1276 行，32 个函数，51KB
- **主要问题**: 过度工程化、错误处理裸奔、HTML 用正则解析、全局状态混乱

## 重构目标

1. **可靠性**: 消灭裸 `except: pass`，正确错误处理
2. **简洁性**: 减少 50%+ 代码量，删除过度设计
3. **可维护性**: 清晰结构，一致命名
4. **零依赖**: 用标准库替代 subprocess curl

## 阶段一：修复最傻逼的问题（1-2 天）

### 1.1 替换 subprocess curl → urllib
**文件**: `core.py`
**改动**:
```python
# 删除
subprocess.run(["curl", ...])

# 改为
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

def curl(url: str, timeout: int = 10) -> str:
    req = Request(url, headers=HTTP_HEADERS)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode('utf-8', errors='replace')
```
**收益**: 移除外部依赖，Windows 也能用

### 1.2 修复裸 except: pass
**文件**: `core.py`
**改动**:
```python
# 删除
except Exception:
    pass

# 改为
except Exception as e:
    logger.warning(f"Failed to fetch {url}: {e}")
    return ""
```
**收益**: 错误可见，可调试

### 1.3 简化常量
**文件**: `core.py`, `cli.py`
**改动**:
```python
# 删除这 70+ 个常量
_MIN_PARAGRAPH_LEN = 20
_MIN_SHORT_TEXT_LEN = 35
...

# 保留真正需要的
TIMEOUT = 10
MAX_RESULTS = 10
CACHE_TTL = 3600
```
**收益**: 减少噪音，代码清晰

## 阶段二：代码结构重组（2-3 天）

### 2.1 拆分 core.py
```
scripts/
├── __init__.py
├── cli.py              # 保持，但简化
├── core.py             # 只保留公共 API
├── platforms/
│   ├── __init__.py
│   ├── mcmod.py        # MC 百科搜索+解析
│   ├── modrinth.py     # Modrinth API
│   └── wiki.py         # minecraft.wiki
├── cache.py            # 缓存管理
└── utils.py            # 工具函数
```

### 2.2 统一错误处理
```python
# 新增 errors.py
class SearchError(Exception):
    pass

class NetworkError(SearchError):
    pass

class ParseError(SearchError):
    pass

class NotFoundError(SearchError):
    pass
```

### 2.3 统一返回类型
```python
# 新增 types.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class SearchResult:
    name: str
    name_en: Optional[str]
    name_zh: Optional[str]
    url: str
    source: str
    description: Optional[str] = None
    # ...
```

## 阶段三：简化过度设计（2-3 天）

### 3.1 简化评分算法
```python
# 删除复杂的评分系统
_SCORE_EXACT_MATCH_BASE = 100
_SCORE_EXACT_MATCH_MAX_BONUS = 20
...

# 改为简单匹配
def rank_results(results, query):
    exact = [r for r in results if query.lower() == r.name.lower()]
    prefix = [r for r in results if r.name.lower().startswith(query.lower())]
    contains = [r for r in results if query.lower() in r.name.lower()]
    return exact + prefix + contains
```

### 3.2 简化 CLI 输出
```python
# 删除
_INFO_FIELDS = [...]
def _fmt_title(info): ...
def _fmt_status(info): ...
...

# 改为简单格式化
def format_result(result):
    return f"{result.name}\n  {result.url}\n  {result.description[:200]}"
```

### 3.3 删除字段过滤
```python
# 删除 -T, -a, -d, -v, -g, -c, -s, -S 选项
# Agent 可以自己过滤 JSON，不需要 CLI 支持
```

## 阶段四：HTML 解析改进（可选，3-5 天）

### 4.1 用 html.parser 替代正则
```python
from html.parser import HTMLParser

class McmodParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        # ...
```

**注意**: 这是大改动，可能引入 bug，建议先完成前三阶段。

## 重构检查清单

### 阶段一完成标准
- [ ] curl 使用 urllib，不用 subprocess
- [ ] 没有裸 `except: pass`
- [ ] 常量减少到 10 个以内
- [ ] 所有测试通过

### 阶段二完成标准
- [ ] core.py 拆分到 platforms/
- [ ] 有统一的错误类型
- [ ] 有统一的返回类型
- [ ] 代码行数减少 30%

### 阶段三完成标准
- [ ] 评分算法简化
- [ ] CLI 输出简化
- [ ] 删除字段过滤选项
- [ ] 代码行数再减少 20%

### 阶段四完成标准
- [ ] HTML 解析用 html.parser
- [ ] 正则表达式减少到 20 个以内
- [ ] 有完整的测试覆盖

## 风险与回滚

### 高风险改动
1. **HTML 解析重构**: 可能破坏现有功能
2. **错误处理修改**: 可能暴露之前隐藏的问题

### 低风险改动
1. **替换 curl**: 功能等价，风险低
2. **简化常量**: 纯删除，风险低

### 回滚策略
- 每个阶段独立分支
- 阶段完成后测试通过再合并
- 保留原分支作为备份

## 预期结果

| 指标 | 现状 | 目标 |
|------|------|------|
| 总行数 | 4249 | < 2000 |
| 函数数量 | 124 | < 50 |
| 正则数量 | 116 | < 30 |
| 裸 except | 12 | 0 |
| 外部依赖 | curl | 无 |

## 开始重构

建议从**阶段一**开始，风险最低，收益明显。

要我帮你开始阶段一吗？