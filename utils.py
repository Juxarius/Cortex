from pathlib import Path
import json
from xml.dom import minidom
from itertools import permutations
import pickle

CONFIG_FILE_PATH = Path(__file__).parent / 'config.json'
BIN_DUMP_ROOT_PATH = Path('D:/Coding Projects/ao-bin-dumps/')

MAP_ID2NAME_PATH = Path(__file__).parent / 'bin-dumps' / 'map_id2name.pickle'
MAP_NAME2ID_PATH = Path(__file__).parent / 'bin-dumps' / 'map_name2id.pickle'

PORTALS_EDGE_PATH = Path(__file__).parent / 'bin-dumps' / 'portals_edge.pickle'
ADDITIONAL_EDGES_PATH = Path(__file__).parent / 'add_portals.json'
LOCATIONS_WEIGHT_PATH = Path(__file__).parent / 'bin-dumps' / 'locations_weight.pickle'

# General Utils
with open(CONFIG_FILE_PATH, 'r') as f:
    config = json.load(f)

def contains_digits(s: str) -> bool:
    return any(char.isdigit() for char in s)

def pythagoras(pos1: list[float], pos2: list[float]) -> float:
    return ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)**0.5

def extract_pos_floats(item: minidom.Element) -> tuple[float]:
    return tuple(map(float, item.getAttribute('pos').split(' ')))

def load_pickle(path: Path) -> dict:
    with open(path, 'rb') as f:
        return pickle.load(f)

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
            map1, map2 = (exit_pair[0].getAttribute('id'), map_id), (exit_pair[1].getAttribute('id'), map_id)
            map1_pos, map2_pos = extract_pos_floats(exit_pair[0]), extract_pos_floats(exit_pair[1])
            distance = pythagoras(map1_pos, map2_pos)
            if map1 not in graph: graph[map1] = {}
            if map2 not in graph: graph[map2] = {}
            graph[map1][map2] = distance
            graph[map2][map1] = distance
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

import heapq
def dijkstra(graph: dict, start: str, end: str):
    starting_nodes = [key for key in graph.keys() if key[1] == start] 
    queue = [(0, node, []) for node in starting_nodes]  # (total_cost, current_node, path)
    visited = set()
    
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node[1] == end:
            return path + [node]
        if node in visited:
            continue
        visited.add(node)
        for neighbor, weight in graph[node].items():
            heapq.heappush(queue, (cost + weight, neighbor, path + [node]))
    return None  # No path exists

def translated_djikstra(map1: str, map2: str) -> list[str]:
    path = dijkstra(PORTALS_EDGE, MAP_NAME2ID[map1], MAP_NAME2ID[map2])
    if not path:
        return []
    road = []
    for step in path:
        map_name = MAP_ID2NAME[step[1]]
        if road and road[-1] == map_name:
            continue
        road.append(map_name)
    return road

def get_all_zone_names() -> list[str]:
    with open(BIN_DUMP_ROOT_PATH / 'cluster' / 'world_asia.xml', encoding='utf-8') as f:
        doc = minidom.parseString(f.read())
    all_clusters = doc.getElementsByTagName('clusters').item(0).getElementsByTagName('cluster')
    return list(filter(lambda s: s and not contains_digits(s), [cluster.getAttribute('displayname') for cluster in all_clusters]))

def get_locations_weight() -> list:
    return {loc: (len(translated_djikstra(config['homeMap'], loc)) or None) for loc in set(get_all_zone_names())}

def make_locations_weight_pickle() -> None:
    lw = get_locations_weight()
    with open(LOCATIONS_WEIGHT_PATH, 'wb') as f:
        pickle.dump(lw, f)

LOCATIONS_WEIGHT = load_pickle(LOCATIONS_WEIGHT_PATH)

# AI Behaviour
def best_guesses(s: str) -> list[str, int]:
    s = s.lower()
    guesses = []
    for lw in LOCATIONS_WEIGHT.items():
        name = lw[0].lower()
        if s not in name: continue
        if lw[1] is None: continue
        guesses.append(lw)
    return sorted(guesses, key=lambda x: x[1])

def best_guess(s: str) -> str:
    try:
        return best_guesses(s)[0][0]
    except IndexError:
        return None

def est_traveling_time_seconds(m: str) -> int:
    distance = LOCATIONS_WEIGHT[m]
    if distance is None:
        return None
    return (distance - 1) * config['secondsPerMap']

def show(obj) -> None:
    import json
    print(json.dumps(obj, indent=4))

def datetime_test():
    from pymongo import MongoClient
    from models import Reminders
    db = MongoClient(f"mongodb://{config['mongoDbHostname']}:{config['mongoDbPort']}/")["cortex"]
    REMINDERS = Reminders(database=db)
    reminders = list(REMINDERS.find_by({}))

if __name__ == "__main__":
    pass
    # datetime_test()
    # Make files
    # make_map_id_name_pickle()
    # make_portals_edge_pickle()
    # make_locations_weight_pickle()
    # show(LOCATIONS_WEIGHT)
