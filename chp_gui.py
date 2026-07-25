#!/usr/bin/env python3
"""MARK desktop launcher with product-specific header branding."""
from __future__ import annotations

import sys
from tkinter import ttk

try:
    from mark_app import MarkApp
except ImportError as exc:
    raise SystemExit(
        "MARK dashboard modules are incomplete. Run git pull again after the current update completes. "
        f"Missing dependency: {exc}"
    )


class BrandedMarkApp(MarkApp):
    """Use the MARK acronym expansion directly beneath the product name."""

    def _build_header(self, root: ttk.Frame) -> None:
        header = ttk.Frame(root)
        header.pack(fill="x")

        brand = ttk.Frame(header)
        brand.pack(side="left", fill="x", expand=True)
        self._load_logo(brand)

        words = ttk.Frame(brand)
        words.pack(side="left", anchor="center")
        ttk.Label(words, text="MARK", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            words,
            text="Map-Aware Roadway Knowledge",
            style="Subtitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            words,
            text="Real-time CHP incident monitoring and map-aware notifications.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        cards = ttk.Frame(header)
        cards.pack(side="right")
        self.status_card_value = self._card(cards, "STATUS", self.status)
        self._card(cards, "LAST POLL", self.last_poll)
        self._card(cards, "LATEST SUMMARY", self.latest_summary, width=28)


def main() -> int:
    BrandedMarkApp().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
