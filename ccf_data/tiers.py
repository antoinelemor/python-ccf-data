"""Tier metadata: client-side mirror of the server's enforcement table.

The server enforces tiers atomically (see scripts/migrate_add_tiers.sql);
this module exposes the same information so callers can introspect
which tier a given method requires *before* hitting the API.

Usage
-----

    >>> from ccf_data import tier_required, methods_by_tier
    >>> tier_required('search')
    'researcher'
    >>> methods_by_tier('analyst')
    ['canada_coverage', 'cross_tabulation', 'distribution', ...]
"""

from __future__ import annotations

from typing import Dict, List


# ---------------------------------------------------------------------------
# Tier order + descriptions
# ---------------------------------------------------------------------------

TIERS: tuple[str, ...] = (
    'metadata',
    'analyst',
    'researcher',
    'expert',
    'writer',
)

TIER_RANK: Dict[str, int] = {t: i for i, t in enumerate(TIERS)}

TIER_DESCRIPTIONS: Dict[str, str] = {
    'metadata':   'Read summary, schema, geographic and pre-aggregated data.',
    'analyst':    'Run distributions, time series, cross-tabulations, frame analyses.',
    'researcher': 'Search the corpus, fetch full articles, browse cascades and event clusters.',
    'expert':     'Unlimited search and CSV exports for offline analysis.',
    'writer':     'Full access (admin/maintainer-equivalent).',
    # Not a token tier: the live observatory API is public and unauthenticated.
    'public':     'Live observatory (ccf.live / CCFLive) — public real-time API, '
                  'no token required.',
}


# ---------------------------------------------------------------------------
# Method → tier table
# ---------------------------------------------------------------------------
# Every public method on CCF / CCF.cascades / CCF.events.
# Keys are dot paths so they can be displayed unambiguously.

METHOD_TIERS: Dict[str, str] = {
    # Identity (any authenticated token)
    'me':                         'metadata',
    'tiers':                      'metadata',

    # Aggregate / static data
    'summary':                    'metadata',
    'schema':                     'metadata',
    'geo_data':                   'metadata',
    'articles_by_year':           'metadata',
    'articles_by_media':          'metadata',
    'frame_trends':               'metadata',

    # Distributions / analyses
    'distribution':               'analyst',
    'subcategory_detail':         'analyst',
    'messenger_analysis':         'analyst',
    'event_analysis':             'analyst',
    'solution_analysis':          'analyst',
    'tone_trends':                'analyst',
    'urgency_trends':             'analyst',
    'canada_coverage':            'analyst',
    'cross_tabulation':           'analyst',

    # Search & articles
    'search':                     'researcher',
    'search_summary':             'researcher',
    'threshold_filter':           'researcher',
    'cascade_xref':               'researcher',
    'event_xref':                 'researcher',
    'semantic_search':            'researcher',
    'article':                    'researcher',
    'articles_batch':             'researcher',

    # Exports (CSV)
    'search_export':              'expert',

    # Cascades sub-namespace
    'cascades.summary':           'researcher',
    'cascades.year':              'researcher',
    'cascades.detail':            'researcher',
    'cascades.events':            'researcher',
    'cascades.event_detail':      'researcher',
    'cascades.network':           'researcher',
    'cascades.year_network':      'researcher',
    'cascades.paradigm_shifts':   'researcher',
    'cascades.convergence':       'researcher',
    'cascades.time_series':       'researcher',
    'cascades.impact':            'researcher',
    'cascades.cross_year':        'researcher',
    'cascades.cross_year_all':    'researcher',
    'cascades.paradigm_timeline': 'researcher',
    'cascades.search':            'researcher',
    'cascades.semantic_search':   'researcher',

    # Events sub-namespace
    'events.summary':             'researcher',
    'events.clusters':            'researcher',
    'events.cluster':             'researcher',
    'events.cluster_articles':    'researcher',
    'events.type_network':        'researcher',
    'events.search':              'researcher',
    'events.semantic_search':     'researcher',

    # Live observatory namespace — PUBLIC real-time API (no token at all):
    # https://ccf-project.ca/api. Any tier (and no tier) can call these.
    'live.latest_events':         'public',
    'live.ongoing_events':        'public',
    'live.event':                 'public',
    'live.search_events':         'public',
    'live.recent_cascades':       'public',
    'live.cascade':               'public',
    'live.cascade_summary':       'public',
    'live.search_cascades':       'public',
    'live.latest_articles':       'public',
    'live.latest_classified':     'public',
    'live.article':               'public',
    'live.articles_timeline':     'public',
    'live.search_titles':         'public',
    'live.geo_data':              'public',
    'live.province_panels':       'public',
    'live.frames_by_province':    'public',
    'live.media_panels':          'public',
    'live.media_coverage':        'public',
    'live.frames_by_media':       'public',
    'live.articles_by_media':     'public',
    'live.articles_by_month':     'public',
    'live.frames_national':       'public',
    'live.frames_data':           'public',
    'live.tone_over_time':        'public',
    'live.category_distribution': 'public',
    'live.network_data':          'public',
    'live.annotation_metrics':    'public',
    'live.daily_brief':           'public',
    'live.overview_summary':      'public',
    'live.observatory_summary':   'public',
    'live.observatory_stats':     'public',
    'live.stats':                 'public',

    # Local helpers — no tier required (no HTTP call)
    'define':                     None,
    'codebook':                   None,
    'codebook_dataframe':         None,
    'tier_required':              None,
    'methods_by_tier':            None,
}


def tier_required(method_name: str):
    """Return the minimum tier required to call `method_name`, or None
    for offline/codebook helpers.

    >>> tier_required('search')
    'researcher'
    >>> tier_required('search_export')
    'expert'
    >>> tier_required('cascades.summary')
    'researcher'
    >>> tier_required('define') is None
    True
    """
    if method_name not in METHOD_TIERS:
        raise KeyError(f"Unknown method {method_name!r}. "
                       f"See METHOD_TIERS for the full list.")
    return METHOD_TIERS[method_name]


def methods_by_tier(tier: str, *, exact: bool = False) -> List[str]:
    """Return method names for a given tier.

    Parameters
    ----------
    tier : one of `TIERS`
    exact : if True, only methods whose required tier is exactly `tier`;
            if False (default), all methods callable at this tier
            (i.e. requiring `tier` or a lower one).

    >>> 'search' in methods_by_tier('researcher')
    True
    >>> 'search_export' in methods_by_tier('researcher')
    False
    >>> 'search_export' in methods_by_tier('expert')
    True
    >>> 'live.latest_events' in methods_by_tier('metadata')   # public: any tier
    True
    >>> methods_by_tier('public', exact=True)[0].startswith('live.')
    True
    """
    if tier != 'public' and tier not in TIER_RANK:
        raise ValueError(f"Unknown tier {tier!r}. "
                         f"Valid tiers: {list(TIERS) + ['public']}")
    rank = TIER_RANK.get(tier, -1)
    out = []
    for name, t in METHOD_TIERS.items():
        if t is None:
            continue
        if exact:
            if t == tier:
                out.append(name)
        else:
            # 'public' methods are callable from any tier (and no tier at all).
            if t == 'public' or (tier != 'public' and TIER_RANK[t] <= rank):
                out.append(name)
    return sorted(out)


def tier_at_least(token_tier: str, required: str) -> bool:
    """Return True if `token_tier` is privileged enough for `required`.

    ``required='public'`` is always satisfied (the live observatory API
    needs no token at all)."""
    if required == 'public':
        return True
    return TIER_RANK.get(token_tier, -1) >= TIER_RANK.get(required, 999)
