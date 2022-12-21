from pathlib import Path
import pathlib
from typing import Dict, List
import dataclasses
import datetime
import json

from common import CardId
import spaced_repetition

DATETIME_FMT = "%Y/%m/%d %H:%M:%S"


def read(root_dir: pathlib.Path) -> Dict[CardId, spaced_repetition.SpacedRepetition]:
    result: Dict[CardId, spaced_repetition.SpacedRepetition] = {}
    history_path = root_dir / ".flashcards.json"
    if history_path.is_file():
        with history_path.open("r") as f:
            card_histories = json.load(f)
        for card_history in card_histories:
            result[tuple(card_history["headings"])] = spaced_repetition.SpacedRepetition(
                next_revision=datetime.datetime.strptime(
                    card_history["next_revision"], DATETIME_FMT
                ),
                num_revisions=card_history["num_revisions"],
                last_interval_days=card_history["last_interval_days"],
                e_factor=card_history["e_factor"],
            )
    return result


def write(
    root_dir: pathlib.Path, card_histories: Dict[CardId, spaced_repetition.SpacedRepetition]
) -> None:
    result = []
    for card_id in card_histories:
        result.append(
            dict(
                headings=list(card_id),
                next_revision=card_histories[card_id].next_revision.strftime(DATETIME_FMT),
                num_revisions=card_histories[card_id].num_revisions,
                last_interval_days=card_histories[card_id].last_interval_days,
                e_factor=card_histories[card_id].e_factor,
            )
        )
    with (root_dir / ".flashcards.json").open("w") as f:
        json.dump(result, f, indent=4)
