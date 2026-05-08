"""Tests for the embedded codebook + schema helpers (no network)."""

from ccf_data import (
    ALL_ANNOTATION_COLUMNS, FRAME_COLUMNS, FRAME_NAMES, MEDIA_OUTLETS,
    define, subcategories_of, codebook_dataframe,
)


def test_codebook_has_65_operational_categories():
    # 67 categories in the codebook total; 2 are documented but excluded
    # from analysis (health_pos_impact, health_footprint — insufficient
    # training data). ALL_ANNOTATION_COLUMNS holds the operational set.
    # 8 frames + 30 subcategories + 10 messengers + 9 events
    # + 3 solutions + 3 tones + 2 other == 65.
    assert len(ALL_ANNOTATION_COLUMNS) == 65


def test_frame_names_are_eight():
    assert len(FRAME_NAMES) == 8
    assert 'economic' in FRAME_NAMES and 'cultural' in FRAME_NAMES


def test_frame_columns_match_frame_names():
    assert all(c.endswith('_frame') for c in FRAME_COLUMNS)


def test_define_known_column():
    text = define('eco_neg_impact')
    assert 'economy' in text.lower()


def test_define_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        define('not_a_real_column')


def test_subcategories_of_economic():
    subs = subcategories_of('economic')
    assert 'eco_neg_impact' in subs
    assert len(subs) == 5


def test_media_outlets_count():
    assert len(MEDIA_OUTLETS) == 20


def test_codebook_dataframe_round_trip():
    df = codebook_dataframe()
    # Same number of rows as our flat list (one row per column).
    assert len(df) == 65
    assert set(df.columns) >= {'column', 'group', 'subgroup', 'definition'}
