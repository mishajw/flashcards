import datetime
import hashlib
import itertools
import json
import os
import pathlib
import re
import subprocess
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
    password = os.environ.get("FLASHCARDS_PASSWORD", None)
    if password is not None and st.text_input("Password", type="password") != password:
        st.write("Incorrect password")
        return

    cards: List[Card] = []
    root_dirs = list(map(pathlib.Path, sys.argv[1:]))
    for root_dir in root_dirs:
        assert root_dir.is_dir()
        card_mds = _read_card_mds(root_dir)
        card_histories = _read_card_stats(root_dir)
        cards.extend(
            Card(
                id=card_md.id,
                card_stats=card_histories.get(
                    card_md.id, spaced_repetition.default_card_stats()
                ),
                root_dir=root_dir,
                md=card_md.md,
            )
            for card_md in card_mds
        )

    mode = st.selectbox("Mode", options=["Revise", "Stats", "Git"])

    if mode == "Revise":
        revision_cards = list(
            filter(lambda c: c.due_date() == datetime.date.today(), cards)
        )
        if not revision_cards:
            st.write("No cards!")
            return
        card = min(
            revision_cards,
            key=lambda c: hashlib.sha256(
                str((c.id, c.card_stats)).encode()
            ).hexdigest(),
        )

        ratings = ["Failed", "Hard", "OK", "Easy"]
        quality = None
        due_column, *columns = st.columns([1] * (len(ratings) + 1))
        with due_column:
            this_morning = datetime.datetime.combine(
                datetime.date.today(),
                datetime.datetime.min.time(),
            )
            num_cards_revised_today = len(
                [
                    card
                    for card in cards
                    if card.card_stats.last_successful_revision is not None
                    and card.card_stats.last_successful_revision >= this_morning
                ]
            )
            st.write(f"**{len(revision_cards)} due, {num_cards_revised_today} done**")
        for i, (rating, column) in enumerate(zip(ratings, columns)):
            with column:
                if st.button(rating):
                    quality = i
        if quality is not None:
            card.card_stats = spaced_repetition.update_history(card.card_stats, quality)
            _write_card_stats(cards)
            st.experimental_rerun()

        st.write("---")
        st.write(f"`{card.root_dir}` / `{card.id[0]}`")
        for i, title in enumerate(card.id[1:]):
            st.markdown(("#" * (i + 3)) + " " + title)
        if st.button("Show"):
            md = MD_IMAGE_REGEX.sub("", card.md)
            st.markdown(md)
            for alt_text, path in MD_IMAGE_REGEX.findall(card.md):
                # TODO: Clean this up.
                st.image(str(IMAGE_ROOT_DIR / path[1:]), alt_text)

    if mode == "Stats":
        st.markdown("# Stats")
        st.write(f"Number of cards: {len(cards)}")

        df = pd.DataFrame(
            [dict(id=card.id, due_date=card.due_date()) for card in cards]
        )
        df = df.groupby("due_date").count()
        fig, ax = plt.subplots(figsize=(8, 4))
        df.plot.bar(ax=ax)
        st.pyplot(fig)

        cards_md = "Due:\n\n"
        for card in cards:
            if card.due_date() == datetime.date.today():
                cards_md += f"- {' / '.join(card.id)}\n"
        st.markdown(cards_md)

    if mode == "Git":
        st.markdown("# Git")
        root_dir = st.selectbox("Directory", options=root_dirs)
        run_kwargs = {
            'cwd': str(root_dir),
            'text': True,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
        }
        if st.button("Status"):
            st.code(
                subprocess.run(["git", "status"], **run_kwargs).stdout,
            )
        if st.button("Pull"):
            st.code(
                subprocess.run(["git", "pull"], **run_kwargs).stdout,
            )
        if st.button("Push"):
            st.code(
                subprocess.run(
                    [
                        "git",
                        "commit",
                        "-a",
                        "-m",
                        f"Streamlit autocommit: {datetime.datetime.now()}",
                    ],
                    **run_kwargs,
                ).stdout,
            )
            st.code(
                subprocess.run(["git", "push"], **run_kwargs).stdout,
            )


def _read_card_mds(root_dir: Path) -> List[CardMd]:
    md_paths = list(root_dir.rglob("*.md"))
    result: Dict[CardId, str] = defaultdict(str)
    skip_card_ids: List[Tuple[str, ...]] = []
    for md_path in md_paths:
        md = md_path.read_text()
        headings: Tuple[str, ...] = (str(md_path.relative_to(root_dir)),)
        should_store_line = True
        for line in md.split("\n"):
            heading_match = re.match("^(#+) (.*)", line)
            skip_match = re.match(r"^\s*<!--\s*flashcards:\s*skip\s*-->\s*$", line)
            if heading_match:
                heading_number = max(len(heading_match[1]) - 1, 1)
                heading = heading_match[2].strip()
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


def _read_card_stats(
    root_dir: pathlib.Path,
) -> Dict[CardId, spaced_repetition.CardStats]:
    result: Dict[CardId, spaced_repetition.CardStats] = {}
    history_path = root_dir / STATE_FILE
    if history_path.is_file():
        with history_path.open("r") as f:
            card_histories = json.load(f)
        for card_history in card_histories:
            headings = tuple(heading.strip() for heading in card_history["headings"])
            result[headings] = spaced_repetition.CardStats(
                next_revision=datetime.datetime.strptime(
                    card_history["next_revision"], DATETIME_FMT
                ),
                last_successful_revision=(
                    datetime.datetime.strptime(
                        card_history["last_successful_revision"], DATETIME_FMT
                    )
                    if card_history.get("last_successful_revision", None) is not None
                    else None
                ),
                num_revisions=card_history["num_revisions"],
                num_failures=card_history.get("num_failures", 0),
                last_interval_days=card_history["last_interval_days"],
                e_factor=card_history["e_factor"],
                first_seen=datetime.datetime.strptime(
                    card_history.get("first_seen", card_history["next_revision"]),
                    DATETIME_FMT
                ),
            )
    return result


def _write_card_stats(cards: List[Card]) -> None:
    cards = sorted(cards, key=lambda card: card.id)
    cards = sorted(cards, key=lambda card: card.root_dir)
    cards_grouped = itertools.groupby(cards, key=lambda card: card.root_dir)
    for root_dir, card_group in cards_grouped:
        result = []
        for card in card_group:
            assert card.root_dir == root_dir
            result.append(
                dict(
                    headings=list(card.id),
                    next_revision=card.card_stats.next_revision.strftime(DATETIME_FMT),
                    last_successful_revision=(
                        card.card_stats.last_successful_revision.strftime(DATETIME_FMT)
                        if card.card_stats.last_successful_revision is not None
                        else None
                    ),
                    num_revisions=card.card_stats.num_revisions,
                    num_failures=card.card_stats.num_failures,
                    last_interval_days=card.card_stats.last_interval_days,
                    e_factor=card.card_stats.e_factor,
                    first_seen=card.card_stats.first_seen.strftime(DATETIME_FMT),
                )
            )
        with (root_dir / STATE_FILE).open("w") as f:
            json.dump(result, f, indent=4)


if __name__ == "__main__":
    main()
