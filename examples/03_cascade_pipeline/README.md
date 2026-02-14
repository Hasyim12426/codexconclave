# Example 03: Cascade Data Analysis Pipeline

An event-driven pipeline that ingests raw student data, cleans it,
computes statistics, and produces a formatted report — all without
any LLM calls.

## What This Shows

- `@initiate` — pipeline entry point
- `@observe(method)` — run after a specific method completes
- Multiple `@observe` methods running after the same upstream method
- `@route` — conditionally branch to different report generators
- Typed `CascadeState` for structured pipeline state
- `CascadeResult` with completed methods and execution time

## Pipeline Graph

```
ingest
  └─► clean
        ├─► compute_stats
        ├─► identify_top_students
        └─► check_for_outliers
              └─► decide_report_type (@route)
                    ├─► generate_detailed_report
                    └─► generate_standard_report
```

## Prerequisites

```bash
pip install codexconclave
```

No API keys required — all processing is pure Python.

## Run

```bash
python main.py
```

## Expected Output

```
==================================================
STUDENT PERFORMANCE REPORT
==================================================

MATH
  Students:   3
  Average:    90.3
  Highest:    95
  Lowest:     87
...

TOP PERFORMERS (score ≥ 90)
  Alice, Dave

DATA QUALITY NOTES
  3 record(s) were removed due to missing or out-of-range scores.
==================================================

Pipeline completed 7 method(s) in 2.1ms.
```

## Key Concepts

```python
class MyPipeline(Cascade):
    state: MyState = MyState()

    @initiate
    def start(self):
        return "initial value"

    @observe(start)          # runs after start()
    def process(self, value):
        return value.upper()

    @route
    def branch(self):
        return "path_a" if condition else "path_b"

    def path_a(self):
        ...
```
