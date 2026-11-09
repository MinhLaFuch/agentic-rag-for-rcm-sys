"""Schema and constants for the corpus module.

This module defines:
- Constants for chunking and sampling
- Table schema column definitions

SQL queries (CREATE TABLE, indexes, FTS population) are in _sql.py.
"""

# ---- constants ----------------------------------------------------------- #

# Chunk size for batched queries (avoids overly large IN clauses)
QUERY_CHUNK_SIZE = 500
