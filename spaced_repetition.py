# Algorithm taken from:
# https://www.supermemo.com/en/archives1990-2015/english/ol/sm2

import dataclasses
import datetime
import math

from classes import CardStats

DEFAULT_E_FACTOR = 2.5


def default_card_stats() -> CardStats:
    return CardStats(
        next_revision=datetime.datetime.combine(
            datetime.date.today(),
            datetime.datetime.min.time(),
        ),
        last_successful_revision=None,
        num_revisions=0,
        num_failures=0,
        last_interval_days=1,
        e_factor=DEFAULT_E_FACTOR,
    )


def update_history(card_stats: CardStats, quality: int) -> CardStats:
    e_factor = _update_e_factor(card_stats.e_factor, quality)
    num_revisions = card_stats.num_revisions + 1 if quality > 0 else card_stats.num_revisions
    num_failures = card_stats.num_failures + 1 if quality == 0 else card_stats.num_failures
    last_interval_days = _update_last_interval_days(
        card_stats.last_interval_days, e_factor, num_revisions
    )
    next_revision = _update_next_revision(last_interval_days, quality)
    last_successful_revision = card_stats.last_successful_revision
    if quality > 0:
        last_successful_revision = datetime.datetime.now()
    return dataclasses.replace(
        card_stats,
        next_revision=next_revision,
        last_successful_revision=last_successful_revision,
        num_revisions=num_revisions,
        num_failures=num_failures,
        last_interval_days=last_interval_days,
        e_factor=e_factor,
    )


def _update_e_factor(e_factor: float, quality: int) -> float:
    assert 0 <= quality <= 3
    # Change [1, 2, 3] to [3, 4, 5].
    if quality > 0:
        quality += 2
    e_factor = e_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    e_factor = min(2.5, e_factor)
    e_factor = max(1.3, e_factor)
    return e_factor


def _update_last_interval_days(last_interval_days: int, e_factor: float, num_revisions: int) -> int:
    if num_revisions == 1:
        return 1
    elif num_revisions == 2:
        return 6
    else:
        return math.ceil(last_interval_days * e_factor)


def _update_next_revision(last_interval_days: int, quality: int) -> datetime.datetime:
    if quality == 0:
        return datetime.datetime.now()
    return datetime.datetime.now() + datetime.timedelta(days=last_interval_days)
