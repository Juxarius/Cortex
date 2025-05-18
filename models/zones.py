from logger import error

class Zones:
    # Locations will be stored as [map_name: str, map_id: str, portal_ids: list[str]]
    def __init__(self, locations: list) -> None:
        self.locations = locations
        self.name_map = {name: idx for idx, (name, _, _) in enumerate(locations)}
        self.id_map = {id: idx for idx, (_, id, _) in enumerate(locations)}
        self.portal_map = {p: idx for idx, (_, _, portals) in enumerate(locations) for p in portals}

    @property
    def map_names(self) -> list:
        return [loc[0] for loc in self.locations]
    
    @property
    def map_ids(self) -> list:
        return [loc[1] for loc in self.locations]
    
    @property
    def portal_ids(self) -> list:
        return [p for loc in self.locations for p in loc[2]]

    def get_portal(self, name_or_id: str) -> str:
        if name_or_id in self.name_map:
            loc = self.locations[self.name_map[name_or_id]]
        elif name_or_id in self.id_map:
            loc = self.locations[self.id_map[name_or_id]]
        else:
            error(f'{name_or_id} is not a valid name or mapId')
            raise KeyError(f'{name_or_id} is not a valid name or mapId')
        if not loc[2] and '-' in loc[0]:
            return "ROADS", loc[1]
        return loc[2][0], loc[1]
    
    def get_map_id(self, name_or_portal: str) -> str:
        try:
            if name_or_portal in self.name_map:
                return self.locations[self.name_map[name_or_portal]][1]
            elif name_or_portal in self.portal_map:
                return self.locations[self.portal_map[name_or_portal]][1]
            return None
        except IndexError:
            return None
    
    def get_map_name(self, name_or_portal: str) -> str:
        try:
            if name_or_portal in self.id_map:
                return self.locations[self.id_map[name_or_portal]][0]
            elif name_or_portal in self.portal_map:
                return self.locations[self.portal_map[name_or_portal]][0]
            return None
        except IndexError:
            return None
