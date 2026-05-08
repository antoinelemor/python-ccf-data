"""High-level Python client for the Canadian Climate Framing data API.

Quick start
-----------

    >>> from ccf_data import CCF
    >>> ccf = CCF(token='eyJhbG...')        # generate via https://data.ccf-project.ca
    >>> ccf.summary()                       # corpus stats — dict
    >>> ccf.distribution(['economic_frame', 'health_frame'], group_by='year')
    # → pandas DataFrame: year, sentence_count, economic_frame, health_frame, ...
    >>> ccf.search('carbon tax', level='sentence')             # auto-paginates
    >>> ccf.search('carbon tax', level='article', limit=200)   # cap at 200 rows
    >>> ccf.semantic_search('climate refugees in the Arctic', k=500)
    >>> df = ccf.search_export('carbon tax', filters={'lang': 'en'})  # CSV → DataFrame
    >>> ccf.me()['quota']                   # how many requests/searches/exports left today
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from ._http import _HTTP, DEFAULT_BASE_URL, DEFAULT_TIMEOUT, TierStatus
from .exceptions import CCFBadRequest
from . import schema as _schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_df(rows, raw=False):
    """Convert a list of dicts (or dict with one list field) to DataFrame."""
    if raw:
        return rows
    import pandas as pd
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, list):
        return pd.DataFrame(rows)
    if isinstance(rows, dict):
        # If a dict has a single list value, treat that as the data;
        # otherwise return a one-row frame.
        list_keys = [k for k, v in rows.items() if isinstance(v, list)]
        if len(list_keys) == 1:
            return pd.DataFrame(rows[list_keys[0]])
        return pd.DataFrame([rows])
    return pd.DataFrame(rows)


def _drop_empty(d: Dict[str, Any]) -> Dict[str, Any]:
    """Drop keys whose value is None / '' / empty list."""
    return {k: v for k, v in d.items() if v not in (None, '', [])}


def _norm_lang(value):
    """Normalize a language value to the DB's uppercase form ('EN' / 'FR').

    The CCF database stores language as uppercase 2-letter codes; clients
    routinely pass 'en' / 'fr', so normalize quietly to avoid silent zero
    results.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value.upper() if len(value) == 2 else value
    if isinstance(value, (list, tuple, set)):
        return [_norm_lang(v) for v in value]
    return value


def _norm_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize the `lang`/`language` keys of a filter dict in place."""
    if not filters:
        return {}
    out = dict(filters)
    if 'lang' in out:
        out['lang'] = _norm_lang(out['lang'])
    if 'language' in out:
        out['language'] = _norm_lang(out['language'])
    return out


# ---------------------------------------------------------------------------
# Sub-namespaces (cascades, events) — exposed as `ccf.cascades` / `ccf.events`
# ---------------------------------------------------------------------------

class _Cascades:
    """Cross-year media cascade analysis (cascades = bursts of correlated coverage).

    Access via `ccf.cascades`.
    """

    def __init__(self, http: _HTTP):
        self._http = http

    # --- summaries / lookup ------------------------------------------------
    def summary(self, raw: bool = False):
        """Cross-year cascade summary (counts + by-year breakdown)."""
        return self._http.get('/api/cascades/summary')

    def year(self, year: int, raw: bool = False):
        """All cascades for a given year (metadata + list)."""
        return self._http.get(f'/api/cascades/{year}')

    def detail(self, year: int, cascade_id: str, raw: bool = False):
        """Full detail for a single cascade."""
        return self._http.get(f'/api/cascades/{year}/{cascade_id}')

    def events(self, year: int, raw: bool = False):
        """Event clusters for a year (returns a list)."""
        rows = self._http.get(f'/api/cascades/{year}/events')
        return _to_df(rows, raw=raw)

    def event_detail(self, year: int, cluster_id: int):
        return self._http.get(f'/api/cascades/{year}/events/{cluster_id}')

    def network(self, year: int, cascade_id: str):
        """Network edges for a single cascade."""
        return self._http.get(f'/api/cascades/{year}/network/{cascade_id}')

    def year_network(self, year: int, cascade_ids: Optional[Sequence[str]] = None,
                     frames: Optional[Sequence[str]] = None,
                     media: Optional[Sequence[str]] = None,
                     classifications: Optional[Sequence[str]] = None,
                     score_min: Optional[float] = None,
                     score_max: Optional[float] = None):
        """Whole-year network (filterable). Returns dict with edges + metrics."""
        params = _drop_empty({
            'cascade_ids': ','.join(cascade_ids) if cascade_ids else None,
            'frames': ','.join(frames) if frames else None,
            'media': ','.join(media) if media else None,
            'classifications': ','.join(classifications) if classifications else None,
            'score_min': score_min, 'score_max': score_max,
        })
        return self._http.get(f'/api/cascades/{year}/network', params=params)

    def paradigm_shifts(self, year: int):
        return self._http.get(f'/api/cascades/{year}/paradigm-shifts')

    def convergence(self, year: int):
        return self._http.get(f'/api/cascades/{year}/convergence')

    def time_series(self, year: int):
        return self._http.get(f'/api/cascades/{year}/time-series')

    def impact(self, year: int):
        return self._http.get(f'/api/cascades/{year}/impact')

    # --- cross-year --------------------------------------------------------
    def cross_year(self, page: int = 1, page_size: int = 100, raw: bool = False):
        """One paginated page of the cross-year cascade table."""
        resp = self._http.get('/api/cascades/cross-year',
                              params={'page': page, 'page_size': page_size})
        return resp if raw else _to_df(resp.get('data', []))

    def cross_year_all(self, raw: bool = False):
        """Slim metadata for all cascades across all years (single response)."""
        resp = self._http.get('/api/cascades/cross-year/all')
        return resp if raw else _to_df(resp.get('cascades', []))

    def paradigm_timeline(self, raw: bool = False):
        """Cross-year paradigm-shift timeline."""
        rows = self._http.get('/api/cascades/cross-year/paradigm-timeline')
        return _to_df(rows, raw=raw)

    # --- search ------------------------------------------------------------
    def search(self, query: str, mode: str = 'text',
               cascade_id: Optional[str] = None, raw: bool = False):
        """Keyword/metadata search over cascades. mode='similar' compares
        sub-index vectors against the cascade given by `cascade_id`."""
        body = {'query': query, 'mode': mode}
        if cascade_id:
            body['cascade_id'] = cascade_id
        resp = self._http.post('/api/cascades/search', json=body)
        return resp if raw else _to_df(resp.get('results', []))

    def semantic_search(self, query: str, k: int = 100_000, raw: bool = False):
        """FAISS-backed semantic search → cascades that contain matching articles."""
        resp = self._http.post('/api/cascades/semantic-search',
                               json={'query': query, 'k': int(k)})
        return resp if raw else _to_df(resp.get('results', []))


class _Events:
    """Cross-year event-cluster analysis. Access via `ccf.events`."""

    def __init__(self, http: _HTTP):
        self._http = http

    def summary(self):
        return self._http.get('/api/events/summary')

    def clusters(self, year_min: Optional[int] = None, year_max: Optional[int] = None,
                 types: Optional[Sequence[str]] = None,
                 strength_min: Optional[float] = None, strength_max: Optional[float] = None,
                 multi_type: Optional[bool] = None,
                 sort: str = 'strength', order: str = 'desc',
                 search: str = '', limit: Optional[int] = None,
                 page_size: int = 200, raw: bool = False):
        """Filtered + paginated list of event clusters. By default fetches
        all matching clusters; pass `limit=N` to cap."""
        from ._pagination import _paginate
        base_params = _drop_empty({
            'year_min': year_min, 'year_max': year_max,
            'types': ','.join(types) if types else None,
            'strength_min': strength_min, 'strength_max': strength_max,
            'multi_type': str(multi_type).lower() if multi_type is not None else None,
            'sort': sort, 'order': order, 'search': search or None,
        })
        rows = _paginate(
            self._http, '/api/events/clusters',
            base_params, key='clusters',
            page_param='page', size_param='per_page',
            page_size=page_size, total_key='total', limit=limit,
        )
        return rows if raw else _to_df(rows)

    def cluster(self, year: int, cluster_id: int):
        return self._http.get(f'/api/events/clusters/{year}/{cluster_id}')

    def cluster_articles(self, year: int, cluster_id: int):
        return self._http.get(f'/api/events/clusters/{year}/{cluster_id}/articles')

    def type_network(self, year: Optional[int] = None):
        params = _drop_empty({'year': year})
        return self._http.get('/api/events/type-network', params=params)

    def search(self, query: str, types: Optional[Sequence[str]] = None,
               year_min: Optional[int] = None, year_max: Optional[int] = None,
               strength_min: Optional[float] = None, raw: bool = False):
        params = _drop_empty({
            'q': query,
            'types': ','.join(types) if types else None,
            'year_min': year_min, 'year_max': year_max,
            'strength_min': strength_min,
        })
        resp = self._http.get('/api/events/search', params=params)
        return resp if raw else _to_df(resp.get('results', []))

    def semantic_search(self, query: str, k: int = 100_000, raw: bool = False):
        resp = self._http.post('/api/events/semantic-search',
                               json={'query': query, 'k': int(k)})
        return resp if raw else _to_df(resp.get('results', []))


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

class CCF:
    """Authenticated client for the CCF data API.

    Parameters
    ----------
    token : str
        API JWT generated in your CCF Explorer profile
        (https://data.ccf-project.ca → Profile → Generate API key).
    base_url : str, default 'https://data.ccf-project.ca'
        Override only for self-hosted deployments or tests.
    timeout : int, default 60
        Per-request timeout in seconds.
    """

    def __init__(self, token: str, base_url: str = DEFAULT_BASE_URL,
                 timeout: int = DEFAULT_TIMEOUT):
        self._http = _HTTP(token, base_url=base_url, timeout=timeout)
        self.cascades = _Cascades(self._http)
        self.events = _Events(self._http)
        # The codebook is a class-level constant — also expose on instance.
        self.codebook = _schema.CODEBOOK

    # ------------------------------------------------------------------
    # Identity / quotas
    # ------------------------------------------------------------------
    @property
    def base_url(self) -> str:
        return self._http.base_url

    @property
    def last_status(self) -> TierStatus:
        """Tier + remaining-quota info from the most recent response."""
        return self._http.last_status

    def me(self) -> Dict[str, Any]:
        """Account info + tier + remaining quotas. Hits /auth/me."""
        return self._http.get('/auth/me')

    def tiers(self) -> Dict[str, Any]:
        """Public listing of all tiers + their default quotas. /auth/tiers."""
        return self._http.get('/auth/tiers')

    # ------------------------------------------------------------------
    # Static / aggregate data
    # ------------------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        """Corpus-level stats: total articles, sentences, frames, annotation totals."""
        return self._http.get('/api/summary')

    def schema(self) -> Dict[str, Any]:
        """Server-side annotation schema (frames, subcategories, columns)."""
        return self._http.get('/api/schema')

    def geo_data(self) -> Dict[str, Any]:
        """Pre-computed geographic aggregates by Canadian province."""
        return self._http.get('/api/geo-data')

    def articles_by_year(self, raw: bool = False):
        rows = self._http.get('/api/articles-by-year')
        return _to_df(rows, raw=raw)

    def articles_by_media(self, raw: bool = False):
        rows = self._http.get('/api/articles-by-media')
        return _to_df(rows, raw=raw)

    def frame_trends(self, raw: bool = False):
        """Monthly frame coverage (precomputed view)."""
        rows = self._http.get('/api/frame-trends')
        return _to_df(rows, raw=raw)

    # ------------------------------------------------------------------
    # Distributions / analyses (analyst tier)
    # ------------------------------------------------------------------
    def distribution(self, columns: Sequence[str], group_by: str = 'year',
                     lang: Optional[str] = None, media: Optional[str] = None,
                     date_from: Optional[str] = None, date_to: Optional[str] = None,
                     raw: bool = False):
        """Aggregate annotation counts grouped by year/month/media/language.

        Parameters
        ----------
        columns : list of column names from `ALL_ANNOTATION_COLUMNS`
        group_by : 'year' | 'month' | 'media' | 'language'
        lang, media, date_from, date_to : optional filters
        """
        if group_by not in ('year', 'month', 'media', 'language'):
            raise CCFBadRequest("group_by must be one of: year, month, media, language")
        params = _drop_empty({
            'columns': ','.join(columns), 'group_by': group_by,
            'lang': _norm_lang(lang), 'media': media,
            'date_from': date_from, 'date_to': date_to,
        })
        resp = self._http.get('/api/distribution', params=params)
        return resp if raw else _to_df(resp.get('data', []))

    def subcategory_detail(self, frame: str, date_from: Optional[str] = None,
                           date_to: Optional[str] = None, media: Optional[str] = None,
                           language: Optional[str] = None):
        """Totals + monthly trend for a frame's subcategories.

        Returns a dict with keys 'totals' and 'monthly_trend' (DataFrame-able).
        """
        params = _drop_empty({
            'frame': frame, 'date_from': date_from, 'date_to': date_to,
            'media': media, 'language': _norm_lang(language),
        })
        return self._http.get('/api/subcategory-detail', params=params)

    def messenger_analysis(self, **filters):
        return self._http.get('/api/messenger-analysis',
                              params=_drop_empty(_norm_filters(filters)))

    def event_analysis(self, **filters):
        return self._http.get('/api/event-analysis',
                              params=_drop_empty(_norm_filters(filters)))

    def solution_analysis(self, **filters):
        return self._http.get('/api/solution-analysis',
                              params=_drop_empty(_norm_filters(filters)))

    def tone_trends(self, raw: bool = False, **filters):
        rows = self._http.get('/api/tone-trends',
                              params=_drop_empty(_norm_filters(filters)))
        return _to_df(rows, raw=raw)

    def urgency_trends(self, raw: bool = False, **filters):
        rows = self._http.get('/api/urgency-trends',
                              params=_drop_empty(_norm_filters(filters)))
        return _to_df(rows, raw=raw)

    def canada_coverage(self, raw: bool = False, **filters):
        rows = self._http.get('/api/canada-coverage',
                              params=_drop_empty(_norm_filters(filters)))
        return _to_df(rows, raw=raw)

    def cross_tabulation(self, row_var: str, col_var: str,
                         filters: Optional[Dict[str, Any]] = None):
        """2x2 contingency table of two binary annotation columns."""
        return self._http.post('/api/cross-tabulation', json={
            'row_var': row_var, 'col_var': col_var, 'filters': filters or {},
        })

    # ------------------------------------------------------------------
    # Search (researcher tier)
    # ------------------------------------------------------------------
    def search(self, query: str, level: str = 'sentence', mode: str = 'text',
               filters: Optional[Dict[str, Any]] = None,
               thresholds: Optional[List[Dict[str, Any]]] = None,
               filter_timing: str = 'pre', hybrid_weight: float = 0.5,
               page_size: int = 100, limit: Optional[int] = None,
               raw: bool = False):
        """Unified search endpoint (POST /api/search/advanced).

        Parameters
        ----------
        query : str
            Search text. Use ``'*'`` or empty to enter "browse" mode.
        level : 'sentence' | 'article'
            Whether to return individual sentences or article-level aggregates.
        mode : 'text' | 'keyword' | 'semantic' | 'hybrid' | 'entity' | 'browse'
                | 'cascade_xref' | 'event_xref'
            'text' uses Postgres FTS with stemming. 'keyword' is exact ILIKE.
            'semantic' is FAISS dense retrieval. 'hybrid' blends both.
            'entity' searches NER fields. 'browse' lists results without query.
        filters : dict, optional
            Server-side filters (e.g. ``{'lang': 'en', 'media': ['Globe and Mail'],
            'date_from': '2010-01-01', 'frames': ['economic'], 'tone': 'negative'}``).
        thresholds : list of dict
            Annotation-percentage thresholds per article, e.g.
            ``[{'column': 'economic_frame', 'min_pct': 0.3}]``.
        filter_timing : 'pre' | 'post'
            'pre' applies filters during the SQL query (faster); 'post' fetches
            a wider result and filters in-memory (more flexible).
        page_size : int
            Server page size; auto-paginates by default.
        limit : int or None
            Stop after this many rows (None = fetch all).

        Returns
        -------
        pandas.DataFrame (when raw=False) or list of dicts.
        """
        from ._pagination import _paginate_post
        body_template: Dict[str, Any] = {
            'query': query, 'mode': mode, 'level': level,
            'filters': _norm_filters(filters),
            'filter_timing': filter_timing,
            'hybrid_weight': float(hybrid_weight),
        }
        if thresholds:
            body_template['thresholds'] = thresholds

        rows, last = _paginate_post(
            self._http, '/api/search/advanced', body_template,
            list_keys=('sentences', 'articles', 'results'),
            page_size=page_size, limit=limit,
        )
        if raw:
            return {'rows': rows, 'last_response': last}
        return _to_df(rows)

    def search_summary(self, query: str, filters: Optional[Dict[str, Any]] = None):
        """Aggregate stats for a search (year/media distribution, frame breakdown)."""
        return self._http.post('/api/search/summary',
                               json={'query': query, 'filters': _norm_filters(filters)})

    def search_export(self, query: str, filters: Optional[Dict[str, Any]] = None,
                      columns: Optional[Sequence[str]] = None,
                      max_rows: int = 50_000, mode: str = 'text',
                      include_search_params: bool = False,
                      to_dataframe: bool = True):
        """Server-side CSV export. Returns DataFrame by default; pass
        ``to_dataframe=False`` to get raw CSV bytes."""
        body = {
            'query': query, 'filters': _norm_filters(filters), 'mode': mode,
            'max_rows': int(max_rows),
            'include_search_params': include_search_params,
        }
        if columns:
            body['columns'] = list(columns)
        resp = self._http.post_raw('/api/search/export', json=body)
        if to_dataframe:
            import io
            import pandas as pd
            content = resp.text
            # Strip leading parameter comments if include_search_params is true.
            return pd.read_csv(io.StringIO(content), comment='#')
        return resp.content

    def threshold_filter(self, doc_ids: Sequence[int], column: str,
                         min_pct: float = 0.3):
        """Among `doc_ids`, return those whose AVG(column) ≥ `min_pct`."""
        return self._http.post('/api/search/threshold-filter', json={
            'doc_ids': list(doc_ids), 'column': column, 'min_pct': float(min_pct),
        })

    def cascade_xref(self, query: str, filters: Optional[Dict[str, Any]] = None):
        """Cascades whose articles overlap with this search query."""
        return self._http.post('/api/search/cascade-xref',
                               json={'query': query, 'filters': _norm_filters(filters)})

    def event_xref(self, query: str, filters: Optional[Dict[str, Any]] = None):
        return self._http.post('/api/search/event-xref',
                               json={'query': query, 'filters': _norm_filters(filters)})

    def semantic_search(self, query: str, k: int = 100_000, raw: bool = False):
        """FAISS dense semantic search (POST /api/semantic-search)."""
        resp = self._http.post('/api/semantic-search',
                               json={'query': query, 'k': int(k)})
        return resp if raw else _to_df(resp.get('results', []))

    # ------------------------------------------------------------------
    # Articles (researcher tier)
    # ------------------------------------------------------------------
    def article(self, doc_id: int) -> Dict[str, Any]:
        """Full article: metadata + all sentences + per-sentence annotations."""
        return self._http.get(f'/api/article/{int(doc_id)}')

    def articles_batch(self, doc_ids: Iterable[int], raw: bool = False):
        """Batch-fetch article metadata (no sentences). Faster than N calls."""
        resp = self._http.post('/api/articles/batch',
                               json={'doc_ids': [int(d) for d in doc_ids]})
        return resp if raw else _to_df(resp.get('articles', []))

    # ------------------------------------------------------------------
    # Codebook helpers (no HTTP — local)
    # ------------------------------------------------------------------
    @staticmethod
    def define(column: str) -> str:
        """Operational definition of an annotation column."""
        return _schema.define(column)

    @staticmethod
    def codebook_dataframe():
        """Full codebook as a tidy pandas DataFrame."""
        return _schema.codebook_dataframe()
