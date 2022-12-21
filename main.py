from collections import defaultdict
import dataclasses
import datetime
import hashlib
from pathlib import Path
import pathlib
from typing import Dict, List, Tuple
import re
import matplotlib.pyplot as plt

import card_histories as card_histories_
from common import CardId
import spaced_repetition
import streamlit as st
import pandas as pd

ROOT_DIR = Path("/home/mishaw/src/site/md/notes")


@dataclasses.dataclass
class Card:
    id: CardId
    spaced_repetition: spaced_repetition.SpacedRepetition
    root_dir: pathlib.Path
    md: str

    def due_date(self) -> datetime.date:
        return max(self.spaced_repetition.next_revision.date(), datetime.date.today())


@dataclasses.dataclass
class CardMd:
    id: CardId
    md: str


def main():
    st.title("Flashcards")

    card_mds = _read_card_mds(ROOT_DIR)
    card_histories = card_histories_.read(ROOT_DIR)
    cards = [
        Card(
            id=card_md.id,
            spaced_repetition=card_histories.get(
                card_md.id, spaced_repetition.SpacedRepetition.default()
            ),
            root_dir=ROOT_DIR,
            md=card_md.md,
        )
        for card_md in card_mds
    ]

    mode = st.selectbox("Mode", options=["Revise", "Stats"])
    st.write("---")

    if mode == "Revise":
        cards = list(filter(lambda c: c.due_date() == datetime.date.today(), cards))
        card = min(
            cards,
            key=lambda c: hashlib.sha256(
                str((c.id, c.spaced_repetition.num_revisions, 2)).encode()
            ).hexdigest(),
        )
        st.write(f"**due**={len(cards)}, **file**={card.id[0]}, **root**={ROOT_DIR}")

        ratings = ["Failed", "Hard", "OK", "Easy"]
        quality = None
        columns = st.columns([1] * len(ratings))
        for i, (rating, column) in enumerate(zip(ratings, columns)):
            with column:
                if st.button(rating):
                    quality = i
        if quality is not None:
            card_histories[card.id] = spaced_repetition.update_history(
                card.spaced_repetition, quality
            )
            card_histories_.write(ROOT_DIR, card_histories)
            st.experimental_rerun()

        st.write("---")
        for i, title in enumerate(card.id[1:]):
            st.markdown(("#" * (i + 2)) + " " + title)
        if st.button("Show"):
            st.markdown(card.md)
            quality = None

    if mode == "Stats":
        st.markdown("# Stats")
        st.write(f"Number of cards: {len(cards)}")

        df = pd.DataFrame([dict(id=card.id, due_date=card.due_date()) for card in cards])
        df = df.groupby("due_date").count()
        fig, ax = plt.subplots(figsize=(8, 4))
        df.plot.bar(ax=ax)
        st.pyplot(fig)


def _read_card_mds(root_dir: Path) -> List[CardMd]:
    md_paths = list(root_dir.rglob("*.md"))
    result: Dict[CardId, str] = defaultdict(str)
    skip_card_ids: List[Tuple[str, ...]] = []
    for md_path in md_paths:
        md = md_path.read_text()
        headings: Tuple[str, ...] = (md_path.name,)
        should_store_line = True
        for line in md.split("\n"):
            heading_match = re.match("^(#+) (.*)", line)
            skip_match = re.match(r"^\s*<!--\s*flashcards:\s*skip\s*-->\s*$", line)
            if heading_match:
                heading_number = max(len(heading_match[1]) - 1, 1)
                heading = heading_match[2]
                assert len(headings) >= heading_number
                headings = (*headings[:heading_number], heading)
            elif skip_match:
                skip_card_ids.append(headings)
            elif line.startswith("---"):
                should_store_line = not should_store_line
            elif should_store_line:
                result[headings] += line + "\n"
    card_ids = list(result.keys())
    for card_id in card_ids:
        if result[card_id].strip() == "" or card_id in skip_card_ids:
            del result[card_id]
    return [CardMd(card_id, md) for card_id, md in result.items()]


if __name__ == "__main__":
    main()
