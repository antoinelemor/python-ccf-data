"""Embedded codebook + helpers for inspecting the 67-category annotation schema."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict, List


def _load_codebook() -> Dict[str, Any]:
    """Load the bundled codebook.json."""
    with resources.files('ccf_data').joinpath('codebook.json').open('r') as f:
        return json.load(f)


CODEBOOK: Dict[str, Any] = _load_codebook()


# ---------------------------------------------------------------------------
# Convenient flat lists
# ---------------------------------------------------------------------------

FRAME_NAMES: List[str] = list(CODEBOOK['frames'].keys())
FRAME_COLUMNS: List[str] = [v['col'] for v in CODEBOOK['frames'].values()]

ALL_FRAME_SUBCATEGORIES: List[str] = [
    sub for subs in CODEBOOK['frame_subcategories'].values() for sub in subs
]
MESSENGERS: List[str] = list(CODEBOOK['messengers'])
EVENTS: List[str] = list(CODEBOOK['events'])
SOLUTIONS: List[str] = list(CODEBOOK['solutions'])
TONES: List[str] = list(CODEBOOK['tone'])
OTHER: List[str] = list(CODEBOOK['other'])

ALL_ANNOTATION_COLUMNS: List[str] = (
    FRAME_COLUMNS + ALL_FRAME_SUBCATEGORIES + MESSENGERS + EVENTS
    + SOLUTIONS + TONES + OTHER
)

MEDIA_OUTLETS: List[str] = list(CODEBOOK['media_outlets'])
LANGUAGES: List[str] = list(CODEBOOK['languages'])


def define(column: str) -> str:
    """Return the operational definition for an annotation column.

    >>> define('eco_neg_impact')
    'Negative effects of climate change on the economy ...'
    """
    defs = CODEBOOK.get('definitions', {})
    if column not in defs:
        raise KeyError(f"Unknown annotation column: {column!r}. "
                       f"See ALL_ANNOTATION_COLUMNS for the full list.")
    return defs[column]


def subcategories_of(frame: str) -> List[str]:
    """Return the subcategory column names for a given frame.

    >>> subcategories_of('economic')
    ['eco_neg_impact', 'eco_pos_impact', 'eco_cost', 'eco_benefit', 'eco_footprint']
    """
    if frame not in CODEBOOK['frame_subcategories']:
        raise KeyError(f"Unknown frame: {frame!r}. Valid frames: {FRAME_NAMES}")
    return list(CODEBOOK['frame_subcategories'][frame])


def codebook_dataframe():
    """Return the full codebook as a tidy pandas DataFrame.

    Columns: column, group, subgroup, definition.
    """
    import pandas as pd
    rows = []
    for fname, meta in CODEBOOK['frames'].items():
        rows.append({
            'column': meta['col'], 'group': 'frame', 'subgroup': fname,
            'definition': CODEBOOK['definitions'].get(meta['col'], ''),
        })
    for fname, subs in CODEBOOK['frame_subcategories'].items():
        for s in subs:
            rows.append({
                'column': s, 'group': 'frame_subcategory', 'subgroup': fname,
                'definition': CODEBOOK['definitions'].get(s, ''),
            })
    for col in CODEBOOK['messengers']:
        rows.append({'column': col, 'group': 'messenger', 'subgroup': '',
                     'definition': CODEBOOK['definitions'].get(col, '')})
    for col in CODEBOOK['events']:
        rows.append({'column': col, 'group': 'event', 'subgroup': '',
                     'definition': CODEBOOK['definitions'].get(col, '')})
    for col in CODEBOOK['solutions']:
        rows.append({'column': col, 'group': 'solution', 'subgroup': '',
                     'definition': CODEBOOK['definitions'].get(col, '')})
    for col in CODEBOOK['tone']:
        rows.append({'column': col, 'group': 'tone', 'subgroup': '',
                     'definition': CODEBOOK['definitions'].get(col, '')})
    for col in CODEBOOK['other']:
        rows.append({'column': col, 'group': 'other', 'subgroup': '',
                     'definition': CODEBOOK['definitions'].get(col, '')})
    return pd.DataFrame(rows)
