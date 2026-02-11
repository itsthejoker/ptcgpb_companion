import sys
import os
from pathlib import Path
from collections.abc import Callable


# Turn off bytecode generation
sys.dont_write_bytecode = True
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

import django

django.setup()

from app.db.models import Card, CardSet
from app.names import C
import httpx

data = httpx.get(
    "https://raw.githubusercontent.com/flibustier/pokemon-tcg-pocket-database/refs/heads/main/dist/cards.json"
).json()
sets = list({i["set"] for i in data})
sets.sort()

# todo: now that we have access to more rarity data without having to do it manually,
#  update the app so that it uses the rarity data from the json file. Will need to
#  make sure to update the card removal / shinedust amounts as well.
rarity = {
    "C": Card.Rarity.COMMON,
    "U": Card.Rarity.UNCOMMON,
    "R": Card.Rarity.RARE,
    "RR": Card.Rarity.DOUBLE_RARE,
    "AR": Card.Rarity.ILLUSTRATION_RARE,
    "SR": Card.Rarity.SUPER_SPECIAL_RARE,
    "SAR": Card.Rarity.SUPER_SPECIAL_RARE,
    "IM": Card.Rarity.IMMERSIVE,
    "UR": Card.Rarity.CROWN_RARE,
    "S": Card.Rarity.ILLUSTRATION_RARE,
    "SSR": Card.Rarity.SUPER_SPECIAL_RARE,
}

for count, s in enumerate(sets):
    if "PROMO" in s:
        sets[count] = s.replace("PROMO", "P")

cards = []
card_set_map = CardSet.set_map()

set2factory: Callable[[CardSet], str] = lambda s_id: s_id.label.lower().replace(" ", "_").replace("-", "_")

for set_id in sets:
    set_cards = [c for c in data if c["set"] == set_id]
    for card in set_cards:
        card_name = card["name"].replace("’", "'")
        cards.append(
            C(
                card_set_map[set_id],
                card["number"],
                card_name,
                rarity[card['rarity']],
            )
        )


def sort_key(card_key: str):
    prefix, number = card_key.rsplit("_", 1)
    try:
        number_value = int(number)
    except ValueError:
        number_value = number
    return prefix, number_value


names_path = Path(__file__).resolve().parent / "app" / "names.py"
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
    card_lines.append(
        f"""    {set2factory(key.set_id)}({key.number}, "{key.name}", {str(key).split('rarity=')[1].strip(')')}),\n"""
    )
card_lines.append("]\n")

updated_lines = names_lines[: start_index + 1] + card_lines + names_lines[end_index + 1 :]
names_path.write_text("".join(updated_lines), encoding="utf-8")
