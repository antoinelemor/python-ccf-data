"""Quickstart for ccf_data — the Python client for the CCF data platform.

Generate your API token at https://data.ccf-project.ca → Profile, then:

    export CCF_TOKEN="eyJhbG..."
    python examples/quickstart.py
"""

import os

from ccf_data import CCF, ALL_ANNOTATION_COLUMNS, define


def main():
    token = os.environ.get('CCF_TOKEN')
    if not token:
        raise SystemExit("Set CCF_TOKEN to your API token (see https://data.ccf-project.ca).")

    ccf = CCF(token=token)

    # 1. Inspect your tier and remaining quotas
    me = ccf.me()
    print(f"Logged in as {me.get('username')!r} — tier {me.get('tier')!r}")
    quota = me.get('quota', {})
    if quota:
        req = quota.get('requests', {})
        print(f"  Requests today: {req.get('used_today')} "
              f"/ {req.get('max_day') or 'unlimited'}")

    # 2. Corpus-level stats
    print("\nCorpus summary:")
    s = ccf.summary()
    print(f"  Articles: {s.get('total_articles'):,}")
    print(f"  Sentences: {s.get('total_sentences'):,}")
    print(f"  Date range: {s.get('first_article')} → {s.get('last_article')}")

    # 3. Distribution of all 8 frames over time (year-level)
    print("\nFrame coverage by year (first 5 rows):")
    df = ccf.distribution(
        columns=['economic_frame', 'health_frame', 'environmental_frame'],
        group_by='year',
    )
    print(df.head())

    # 4. Operational definitions (offline — embedded codebook)
    print("\nDefinition of 'sci_skepticism':")
    print(" ", define('sci_skepticism'))
    print(f"\nThere are {len(ALL_ANNOTATION_COLUMNS)} operational annotation columns.")

    # 5. A small search (researcher tier required)
    try:
        results = ccf.search('carbon tax', level='sentence', limit=20,
                             filters={'lang': 'en'})
        print(f"\n'carbon tax' search → {len(results)} sentences (capped at 20).")
        if not results.empty:
            print(results[['doc_id', 'media', 'pub_date']].head())
    except Exception as e:
        print(f"\nSearch skipped: {e}")


if __name__ == '__main__':
    main()
