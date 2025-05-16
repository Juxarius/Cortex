from pydantic_mongo import AbstractRepository, PydanticObjectId
from pydantic import BaseModel, field_validator
from typing import Optional
import datetime as dt
from enum import Enum
from bisect import bisect_left

class SubstringSearcher:
    def __init__(self, string_list: list[str]) -> None:
        self.strings = list(string_list)
        # Build a suffix array (sorted list of all suffixes)
        self.suffixes = []
        for idx, s in enumerate(string_list):
            for word in s.replace('-', ' ').lower().split():
                for i in range(len(word)):
                    self.suffixes.append((word[i:], idx))
        self.suffixes.sort()
    
    def get(self, query: str) -> list[str]:
        query = query.lower()
        # Binary search to find the first matching suffix
        left = bisect_left(self.suffixes, (query, 0))
        results = set()
        # Collect all strings that have this prefix in their suffix
        for i in range(left, len(self.suffixes)):
            if not self.suffixes[i][0].startswith(query):
                break
            results.add(self.strings[self.suffixes[i][1]])
        return list(results)

class ReminderStatus(str, Enum):
    UNPINGED = "unpinged"
    PINGED = "pinged"

class Reminder(BaseModel):
    id: Optional[PydanticObjectId] = None
    objective: str
    location: str
    time_unlocked: dt.datetime
    submitter: str
    time_submitted: dt.datetime
    pingChannelId: int
    roleMention: str
    time_to_ping: dt.datetime

    @field_validator("time_unlocked")
    def unlock_timezone(cls, v: dt.datetime) -> dt.datetime:
        return v.replace(tzinfo=dt.timezone.utc)
    
    @field_validator("time_submitted")
    def submit_timezone(cls, v: dt.datetime) -> dt.datetime:
        return v.replace(tzinfo=dt.timezone.utc)
    
    @field_validator("time_to_ping")
    def ping_timezone(cls, v: dt.datetime) -> dt.datetime:
        return v.replace(tzinfo=dt.timezone.utc)

class Reminders(AbstractRepository[Reminder]):
    class Meta:
        collection_name = "reminders"

class Portal(BaseModel):
    id: Optional[PydanticObjectId] = None
    from_map: str
    to_map: str
    from_map_id: str
    to_map_id: str
    time_expire: dt.datetime
    submitter: str
    time_submitted: dt.datetime

    @field_validator("time_expire")
    def expire_timezone(cls, v: dt.datetime) -> dt.datetime:
        return v.replace(tzinfo=dt.timezone.utc)
    
    @field_validator("time_submitted")
    def submit_timezone(cls, v: dt.datetime) -> dt.datetime:
        return v.replace(tzinfo=dt.timezone.utc)

class Portals(AbstractRepository[Portal]):
    class Meta:
        collection_name = "portals"
    
    def remove_expired(self):
        return super().get_collection().delete_many({"time_expire": {"$lt": dt.datetime.now().replace(tzinfo=dt.timezone.utc)}})

    def get_all(self):
        self.remove_expired()
        return self.find_by({})

if __name__ == '__main__':
    from main import PORTALS
    from utils import MAP_NAME2ID
    p1 = ["Shaleheath Steep", "Qiient-Al-Nusom"]
    p2 = ["Qiient-Al-Nusom", "Fort Sterling"]
    pp = PORTALS.get_all()
    for p in [p1, p2]:
        PORTALS.save(Portal(
            from_map=p[0], 
            to_map=p[1], 
            from_map_id=MAP_NAME2ID[p[0]], 
            to_map_id=MAP_NAME2ID[p[1]], 
            time_expire=dt.datetime.now()+dt.timedelta(days=1), 
            submitter="test", 
            time_submitted=dt.datetime.now()
        ))
