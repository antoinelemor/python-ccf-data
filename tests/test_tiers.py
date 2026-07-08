"""Tests for the offline tier-introspection helpers."""

import pytest

from ccf_data import (
    CCF, METHOD_TIERS, TIERS, TIER_DESCRIPTIONS,
    methods_by_tier, tier_at_least, tier_required,
)


def test_method_tiers_all_known():
    """Every value in METHOD_TIERS is a valid tier, 'public' (the live
    observatory API, no token) or None (offline)."""
    valid = set(TIERS) | {None, 'public'}
    assert all(t in valid for t in METHOD_TIERS.values())


def test_live_methods_are_public():
    """Every CCFLive endpoint method is registered as 'public', and every
    'live.*' registry entry matches a real method on CCFLive."""
    from ccf_data import CCFLive
    live_methods = {n for n in dir(CCFLive)
                    if not n.startswith('_') and callable(getattr(CCFLive, n))}
    registered = {k.split('.', 1)[1] for k, v in METHOD_TIERS.items()
                  if k.startswith('live.')}
    assert registered == live_methods
    assert all(v == 'public' for k, v in METHOD_TIERS.items()
               if k.startswith('live.'))
    assert tier_required('live.latest_events') == 'public'


def test_tier_required_for_core_methods():
    assert tier_required('summary') == 'metadata'
    assert tier_required('distribution') == 'analyst'
    assert tier_required('search') == 'researcher'
    assert tier_required('search_export') == 'expert'
    assert tier_required('define') is None


def test_tier_required_unknown_method():
    with pytest.raises(KeyError):
        tier_required('not_a_method')


def test_tier_at_least_ordering():
    assert tier_at_least('researcher', 'analyst') is True
    assert tier_at_least('analyst', 'researcher') is False
    assert tier_at_least('writer', 'expert') is True
    assert tier_at_least('metadata', 'metadata') is True


def test_methods_by_tier_includes_lower_tiers_by_default():
    researcher = set(methods_by_tier('researcher'))
    metadata   = set(methods_by_tier('metadata'))
    analyst    = set(methods_by_tier('analyst'))
    # metadata ⊂ analyst ⊂ researcher
    assert metadata <= analyst <= researcher


def test_methods_by_tier_exact():
    expert_only = methods_by_tier('expert', exact=True)
    assert 'search_export' in expert_only
    assert 'search' not in expert_only  # search is researcher-tier


def test_ccf_static_methods_match_module_helpers():
    assert CCF.tier_required('search') == tier_required('search')
    assert CCF.methods_by_tier('expert', exact=True) == methods_by_tier('expert', exact=True)


def test_tier_descriptions_are_complete():
    # Every token tier described + the extra 'public' pseudo-tier (live API).
    assert set(TIER_DESCRIPTIONS) == set(TIERS) | {'public'}
    assert all(isinstance(v, str) and v for v in TIER_DESCRIPTIONS.values())
