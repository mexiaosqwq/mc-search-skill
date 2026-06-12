# mc-search - Minecraft 聚合搜索工具
from ._http import SearchError, _clean_html_text, curl, MIN_HTML_LEN, MIN_HTML_LEN_ITEM
from ._mcmod_parse import _parse_mcmod_mod_result
from ._mcmod_search import search_mcmod, search_mcmod_author, search_mcmod_modpack
from ._modrinth import search_modrinth, search_modrinth_author, fetch_mod_info, get_mod_dependencies
from ._wiki import search_wiki, search_wiki_zh, read_wiki, read_wiki_zh
from ._fuse import search_all
from ._http import set_platform_enabled
