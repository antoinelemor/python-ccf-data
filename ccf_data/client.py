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
    if 'corpus' in out:
        out['corpus'] = _norm_corpus(out['corpus'])
    return out


VALID_CORPORA = ('legacy', 'continuous', 'all')


def _norm_corpus(value):
    """Validate the corpus-provenance selector.

    ``legacy`` (the frozen, citable corpus) is the server default and open to
    every tier. ``continuous`` (the real-time extraction feed) and ``all``
    (both) require an ``observer`` tier token — the server returns 403
    otherwise. ``None`` is left untouched so the request omits the parameter.
    """
    if value is None:
        return None
    if value not in VALID_CORPORA:
        raise CCFBadRequest(
            f"corpus must be one of {VALID_CORPORA}, got {value!r}")
    return value


# ---------------------------------------------------------------------------
# Sub-namespaces (cascades, events) — exposed as `ccf.cascades` / `ccf.events`
# ---------------------------------------------------------------------------

class _Cascades:
    """Cross-year media cascade analysis. Access via ``ccf.cascades``.

    Cascades model bursts of correlated coverage across newspapers — each
    cascade has a frame, a classification, scores (temporal /
    participation / convergence / source / total), participating
    journalists and outlets, and time-resolved network edges.

    **Tier required for every method in this namespace: ``researcher``.**

    Methods
    -------
    summary, year, detail, events, event_detail, network, year_network,
    paradigm_shifts, convergence, time_series, impact, cross_year,
    cross_year_all, paradigm_timeline, search, semantic_search.
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
    """Cross-year event-cluster analysis. Access via ``ccf.events``.

    Event clusters group together occurrences of similar events
    (extreme weather, summits, elections, judiciary decisions, …)
    across multiple newspapers and dates. Each cluster has a dominant
    type, a strength score, NER entities, and the underlying article IDs.

    **Tier required for every method in this namespace: ``researcher``.**

    Methods
    -------
    summary, clusters, cluster, cluster_articles, type_network,
    search, semantic_search.
    """

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
        # Public real-time observatory API (no token, separate base URL):
        # live events/cascades/articles WITH their bilingual LLM summaries.
        from .live import CCFLive
        self.live = CCFLive()
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
        """Return account info, tier, and remaining quotas for the current token.

        Hits ``GET /auth/me``. The response includes ``username``, ``role``,
        ``tier``, ``tier_description``, and a ``quota`` block with
        ``requests`` / ``searches`` / ``exports`` (each with ``used_today``,
        ``used_total``, ``max_day``, ``max_total``).

        Tier: not required (any authenticated token).

        >>> ccf.me()['quota']['requests']['used_today']
        17
        """
        return self._http.get('/auth/me')

    def tiers(self) -> Dict[str, Any]:
        """Public listing of all tiers + their default quotas (``GET /auth/tiers``).

        Tier: not required (no authentication needed in fact).

        >>> ccf.tiers()['default_minimum']
        'researcher'
        """
        return self._http.get('/auth/tiers')

    # ------------------------------------------------------------------
    # Static / aggregate data (tier: metadata)
    # ------------------------------------------------------------------
    def summary(self, corpus: Optional[str] = None) -> Dict[str, Any]:
        """Corpus-level statistics: totals, date range, frames, annotation counts.

        Tier: ``metadata``. Hits ``GET /api/summary``.

        ``corpus`` selects the provenance: ``'legacy'`` (default, frozen corpus),
        ``'continuous'`` (real-time feed) or ``'all'`` — the last two need the
        ``observer`` tier.

        >>> s = ccf.summary()
        >>> s['total_articles'], s['total_sentences']
        (266271, 9198958)
        """
        return self._http.get('/api/summary',
                              params=_drop_empty({'corpus': _norm_corpus(corpus)}))

    def schema(self) -> Dict[str, Any]:
        """Server-side annotation schema (frames, subcategories, columns,
        media list, allowed group_by values).

        Tier: ``metadata``. Hits ``GET /api/schema``.
        """
        return self._http.get('/api/schema')

    def geo_data(self) -> Dict[str, Any]:
        """Pre-computed per-province aggregates: articles, frames, events,
        tone, strategy, entities, cascades, and media-by-province mapping.

        Tier: ``metadata``. Hits ``GET /api/geo-data``.
        """
        return self._http.get('/api/geo-data')

    def articles_by_year(self, raw: bool = False, corpus: Optional[str] = None):
        """Article counts by year as a DataFrame (year, count).

        Tier: ``metadata``. Hits ``GET /api/articles-by-year``.

        Pass ``raw=True`` to receive the underlying list of dicts.
        ``corpus``: see :py:meth:`summary`.
        """
        rows = self._http.get('/api/articles-by-year',
                              params=_drop_empty({'corpus': _norm_corpus(corpus)}))
        return _to_df(rows, raw=raw)

    def articles_by_media(self, raw: bool = False, corpus: Optional[str] = None):
        """Article counts by media outlet as a DataFrame (media, count).

        Tier: ``metadata``. Hits ``GET /api/articles-by-media``.
        ``corpus``: see :py:meth:`summary`.
        """
        rows = self._http.get('/api/articles-by-media',
                              params=_drop_empty({'corpus': _norm_corpus(corpus)}))
        return _to_df(rows, raw=raw)

    def frame_trends(self, raw: bool = False, corpus: Optional[str] = None):
        """Pre-computed monthly frame coverage (one row per month with
        per-frame counts).

        Tier: ``metadata``. Hits ``GET /api/frame-trends``.
        ``corpus``: see :py:meth:`summary`.
        """
        rows = self._http.get('/api/frame-trends',
                              params=_drop_empty({'corpus': _norm_corpus(corpus)}))
        return _to_df(rows, raw=raw)

    # ------------------------------------------------------------------
    # Distributions / analyses (analyst tier)
    # ------------------------------------------------------------------
    def distribution(self, columns: Sequence[str], group_by: str = 'year',
                     lang: Optional[str] = None, media: Optional[str] = None,
                     date_from: Optional[str] = None, date_to: Optional[str] = None,
                     raw: bool = False, corpus: Optional[str] = None):
        """Aggregate annotation counts grouped by year / month / media / language.

        Tier: ``analyst``. Hits ``GET /api/distribution``.

        Parameters
        ----------
        columns : list of column names from ``ALL_ANNOTATION_COLUMNS``
        group_by : ``'year'`` | ``'month'`` | ``'media'`` | ``'language'``
        lang : optional language filter (``'en'`` / ``'fr'`` — case-insensitive)
        media : optional single media-outlet filter
        date_from, date_to : ISO date strings
        raw : if True return the raw response dict

        >>> ccf.distribution(['economic_frame', 'health_frame'],
        ...                  group_by='year', lang='en')
            year  economic_frame  health_frame  sentence_count
        0   1978               0             0              11
        ...
        """
        if group_by not in ('year', 'month', 'media', 'language'):
            raise CCFBadRequest("group_by must be one of: year, month, media, language")
        params = _drop_empty({
            'columns': ','.join(columns), 'group_by': group_by,
            'lang': _norm_lang(lang), 'media': media,
            'date_from': date_from, 'date_to': date_to,
            'corpus': _norm_corpus(corpus),
        })
        resp = self._http.get('/api/distribution', params=params)
        return resp if raw else _to_df(resp.get('data', []))

    def subcategory_detail(self, frame: str, date_from: Optional[str] = None,
                           date_to: Optional[str] = None, media: Optional[str] = None,
                           language: Optional[str] = None, corpus: Optional[str] = None):
        """Totals + monthly trend for a frame's subcategories.

        Returns a dict with keys 'totals' and 'monthly_trend' (DataFrame-able).
        ``corpus``: see :py:meth:`summary`.
        """
        params = _drop_empty({
            'frame': frame, 'date_from': date_from, 'date_to': date_to,
            'media': media, 'language': _norm_lang(language),
            'corpus': _norm_corpus(corpus),
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
                         filters: Optional[Dict[str, Any]] = None,
                         corpus: Optional[str] = None):
        """2x2 contingency table of two binary annotation columns.

        ``corpus``: see :py:meth:`summary`.
        """
        return self._http.post('/api/cross-tabulation', json=_drop_empty({
            'row_var': row_var, 'col_var': col_var, 'filters': filters or {},
            'corpus': _norm_corpus(corpus),
        }))

    # ------------------------------------------------------------------
    # Search (researcher tier)
    # ------------------------------------------------------------------
    def search(self, query: str, level: str = 'sentence', mode: str = 'text',
               filters: Optional[Dict[str, Any]] = None,
               thresholds: Optional[List[Dict[str, Any]]] = None,
               filter_timing: str = 'pre', hybrid_weight: float = 0.5,
               page_size: int = 100, limit: Optional[int] = None,
               raw: bool = False, corpus: Optional[str] = None):
        """Unified search over the CCF corpus (``POST /api/search/advanced``).

        Tier: ``researcher``. This is the workhorse method — it covers
        full-text, keyword, semantic, hybrid, entity, and browse searches at
        either sentence or article granularity. Auto-paginates results.

        Parameters
        ----------
        query : str
            Search text. Use ``'*'`` or empty to enter ``browse`` mode.
        level : str
            ``'sentence'`` (default) returns one row per matching sentence with
            highlighted ``headline``; ``'article'`` aggregates per ``doc_id``
            with frame percentages and matching counts.
        mode : str
            - ``'text'``: Postgres full-text search (language-aware stemming).
            - ``'keyword'``: exact ``ILIKE`` substring match (no stemming).
            - ``'semantic'``: FAISS dense retrieval over BAAI/bge-m3 embeddings.
            - ``'hybrid'``: blend of FTS + semantic (``hybrid_weight``).
            - ``'entity'``: search inside the NER fields (``ner_entities``).
            - ``'browse'``: list results without a query (apply filters only).
            - ``'cascade_xref'`` / ``'event_xref'``: results limited to those
              overlapping with cascades / event clusters.
        filters : dict, optional
            Server-side filters. Useful keys:

            - ``lang`` (``'en'`` / ``'fr'``, case-insensitive)
            - ``media`` (string or list of media outlets — see ``MEDIA_OUTLETS``)
            - ``date_from`` / ``date_to`` (ISO date strings)
            - ``frames`` (list, e.g. ``['economic', 'environmental']``)
            - ``tone`` (``'positive'`` / ``'negative'`` / ``'neutral'``)
            - ``subcategories`` / ``messenger_subs`` / ``event_subs`` /
              ``solutions`` (lists of column names)
            - ``front_page`` (bool), ``urgency`` / ``canada`` (0/1),
              ``news_type``, ``author``, ``words_count_min/max``
            - ``province`` (Canadian province; auto-translated to media list)
        thresholds : list of dict
            Per-article annotation-percentage thresholds, e.g.
            ``[{'column': 'economic_frame', 'min_pct': 0.3}]`` keeps
            articles whose AVG(economic_frame) ≥ 30 %.
        filter_timing : str
            ``'pre'`` (default) applies filters during the SQL query
            (faster); ``'post'`` fetches a wider result set and applies
            annotation filters in-memory (more flexible at the cost of
            extra rows fetched).
        hybrid_weight : float in [0, 1]
            Mix between semantic (1.0) and FTS (0.0) when ``mode='hybrid'``.
        page_size : int
            Server page size; auto-paginates until ``limit`` is reached.
        limit : int or None
            Cap rows returned. ``None`` = fetch every page.
        raw : bool
            If True return ``{'rows': [...], 'last_response': {...}}``
            instead of a DataFrame.

        Returns
        -------
        pandas.DataFrame (default) or dict (``raw=True``).

        >>> df = ccf.search('carbon tax', level='sentence',
        ...                 filters={'lang': 'en', 'media': ['Globe and Mail']},
        ...                 limit=200)
        >>> df.columns.tolist()[:6]
        ['doc_id', 'sentence_id', 'title', 'author', 'media', 'pub_date']
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
        if _norm_corpus(corpus) is not None:
            body_template['corpus'] = corpus

        rows, last = _paginate_post(
            self._http, '/api/search/advanced', body_template,
            list_keys=('sentences', 'articles', 'results'),
            page_size=page_size, limit=limit,
        )
        if raw:
            return {'rows': rows, 'last_response': last}
        return _to_df(rows)

    def search_summary(self, query: str, filters: Optional[Dict[str, Any]] = None,
                       corpus: Optional[str] = None):
        """Aggregate stats for a search (year/media distribution, frame breakdown).

        ``corpus``: see :py:meth:`summary`.
        """
        return self._http.post('/api/search/summary', json=_drop_empty({
            'query': query, 'filters': _norm_filters(filters),
            'corpus': _norm_corpus(corpus)}))

    def search_export(self, query: str, filters: Optional[Dict[str, Any]] = None,
                      columns: Optional[Sequence[str]] = None,
                      max_rows: int = 50_000, mode: str = 'text',
                      include_search_params: bool = False,
                      to_dataframe: bool = True, corpus: Optional[str] = None):
        """Server-side CSV export of a search query. Returns a DataFrame by
        default; pass ``to_dataframe=False`` to get raw CSV bytes.

        Tier: ``expert``. Hits ``POST /api/search/export``. The export
        endpoint enforces a per-token export quota in addition to the
        normal request quota, so exports also count against
        ``last_status.exports_remaining``.

        Parameters
        ----------
        query : str
            Search text (uses Postgres FTS regardless of `mode`).
        filters : dict
            Same keys as :py:meth:`search`.
        columns : list of str, optional
            Restrict the CSV to these columns
            (see ``EXPORT_COLUMNS_WHITELIST`` server-side).
        max_rows : int, default 50_000
            Server-side cap on rows.
        mode : str
            Logged with the export but does not change the SQL strategy.
        include_search_params : bool
            Prepend a ``# Query:`` comment block at the top of the CSV.
        to_dataframe : bool
            If True (default) parse the CSV with pandas and return a DataFrame;
            otherwise return raw bytes (suitable for ``open('out.csv','wb')``).

        >>> df = ccf.search_export('carbon tax',
        ...     filters={'lang': 'en'},
        ...     columns=['doc_id', 'sentence_text', 'pub_date',
        ...              'media', 'dominant_frame'])
        """
        body = {
            'query': query, 'filters': _norm_filters(filters), 'mode': mode,
            'max_rows': int(max_rows),
            'include_search_params': include_search_params,
        }
        if columns:
            body['columns'] = list(columns)
        if _norm_corpus(corpus) is not None:
            body['corpus'] = corpus
        resp = self._http.post_raw('/api/search/export', json=body)
        if to_dataframe:
            import io
            import pandas as pd
            content = resp.text
            # Strip leading parameter comments if include_search_params is true.
            return pd.read_csv(io.StringIO(content), comment='#')
        return resp.content

    def threshold_filter(self, doc_ids: Sequence[int], column: str,
                         min_pct: float = 0.3, corpus: Optional[str] = None):
        """Among `doc_ids`, return those whose AVG(column) ≥ `min_pct`.

        ``corpus``: see :py:meth:`summary`.
        """
        return self._http.post('/api/search/threshold-filter', json=_drop_empty({
            'doc_ids': list(doc_ids), 'column': column, 'min_pct': float(min_pct),
            'corpus': _norm_corpus(corpus),
        }))

    def cascade_xref(self, query: str, filters: Optional[Dict[str, Any]] = None):
        """Cascades whose articles overlap with this search query."""
        return self._http.post('/api/search/cascade-xref',
                               json={'query': query, 'filters': _norm_filters(filters)})

    def event_xref(self, query: str, filters: Optional[Dict[str, Any]] = None):
        return self._http.post('/api/search/event-xref',
                               json={'query': query, 'filters': _norm_filters(filters)})

    def semantic_search(self, query: str, k: int = 100_000, raw: bool = False,
                        corpus: Optional[str] = None):
        """FAISS dense semantic search (POST /api/semantic-search).

        ``corpus``: see :py:meth:`summary`.
        """
        resp = self._http.post('/api/semantic-search', json=_drop_empty({
            'query': query, 'k': int(k), 'corpus': _norm_corpus(corpus)}))
        return resp if raw else _to_df(resp.get('results', []))

    # ------------------------------------------------------------------
    # Articles (researcher tier)
    # ------------------------------------------------------------------
    def article(self, doc_id: int, corpus: Optional[str] = None) -> Dict[str, Any]:
        """Fetch a full article by ``doc_id``: metadata + every sentence +
        per-sentence annotation columns.

        Tier: ``researcher``. Hits ``GET /api/article/<doc_id>``.
        ``corpus``: see :py:meth:`summary`.

        Viewer accounts (different from the tier system) have a per-account
        article-view quota; once exhausted, sentences come back with
        ``sentence_text=''`` and the response carries
        ``viewer_limit_reached=True``. Tier-based tokens are not affected.

        >>> art = ccf.article(123456)
        >>> art['title'], len(art['sentences'])
        ('Drive in Alberta...', 30)
        """
        return self._http.get(f'/api/article/{int(doc_id)}',
                              params=_drop_empty({'corpus': _norm_corpus(corpus)}))

    def articles_batch(self, doc_ids: Iterable[int], raw: bool = False,
                       corpus: Optional[str] = None):
        """Batch-fetch article metadata (without sentences) for a list of IDs.

        Tier: ``researcher``. Hits ``POST /api/articles/batch``. Returns a
        DataFrame with ``doc_id, title, media, date, author``. Much faster
        than N individual :py:meth:`article` calls when you only need
        metadata. ``corpus``: see :py:meth:`summary`.
        """
        resp = self._http.post('/api/articles/batch', json=_drop_empty({
            'doc_ids': [int(d) for d in doc_ids], 'corpus': _norm_corpus(corpus)}))
        return resp if raw else _to_df(resp.get('articles', []))

    # ------------------------------------------------------------------
    # Codebook helpers (no HTTP — local)
    # ------------------------------------------------------------------
    @staticmethod
    def define(column: str) -> str:
        """Operational definition of an annotation column.

        Tier: not required (offline lookup against the embedded codebook).
        """
        return _schema.define(column)

    @staticmethod
    def codebook_dataframe():
        """Full codebook as a tidy pandas DataFrame.

        Tier: not required (offline).
        """
        return _schema.codebook_dataframe()

    # ------------------------------------------------------------------
    # Tier introspection (no HTTP — local)
    # ------------------------------------------------------------------
    @staticmethod
    def tier_required(method_name: str):
        """Return the minimum tier required to call a given method, or None
        for offline helpers. Useful before issuing a call:

        >>> CCF.tier_required('search_export')
        'expert'
        """
        from . import tiers as _tiers
        return _tiers.tier_required(method_name)

    @staticmethod
    def methods_by_tier(tier: str, *, exact: bool = False):
        """List methods callable at a given tier.

        Pass ``exact=True`` to get only methods whose minimum tier is exactly
        ``tier`` (excluding lower-tier methods that are also callable).

        >>> CCF.methods_by_tier('expert', exact=True)
        ['search_export']
        """
        from . import tiers as _tiers
        return _tiers.methods_by_tier(tier, exact=exact)
