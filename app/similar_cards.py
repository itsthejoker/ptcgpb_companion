"""
Similar cards disambiguation system.

Some cards look nearly identical to one or more other cards (different rarities,
holo/foil variants, alternate arts, etc.) and the standard low-resolution
matching pipeline frequently confuses them.

When the standard matcher produces a result whose `"<set>_<card>"` identifier
appears in `SIMILAR_CARDS`, `ImageProcessor.process_screenshot` performs
an additional high-quality rescan limited to the listed candidates, then picks
the most accurate one.

The mapping format is::

    {
        "<set>_<card>": ["<set>_<candidate1>", "<set>_<candidate2>", ...],
        ...
    }

Each candidate identifier MUST include the set prefix, exactly matching the
`<set>_<card_name>` used by the image processor's template database.

The list of candidates should always include the key itself, so that the
high-quality rescan is allowed to keep the original match if it is in fact the
best one.
"""

from typing import Dict, List


SIMILAR_CARDS: Dict[str, List[str]] = {
    "A2b_99": ["A2b_99", "A2b_100"],  # shiny charmander
    "A2b_100": ["A2b_99", "A2b_100"],  # shiny charmeleon
    "B2a_120": ["B2a_120", "B2a_121"],  # shiny pawmo
    "B2a_121": ["B2a_120", "B2a_121"],  # shiny pawmot
    "B2b_93": ["B2b_93", "B2b_91"],  # shiny ponyta
    "B2b_91": ["B2b_93", "B2b_91"],  # shiny charmander
}
