# Phase 4 Move Plan: Reorganize package/tools/ by functionality

## Current Structure Analysis

**package/tools/** current contents:
- `base/` - Tool base class, validation, error handling, call logger (tool infrastructure)
- `corpus/` - ItemCorpus and corpus management (data infrastructure)
- `ranking/` - RankTool, SimilarTool (ranking tools)
- `retrieval/` - SearchTool (retrieval tool)
- `score/` - BaselineScorer, CandidateScorer (scoring tools)
- `sql_query/` - FilterTool, LookupTool (SQL tools)
- `recommenders/` - Recommender models (MODEL infrastructure, NOT tools)
- `evaluation/` - DELETED in Phase 3
- `embeddings/` - DELETED in Phase 2
- `_limits.py`, `_schema.py` - Tool configuration/limits (tool infrastructure)

## Functional Analysis

**Tool Infrastructure (not user-facing tools):**
- `base/` - Tool base class, validation, errors, helpers
- `_limits.py`, `_schema.py` - Tool configuration

**Data Infrastructure:**
- `corpus/` - ItemCorpus, corpus management (used by tools and models)

**Actual Tools (used by agents):**
- `retrieval/` - SearchTool (semantic search)
- `ranking/` - RankTool, SimilarTool (item ranking)
- `score/` - BaselineScorer, CandidateScorer (item scoring)
- `sql_query/` - FilterTool, LookupTool (SQL filtering/lookup)

**Model Infrastructure (NOT tools):**
- `recommenders/` - Recommender model training/evaluation/serving (should not be in tools/)

## Proposed Functional Organization

```
package/
├── tools/                      # Agent tools only
│   ├── __init__.py
│   ├── _limits.py              # Tool limits/config
│   ├── _schema.py              # Tool schema
│   ├── base/                   # Tool infrastructure
│   │   ├── __init__.py
│   │   ├── tool.py
│   │   ├── _dataclass.py
│   │   ├── _error.py
│   │   ├── _helper.py
│   │   ├── _validation.py
│   │   ├── candidate_ids.py
│   │   ├── candidate_results.py
│   │   ├── check_top_k.py
│   │   └── tool_call_logger.py
│   ├── retrieval/              # Retrieval tools
│   │   ├── __init__.py
│   │   ├── search_tool.py
│   │   ├── _helper.py
│   │   └── _schema.py
│   ├── ranking/                # Ranking tools
│   │   ├── __init__.py
│   │   ├── rank_tool.py
│   │   └── similar_tool.py
│   ├── scoring/                # Scoring tools (renamed from score/)
│   │   ├── __init__.py
│   │   ├── baseline_scorer.py
│   │   └── candidate_scorer.py
│   └── sql/                    # SQL tools (renamed from sql_query/)
│       ├── __init__.py
│       ├── filter_tool.py
│       ├── lookup_tool.py
│       └── compile_filters.py
│
├── corpus/                     # Data infrastructure (moved from tools/corpus)
│   ├── __init__.py
│   ├── corpus.py
│   ├── build_corpus.py
│   ├── load_corpus.py
│   ├── save_corpus.py
│   ├── apply_metadata_policy.py
│   └── metadata_policy.py
│
├── recommenders/               # Model infrastructure (moved from tools/recommenders)
│   ├── __init__.py
│   ├── evaluation/             # Model training/tuning
│   ├── runtime/                # Model inference
│   └── shared/                 # Shared utilities
│
└── evaluation/                 # Agent evaluation (from Phase 3)
    ├── recommender/            # Recommender evaluation metrics
    ├── product_reply/
    ├── trajectory/
    ├── provenance/
    └── ...
```

## Key Improvements

1. **tools/ now contains ONLY tools used by agents** - base, retrieval, ranking, scoring, sql
2. **recommenders/ moved out of tools/** - it's model infrastructure, not a tool
3. **corpus/ moved out of tools/** - it's data infrastructure, not a tool
4. **Renamed for clarity:**
   - `score/` → `scoring/` (matches naming pattern of other tool types)
   - `sql_query/` → `sql/` (shorter, clearer)
5. **Functional grouping within tools/**: all subdirectories are tool types
6. **tools/__init__.py exports only tools** - no corpus, no recommenders

## Detailed Move Operations

### Step 1: Move corpus/ to package level
```bash
git mv package/tools/corpus/ package/corpus/
```

### Step 2: Move recommenders/ to package level
```bash
git mv package/tools/recommenders/ package/recommenders/
```

### Step 3: Rename score/ to scoring/ within tools/
```bash
git mv package/tools/score/ package/tools/scoring/
```

### Step 4: Rename sql_query/ to sql/ within tools/
```bash
git mv package/tools/sql_query/ package/tools/sql/
```

### Step 5: Update tools/__init__.py
Remove corpus and recommenders exports, update score/scoring and sql_query/sql references:
```python
from ._limits import get_tool_limits, clear_tool_limits_cache
from ._schema import ITEM_COLUMNS, FILTER_KEYS, ORDER_COLUMNS, SCHEMA_HINT
from .base import ToolCallLogger
from .retrieval import SearchTool
from .ranking import SimilarTool, RankTool
from .scoring import BaselineScorer, CandidateScorer  # renamed
from .sql import FilterTool, LookupTool  # renamed
```

### Step 6: Update imports for corpus/ (24 importers)
Mapping: `from package.tools.corpus import` → `from package.corpus import`

### Step 7: Update imports for recommenders/ (31 importers)
Mapping: `from package.tools.recommenders import` → `from package.recommenders import`

### Step 8: Update imports for scoring/ (4 importers)
Mapping: `from package.tools.score import` → `from package.tools.scoring import`

### Step 9: Update imports for sql/ (3 importers)
Mapping: `from package.tools.sql_query import` → `from package.tools.sql import`

### Step 10: Update internal imports within moved directories
- Check corpus/ for internal imports
- Check recommenders/ for internal imports (especially shared/provenance.py self-reference)
- Update relative imports as needed

### Step 11: Update YAML configs
Search for class paths referencing:
- tools.corpus → corpus
- tools.recommenders → recommenders
- tools.score → tools.scoring
- tools.sql_query → tools.sql

### Step 12: Update documentation
- scripts/README.md
- Any README files
- Update path references

## Risk Assessment

- **Risk:** High (59 importers across 3 directories, plus 2 renames)
- **Test impact:** Will break tests until all imports updated
- **Rollback:** `git revert`

## Expected Test Impact

- All tests importing from tools.corpus, tools.recommenders, tools.score, tools.sql_query will fail until imports updated
- After updates, all tests should pass
- No functional changes, only structural and naming

## Rollback Strategy

If issues arise:
1. `git revert` the move commit
2. All imports will revert to original paths
3. No data loss (git mv preserves history)

## Files Touched

- 2 directories moved (corpus/, recommenders/)
- 2 directories renamed (score/ → scoring/, sql_query/ → sql/)
- ~59 importers updated
- ~5 YAML config files (if any)
- ~3 documentation files
- 1 tools/__init__.py file

Total: ~70 files
