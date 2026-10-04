"""Configuration for semantic search tool."""

DEFAULT_LIMIT = 50
MAX_QUERY_TOKENS = 20

# Small on purpose: BM25 already down-weights common words; this only removes
# glue words that add noise to an OR query.
_STOPWORDS = frozenset(
    "a an the for with and or of to in on at by from is are be i me my we our you your "
    "want need looking find get some any good best cheap new".split()
)
