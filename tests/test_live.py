"""Offline tests for the public live-observatory namespace."""

import pytest

from ccf_data import CCFLive
from ccf_data.live import DEFAULT_LIVE_BASE_URL, _PublicHTTP


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = ''

    def json(self):
        return self._payload


class _FakeSession:
    """Records requests and returns a canned payload."""

    def __init__(self, payload=None):
        self.payload = payload if payload is not None else []
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        return _FakeResponse(self.payload)


@pytest.fixture()
def live():
    session = _FakeSession()
    client = CCFLive(session=session)
    return client, session


def test_default_base_url():
    assert DEFAULT_LIVE_BASE_URL == "https://ccf-project.ca/api"


def test_no_token_needed():
    CCFLive(session=_FakeSession())          # must not raise


ENDPOINTS = {
    # method name -> (args, expected path, expected params subset)
    'latest_events': ((), 'latest-events', {'limit': 20}),
    'ongoing_events': ((), 'ongoing-events', {}),
    'search_events': (('pipeline',), 'search-events', {'q': 'pipeline'}),
    'recent_cascades': ((), 'recent-cascades', {'limit': 20}),
    'cascade_summary': ((), 'cascade-summary', {}),
    'search_cascades': (('taxe',), 'search-cascades', {'q': 'taxe'}),
    'latest_articles': ((), 'latest-articles', {}),
    'latest_classified': ((), 'latest-classified', {}),
    'articles_timeline': ((), 'articles-timeline', {'days': 15}),
    'search_titles': (('flood',), 'search-titles', {'q': 'flood'}),
    'geo_data': ((), 'geo-data', {}),
    'province_panels': ((), 'province-panels', {}),
    'frames_by_province': ((), 'frames-by-province', {}),
    'media_panels': ((), 'media-panels', {}),
    'media_coverage': ((), 'media-coverage', {}),
    'frames_by_media': ((), 'frames-by-media', {}),
    'articles_by_media': ((), 'articles-by-media', {}),
    'articles_by_month': ((), 'articles-by-month', {}),
    'frames_national': ((), 'frames-national', {}),
    'frames_data': ((), 'frames-data', {}),
    'tone_over_time': ((), 'tone-over-time', {}),
    'category_distribution': ((), 'category-distribution', {}),
    'network_data': ((), 'network-data', {}),
    'annotation_metrics': ((), 'annotation-metrics', {}),
    'daily_brief': ((), 'daily-brief', {}),
    'overview_summary': ((), 'overview-summary', {}),
    'observatory_summary': ((), 'observatory-summary', {}),
    'observatory_stats': ((), 'observatory-stats', {}),
    'stats': ((), 'stats', {}),
}


@pytest.mark.parametrize('method', sorted(ENDPOINTS))
def test_endpoint_urls(live, method):
    client, session = live
    args, path, expected_params = ENDPOINTS[method]
    getattr(client, method)(*args)
    url, params = session.calls[-1]
    assert url.endswith('/' + path)
    for k, v in expected_params.items():
        assert params.get(k) == v


def test_detail_endpoints(live):
    client, session = live
    client.event('evt-abc')
    assert session.calls[-1][0].endswith('/event/evt-abc')
    client.cascade('2026-06_economic')
    assert session.calls[-1][0].endswith('/cascade/2026-06_economic')
    client.article(275849)
    assert session.calls[-1][0].endswith('/article/275849')


def test_none_params_dropped(live):
    client, session = live
    client.latest_events(limit=50, min_media=None)
    _, params = session.calls[-1]
    assert 'min_media' not in params
    assert params['limit'] == 50


def test_main_client_exposes_live():
    from ccf_data import CCF
    ccf = CCF(token='x' * 10)
    assert isinstance(ccf.live, CCFLive)
