"""Pagination helpers for endpoints that expose page/page_size + total."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _paginate(http, path: str, base_params: Dict[str, Any],
              key: str, page_param: str = 'page',
              size_param: str = 'page_size',
              page_size: int = 100, total_key: Optional[str] = 'total',
              limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Iterate GET requests, accumulating items under `key` until exhausted
    or `limit` is reached.

    Stops when:
      - server returns fewer items than page_size (last page),
      - accumulated rows >= limit (if provided),
      - server returns no items.
    """
    out: List[Dict[str, Any]] = []
    page = 1
    while True:
        params = dict(base_params)
        params[page_param] = page
        params[size_param] = page_size
        if limit is not None:
            remaining = limit - len(out)
            if remaining <= 0:
                break
            params[size_param] = min(page_size, remaining)
        resp = http.get(path, params=params)
        items = resp.get(key) or []
        if not items:
            break
        out.extend(items)
        # If the API tells us total_count we can short-circuit
        if total_key and total_key in resp:
            try:
                if len(out) >= int(resp[total_key]):
                    break
            except (TypeError, ValueError):
                pass
        # Heuristic: stopped early if the page was not full
        if len(items) < params[size_param]:
            break
        if limit is not None and len(out) >= limit:
            break
        page += 1
    return out[:limit] if limit else out


def _paginate_post(http, path: str, body_template: Dict[str, Any],
                   list_keys: Sequence[str] = ('sentences', 'articles', 'results'),
                   page_size: int = 100,
                   limit: Optional[int] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Same idea as _paginate but for POST endpoints (search/advanced).

    Returns (accumulated_rows, last_response_body).
    """
    out: List[Dict[str, Any]] = []
    last: Dict[str, Any] = {}
    page = 1
    while True:
        body = dict(body_template)
        body['page'] = page
        if limit is not None:
            remaining = limit - len(out)
            if remaining <= 0:
                break
            body['page_size'] = min(page_size, remaining)
        else:
            body['page_size'] = page_size
        resp = http.post(path, json=body)
        last = resp if isinstance(resp, dict) else {}
        items = []
        for k in list_keys:
            v = last.get(k) if isinstance(last, dict) else None
            if isinstance(v, list):
                items = v
                break
        if not items:
            break
        out.extend(items)
        total = last.get('total') if isinstance(last, dict) else None
        if total is not None:
            try:
                if len(out) >= int(total):
                    break
            except (TypeError, ValueError):
                pass
        if len(items) < body['page_size']:
            break
        if limit is not None and len(out) >= limit:
            break
        page += 1
    if limit:
        out = out[:limit]
    return out, last
