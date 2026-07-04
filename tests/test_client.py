"""Tests for the CCF client (HTTP mocked via responses)."""

import pytest
import responses

from ccf_data import CCF, CCFAuthError, CCFTierError, CCFQuotaError


BASE = 'https://data.ccf-project.ca'


@pytest.fixture
def ccf():
    return CCF(token='test-token', base_url=BASE)


@responses.activate
def test_summary_returns_dict(ccf):
    responses.add(responses.GET, f'{BASE}/api/summary',
                  json={'total_articles': 250000, 'total_sentences': 9_200_000},
                  headers={'X-CCF-Tier': 'researcher',
                           'X-CCF-Requests-Remaining': '19999'})
    s = ccf.summary()
    assert s['total_articles'] == 250000
    assert ccf.last_status.tier == 'researcher'
    assert ccf.last_status.requests_remaining == 19999


@responses.activate
def test_distribution_to_dataframe(ccf):
    responses.add(responses.GET, f'{BASE}/api/distribution',
                  json={'data': [{'year': 2010, 'sentence_count': 100,
                                  'economic_frame': 30}]})
    df = ccf.distribution(['economic_frame'], group_by='year')
    assert df.shape[0] == 1
    assert int(df.iloc[0]['economic_frame']) == 30


@responses.activate
def test_401_raises_auth_error(ccf):
    responses.add(responses.GET, f'{BASE}/api/summary',
                  status=401, json={'error': 'Invalid or expired token'})
    with pytest.raises(CCFAuthError):
        ccf.summary()


@responses.activate
def test_403_tier_error_carries_metadata(ccf):
    responses.add(responses.GET, f'{BASE}/api/search/articles',
                  status=403, json={'error': 'tier_insufficient',
                                     'tier': 'metadata', 'required_tier': 'researcher',
                                     'message': "needs researcher"})
    with pytest.raises(CCFTierError) as excinfo:
        ccf._http.get('/api/search/articles')
    assert excinfo.value.tier == 'metadata'
    assert excinfo.value.required_tier == 'researcher'


@responses.activate
def test_429_quota_error_carries_reason(ccf):
    responses.add(responses.GET, f'{BASE}/api/summary',
                  status=429, json={'error': 'quota_exceeded',
                                     'reason': 'request_quota_day',
                                     'tier': 'metadata'})
    with pytest.raises(CCFQuotaError) as excinfo:
        ccf.summary()
    assert excinfo.value.reason == 'request_quota_day'


@responses.activate
def test_search_paginates_and_stops_at_limit(ccf):
    # Two pages, then stop because we hit limit=15
    page1 = [{'doc_id': i, 'sentence_id': i} for i in range(10)]
    page2 = [{'doc_id': 10 + i, 'sentence_id': 10 + i} for i in range(10)]
    responses.add(responses.POST, f'{BASE}/api/search/advanced',
                  json={'sentences': page1, 'total': 100, 'page': 1, 'pages': 10})
    responses.add(responses.POST, f'{BASE}/api/search/advanced',
                  json={'sentences': page2, 'total': 100, 'page': 2, 'pages': 10})
    df = ccf.search('carbon', level='sentence', limit=15, page_size=10)
    assert len(df) == 15


@responses.activate
def test_codebook_accessible_offline(ccf):
    # No HTTP needed — codebook is bundled.
    assert 'economic' in ccf.codebook['frames']
    assert ccf.define('eco_cost').startswith('Negative economic')


@responses.activate
def test_corpus_param_sent_on_get(ccf):
    responses.add(responses.GET, f'{BASE}/api/summary', json={'total_articles': 1})
    ccf.summary(corpus='all')
    assert 'corpus=all' in responses.calls[0].request.url


@responses.activate
def test_corpus_param_sent_in_search_body(ccf):
    import json
    responses.add(responses.POST, f'{BASE}/api/search/advanced',
                  json={'sentences': [], 'total': 0, 'page': 1, 'pages': 1})
    ccf.search('carbon', corpus='continuous', page_size=10)
    body = json.loads(responses.calls[0].request.body)
    assert body['corpus'] == 'continuous'


def test_corpus_invalid_rejected(ccf):
    from ccf_data import CCFBadRequest
    with pytest.raises(CCFBadRequest):
        ccf.summary(corpus='bogus')


@responses.activate
def test_corpus_omitted_by_default(ccf):
    responses.add(responses.GET, f'{BASE}/api/summary', json={'total_articles': 1})
    ccf.summary()
    assert 'corpus' not in responses.calls[0].request.url
