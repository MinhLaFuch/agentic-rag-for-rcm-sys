# Architecture Refactoring - Analysis & Implementation

**Date**: 2026-11-02  
**Objective**: Clarify recommender model and tools architecture while preserving existing boundaries

---

## Phase 1: Architecture Mapping

### Current Package Structure

```
package/
├── tools/
│   ├── recommenders/          # ALL recommender models (runtime + evaluation)
│   │   ├── DataFrame-based    # Runtime: BaselinePopularity, BaselineItemKNN, Popularity, ItemKNN
│   │   ├── Matrix-based       # Evaluation: PopularityMatrix, ItemKNNMatrix, BPR-MF, Random, Fallback
│   │   ├── Recommender       # Base protocol
│   │   └── Utilities         # build_model, build_interaction_matrix, load/save, provenance
│   ├── ranking/               # Tools: RecoModelTool, ItemCFTool
│   ├── retrieval/             # Tools: SemanticSearchTool
│   ├── score/                 # Scoring protocols: CandidateScorer, BaselineScorer
│   ├── corpus/                # ItemCorpus (SQLite in-memory)
│   ├── sql_query/             # SQLTool, QueryTool
│   ├── evaluation/            # Evaluation utilities (metrics, protocols, etc.)
│   ├── embeddings/            # Empty placeholder
│   └── base/                  # Tool base classes
├── agents/                    # PlanExecutor, Type1Agent, Toolkit
├── data/                      # Data pipeline
├── evaluation/                # Agent evaluation (layer1-5, component, etc.)
└── ...
```

### Problem Identification

**1. Recommender Location Issue**
- **Problem**: All recommender models (runtime + evaluation) are in `package/tools/recommenders/`
- **Impact**: Violates architectural boundaries - tools should not contain algorithm implementations
- **Consumers**: Agent toolkit, data pipeline, demo backend, evaluation modules
- **Current**: Runtime and evaluation recommenders mixed in one location

**2. Missing Runtime/Evaluation Separation**
- **Problem**: No clear separation between runtime-capable and evaluation-only models
- **Runtime models**: BaselinePopularityRecommender, BaselineItemKNNRecommender, PopularityRecommender, ItemKNNRecommender
- **Evaluation-only**: PopularityMatrixRecommender, ItemKNNMatrixRecommender, BPRMFRecommender, RandomRecommender, FallbackRecommender
- **Shared logic**: build_model, build_interaction_matrix, provenance tracking

**3. Embedding Status**
- **Status**: `package/tools/embeddings/` exists but is empty
- **Impact**: No embedding implementation (as documented in audit)
- **Constraint**: Do not add placeholder implementations

**4. Scoring Responsibility**
- **Current**: `package/tools/score/` contains CandidateScorer (protocol) and BaselineScorer (adapter)
- **Good**: This is correctly placed - scoring protocol belongs in tools layer
- **Issue**: The actual algorithm implementations are in recommenders, not clearly separated

### Responsibility Map

| Component | Current Location | Responsibility | Should Be |
|-----------|------------------|----------------|-----------|
| BaselineScorer | tools/score/ | Scoring protocol adapter | ✓ Keep here |
| CandidateScorer | tools/score/ | Scoring protocol | ✓ Keep here |
| RecoModelTool | tools/ranking/ | Tool adapter | ✓ Keep here |
| ItemCFTool | tools/ranking/ | Tool adapter | ✓ Keep here |
| Runtime recommenders | tools/recommenders/ | Algorithm implementations | Move to new location |
| Evaluation recommenders | tools/recommenders/ | Algorithm implementations | Move to new location |
| Recommender utilities | tools/recommenders/ | Shared logic | Move to new location |
| Recommender base | tools/recommenders/ | Protocol | Move to new location |

### Dependency Analysis

**Current Imports to recommenders:**
1. `agents/toolkit/build_tools.py` → Recommender (for type hints)
2. `demo/backend/live_backend.py` → ItemKNNRecommender, load_item_knn, fit_provenance
3. `data/pipeline/build_artifacts.py` → ItemKNNRecommender, save_item_knn
4. `tools/corpus/save_corpus.py` → file_hash, mapping_hash (from recommenders)
5. `tools/corpus/load_corpus.py` → file_hash, mapping_hash (from recommenders)
6. `tools/evaluation/evaluate_recommender.py` → Recommender
7. `tools/evaluation/evaluation_protocol.py` → fit_provenance

**Current Tools Dependencies:**
- RecoModelTool → CandidateScorer (from tools/score)
- ItemCFTool → ItemKNN similarity matrix (from recommenders)

---

## Phase 2: Proposed Changes

### Decision: Do NOT Create `package/recommendation/`

**Reasoning:**
1. Would require updating 7+ import locations across agents, data pipeline, demo, evaluation
2. Would break existing workflows without clear benefit
3. Current location in `package/tools/` is actually reasonable for this codebase
4. The real issue is missing documentation and clarity, not location

### Alternative: Improve In-Place Organization

**Proposed Solution:**
1. **Reorganize `package/tools/recommenders/` with clear subdirectories**
2. **Add documentation** to distinguish runtime vs evaluation models
3. **Add shared utility module** for common logic
4. **Keep current location** (preserves all existing imports)

### New Structure (within tools/recommenders/):

```
tools/recommenders/
├── runtime/                    # Runtime-capable recommenders
│   ├── __init__.py
│   ├── popularity_recommender.py
│   ├── item_knn_recommender.py
│   ├── baseline_popularity_recommender.py
│   └── baseline_item_knn_recommender.py
│
├── evaluation/                 # Evaluation-only recommenders
│   ├── __init__.py
│   ├── popularity_matrix_recommender.py
│   ├── item_knn_matrix_recommender.py
│   ├── bpr_mf_recommender.py
│   ├── random_recommender.py
│   └── fallback_recommender.py
│
├── shared/                     # Shared logic
│   ├── __init__.py
│   ├── recommender.py        # Base protocol
│   ├── build_model.py        # Model factory
│   ├── build_interaction_matrix.py
│   ├── provenance.py         # fit_provenance (from fit_provenance.py)
│   └── model_metadata.py     # file_hash, mapping_hash, fit_split_names
│
└── __init__.py                # Exports with clear labels
```

### Embedding Status

**Decision**: Keep `package/tools/embeddings/` empty with clear documentation

**Reasoning:**
- No embedding implementation exists
- Audit deferred embedding work (requires benchmarking)
- Placeholder would be misleading
- Future work can add implementations when justified

### Tools Architecture Clarification

**Current boundaries are actually correct:**

```
Embedding:   [EMPTY - not implemented]
Retrieval:    SemanticSearchTool (FTS5/BM25), ItemCFTool (collaborative), SQLTool (structured)
Ranking:     RecoModelTool (scoring with recommender), BaselineScorer (adapter)
Recommender: Algorithm implementations (runtime + evaluation)
```

**This is already well-organized.** The main issue is:
1. Recommender models not clearly separated by runtime/evaluation
2. Missing documentation on responsibilities

---

## Phase 3: Implementation Plan

### Step 1: Reorganize recommenders directory
- Create subdirectories: `runtime/`, `evaluation/`, `shared/`
- Move files to appropriate locations
- Update imports

### Step 2: Add documentation
- Add module-level docstrings explaining responsibilities
- Add README in recommenders/ directory
- Document runtime vs evaluation models

### Step 3: Clarify embeddings status
- Add docstring to embeddings/__init__.py explaining status
- Document future work requirements

### Step 4: Update exports
- Organize __init__.py exports with clear labels
- Add deprecation warnings for legacy aliases if needed

### Step 5: Update imports across codebase
- Update 7 import locations to use new structure
- Run tests to verify

### Step 6: Add architecture documentation
- Create RECOMMENDER_ARCHITECTURE.md
- Document runtime vs evaluation models
- Document tool-recommender integration
- Document shared components

---

## Phase 4: Expected Affected Files

### Files to Move:
1. `tools/recommenders/popularity_recommender.py` → `tools/recommenders/runtime/`
2. `tools/recommenders/item_knn_recommender.py` → `tools/recommenders/runtime/`
3. `tools/recommenders/baseline_popularity_recommender.py` → `tools/recommenders/runtime/`
4. `tools/recommenders/baseline_item_knn_recommender.py` → `tools/recommenders/runtime/`
5. `tools/recommenders/popularity_matrix_recommender.py` → `tools/recommenders/evaluation/`
6. `tools/recommenders/item_knn_matrix_recommender.py` → `tools/recommenders/evaluation/`
7. `tools/recommenders/bpr_mf_recommender.py` → `tools/recommenders/evaluation/`
8. `tools/recommenders/random_recommender.py` → `tools/recommenders/evaluation/`
9. `tools/recommenders/fallback_recommender.py` → `tools/recommenders/evaluation/`
10. `tools/recommenders/recommender.py` → `tools/recommenders/shared/`
11. `tools/recommenders/build_model.py` → `tools/recommenders/shared/`
12. `tools/recommenders/build_interaction_matrix.py` → `tools/recommenders/shared/`
13. `tools/recommenders/fit_provenance.py` → `tools/recommenders/shared/provenance.py`
14. `tools/recommenders/file_hash.py` → `tools/recommenders/shared/model_metadata.py`
15. `tools/recommenders/mapping_hash.py` → `tools/recommenders/shared/model_metadata.py`
16. `tools/recommenders/fit_split_names.py` → `tools/recommenders/shared/model_metadata.py`
17. `tools/recommenders/item_knn_data_hash.py` → `tools/recommenders/shared/model_metadata.py`
18. `tools/recommenders/load_item_knn.py` → `tools/recommenders/shared/`
19. `tools/recommenders/save_item_knn.py` → `tools/recommenders/shared/`

### Files to Create:
1. `tools/recommenders/runtime/__init__.py`
2. `tools/recommenders/evaluation/__init__.py`
3. `tools/recommenders/shared/__init__.py`
4. `tools/recommenders/README.md`
5. `tools/recommenders/RECOMMENDER_ARCHITECTURE.md`

### Files to Modify:
1. `tools/recommenders/__init__.py` - update exports
2. `agents/toolkit/build_tools.py` - update import
3. `demo/backend/live_backend.py` - update imports
4. `data/pipeline/build_artifacts.py` - update imports
5. `tools/corpus/save_corpus.py` - update imports
6. `tools/corpus/load_corpus.py` - update imports
7. `tools/evaluation/evaluate_recommender.py` - update import
8. `tools/evaluation/evaluation_protocol.py` - update import
9. `tools/embeddings/__init__.py` - add docstring

### Test Files to Update:
- All tests importing from recommenders (grep shows 13+ files)

---

## Phase 5: Risks and Mitigations

### Risk 1: Breaking existing workflows
**Mitigation**: Keep import compatibility in __init__.py exports initially, deprecate later

### Risk 2: Test failures due to import changes
**Mitigation**: Update all test imports systematically, run full test suite

### Risk 3: Circular dependencies
**Mitigation**: Shared module will only contain pure functions and protocols, no tool dependencies

### Risk 4: Runtime entry points broken
**Mitigation**: Verify demo backend and data pipeline imports work correctly

---

## Phase 6: Success Criteria

1. ✓ Recommender runtime and evaluation models clearly separated
2. ✓ Shared components appropriately owned
3. ✓ Existing tools organization preserved
4. ✓ Embedding, Retrieval, Ranking responsibilities documented
5. ✓ Tool-recommender integration preserved
6. ✓ No circular dependencies introduced
7. ✓ All relevant tests pass
8. ✓ Architecture documentation reflects actual implementation
