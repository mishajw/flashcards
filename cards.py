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
from pydantic import BaseModel


class Card(BaseModel):
    id: str
    md: str
    path: Path
    headings: list[str]


def read_cards(root_dir: Path) -> list[Card]:
    card_mds: dict[str, Card] = {}
    skip_ids: list[str] = []

    for path in root_dir.rglob("*.md"):
        md = path.read_text()
        headings: list[str] = []
        should_store_line = True
        for line in md.split("\n"):
            if heading_match := re.match(r"^(#+) (.*)", line):
                heading_number = len(heading_match[1])
                assert heading_number > 1, heading_match
                heading_number -= 2
                heading = heading_match[2].strip()
                assert heading not in card_mds, (path, heading_match)
                assert len(headings) >= heading_number, (headings, heading_number)
                headings = [*headings[:heading_number], heading]

            elif skip_match := re.match(
                r"^\s*<!--\s*flashcards:\s*skip\s*-->\s*$", line
            ):
                id = headings[-1] if headings else path.stem
                skip_ids.append(id)

            elif line.startswith("---"):
                should_store_line = not should_store_line

            elif should_store_line:
                id = headings[-1] if headings else path.stem
                if id not in card_mds:
                    card_mds[id] = Card(id=id, md="", path=path, headings=headings)
                card_mds[id].md += line + "\n"

    return [
        card_md
        for id, card_md in card_mds.items()
        if id not in skip_ids and card_md.md.strip() != ""
    ]
