# ccf-data — Python client for the Canadian Climate Framing API

Authenticated, tibble-friendly access to the Canadian Climate Framing (CCF)
data platform: a corpus of ~250,000 Canadian newspaper articles
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

The platform enforces five progressive tiers per token. The tier is
assigned by an administrator when the token is created and dictates
both *which* endpoints the token may call and *how many* requests it
can issue per day.

| Tier         | Default req/day | Endpoints unlocked                                              |
|--------------|----------------:|-----------------------------------------------------------------|
| `metadata`   | 1 000           | summary, schema, geo, articles-by-year/media, frame-trends      |
| `analyst`    | 5 000           | + distributions, trends, cross-tab, subcategory/messenger/event/solution analyses |
| `researcher` | 20 000          | + search/article/articles batch, all cascades + events, semantic search |
| `expert`     | unlimited       | + CSV exports                                                   |
| `writer`     | unlimited       | + admin endpoints (used for internal tools)                     |

Two extra search-specific quotas (`searches/day`, `exports/day`) layer on
top. When you call any `/api/*` endpoint the server returns these
`X-CCF-*` response headers — accessible via `ccf.last_status`:

```python
ccf.summary()
ccf.last_status   # TierStatus(tier='researcher',
                  #            requests_remaining=19999, ...)
```

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

## Quick tour

### Corpus stats and schema

```python
ccf.summary()                 # totals, frame counts, date range
ccf.schema()                  # server-side annotation schema
ccf.codebook                  # offline dict — operational definitions
CCF.define('eco_neg_impact')  # a single column's definition
CCF.codebook_dataframe()      # full codebook as a DataFrame
```

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

### Articles

```python
art = ccf.article(123456)
art['title'], art['media'], art['date']
ccf.articles_batch([123456, 123457, 123458])  # metadata for many docs
```

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
Lemorphic (Université de Sherbrooke), Tristan Boursier (Sciences Po
Paris & Université du Québec en Outaouais).
