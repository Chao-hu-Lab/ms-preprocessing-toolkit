# Conservative I/O Write Optimization Notes

Date: 2026-03-05
Status: Verification and decision notes

## Scope

- Keep core processing available without requiring parquet intermediates.
- Move machine-only parquet intermediates/caches out of `OUTPUT`.
- Reduce full-run I/O overhead while preserving final xlsx compatibility.

## Performance Gates

- Baseline legacy total runtime: `1497.067` seconds.
- Current unified-parquet-v2 reference runtime: `1763.8` seconds.
- Gate A (required): optimized runtime `<= 1497.067` seconds.
- Gate B (target): optimized runtime `<= 1420.0` seconds.

## Go/No-Go Rule

- If Gate A passes, rollout can proceed.
- If Gate A fails, keep previous behavior and do not switch the release baseline.

## Rollback Criteria

- Any failure of Gate A in full-dataset validation.
- Any regression in final output schema or DNP xlsx bridge compatibility.
- Any pipeline path that becomes dependent on parquet availability.

## Rollback Actions

- Revert to previous runtime behavior with stable delivery path.
- Keep final `.xlsx` output contract unchanged.
- Re-run full dataset verification and archive timing evidence.
