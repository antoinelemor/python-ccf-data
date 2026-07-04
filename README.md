# ccf-data — Python client for the Canadian Climate Framing API

Authenticated, DataFrame-friendly access to the Canadian Climate Framing
(CCF) data platform: a corpus of ~250,000 Canadian newspaper articles
(1978–2024), 9.2 M sentences, and 67 climate-coverage annotations
(framings, messengers, events, solutions, tone, named entities).

Live API: <https://data.ccf-project.ca>

## Installation

```bash
pip install git+https://github.com/antoinelemor/python-ccf-data.git
```

Requires Python 3.9+. Hard dependencies: `requests`, `pandas`.

## Authentication

All requests need a long-lived JWT API key.

1. Sign in at <https://data.ccf-project.ca>.
2. Open the **Profile** page → **Generate API key**.
3. Copy the key. Each key is bound to one user account and a tier
   (see below) with daily request / search / export quotas.

```python
import os
from ccf_data import CCF

ccf = CCF(token=os.environ['CCF_TOKEN'])
print(ccf.me())   # username, role, tier, quota usage
```

You can also point at a self-hosted instance:

```python
CCF(token='...', base_url='http://localhost:8005')
```

## API tiers

The platform enforces six progressive tiers per token. The tier is
assigned by an administrator when the token is created and dictates
both *which* endpoints the token may call and *how many* requests it
can issue per day.

| Tier         | Default req/day | Default search/day | Default export/day | Unlocks                                               |
|--------------|----------------:|-------------------:|-------------------:|-------------------------------------------------------|
| `metadata`   |           1 000 |                  — |                  — | summary, schema, geo, articles-by-*, frame-trends     |
| `analyst`    |           5 000 |                100 |                  — | + distributions, trends, cross-tab, *_analysis        |
| `researcher` |          20 000 |              1 000 |                 20 | + search/article/cascades/events/semantic             |
| `expert`     |       unlimited |          unlimited |          unlimited | + CSV exports                                         |
| `writer`     |       unlimited |          unlimited |          unlimited | + admin endpoints (internal tooling)                  |
| `observer`   |       unlimited |          unlimited |          unlimited | + the real-time continuous feed (`corpus=continuous`/`all`) |

### Corpus provenance (`corpus=`)

Every data method accepts an optional `corpus` argument selecting which
slice of the observatory to read:

| Value          | Meaning                                                              |
|----------------|----------------------------------------------------------------------|
| `legacy`       | The frozen, citable corpus from the study (**default**, reproducible). |
| `continuous`   | The continuously extracted real-time feed only.                      |
| `all`          | Legacy + continuous combined.                                        |

`legacy` is served to every tier. `continuous` and `all` require an
`observer` token — other tiers get `403 corpus_forbidden`. Omitting the
argument keeps the legacy default, so existing code is unchanged.

```python
ccf.summary()                       # legacy (default)
ccf.search('carbon tax', corpus='all')      # needs observer tier
ccf.distribution(['economic_frame'], corpus='continuous')
```

These quotas are stored per-token; an admin can override any of them.
After every call the client stashes `tier`, `requests_remaining`,
`searches_remaining`, `exports_remaining` from the `X-CCF-*` response
headers — accessible via `ccf.last_status`.

When a quota is exhausted you get a `CCFQuotaError`; when your tier is
too low you get a `CCFTierError`. Catch them by class:

```python
from ccf_data import CCFQuotaError, CCFTierError
try:
    ccf.search('carbon tax')
except CCFTierError as e:
    print(f"Need tier {e.required_tier}, you have {e.tier}")
except CCFQuotaError as e:
    print(f"Quota '{e.reason}' hit on tier '{e.tier}'")
```

You can introspect tiers offline:

```python
from ccf_data import CCF, methods_by_tier, tier_required, TIER_DESCRIPTIONS

CCF.tier_required('search_export')        # 'expert'
CCF.tier_required('search')               # 'researcher'
methods_by_tier('analyst', exact=True)    # only analyst-tier methods
TIER_DESCRIPTIONS['expert']               # one-line description
```

## All methods at a glance

Methods are listed below with their endpoint, minimum tier, and what
they do. *Offline* helpers don't hit the network and don't require a
token at all (the codebook is bundled with the package).

### Identity & quota introspection

| Method                | HTTP                       | Tier      | Description |
|-----------------------|----------------------------|-----------|-------------|
| `ccf.me()`            | GET /auth/me               | metadata  | Username, role, tier, quota usage. |
| `ccf.tiers()`         | GET /auth/tiers            | metadata  | Public listing of all tiers + default quotas. |
| `ccf.last_status`     | (no HTTP — last call)      | —         | TierStatus from the most recent response headers. |

### Aggregate / static data — tier `metadata`

| Method                          | HTTP                          | Description |
|---------------------------------|-------------------------------|-------------|
| `ccf.summary()`                 | GET /api/summary              | Corpus totals (articles, sentences, frames, annotation totals). |
| `ccf.schema()`                  | GET /api/schema               | Server-side annotation schema. |
| `ccf.geo_data()`                | GET /api/geo-data             | Per-province aggregates (frames, events, tone, entities). |
| `ccf.articles_by_year()`        | GET /api/articles-by-year     | DataFrame with one row per year. |
| `ccf.articles_by_media()`       | GET /api/articles-by-media    | DataFrame with one row per media outlet. |
| `ccf.frame_trends()`            | GET /api/frame-trends         | Pre-computed monthly frame coverage. |

### Distributions / analyses — tier `analyst`

| Method                            | HTTP                              | Description |
|-----------------------------------|-----------------------------------|-------------|
| `ccf.distribution(...)`           | GET /api/distribution             | Annotation counts grouped by year/month/media/language. |
| `ccf.subcategory_detail(frame)`   | GET /api/subcategory-detail       | Totals + monthly trend for a frame's subcategories. |
| `ccf.messenger_analysis(...)`     | GET /api/messenger-analysis       | Messenger column totals + monthly trend. |
| `ccf.event_analysis(...)`         | GET /api/event-analysis           | Event column totals + monthly trend. |
| `ccf.solution_analysis(...)`      | GET /api/solution-analysis        | Solution column totals + monthly trend. |
| `ccf.tone_trends(...)`            | GET /api/tone-trends              | Monthly positive/negative/neutral counts. |
| `ccf.urgency_trends(...)`         | GET /api/urgency-trends           | Monthly urgency-flag counts. |
| `ccf.canada_coverage(...)`        | GET /api/canada-coverage          | Monthly Canada-mention counts. |
| `ccf.cross_tabulation(r, c)`      | POST /api/cross-tabulation        | 2×2 contingency table of two binary columns. |

### Search & articles — tier `researcher`

| Method                                  | HTTP                              | Description |
|-----------------------------------------|-----------------------------------|-------------|
| `ccf.search(query, ...)`                | POST /api/search/advanced         | Unified search (text / keyword / semantic / hybrid / entity / browse / *_xref) at sentence or article level. Auto-paginates. |
| `ccf.search_summary(query)`             | POST /api/search/summary          | Aggregate stats for a query (year + media distribution, frame breakdown). |
| `ccf.threshold_filter(doc_ids, col)`    | POST /api/search/threshold-filter | Among `doc_ids`, keep those whose AVG(col) ≥ min_pct. |
| `ccf.cascade_xref(query)`               | POST /api/search/cascade-xref     | Cascades whose articles overlap with this search. |
| `ccf.event_xref(query)`                 | POST /api/search/event-xref       | Event clusters whose articles overlap with this search. |
| `ccf.semantic_search(query, k)`         | POST /api/semantic-search         | FAISS-only dense retrieval (no FTS). |
| `ccf.article(doc_id)`                   | GET /api/article/&lt;doc_id&gt;   | Full article (metadata + every sentence + annotations). |
| `ccf.articles_batch([doc_ids])`         | POST /api/articles/batch          | Metadata-only batch fetch (much faster than N article calls). |

### Cascades sub-namespace — tier `researcher`

Access via `ccf.cascades.<method>`. All methods require tier `researcher`.

| Method                                                 | HTTP                                              | Description |
|--------------------------------------------------------|---------------------------------------------------|-------------|
| `cascades.summary()`                                   | GET /api/cascades/summary                         | Cross-year cascade counts and metadata. |
| `cascades.year(year)`                                  | GET /api/cascades/&lt;year&gt;                    | All cascades for one year. |
| `cascades.detail(year, cascade_id)`                    | GET /api/cascades/&lt;year&gt;/&lt;cid&gt;        | Full cascade record (scores, journalists, media, events). |
| `cascades.events(year)`                                | GET /api/cascades/&lt;year&gt;/events             | Year's event clusters as a DataFrame. |
| `cascades.event_detail(year, cluster_id)`              | GET /api/cascades/&lt;year&gt;/events/&lt;id&gt;  | One year-bound event cluster. |
| `cascades.network(year, cascade_id)`                   | GET /api/cascades/&lt;year&gt;/network/&lt;cid&gt;| Network edges for a single cascade. |
| `cascades.year_network(year, ...)`                     | GET /api/cascades/&lt;year&gt;/network            | Whole-year edge list, filterable. |
| `cascades.paradigm_shifts(year)`                       | GET /api/cascades/&lt;year&gt;/paradigm-shifts    | Paradigm-shift episodes for a year. |
| `cascades.convergence(year)`                           | GET /api/cascades/&lt;year&gt;/convergence        | Year's convergence statistics. |
| `cascades.time_series(year)`                           | GET /api/cascades/&lt;year&gt;/time-series        | Daily articles / journalists / signals tables. |
| `cascades.impact(year)`                                | GET /api/cascades/&lt;year&gt;/impact             | Year's impact summary. |
| `cascades.cross_year(page, page_size)`                 | GET /api/cascades/cross-year                      | One page of the cross-year cascade table. |
| `cascades.cross_year_all()`                            | GET /api/cascades/cross-year/all                  | Slim metadata for every cascade across all years. |
| `cascades.paradigm_timeline()`                         | GET /api/cascades/cross-year/paradigm-timeline    | Cross-year paradigm-shift timeline. |
| `cascades.search(query, mode='text'|'similar')`        | POST /api/cascades/search                         | Keyword search or sub-index similarity over cascades. |
| `cascades.semantic_search(query, k)`                   | POST /api/cascades/semantic-search                | FAISS → cascades whose articles match. |

### Events sub-namespace — tier `researcher`

Access via `ccf.events.<method>`. All methods require tier `researcher`.

| Method                                              | HTTP                                                          | Description |
|-----------------------------------------------------|---------------------------------------------------------------|-------------|
| `events.summary()`                                  | GET /api/events/summary                                       | Cross-year event-cluster summary. |
| `events.clusters(...)`                              | GET /api/events/clusters                                      | Filtered + paginated cluster list. Auto-paginates. |
| `events.cluster(year, cluster_id)`                  | GET /api/events/clusters/&lt;y&gt;/&lt;id&gt;                 | Full cluster detail incl. occurrences. |
| `events.cluster_articles(year, cluster_id)`         | GET /api/events/clusters/&lt;y&gt;/&lt;id&gt;/articles        | Articles attached to the cluster, grouped by occurrence. |
| `events.type_network(year=None)`                    | GET /api/events/type-network                                  | Co-occurrence matrix between event types. |
| `events.search(query, ...)`                         | GET /api/events/search                                        | Keyword search for clusters (FTS + entity match). |
| `events.semantic_search(query, k)`                  | POST /api/events/semantic-search                              | FAISS → matching clusters. |

### CSV export — tier `expert`

| Method                                  | HTTP                              | Description |
|-----------------------------------------|-----------------------------------|-------------|
| `ccf.search_export(query, ...)`         | POST /api/search/export           | Server-side CSV export, parsed back into a DataFrame by default. |

### Codebook (offline — no token, no network)

| Method                                  | Description |
|-----------------------------------------|-------------|
| `ccf.codebook` (property)               | Full bundled codebook as a dict. |
| `CCF.define(column)`                    | Operational definition of one annotation column. |
| `CCF.codebook_dataframe()`              | Tidy DataFrame (column, group, subgroup, definition). |
| `CCF.tier_required(method)`             | Minimum tier for a given client method, or None for offline. |
| `CCF.methods_by_tier(tier, exact=...)`  | List methods callable at a tier. |
| `subcategories_of(frame)`               | Subcategory column names for a frame. |
| `define(column)`                        | Module-level alias of `CCF.define`. |
| `FRAME_NAMES`, `FRAME_COLUMNS`, `MEDIA_OUTLETS`, `ALL_ANNOTATION_COLUMNS`, `LANGUAGES` | Convenience constants. |

## Quick tour

### Time series and distributions

```python
df = ccf.distribution(['economic_frame', 'health_frame'],
                      group_by='year', lang='en')
ccf.tone_trends(media='Globe and Mail')
ccf.canada_coverage(date_from='2015-01-01')
ccf.cross_tabulation('economic_frame', 'tone_negative')
```

### Search

```python
# Plain full-text search (Postgres FTS, language-aware).
df = ccf.search('carbon tax', level='sentence',
                filters={'lang': 'en', 'date_from': '2015-01-01'},
                limit=500)

# Article-level with filters by frame, tone, media, threshold:
ccf.search('carbon tax', level='article',
           filters={'frames': ['economic'], 'tone': 'negative',
                    'media': ['Globe and Mail', 'Toronto Star']},
           thresholds=[{'column': 'economic_frame', 'min_pct': 0.3}])

# FAISS dense semantic search:
ccf.semantic_search('climate refugees in the Arctic', k=500)

# Aggregate stats for any query (year + media distribution):
ccf.search_summary('carbon tax', filters={'lang': 'en'})

# Server-side CSV export → DataFrame (requires expert tier):
ccf.search_export('carbon tax', filters={'lang': 'en'},
                  columns=['doc_id', 'sentence_text', 'pub_date',
                           'media', 'dominant_frame'])
```

`search()` auto-paginates. Pass `limit=N` to cap, or `page_size=N` to
tune the server page size. Set `raw=True` to get a dict with the raw
rows + last response.

### Cascades — cross-year media bursts

```python
ccf.cascades.summary()
ccf.cascades.cross_year_all()                 # all cascades, slim
ccf.cascades.year(2020)
ccf.cascades.detail(2020, 'Eco_x_3')
ccf.cascades.network(2020, 'Eco_x_3')
ccf.cascades.semantic_search('IPCC report')
```

### Events — cross-year event clusters

```python
ccf.events.summary()
ccf.events.clusters(year_min=2018, types=['evt_weather'], limit=200)
ccf.events.cluster(2020, 42)
ccf.events.cluster_articles(2020, 42)
ccf.events.semantic_search('wildfire smoke')
```

## Annotation schema (offline)

The 67-category annotation framework is bundled in `ccf_data/codebook.json`
and exposed through helpers that don't hit the network:

```python
from ccf_data import (FRAME_NAMES, ALL_ANNOTATION_COLUMNS,
                      MEDIA_OUTLETS, define, subcategories_of)

FRAME_NAMES                       # ['economic', 'health', ...]
ALL_ANNOTATION_COLUMNS            # 65 operational columns
subcategories_of('economic')      # ['eco_neg_impact', ...]
define('sci_skepticism')          # operational definition
```

Two of the 67 categories (`health_pos_impact`, `health_footprint`) are
documented in the codebook but excluded from analysis (insufficient
training data). They appear in `CODEBOOK['definitions']` but not in
`ALL_ANNOTATION_COLUMNS`.

## Errors

| Class             | Raised on | Why                                          |
|-------------------|-----------|----------------------------------------------|
| `CCFAuthError`    | 401, 403  | Missing/expired/revoked token, wrong creds.  |
| `CCFTierError`    | 403       | Tier too low — check `e.required_tier`.      |
| `CCFQuotaError`   | 429       | Quota hit — check `e.reason`.                |
| `CCFNotFound`     | 404       | Unknown article / cascade / event.           |
| `CCFBadRequest`   | 400       | Malformed parameters.                        |
| `CCFServerError`  | 5xx       | Upstream failure.                            |
| `CCFError`        | other     | Anything else.                               |

## Running the test suite

```bash
pip install -e '.[dev]'
pytest -q
```

The included tests use [`responses`](https://github.com/getsentry/responses)
to mock all HTTP traffic — no network or token needed.

## License

MIT. Part of the Canadian Climate Framing research project — Antoine
Lemor (Université de Sherbrooke), Tristan Boursier (Sciences Po
Paris & Université du Québec en Outaouais).
