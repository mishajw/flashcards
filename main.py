import datetime
import hashlib
import json
import pathlib
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import spaced_repetition
from classes import Card, CardId, CardMd

DATETIME_FMT = "%Y/%m/%d %H:%M:%S"
STATE_FILE = ".flashcards.json"
MD_IMAGE_REGEX = re.compile("!\[(.*)\]\((.*)\)")
IMAGE_ROOT_DIR = pathlib.Path("../site/html")


def main():
    st.title("Flashcards")
    root_dir = st.selectbox("Root", options=sys.argv[1:])
    root_dir = pathlib.Path(root_dir)
    assert root_dir.is_dir()

    card_mds = _read_card_mds(root_dir)
    card_histories = _read_card_stats(root_dir)
    cards = [
        Card(
            id=card_md.id,
            card_stats=card_histories.get(card_md.id, spaced_repetition.default_card_stats()),
            root_dir=root_dir,
            md=card_md.md,
        )
        for card_md in card_mds
    ]

    mode = st.selectbox("Mode", options=["Revise", "Stats"])
    st.write("---")

    if mode == "Revise":
        cards = list(filter(lambda c: c.due_date() == datetime.date.today(), cards))
        if not cards:
            st.write("No cards!")
            return
        card = min(
            cards,
            key=lambda c: hashlib.sha256(str((c.id, c.card_stats)).encode()).hexdigest(),
        )
        st.write(f"**due**={len(cards)}, **file**={card.id[0]}, **root**={root_dir}")

        ratings = ["Failed", "Hard", "OK", "Easy"]
        quality = None
        columns = st.columns([1] * len(ratings))
        for i, (rating, column) in enumerate(zip(ratings, columns)):
            with column:
                if st.button(rating):
                    quality = i
        if quality is not None:
            card_histories[card.id] = spaced_repetition.update_history(card.card_stats, quality)
            _write_card_stats(root_dir, card_histories)
            st.experimental_rerun()

        st.write("---")
        for i, title in enumerate(card.id[1:]):
            st.markdown(("#" * (i + 2)) + " " + title)
        if st.button("Show"):
            md = MD_IMAGE_REGEX.sub("", card.md)
            st.markdown(md)
            for alt_text, path in MD_IMAGE_REGEX.findall(card.md):
                # TODO: Clean this up.
                st.image(str(IMAGE_ROOT_DIR / path[1:]), alt_text)

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


def _read_card_stats(root_dir: pathlib.Path) -> Dict[CardId, spaced_repetition.CardStats]:
    result: Dict[CardId, spaced_repetition.CardStats] = {}
    history_path = root_dir / STATE_FILE
    if history_path.is_file():
        with history_path.open("r") as f:
            card_histories = json.load(f)
        for card_history in card_histories:
            result[tuple(card_history["headings"])] = spaced_repetition.CardStats(
                next_revision=datetime.datetime.strptime(
                    card_history["next_revision"], DATETIME_FMT
                ),
                num_revisions=card_history["num_revisions"],
                num_failures=card_history.get("num_failures", 0),
                last_interval_days=card_history["last_interval_days"],
                e_factor=card_history["e_factor"],
            )
    return result


def _write_card_stats(
    root_dir: pathlib.Path, card_histories: Dict[CardId, spaced_repetition.CardStats]
) -> None:
    result = []
    for card_id in card_histories:
        result.append(
            dict(
                headings=list(card_id),
                next_revision=card_histories[card_id].next_revision.strftime(DATETIME_FMT),
                num_revisions=card_histories[card_id].num_revisions,
                num_failures=card_histories[card_id].num_failures,
                last_interval_days=card_histories[card_id].last_interval_days,
                e_factor=card_histories[card_id].e_factor,
            )
        )
    with (root_dir / STATE_FILE).open("w") as f:
        json.dump(result, f, indent=4)


if __name__ == "__main__":
    main()
