# mc-search - Minecraft 聚合搜索工具
from .core import (
    # 搜索
    search_all,
    search_mcmod,
    search_modrinth,
    search_wiki,
    search_wiki_zh,
    search_modrinth_author,
    search_mcmod_author,
    # 详情
    read_wiki,
    read_wiki_zh,
    fetch_mod_info,
    get_mod_dependencies,
    fetch_item_recipe,
    # 配置
    set_cache,
    set_platform_enabled,
    # 异常类
    SearchError,
    NetworkError,
    ParseError,
    PlatformError,
    CacheError,
    # 公共工具（原下划线前缀已移除）
    clean_html_text,
    curl,
    MIN_HTML_LEN,
    MIN_HTML_LEN_ITEM,
    # 解析函数（公开接口）
    parse_mcmod_result,
)
