# Review Checklist

Use this checklist when producing a formal code review report.

## 1. Blockers First

- Verify syntax/import startup:
  - `python -m compileall -q src/ms_preprocessing`
  - `python main.py --version`
- Verify baseline tests:
  - `pytest -q`

## 2. Severity Rubric

- `Critical`
  - Application cannot start.
  - Core command crashes.
  - Data loss/corruption risk.
- `High`
  - Incorrect scientific result or filtering logic.
  - Core workflow regression.
  - Incorrect row/metadata mapping in pipeline stages.
- `Medium`
  - Performance or reliability issues that can degrade production usage.
  - Incomplete error handling with hidden failures.
  - Risky assumptions around file formats/edge cases.
- `Low`
  - Readability, consistency, maintainability nits.

## 3. Findings Format

For each finding:

1. Severity + short title
2. Why this is a risk (1-2 lines)
3. Evidence with exact file/line reference
4. Minimal fix direction

## 4. Required Coverage Notes

- Mention what was verified:
  - tests run or not run
  - syntax checks run or not run
- Mention residual risk:
  - missing integration test
  - environment-specific behavior not exercised
