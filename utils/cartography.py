from config import config
from logger import debug, info, warning, error
import heapq

from utils.bindata import ZONES, PORTALS_EDGE, N_LETTER_CACHE, SS_SEARCHER
from models.dbmodels import Portal

def dijkstra(graph: dict, start: str, end: str, additional_graph: dict = None, max_distance: int=9999):
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
        if len(path) > max_distance:
            continue
        for neighbor, weight in graph.get(node, {}).items():
            heapq.heappush(queue, (cost + weight, neighbor, path + [node]))
        for neighbor, weight in additional_graph.get(node, {}).items():
            heapq.heappush(queue, (cost + weight, neighbor, path + [node]))
    return None  # No path exists

# @functools.lru_cache
def translated_djikstra(map1: str, map2: str, roads: list[Portal]=None, max_distance: int=9999) -> list[str]:
    if roads is None:
        roads = []
    additional_graph = {}
    for road in roads:
        portal1, portal2 = ZONES.get_portal(road.from_map), ZONES.get_portal(road.to_map)
        if portal1 not in additional_graph: additional_graph[portal1] = {}
        if portal2 not in additional_graph: additional_graph[portal2] = {}
        additional_graph[portal1][portal2] = 0
        additional_graph[portal2][portal1] = 0
    path = dijkstra(PORTALS_EDGE, ZONES.get_map_id(map1), ZONES.get_map_id(map2), additional_graph, max_distance)
    if not path:
        return []
    road = []
    for step in path:
        map_name = ZONES.get_map_name(step[1])
        if road and road[-1] == map_name:
            continue
        road.append(map_name)
    return road

# AI Behaviour
def first_n_letters(s: str) -> list[str]:
    return N_LETTER_CACHE.get(s, [])

def substring_and_proximity(s: str, home_map: str=None) -> list[str]:
    ss_results = SS_SEARCHER.get(s)
    if not home_map: return ss_results
    return sorted(ss_results, key=lambda x: len(translated_djikstra(home_map, x)) or 999)

def best_guesses(s: str, home_map: str=None) -> list[str]:
    s = s.lower()
    fnl_results = first_n_letters(s)
    
    if len(fnl_results) == 1: return fnl_results # Only return if there are exact matches
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
    iterations = 2
    start = time.time()
    for _ in range(iterations):
        for q, home_map, _ in queries:
            best_guess(q, home_map)

    time_taken_seconds = (time.time() - start)
    print(f'Took {time_taken_seconds:.6}s, avg {(time_taken_seconds / len(queries) / iterations):.6}s')
