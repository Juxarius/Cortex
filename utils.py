from discord import ApplicationContext
from pathlib import Path
import json
from xml.dom import minidom
from itertools import permutations
import pickle
import logging
import functools
import os
from datetime import datetime as dt

from models import SubstringSearcher


CONFIG_FILE_PATH = Path(__file__).parent / 'config.json'
BIN_DUMP_ROOT_PATH = Path('D:/Coding Projects/ao-bin-dumps/')

MAP_ID2NAME_PATH = Path(__file__).parent / 'bin-dumps' / 'map_id2name.pickle'
MAP_NAME2ID_PATH = Path(__file__).parent / 'bin-dumps' / 'map_name2id.pickle'

PORTALS_EDGE_PATH = Path(__file__).parent / 'bin-dumps' / 'portals_edge.pickle'
ADDITIONAL_EDGES_PATH = Path(__file__).parent / 'add_portals.json'
N_LETTER_CACHE_PATH = Path(__file__).parent / 'bin-dumps' / 'n_letter_cache.pickle'
M_TRIE_PATH = Path(__file__).parent / 'bin-dumps' / 'm_trie.pickle'
SS_SEARCH_CACHE_PATH = Path(__file__).parent / 'bin-dumps' / 'ss_search_cache.pickle'

LOG_FILE_PATH = Path(__file__).parent / 'cortex.log'

# Load config before anything
with open(CONFIG_FILE_PATH, 'r') as f:
    config = json.load(f)

# Logging
def rotate_logs() -> None:
    if os.path.exists(LOG_FILE_PATH):
        os.rename(LOG_FILE_PATH, f'{LOG_FILE_PATH}.{dt.now().strftime("%Y-%m-%d_%H-%M-%S")}')

rotate_logs()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(LOG_FILE_PATH, 'a', 'utf-8')
handler.setLevel(logging.getLevelNamesMapping()[config['logLevel']])
handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
logger.addHandler(handler)
debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical


# General Utils
def contains_digits(s: str) -> bool:
    return any(char.isdigit() for char in s)

def pythagoras(pos1: list[float], pos2: list[float]) -> float:
    return ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)**0.5

def extract_pos_floats(item: minidom.Element) -> tuple[float]:
    return tuple(map(float, item.getAttribute('pos').split(' ')))

def load_pickle(path: Path) -> dict:
    with open(path, 'rb') as f:
        return pickle.load(f)

def ctx_info(ctx: ApplicationContext) -> str:
    alias = ''
    if config['approvedServers'].get(str(ctx.guild_id), None) is not None:
        alias = f' ({config['approvedServers'][str(ctx.guild_id)]['name']})'
    return f'{ctx.author.name} [{ctx.author.id}] - {ctx.guild}{alias} [{ctx.guild_id}]'

def requires_approved(func):
    @functools.wraps(func)
    async def wrapper(ctx: ApplicationContext, *args, **kwargs):
        server_data = config['approvedServers'].get(str(ctx.guild_id), None)
        cmd = f'/{ctx.command} ' + ' '.join(str(v) for v in kwargs.values())
        if server_data is None:
            warning(f"{ctx_info(ctx)} Unapproved server sent {cmd}")
            await ctx.respond("This server is not approved to use this command.")
            return
        info(f"{ctx_info(ctx)} Approved server sent {cmd}")
        ctx.server_data = server_data
        return await func(ctx, *args, **kwargs)
    return wrapper

# Map Utils
def get_map_id_to_name() -> dict[str, str]:
    with open(BIN_DUMP_ROOT_PATH / 'cluster' / 'world_asia.xml', encoding='utf-8') as f:
        doc = minidom.parseString(f.read())
    all_clusters = doc.getElementsByTagName('clusters').item(0).getElementsByTagName('cluster')
    return dict(map(lambda x: (x.getAttribute('id'), x.getAttribute('displayname')), all_clusters))

def make_map_id_name_pickle() -> None:
    id2name = get_map_id_to_name()
    name2id = {v: k for k, v in id2name.items()}
    with open(MAP_ID2NAME_PATH, 'wb') as f:
        pickle.dump(id2name, f)
    with open(MAP_NAME2ID_PATH, 'wb') as f:
        pickle.dump(name2id, f)

MAP_ID2NAME = load_pickle(MAP_ID2NAME_PATH)
MAP_NAME2ID = load_pickle(MAP_NAME2ID_PATH)

# Portal Edges
def get_portals_edge_map() -> list:
    with open(BIN_DUMP_ROOT_PATH / 'cluster' / 'world_asia.xml', encoding='utf-8') as f:
        doc = minidom.parseString(f.read())
    all_clusters = doc.getElementsByTagName('clusters').item(0).getElementsByTagName('cluster')
    graph = {}
    for cluster in all_clusters:
        map_id, map_name = cluster.getAttribute('id'), cluster.getAttribute('displayname')
        if contains_digits(map_name):
            continue
        exits = [c for c in cluster.getElementsByTagName('exit') if '@' in c.getAttribute('targetid')]
        for exit in exits:
            map1, map2 = (exit.getAttribute('id'), map_id), tuple(exit.getAttribute('targetid').split('@'))
            if map1 not in graph: graph[map1] = {}
            if map2 not in graph: graph[map2] = {}
            graph[map1][map2] = 0
            graph[map2][map1] = 0
            # Each portal goes to another map instantly, bidirectional
        for exit_pair in permutations(exits,2):
            multiplier = 1
            if "DUNGEON" in cluster.getAttribute('type'):
                multiplier += 3
            map1, map2 = (exit_pair[0].getAttribute('id'), map_id), (exit_pair[1].getAttribute('id'), map_id)
            map1_pos, map2_pos = extract_pos_floats(exit_pair[0]), extract_pos_floats(exit_pair[1])
            distance = pythagoras(map1_pos, map2_pos)
            if map1 not in graph: graph[map1] = {}
            if map2 not in graph: graph[map2] = {}
            graph[map1][map2] = distance * multiplier
            graph[map2][map1] = distance * multiplier
            # Crossing the map has weight
    try:
        with open(ADDITIONAL_EDGES_PATH) as f:
            additional_edges = json.load(f)
        for edge in additional_edges:
            portal1, portal2 = get_portal_by_map_id(MAP_NAME2ID[edge[0]]), get_portal_by_map_id(MAP_NAME2ID[edge[1]])
            graph[portal1][portal2] = edge[2]
            graph[portal2][portal1] = edge[2]
    except FileNotFoundError:
        pass
    return graph

def make_portals_edge_pickle() -> None:
    graph = get_portals_edge_map()
    with open(PORTALS_EDGE_PATH, 'wb') as f:
        pickle.dump(graph, f)

PORTALS_EDGE = load_pickle(PORTALS_EDGE_PATH)

def get_portal_by_map_id(map_id: str) -> tuple[str, str]:
    for k in PORTALS_EDGE:
        if k[1] == map_id:
            return k
    return ("ROADS", map_id)

import heapq
def dijkstra(graph: dict, start: str, end: str, additional_graph: dict = None):
    if additional_graph is None:
        additional_graph = {}
    starting_nodes = [key for key in graph if key[1] == start] + [key for key in additional_graph if key[1] == start]
    queue = [(0, node, []) for node in starting_nodes]  # (total_cost, current_node, path)
    visited = set()
    
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node[1] == end:
            return path + [node]
        if node in visited:
            continue
        visited.add(node)
        for neighbor, weight in graph.get(node, {}).items():
            heapq.heappush(queue, (cost + weight, neighbor, path + [node]))
        for neighbor, weight in additional_graph.get(node, {}).items():
            heapq.heappush(queue, (cost + weight, neighbor, path + [node]))
    return None  # No path exists

@functools.lru_cache
def translated_djikstra(map1: str, map2: str, additional_edges: tuple[str] = None) -> list[str]:
    additional_graph = {}
    if additional_edges:
        for from_map_id, to_map_id in additional_edges:
            portal1, portal2 = get_portal_by_map_id(from_map_id), get_portal_by_map_id(to_map_id)
            if portal1 not in additional_graph: additional_graph[portal1] = {}
            if portal2 not in additional_graph: additional_graph[portal2] = {}
            additional_graph[portal1][portal2] = 0
            additional_graph[portal2][portal1] = 0
    path = dijkstra(PORTALS_EDGE, MAP_NAME2ID[map1], MAP_NAME2ID[map2], additional_graph)
    if not path:
        return []
    road = []
    for step in path:
        map_name = MAP_ID2NAME[step[1]]
        if road and road[-1] == map_name:
            continue
        road.append(map_name)
    return road

def get_all_zone_names() -> set[str]:
    with open(BIN_DUMP_ROOT_PATH / 'cluster' / 'world_asia.xml', encoding='utf-8') as f:
        doc = minidom.parseString(f.read())
    all_clusters = doc.getElementsByTagName('clusters').item(0).getElementsByTagName('cluster')
    return set(filter(lambda s: s and not contains_digits(s), [cluster.getAttribute('displayname') for cluster in all_clusters]))

def make_n_letter_cache() -> None:
    max_n = 3
    locations = get_all_zone_names()
    cache_map = {}
    for loc in locations:
        split_loc = loc.replace('-', ' ').lower().split()
        for n in range(1, max_n + 1):
            key = ''.join(w[:n] for w in split_loc)
            if key not in cache_map:
                cache_map[key] = []
            cache_map[key].append(loc)
    with open(N_LETTER_CACHE_PATH, 'wb') as f:
        pickle.dump(cache_map, f)

def make_ss_search() -> None:
    searcher = SubstringSearcher(get_all_zone_names())
    with open(SS_SEARCH_CACHE_PATH, 'wb') as f:
        pickle.dump(searcher, f)

N_LETTER_CACHE = load_pickle(N_LETTER_CACHE_PATH)
SS_SEARCHER = load_pickle(SS_SEARCH_CACHE_PATH)

# AI Behaviour
def best_guesses(s: str, home_map: str=None) -> list[str]:
    def first_n_letters(s: str) -> list[str]:
        return N_LETTER_CACHE.get(s, [])

    def substring_and_proximity(s: str, home_map: str=None) -> list[str]:
        ss_results = SS_SEARCHER.get(s)
        if not home_map: return ss_results
        return sorted(ss_results, key=lambda x: len(translated_djikstra(home_map, x)) or 999)
        
    s = s.lower()
    fnl_results = first_n_letters(s)
    # Only return if there are exact matches
    if len(fnl_results) == 1: return fnl_results
    sap_results = substring_and_proximity(s, home_map)
    return sap_results + [m for m in fnl_results if m not in sap_results]

def best_guess(s: str, home_map: str=None) -> str:
    try:
        guesses = best_guesses(s, home_map)[0]
        debug(f'Guessed {guesses} from {s}')
        return guesses
    except IndexError:
        debug(f'Could not guess {s}')
        return None

def est_traveling_time_seconds(m: str, home_map: str=None) -> int:
    if not home_map: return 0
    return (len(translated_djikstra(home_map, m)) - 1) * config['secondsPerMap']

def show(obj) -> None:
    import json
    print(json.dumps(obj, indent=4))

def datetime_test():
    from pymongo import MongoClient
    from models import Reminders
    db = MongoClient(f"mongodb://{config['mongoDbHostname']}:{config['mongoDbPort']}/")["cortex"]
    REMINDERS = Reminders(database=db)
    reminders = list(REMINDERS.find_by({}))

def test_queries():
    queries = [
        ("marsh", 'Scuttlesink Marsh', 'Scuttlesink Marsh'),
        ("steep", 'Scuttlesink Marsh', 'Shaleheath Steep'),
        ("hills", 'Scuttlesink Marsh', 'Shaleheath Hills'),
        ("descent", 'Fort Sterling', 'Whitebank Descent'),
        ("precipice", 'Lymhurst', 'Watchwood Precipice'),
        ('qan', None, 'Qiient-Al-Nusom'),
        ('qialte', None, 'Qiient-Al-Tersas'),
        ('qat', None, 'Quaent-Al-Tersis'),
    ]
    import time
    iterations = 500
    start = time.time()
    for _ in range(iterations):
        for q, home_map, _ in queries:
            best_guess(q, home_map)

    time_taken_seconds = (time.time() - start)
    print(f'Took {time_taken_seconds:.6}s, avg {(time_taken_seconds / len(queries) / iterations):.6}s')


if __name__ == "__main__":
    pass
    # datetime_test()
    # Make files
    # make_map_id_name_pickle()
    # make_portals_edge_pickle()
    # make_n_letter_cache()
    # make_m_trie()
    # make_locations_weight_pickle()
    
    # make_ss_search()
    test_queries()
    # ag = [
    #     (MAP_NAME2ID["Shaleheath Steep"], MAP_NAME2ID["Qiient-Al-Nusom"]),
    #     (MAP_NAME2ID["Qiient-Al-Nusom"], MAP_NAME2ID["Fort Sterling"]),
    # ]
    # print(translated_djikstra("Scuttlesink Marsh", "Fort Sterling", ag))
