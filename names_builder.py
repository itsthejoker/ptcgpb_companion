import argparse
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

# Turn off bytecode generation
sys.dont_write_bytecode = True
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

import django

django.setup()

import httpx
from bs4 import BeautifulSoup

from app.db.models import Card, CardSet
from app.names import C

BASE_URL = "https://pocket.limitlesstcg.com/cards"
REPO_ROOT = Path(__file__).resolve().parent
SNAPSHOT_DIR = REPO_ROOT / "limitless"
SNAPSHOT_INDEX = SNAPSHOT_DIR / "example_cards.html"
SNAPSHOT_SET = SNAPSHOT_DIR / "example_set_page.html"
SNAPSHOT_SET_CODE = "B3a"

RARITY_MAP: dict[str, Card.Rarity] = {
    "◊": Card.Rarity.COMMON,
    "◊◊": Card.Rarity.UNCOMMON,
    "◊◊◊": Card.Rarity.RARE,
    "◊◊◊◊": Card.Rarity.DOUBLE_RARE,
    "☆": Card.Rarity.ILLUSTRATION_RARE,
    "☆☆": Card.Rarity.SUPER_SPECIAL_RARE,
    "☆☆☆": Card.Rarity.IMMERSIVE,
    "Crown Rare": Card.Rarity.CROWN_RARE,
}

# Rarities to silently skip (no warning printed).
SKIP_RARITIES: set[str] = {"Promo"}


def fetch(url: str) -> str:
    response = httpx.get(url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    return response.text


def parse_set_codes(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="sets-table")
    if table is None:
        raise RuntimeError("Could not find sets-table on index page")

    codes: list[str] = []
    seen: set[str] = set()
    for img in table.find_all("img", class_="set"):
        code = img.get("alt", "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def parse_set_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="card-list")
    if table is None:
        raise RuntimeError("Could not find card-list table on set page")

    cards: list[dict] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 5:
            continue
        number_text = cells[1].get_text(strip=True)
        name_text = cells[2].get_text(strip=True).replace("’", "'")
        rarity_text = cells[4].get_text(strip=True)
        try:
            number = int(number_text)
        except ValueError:
            print(f"  ! skipping non-integer card number {number_text!r}")
            continue
        cards.append(
            {"number": number, "name": name_text, "rarity_symbol": rarity_text}
        )
    return cards


def load_snapshot(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_cards(use_snapshot: bool) -> list[C]:
    card_set_map = CardSet.set_map()

    if use_snapshot:
        index_html = load_snapshot(SNAPSHOT_INDEX)
    else:
        index_html = fetch(f"{BASE_URL}/")

    set_codes = parse_set_codes(index_html)
    print(f"Found {len(set_codes)} set codes: {set_codes}")

    if use_snapshot:
        if SNAPSHOT_SET_CODE not in set_codes:
            print(
                f"  ! snapshot set {SNAPSHOT_SET_CODE} not in index; "
                "skipping all sets"
            )
            return []
        set_codes = [SNAPSHOT_SET_CODE]
        print(f"Snapshot mode: limiting to {set_codes}")

    cards: list[C] = []
    for set_code in set_codes:
        if set_code not in card_set_map:
            print(f"  ! unknown set code {set_code!r}; add to CardSet enum to include")
            continue

        if use_snapshot:
            set_html = load_snapshot(SNAPSHOT_SET)
        else:
            set_html = fetch(f"{BASE_URL}/{set_code}?display=list")
            time.sleep(0.5)

        raw_cards = parse_set_cards(set_html)
        print(f"  {set_code}: {len(raw_cards)} cards")

        for raw in raw_cards:
            symbol = raw["rarity_symbol"]
            if symbol in SKIP_RARITIES:
                continue
            rarity = RARITY_MAP.get(symbol)
            if rarity is None:
                print(
                    f"  ! {set_code} #{raw['number']} {raw['name']!r}: "
                    f"unknown rarity {symbol!r}; skipping"
                )
                continue
            cards.append(
                C(card_set_map[set_code], raw["number"], raw["name"], rarity)
            )

    return cards


def write_names(cards: list[C]) -> None:
    set2factory: Callable[[CardSet], str] = lambda s_id: (
        s_id.label.lower().replace(" ", "_").replace("-", "_")
    )

    names_path = REPO_ROOT / "app" / "names.py"
    names_lines = names_path.read_text(encoding="utf-8").splitlines(keepends=True)

    start_index = None
    end_index = None
    for index, line in enumerate(names_lines):
        if line.lstrip().startswith("_cards = ["):
            start_index = index
            continue
        if start_index is not None and line.strip() == "]":
            end_index = index
            break

    if start_index is None or end_index is None:
        raise RuntimeError("Unable to locate cards list in app/names.py")

    card_lines = []
    for key in cards:
        rarity_literal = str(key).split("rarity=")[1].rstrip(")")
        card_lines.append(
            f'    {set2factory(key.set_id)}({key.number}, "{key.name}", {rarity_literal}),\n'
        )
    card_lines.append("]\n")

    updated_lines = (
        names_lines[: start_index + 1] + card_lines + names_lines[end_index + 1 :]
    )
    names_path.write_text("".join(updated_lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help=(
            "read from local HTML snapshots in limitless/ instead of hitting the "
            "network; limits to set " + SNAPSHOT_SET_CODE
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="parse and report but do not modify app/names.py",
    )
    args = parser.parse_args()

    cards = build_cards(use_snapshot=args.snapshot)
    print(f"Total cards: {len(cards)}")

    if args.dry_run:
        print("Dry run; not writing app/names.py")
        return

    write_names(cards)
    print(f"Wrote {len(cards)} cards to app/names.py")


if __name__ == "__main__":
    main()
