import datetime
import pathlib
from typing import Optional
from pydantic import BaseModel

CardId = tuple[str, ...]


class Card(BaseModel):
    id: CardId
    card_stats: "CardStats"
    root_dir: pathlib.Path
    md: str

    def due_date(self) -> datetime.date:
        if self.card_stats.next_revision is None:
            return datetime.date.today()
        return max(self.card_stats.next_revision.date(), datetime.date.today())


class CardMd(BaseModel):
    id: CardId
    md: str


class CardStats(BaseModel):
    next_revision: datetime.datetime
    last_successful_revision: datetime.datetime | None
    num_revisions: int
    num_failures: int
    last_interval_days: int
    e_factor: float
    first_seen: datetime.datetime
