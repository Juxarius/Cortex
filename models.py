from pydantic_mongo import AbstractRepository, PydanticObjectId
from pydantic import BaseModel, field_validator
from typing import Optional
import datetime as dt
from enum import Enum

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

if __name__ == '__main__':
    from main import PORTALS
    from utils import MAP_NAME2ID
    p1 = ["Shaleheath Steep", "Qiient-Al-Nusom"]
    p2 = ["Qiient-Al-Nusom", "Fort Sterling"]
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
