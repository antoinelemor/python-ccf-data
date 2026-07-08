"""Live observatory namespace — the PUBLIC real-time API of the CCF website.

The Canadian Climate Framing observatory (https://ccf-project.ca/observatory)
continuously extracts, annotates and summarises Canadian climate coverage.
Its backing API is **public and unauthenticated** (read-only, cached
server-side): everything the observatory pages display can be queried
programmatically — detected media events and cascades **with their bilingual
LLM summaries**, the last-15-days article timeline with per-article frame
profiles and summaries, province/media panels, national frame trends, and
the daily editorial brief.

Two ways in::

    >>> from ccf_data import CCF, CCFLive
    >>> live = CCFLive()                      # no token needed
    >>> live.latest_events(limit=20)          # events + summary_en / summary_fr
    >>> live.article(275849)['summary_fr']    # LLM summary of one article

    >>> ccf = CCF(token='eyJ...')             # or ride along the main client
    >>> ccf.live.recent_cascades(limit=10)

Data caveat — the live corpus (`continuous`) is refreshed multiple times a
day and is **not frozen**: it complements, but does not replace, the citable
`legacy` corpus served by the authenticated research API.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from .exceptions import CCFError, CCFNotFound, CCFServerError


DEFAULT_LIVE_BASE_URL = "https://ccf-project.ca/api"
DEFAULT_LIVE_TIMEOUT = 30


class _PublicHTTP:
    """Minimal unauthenticated session for the public observatory API."""

    def __init__(self, base_url: str = DEFAULT_LIVE_BASE_URL,
                 timeout: int = DEFAULT_LIVE_TIMEOUT,
                 session: Optional[requests.Session] = None):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': 'ccf-data-python/0.3.0'})

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            resp = self.session.get(url, params=params or {},
                                    timeout=self.timeout)
        except requests.RequestException as exc:  # network-level failure
            raise CCFError(f"Cannot reach the live observatory API: {exc}")
        if resp.status_code == 404:
            raise CCFNotFound(f"Not found: {url}")
        if resp.status_code >= 500:
            raise CCFServerError(f"Server error {resp.status_code} on {url}")
        if resp.status_code >= 400:
            raise CCFError(f"HTTP {resp.status_code} on {url}: {resp.text[:200]}")
        return resp.json()


def _clean(params: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


class CCFLive:
    """Public, real-time observatory API (no token required).

    Everything returns plain Python structures (dicts / lists) exactly as
    served; most list-like payloads convert cleanly with
    ``pandas.DataFrame(...)``. Events, cascades and articles carry their
    LLM summaries in ``summary_en`` / ``summary_fr`` (articles also expose a
    language-matched ``summary``), stamped with ``generated_at``.
    """

    def __init__(self, base_url: str = DEFAULT_LIVE_BASE_URL,
                 timeout: int = DEFAULT_LIVE_TIMEOUT,
                 session: Optional[requests.Session] = None):
        self._http = _PublicHTTP(base_url, timeout, session)

    # --- events (detected multi-outlet convergences) -----------------------
    def latest_events(self, limit: int = 20, min_media: Optional[int] = None):
        """Latest detected events (1..400), each with bilingual titles and
        LLM summaries (``title_en/fr``, ``summary_en/fr``, ``generated_at``),
        typed classification, strength score and 3 key articles."""
        return self._http.get('latest-events',
                              _clean({'limit': limit, 'min_media': min_media}))

    def ongoing_events(self):
        """Events detected today or yesterday — the freshest signals."""
        return self._http.get('ongoing-events')

    def event(self, event_key: str):
        """Full profile of one event (articles, entities, summaries EN/FR)."""
        return self._http.get(f'event/{event_key}')

    def search_events(self, q: str):
        """Full-text search over event titles and summaries (EN + FR)."""
        return self._http.get('search-events', {'q': q})

    # --- cascades (bursts of correlated coverage) ---------------------------
    def recent_cascades(self, limit: int = 20):
        """Most recent media cascades (1..100) with frame, classification,
        z-score and bilingual LLM summaries; ``live`` flags ongoing ones."""
        return self._http.get('recent-cascades', {'limit': limit})

    def cascade(self, cascade_id: str):
        """Full profile of one cascade (articles, outlets, summaries EN/FR)."""
        return self._http.get(f'cascade/{cascade_id}')

    def cascade_summary(self):
        """Aggregate cascade statistics for the observatory."""
        return self._http.get('cascade-summary')

    def search_cascades(self, q: str):
        """Full-text search over cascade titles and summaries (EN + FR)."""
        return self._http.get('search-cascades', {'q': q})

    # --- articles (continuous extraction feed) ------------------------------
    def latest_articles(self):
        """Most recent extracted articles with their LLM summaries."""
        return self._http.get('latest-articles')

    def latest_classified(self):
        """Most recent articles fully classified by the 128 CCF models."""
        return self._http.get('latest-classified')

    def article(self, doc_id: int):
        """One article: metadata, province, full 8-frame profile, entities,
        related events/cascades, and LLM ``summary`` / ``summary_en/fr``."""
        return self._http.get(f'article/{doc_id}')

    def articles_timeline(self, days: int = 15):
        """Day-by-day, outlet-by-outlet article timeline (1..60 days): each
        article carries its top-3 frames, full profile and summaries."""
        return self._http.get('articles-timeline', {'days': days})

    def search_titles(self, q: str):
        """Full-text search over article titles of the live corpus."""
        return self._http.get('search-titles', {'q': q})

    # --- geography -----------------------------------------------------------
    def geo_data(self):
        """Unified map payload: per-province volumes, outlets and city pins
        (CBC/Radio-Canada articles are LLM-classified into provinces)."""
        return self._http.get('geo-data')

    def province_panels(self):
        """Per-province panels: volumes, frame profiles, LLM briefs, articles."""
        return self._http.get('province-panels')

    def frames_by_province(self):
        """Monthly frame shares aggregated by province."""
        return self._http.get('frames-by-province')

    # --- media ---------------------------------------------------------------
    def media_panels(self):
        """Per-outlet panels (volumes, frame profile, LLM brief)."""
        return self._http.get('media-panels')

    def media_coverage(self):
        """Coverage freshness per outlet and per source database."""
        return self._http.get('media-coverage')

    def frames_by_media(self):
        """Monthly frame shares aggregated by outlet."""
        return self._http.get('frames-by-media')

    def articles_by_media(self):
        """Article counts per outlet (live corpus)."""
        return self._http.get('articles-by-media')

    def articles_by_month(self):
        """Article counts per month (live corpus)."""
        return self._http.get('articles-by-month')

    # --- national trends & analytics -----------------------------------------
    def frames_national(self):
        """National monthly frame shares (smoothed), live corpus."""
        return self._http.get('frames-national')

    def frames_data(self):
        """Frame trend data used by the observatory charts."""
        return self._http.get('frames-data')

    def tone_over_time(self):
        """Monthly tone (alarmist / reassuring) trends."""
        return self._http.get('tone-over-time')

    def category_distribution(self):
        """Distribution of detected categories across the corpus."""
        return self._http.get('category-distribution')

    def network_data(self):
        """Entity co-occurrence network of the live corpus."""
        return self._http.get('network-data')

    def annotation_metrics(self):
        """Per-category annotation performance metrics of the CCF models."""
        return self._http.get('annotation-metrics')

    # --- editorial briefs & site stats ----------------------------------------
    def daily_brief(self):
        """LLM-written editorial brief of the day — ``{'en': ..., 'fr': ...}``."""
        return self._http.get('daily-brief')

    def overview_summary(self):
        """LLM overview of the 20 biggest events of the last 15 days (EN/FR)."""
        return self._http.get('overview-summary')

    def observatory_summary(self):
        """Observatory headline summary."""
        return self._http.get('observatory-summary')

    def observatory_stats(self):
        """Observatory counters (events, cascades, articles, freshness)."""
        return self._http.get('observatory-stats')

    def stats(self):
        """Site-wide corpus statistics (articles, sentences, time span)."""
        return self._http.get('stats')
