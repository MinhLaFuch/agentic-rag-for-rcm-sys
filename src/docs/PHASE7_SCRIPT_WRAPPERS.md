# Phase 7: Script Wrappers Decision

## Overview
Thin wrapper scripts provide convenience CLI entry points for package functions. This document documents the decision on whether to keep or consolidate them.

## Thin Wrapper Scripts

The following scripts are thin wrappers that simply call package functions:

### 1. scripts/evaluation/build_memory_correctness_dataset.py
- **Lines:** 30
- **Purpose:** Generate or check memory correctness dataset
- **Package function:** `package.evaluation.component.benchmarks.build_memory_correctness_dataset`
- **Decision:** KEEP - Provides convenient CLI for dataset generation

### 2. scripts/evaluation/memory_utility_analysis.py
- **Lines:** 22
- **Purpose:** Memory UTILITY analysis
- **Package function:** `package.evaluation.component.benchmarks.memory_utility`
- **Decision:** KEEP - Provides convenient CLI for memory analysis

### 3. scripts/demo/demo_full_agent.py
- **Lines:** 40
- **Purpose:** Demo with full PlanExecutor and 5 tools
- **Note:** This is a MODULE for importing, not a script to run directly (raises SystemExit if run as __main__)
- **Decision:** KEEP - Provides reusable tool wiring for other scripts

### 4. scripts/evaluation/evaluate_product_reply.py
- **Lines:** ~80
- **Purpose:** Product reply evaluation
- **Status:** Import fixed in Phase 1 (was importing non-existent module)
- **Decision:** KEEP - Provides convenient CLI for evaluation

## Decision

**KEEP all thin wrapper scripts** for user convenience.

## Rationale

1. **User convenience:** Scripts provide simple CLI entry points without needing to know package structure
2. **Documentation:** Each script has docstring with usage examples
3. **Organization:** scripts/README.md documents all scripts by category
4. **Low maintenance cost:** Thin wrappers are simple and rarely need changes
5. **Separation of concerns:** Scripts are entry points, package/ contains implementation

## Alternative Considered

**Delete wrappers and use `python -m package.*` directly:**
- Pro: Less code duplication
- Con: Requires users to know package structure
- Con: Less convenient for common tasks
- Con: Would need to document module paths instead of script paths

## Action Items

None required. All wrapper scripts are functional and documented.

## Future Consideration

If the number of scripts grows significantly, consider:
- Consolidating similar wrappers
- Adding more detailed categorization in scripts/README.md
- Creating a script registry or CLI dispatcher
