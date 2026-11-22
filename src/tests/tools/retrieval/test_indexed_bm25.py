import pytest

from package.tools import SearchTool
from package.tools.retrieval.indexed_bm25_rows import indexed_bm25_rows
from package.tools.base import ToolInputError
from tests.tools_helpers import VG_A, VG_B


@pytest.mark.parametrize('query,filters', [
    ('game electronics accessories', {}),
    ('game electronics', {'exclude_item_ids': [VG_A]}),
    ('game', {'domain': 'Video_Games'}),
    ('accessory', {'price_max': 20}),
    ('mario', {}),
    ('unmatchedword', {}),
])
def test_indexed_topk_matches_existing_exact_search(corpus, query, filters):
    baseline = SearchTool(corpus)(query=query, filters=filters, limit=2)
    indexed = SearchTool(corpus, indexed_topk=True, exact_count=False)(query=query, filters=filters, limit=2)
    assert baseline.ok and indexed.ok
    assert indexed.data['candidates'] == baseline.data['candidates']
    assert indexed.data['applied_filters'] == baseline.data['applied_filters']
    assert indexed.data['total_matches'] is None


def test_boundary_ties_expand_and_keep_stable_rating_tiebreak():
    class TiedCorpus:
        fetch_sizes = []
        def select(self, sql, params, max_rows):
            if 'ORDER BY rank' in sql:
                self.fetch_sizes.append(max_rows)
                rows = [{'fts_rowid': i, 'relevance': -1.} for i in range(min(max_rows, 600))]
                return rows, max_rows < 600
            # Rating winner is outside the initial 256-row FTS prefix.
            ids = params
            return [{'fts_rowid': i, 'item_id': f'D::{i:04}', 'rating_number': i}
                    for i in ids], False
    corpus = TiedCorpus()
    rows, truncated = indexed_bm25_rows(corpus, 'query', 'items.item_id', '1', [], 2)
    assert [r['item_id'] for r in rows] == ['D::0599', 'D::0598']
    assert corpus.fetch_sizes == [256, 512, 1024]
    assert truncated is True


def test_exactness_cap_fails_instead_of_truncating_ties():
    class CappedCorpus:
        def select(self, sql, params, max_rows):
            if 'ORDER BY rank' in sql:
                return [{'fts_rowid': i, 'relevance': -1.} for i in range(max_rows)], True
            return [{'fts_rowid': i, 'item_id': str(i), 'rating_number': 0} for i in params], False
    with pytest.raises(ToolInputError, match='scan cap'):
        indexed_bm25_rows(CappedCorpus(), 'query', 'items.item_id', '1', [], 1, max_scan=256)


def test_indexed_topk_respects_temporal_policy(corpus):
    from package.corpus.apply_metadata_policy import apply_metadata_policy
    apply_metadata_policy(corpus, 'historical_static_catalog', as_of_timestamp=2)
    baseline = SearchTool(corpus)(query='game mario', filters={'exclude_item_ids': [VG_A]}, limit=2)
    indexed = SearchTool(corpus, indexed_topk=True, exact_count=False)(
        query='game mario', filters={'exclude_item_ids': [VG_A]}, limit=2)
    assert baseline.ok and indexed.ok
    assert baseline.data['candidates'] == indexed.data['candidates']
    assert all(r['rating_number'] is None for r in indexed.data['candidates'])
