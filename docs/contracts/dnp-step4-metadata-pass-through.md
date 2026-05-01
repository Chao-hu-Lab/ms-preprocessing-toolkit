# DNP Step4 Metadata Pass-Through Contract

Status: handoff contract v1
Date: 2026-05-01
Audience: DNP calibration pipeline maintainers
Source contract: `docs/plans/2026-04-30-step4-tag-contract.md`

## Purpose

MS Preprocessing Toolkit Step4 now emits metadata that controls downstream
missing-value routing in MA. DNP is a calibration pipeline. Its responsibility
is to keep this metadata out of numeric calibration matrices while preserving
it row-by-row for MA.

DNP must not reinterpret Step4 imputation semantics.

## Input Expectation

DNP may receive a kept-feature matrix exported after Step4. That matrix can
contain sample intensity columns plus Step4 metadata columns.

Step4 metadata is feature-level metadata. It is not sample intensity data,
even when the values are numeric.

## Kept-Feature Metadata Columns

DNP must recognize and preserve these columns when present:

| Column | Type | DNP responsibility |
| --- | --- | --- |
| `is_Presence_Absence_Marker` | boolean-like | Preserve unchanged. Do not use for calibration decisions. |
| `Feature_Filter_Keep_Reasons` | string | Preserve unchanged. |
| `Imputation_Tag_Reasons` | string | Preserve unchanged. |
| `<analysis_group>_ratio` | numeric metadata | Preserve unchanged; exclude from numeric calibration matrix. Examples: `exposure_ratio`, `normal_ratio`, `control_ratio`. |
| `QC_ratio` | numeric metadata | Preserve unchanged; exclude from numeric calibration matrix. |

`<analysis_group>_ratio` is dynamic. DNP must not hardcode only known group
names.

Recommended detection:

1. If SampleInfo or workflow metadata is available, derive the analysis group
   names from it and exclude `<group>_ratio` for every analysis group.
2. Always exclude `QC_ratio` when present.
3. If explicit group metadata is unavailable, conservatively exclude Step4
   detection columns matching `*_ratio` from the analyte intensity matrix.
   Any non-Step4 ratio column that DNP intentionally wants to calibrate must
   be opt-in allowlisted, not included by default.

## Deleted-Feature Diagnostics

If DNP receives or passes through a deleted-feature diagnostic sheet, it must
recognize and preserve these metadata columns:

| Column | Type | DNP responsibility |
| --- | --- | --- |
| `Feature_Filter_Delete_Reasons` | string | Preserve unchanged. |
| `<analysis_group>_ratio` | numeric metadata | Preserve unchanged; never treat as intensity data. |
| `QC_ratio` | numeric metadata | Preserve unchanged; never treat as intensity data. |

Deleted-feature diagnostics are not calibration input. They are audit output.

## Legacy Column

`Detection_Profile` is legacy display-only metadata.

New Step4 outputs must not emit it. If an older input file still contains
`Detection_Profile`, DNP must treat it as metadata, never as a sample intensity
column. DNP should preserve it if the pipeline is doing generic metadata
pass-through, but it must not synthesize or depend on this column.

## Calibration Matrix Rules

DNP numeric calibration matrices must exclude:

- `is_Presence_Absence_Marker`
- `Feature_Filter_Keep_Reasons`
- `Imputation_Tag_Reasons`
- `Feature_Filter_Delete_Reasons`, when a deleted-feature sheet is handled
- every Step4 `<analysis_group>_ratio` column
- `QC_ratio`
- legacy `Detection_Profile`, when present

Do not build the calibration matrix by selecting every numeric column. The
ratio columns are numeric, but they are metadata. Selecting all numeric
columns is the main failure mode this contract is meant to prevent.

Preferred behavior:

1. Identify sample intensity columns from SampleInfo or an explicit sample
   column list.
2. Run calibration only on those sample intensity columns.
3. Reattach preserved metadata columns to the same feature rows after
   calibration.

## Row Preservation

For every output feature row that originates from Step4, DNP must preserve the
corresponding metadata values on the same feature row.

If DNP keeps original row order, row-wise carryover is acceptable. If DNP
sorts, filters, joins, or reshapes rows, it must use a stable feature identity
column or equivalent join key so metadata does not drift to the wrong feature.

If DNP filters features, it only needs to preserve metadata for rows that
remain in the calibrated output. It must not silently move metadata between
features. If a stable join key is unavailable after reshaping, the safer
behavior is to fail with a clear error instead of emitting a potentially
misaligned file.

## DNP Non-Responsibilities

DNP must not:

- decide whether a feature should use `min positive / 5`
- decide whether a feature should use KNN, RF, or another model-based method
- reinterpret `Feature_Filter_Keep_Reasons`
- reinterpret `Imputation_Tag_Reasons`
- derive new Step4 tags from detection ratios
- recreate `Detection_Profile`

Those decisions belong to Step4 and MA.

## Missing Or Extra Metadata

For new Step4 handoff files, DNP should expect the kept-feature metadata
columns listed above. If a required pass-through column is missing, DNP may
still calibrate the intensity matrix, but it should preserve a clear warning
or log entry so MA maintainers can distinguish a pre-contract file from a
metadata-loss bug.

DNP may carry additional non-intensity metadata columns through unchanged.
The key rule is conservative: unknown metadata may be preserved, but it must
not be included in the numeric calibration matrix unless explicitly
allowlisted as an analyte intensity column.

## Acceptance Checklist

A DNP implementation is compatible when:

- Step4 metadata columns are absent from calibration numeric matrices.
- Numeric `*_ratio` columns do not influence calibration.
- All Step4 metadata columns are still present in the output passed to MA.
- Metadata values remain attached to the correct feature rows.
- Legacy `Detection_Profile`, if present, is treated as metadata only.
- DNP can process files with arbitrary analysis group names, not only
  `exposure`, `normal`, and `control`.
- Missing Step4 metadata creates an explicit warning or legacy-path signal,
  not silent metadata loss.
