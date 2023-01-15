import dataclasses
import datetime
import pathlib
from typing import Tuple

CardId = Tuple[str, ...]


@dataclasses.dataclass
class Card:
    id: CardId
    card_stats: "CardStats"
    root_dir: pathlib.Path
    md: str

    def due_date(self) -> datetime.date:
        return max(self.card_stats.next_revision.date(), datetime.date.today())


@dataclasses.dataclass
class CardMd:
    id: CardId
    md: str


@dataclasses.dataclass
class CardStats:
    next_revision: datetime.datetime
    num_revisions: int
    num_failures: int
    last_interval_days: int
    e_factor: float
