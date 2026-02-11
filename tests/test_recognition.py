from dataclasses import dataclass
from pathlib import Path
import os
import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from app import names
from app.image_processing import ImageProcessor
from app.names import Dex, Card
from app.db.models import CardSet
from settings import BASE_DIR


@dataclass
class CardImg:
    path: str
    set: CardSet
    slot1: Card
    slot2: Card
    slot3: Card
    slot4: Card
    slot5: Card | None
    slot6: Card | None


d = Dex()
if not hasattr(names, "cards"):
    names.cards = {card.id: card.name for card in d.cards}

TEST_IMAGE_DIR = Path(__file__).resolve().parent / "test_images"
TEMPLATE_DIR = BASE_DIR / "resources" / "card_imgs"

cards_to_test = [
    CardImg("img.png", CardSet.DELUXE_PACK_EX, d['A4b_249'], d['A4b_27'], d['A4b_273'], d['A4b_232'], None, None),
    CardImg("img_1.png", CardSet.DELUXE_PACK_EX, d['A4b_320'], d['A4b_206'], d['A4b_203'], d['A4b_160'], None, None),
    CardImg("img_2.png", CardSet.FANTASTICAL_PARADE, d['B2_71'], d['B2_144'], d['B2_84'], d['B2_111'], d['B2_80'], d['B2_223']),
    CardImg("img_3.png", CardSet.MEGA_RISING, d['B1_42'], d['B1_44'], d['B1_178'], d['B1_161'], d['B1_163'], d["B1_287"]),
    CardImg("img_4.png", CardSet.CRIMSON_BLAZE, d['B1a_28'], d['B1a_17'], d['B1a_28'], d['B1a_18'], d['B1a_85'], None),
    CardImg("charizard.png", CardSet.SHINING_REVELRY, d['A2b_60'], d['A2b_49'], d['A2b_59'], d['A2b_4'], d['A2b_80'], None),
    CardImg("charizard_shiny.png", CardSet.SHINING_REVELRY, d['A2b_45'], d['A2b_23'], d['A2b_34'], d['A2b_37'], d['A2b_108'], None),
    CardImg("wugtrio.png", CardSet.SHINING_REVELRY, d['A2b_37'], d['A2b_1'], d['A2b_81'], d['A2b_50'], d['A2b_49'], None),
    CardImg("wugtrio_shiny.png", CardSet.SHINING_REVELRY, d['A2b_18'], d['A2b_66'], d['A2b_41'], d['A2b_53'], d['A2b_109'], None),
    CardImg("img_5.png", CardSet.EXTRADIMENSIONAL_CRISIS, d['A3a_32'], d['A3a_26'], d['A3a_32'], d['A3a_23'], d['A3a_100'], None),
    CardImg("img_6.png", CardSet.SHINING_REVELRY, d['A2b_66'], d['A2b_6'], d['A2b_64'], d['A2b_41'], d['A2b_57'], None),
    CardImg("img_7.png", CardSet.GENETIC_APEX, d['A1_172'], d['A1_174'], d['A1_179'], d['A1_175'], d['A1_129'], None),
    CardImg("img_8.png", CardSet.FANTASTICAL_PARADE, d['B2_40'], d['B2_38'], d['B2_121'], d['B2_152'], d['B2_138'], None),
]

@pytest.fixture(scope="session")
def processor():
    p = ImageProcessor()
    p.load_card_templates(TEMPLATE_DIR)
    return p


@pytest.mark.parametrize("card_img", cards_to_test, ids=lambda c: c.path)
def test_recognition(processor, card_img):
    image_path = TEST_IMAGE_DIR / card_img.path

    results = processor.process_screenshot(str(image_path))
    empty_flags, _positions = _get_empty_flags(processor, str(image_path))
    cards_by_position = {card.get("position"): card for card in results}

    expected_slots = _get_expected_slots(card_img, len(empty_flags))
    assert len(expected_slots) == len(empty_flags)

    for index, (is_empty, expected_card) in enumerate(
        zip(empty_flags, expected_slots), start=1
    ):
        if expected_card is None:
            assert is_empty, f"Expected empty slot {index} for {card_img.path}"
            assert (
                index not in cards_by_position
            ), f"Unexpected card at slot {index} for {card_img.path}"
            continue

        assert not is_empty, f"Empty slot {index} for {card_img.path}"
        card = cards_by_position.get(index)

        assert card is not None, f"Missing card match for slot {index} for {card_img.path}"

        card_obj = card.get("obj")
        assert (
            card_obj.set_id == expected_card.set_id
        ), f"Card {expected_card.id} set mismatch: expected {expected_card.set_id}, got {card_obj.set_id} for {card_img.path}"

        assert (
            card_obj.id == str(expected_card.id)
        ), f"Card {expected_card.id} misidentified as {card_obj.id} for {card_img.path}"


def _get_expected_slots(card_img: CardImg, slot_count: int) -> list[Card | None]:
    slots = [
        card_img.slot1,
        card_img.slot2,
        card_img.slot3,
        card_img.slot4,
        card_img.slot5,
        card_img.slot6,
    ]
    return slots[:slot_count]


def _get_empty_flags(processor: ImageProcessor, image_path: str):
    screenshot = processor._preprocess_screenshot(image_path)
    if screenshot is None:
        raise ValueError("Failed to preprocess screenshot.")

    positions = processor._detect_card_positions(screenshot)
    if not positions:
        raise ValueError("No card positions detected in screenshot.")

    empty_flags = [
        processor._is_empty_card_region(screenshot[y : y + h, x : x + w])
        for x, y, w, h in positions
    ]

    return empty_flags, positions
