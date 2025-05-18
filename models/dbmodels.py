from pydantic_mongo import AbstractRepository, PydanticObjectId
from pydantic import BaseModel, field_validator
from typing import Optional
import datetime as dt

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
    time_expire: dt.datetime
    submitter: str
    time_submitted: dt.datetime

    @field_validator("time_expire")
    def expire_timezone(cls, v: dt.datetime) -> dt.datetime:
        return v.replace(tzinfo=dt.timezone.utc)
    
    @field_validator("time_submitted")
    def submit_timezone(cls, v: dt.datetime) -> dt.datetime:
        return v.replace(tzinfo=dt.timezone.utc)
    
    def __str__(self):
        return f"{self.from_map} -> {self.to_map} (until {self.time_expire.strftime('%H%M %d/%m/%y')})"

class Portals(AbstractRepository[Portal]):
    def __init__(self, database, logger=None):
        self.logger = logger
        super().__init__(database)
    class Meta:
        collection_name = "portals"
    
    def remove_expired(self):
        q = {"time_expire": {"$lt": dt.datetime.now().replace(tzinfo=dt.timezone.utc)}}
        for expired_portal in self.find_by(q):
            self.logger and self.logger.info(f"Removing expired portal: {expired_portal}")
        return super().get_collection().delete_many({"time_expire": {"$lt": dt.datetime.now().replace(tzinfo=dt.timezone.utc)}})

    def get_all(self):
        self.remove_expired()
        return self.find_by({})
    
    def find_portal(self, map1: str, map2: str) -> Portal:
        forward = list(self.find_by({"from_map": map1, "to_map": map2}))
        if forward: return forward[0]
        backward = list(self.find_by({"from_map": map2, "to_map": map1}))
        if backward: return backward[0]
        return None

if __name__ == '__main__':
    from main import PORTALS
    from utils import MAP_NAME2ID
    print(PORTALS.find_portal("Qiient-Al-Nusom", "Whitebank Descent"))
    print(PORTALS.find_portal("Whitebank Descent", "Fort Sterling Portal"))
    print(PORTALS.find_portal("Lymhurst", "Fort Sterling"))
    # p1 = ["Shaleheath Steep", "Qiient-Al-Nusom"]
    # p2 = ["Qiient-Al-Nusom", "Fort Sterling"]
    # pp = PORTALS.get_all()
    # for p in [p1, p2]:
    #     PORTALS.save(Portal(
    #         from_map=p[0], 
    #         to_map=p[1], 
    #         time_expire=dt.datetime.now()+dt.timedelta(days=1), 
    #         submitter="test", 
    #         time_submitted=dt.datetime.now()
    #     ))
