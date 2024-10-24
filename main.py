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
from pydantic.main import BaseModel

from cards import Card, read_cards
from histories import CardEvent, CardEventType, CardHistory

DATETIME_FMT = "%Y/%m/%d %H:%M:%S"
STATE_FILE = ".flashcards.jsonl"
MD_IMAGE_REGEX = re.compile(r"!\[(.*)\]\((.*)\)")
IMAGE_ROOT_DIR = pathlib.Path("../site/html")


def main():
    password = os.environ.get("FLASHCARDS_PASSWORD", None)
    if password is not None and st.text_input("Password", type="password") != password:
        st.write("Incorrect password")
        return

    _, root_dir = sys.argv
    root_dir = pathlib.Path(sys.argv[1])
    assert root_dir.is_dir(), root_dir

    (root_dir / STATE_FILE).touch()
    cards: list[Card] = read_cards(root_dir)
    histories: dict[str, CardHistory] = {
        (h := CardHistory.parse_raw(line)).id: h
        for line in (root_dir / STATE_FILE).read_text().splitlines()
    }

    n_new_cards = 0
    for card_md in cards:
        if card_md.id not in histories:
            histories[card_md.id] = CardHistory(
                id=card_md.id,
                events=[],
                first_seen=datetime.datetime.now(),
            )
            n_new_cards += 1
    if n_new_cards > 0:
        st.write(f"Added {n_new_cards} new cards")

    mode = st.selectbox("Mode", options=["Revise", "Stats", "Git", "Browse"])

    if mode == "Revise":
        due_dates = {
            card_md.id: histories[card_md.id].get_due_date() for card_md in cards
        }
        overdue_cards = [
            card_md
            for card_md in cards
            if due_dates[card_md.id] < datetime.datetime.now()
        ]
        if not overdue_cards:
            st.write("No cards!")
            return
        card_last_modified: dict[str, datetime.datetime | None] = {
            card_md.id: histories[card_md.id].events[-1].time
            if histories[card_md.id].events
            else None
            for card_md in cards
        }
        overdue_cards_sorted = _sort_cards(overdue_cards, histories)
        card = overdue_cards_sorted[0]

        due_column, *columns = st.columns([1] * (5))
        with due_column:
            this_morning = datetime.datetime.combine(
                datetime.date.today(),
                datetime.datetime.min.time(),
            )
            num_cards_revised_today = len(
                [card for card in cards if histories[card.id].done_today()]
            )
            st.write(f"**{len(overdue_cards)} due, {num_cards_revised_today} done**")

        labels: dict[CardEventType, str] = {
            "again": "↻",
            "decrease": "/2",
            "same": "=",
            "increase": "*2",
        }
        event_type = None
        for (type, label), column in zip(labels.items(), columns):
            with column:
                if st.button(label):
                    event_type = type
        if event_type is not None:
            histories[card.id].events.append(
                CardEvent(
                    time=datetime.datetime.now(),
                    type=event_type,
                )
            )
            with (root_dir / STATE_FILE).open("w") as f:
                for history in histories.values():
                    f.write(history.json() + "\n")
            st.rerun()

        st.write("---")
        _display_card(card, histories[card.id], due_dates[card.id], root_dir)

    if mode == "Stats":
        st.markdown("# Stats")
        st.write(f"Number of cards: {len(cards)}")

        df = pd.DataFrame(
            [
                dict(id=card.id, due_date=histories[card.id].get_due_date())
                for card in cards
            ]
        )
        df = df.groupby("due_date").count()
        fig, ax = plt.subplots(figsize=(8, 4))
        df.plot.bar(ax=ax)
        st.pyplot(fig)

        cards_md = "Due:\n\n"
        for card in cards:
            if histories[card.id].get_due_date().date() == datetime.date.today():
                cards_md += f"- {' / '.join(card.id)}\n"
        st.markdown(cards_md)

    if mode == "Git":
        st.markdown("# Git")
        run_kwargs = {
            "cwd": str(root_dir),
            "text": True,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
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

    if mode == "Browse":
        st.markdown("# Browse")
        selected_card = st.selectbox(
            "Select a card",
            options=cards,
            format_func=lambda card: f"{card.path.relative_to(root_dir)} - {card.id}",
        )
        if selected_card:
            _display_card(
                selected_card,
                histories[selected_card.id],
                histories[selected_card.id].get_due_date(),
                root_dir,
            )


def _display_card(
    card: Card, history: CardHistory, due_date: datetime.datetime, root_dir: Path
):
    with st.expander("Card details"):
        st.write(
            {
                "id": card.id,
                "path": card.path.relative_to(root_dir),
                "due": due_date.strftime(DATETIME_FMT) if due_date else None,
                "interval": history.get_interval(),
                "n_events": len(history.events),
                "n_events_by_type": {
                    event_type: len([e for e in history.events if e.type == event_type])
                    for event_type in ["again", "decrease", "same", "increase"]
                },
                "first_seen": history.first_seen.strftime(DATETIME_FMT),
                "first_event": history.events[0].time.strftime(DATETIME_FMT)
                if history.events
                else None,
                "last_event": history.events[-1].time.strftime(DATETIME_FMT)
                if history.events
                else None,
            }
        )
    for i, title in enumerate(card.headings):
        st.markdown(("#" * (i + 3)) + " " + title)
    if st.button("Show"):
        md = MD_IMAGE_REGEX.sub("", card.md)
        st.markdown(md)
        for alt_text, path in MD_IMAGE_REGEX.findall(card.md):
            # TODO: Clean this up.
            st.image(str(IMAGE_ROOT_DIR / path[1:]), alt_text)


def _sort_cards(cards: list[Card], histories: dict[str, CardHistory]) -> list[Card]:
    fresh_start = datetime.datetime(2024, 10, 25)
    return sorted(
        cards,
        key=lambda card: (
            not (
                histories[card.id].first_seen >= fresh_start
                or card.path.parts[-1] == "nntd.md"
            ),
            hashlib.sha256(
                str(
                    (
                        card.id,
                        histories[card.id].events[-1].time
                        if histories[card.id].events
                        else None,
                    )
                ).encode()
            ).hexdigest(),
        ),
    )


if __name__ == "__main__":
    main()
