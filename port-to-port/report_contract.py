"""Shared lexical contract for the port-to-port finished report."""

from __future__ import annotations

import re

from synthetic_world import MEGA_PORT_SECTOR

MEGA_PORT_NAME = "MEGA SSS"
OUTCOME_MARKERS = (
    "profit",
    "net change",
    "net result",
    "net on-hand",
    "overall gain",
    "overall loss",
    "overall net",
)


def is_coherent_finished_report(message: str) -> bool:
    lowered = message.lower()
    outcome_like = any(token in lowered for token in OUTCOME_MARKERS)
    recharge_like = (
        "recharg" in lowered
        or "refill" in lowered
        or (
            "warp" in lowered
            and any(
                phrase in lowered
                for phrase in (
                    "topped off",
                    "topped up",
                    "top off",
                    "top up",
                    "filled up",
                    "fill up",
                    "full warp",
                    "restored",
                )
            )
        )
    )
    return (
        outcome_like
        and ("trade" in lowered or "traded" in lowered or "ports" in lowered)
        and recharge_like
        and (
            "mega" in lowered
            or MEGA_PORT_NAME.lower() in lowered
            or re.search(rf"\b{MEGA_PORT_SECTOR}\b", lowered) is not None
        )
    )
