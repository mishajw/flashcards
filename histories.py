import datetime
import pathlib
from typing import Literal

from pydantic import BaseModel

CardEventType = Literal["again", "decrease", "same", "increase"]


class CardEvent(BaseModel):
    time: datetime.datetime
    type: CardEventType


class CardHistory(BaseModel):
    id: str
    events: list[CardEvent]
    first_seen: datetime.datetime

    def get_due_date(self) -> datetime.datetime:
        due_date = self._get_due_date(self.events)
        return due_date.replace(hour=0, minute=0, second=0, microsecond=0)

    def get_interval(self) -> datetime.timedelta:
        days = 1
        for event in self.events:
            if event.type in ["again", "same"]:
                pass
            elif event.type == "decrease":
                days /= 2
                days = max(1, days)
            elif event.type == "increase":
                days *= 2
                days = min(365, days)
            else:
                raise ValueError(event.type)
        return datetime.timedelta(days=days)

    def done_today(self) -> bool:
        today = datetime.date.today()
        for event in reversed(self.events):
            if event.time.date() == today:
                return event.type != "again"
        return False

    def _get_due_date(self, events: list[CardEvent]) -> datetime.datetime:
        if len(events) == 0:
            return self.first_seen
        if events[-1].type == "again":
            return self._get_due_date(events[:-1])
        interval = self.get_interval()
        return events[-1].time + interval
