from pydantic_mongo import AbstractRepository, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import MongoClient
from typing import Optional, List, Self
from datetime import datetime, timedelta
from enum import Enum

class ReminderStatus(str, Enum):
    UNPINGED = "unpinged"
    PINGED = "pinged"

class Reminder(BaseModel):
    id: Optional[PydanticObjectId] = None
    objective: str
    location: str
    time_unlocked: datetime
    submitter: str
    time_submitted: datetime

class Reminders(AbstractRepository[Reminder]):
    class Meta:
        collection_name = "reminders"
