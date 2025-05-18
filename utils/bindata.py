from pathlib import Path
from xml.dom import minidom
import pickle
from itertools import permutations
from typing import Callable

from models.substringsearcher import SubstringSearcher
from models.zones import Zones

AO_BIN_DUMP_ROOT_PATH = Path('D:/Coding Projects/ao-bin-dumps/')

BIN_DUMP_DIR = Path(__file__).parent.parent / 'bin-dumps'
ZONE_PATH = BIN_DUMP_DIR / 'zones.pickle'

PORTALS_EDGE_PATH = BIN_DUMP_DIR / 'portals_edge.pickle'
ADDITIONAL_EDGES_PATH = BIN_DUMP_DIR / 'add_portals.json'

N_LETTER_CACHE_PATH = BIN_DUMP_DIR / 'n_letter_cache.pickle'
SS_SEARCH_CACHE_PATH = BIN_DUMP_DIR / 'ss_search_cache.pickle'

ADDITIONAL_PORTALS = [
    ["Fort Sterling", "Fort Sterling Portal", 0],
    ["Lymhurst", "Lymhurst Portal", 0],
    ["Bridgewatch", "Bridgewatch Portal", 0],
    ["Martlock", "Martlock Portal", 0],
    ["Thetford", "Thetford Portal", 0]
]

def contains_digits(s: str) -> bool:
    return any(char.isdigit() for char in s)

def pythagoras(pos1: list[float], pos2: list[float]) -> float:
    return ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)**0.5

def extract_pos_floats(item: minidom.Element) -> tuple[float]:
    return tuple(map(float, item.getAttribute('pos').split(' ')))

def load_pickle(path: Path, make_func: Callable=None) -> dict:
    try:
        with open(path, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        if make_func is not None:
            make_func()
        with open(path, 'rb') as f:
            return pickle.load(f)


# Make bin dumps
def make_zones_pickle() -> None:
    with open(AO_BIN_DUMP_ROOT_PATH / 'cluster' / 'world_asia.xml', encoding='utf-8') as f:
        doc = minidom.parseString(f.read())
    all_clusters_dom = doc.getElementsByTagName('clusters').item(0).getElementsByTagName('cluster')
    zones = Zones(list(
        [c.getAttribute('displayname'), c.getAttribute('id'), [p.getAttribute('id') for p in c.getElementsByTagName('exit')]]
    for c in all_clusters_dom))
    with open(ZONE_PATH, 'wb') as f:
        pickle.dump(zones, f)

ZONES: Zones = load_pickle(ZONE_PATH, make_zones_pickle)


def make_portals_edge_pickle() -> None:
    with open(AO_BIN_DUMP_ROOT_PATH / 'cluster' / 'world_asia.xml', encoding='utf-8') as f:
        doc = minidom.parseString(f.read())
    all_clusters = doc.getElementsByTagName('clusters').item(0).getElementsByTagName('cluster')
    graph = {}
    for cluster in all_clusters:
        map_id, map_name = cluster.getAttribute('id'), cluster.getAttribute('displayname')
        if any(char.isdigit() for char in map_name):
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
    for edge in ADDITIONAL_PORTALS:
        portal1, portal2 = ZONES.get_portal(edge[0]), ZONES.get_portal(edge[1])
        graph[portal1][portal2] = edge[2]
        graph[portal2][portal1] = edge[2]
    with open(PORTALS_EDGE_PATH, 'wb') as f:
        pickle.dump(graph, f)

PORTALS_EDGE: dict = load_pickle(PORTALS_EDGE_PATH, make_portals_edge_pickle)


def make_n_letter_cache() -> None:
    max_n = 3
    locations = ZONES.map_names
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

N_LETTER_CACHE: dict = load_pickle(N_LETTER_CACHE_PATH, make_n_letter_cache)


def make_ss_search() -> None:
    searcher = SubstringSearcher(ZONES.map_names)
    with open(SS_SEARCH_CACHE_PATH, 'wb') as f:
        pickle.dump(searcher, f)

SS_SEARCHER: SubstringSearcher = load_pickle(SS_SEARCH_CACHE_PATH, make_ss_search)



if __name__ == "__main__":
    pass
    # make_zones_pickle()
    # make_portals_edge_pickle()
    # make_n_letter_cache()
    # make_ss_search()


