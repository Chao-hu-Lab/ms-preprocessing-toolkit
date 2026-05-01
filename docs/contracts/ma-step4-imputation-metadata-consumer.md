# MA Step4 Imputation Metadata Consumer Contract

Status: handoff contract v1
Date: 2026-05-01
Audience: MA / `Metaboanalyst_clone` imputation pipeline maintainers
Source contract: `docs/plans/2026-04-30-step4-tag-contract.md`

## Purpose

MS Preprocessing Toolkit Step4 emits feature-level metadata so MA can route
missing-value imputation without re-deriving Step4 feature-filter decisions.

MA is the consumer of Step4 imputation metadata. DNP only carries this metadata
through calibration.

## Required Input Columns

MA should read these kept-feature metadata columns when present:

| Column | Type | MA responsibility |
| --- | --- | --- |
| `is_Presence_Absence_Marker` | boolean-like | Primary imputation routing switch. |
| `Feature_Filter_Keep_Reasons` | string | Audit and reporting. Do not use as the primary routing switch. |
| `Imputation_Tag_Reasons` | string | Audit and optional future routing refinement. |
| `<analysis_group>_ratio` | numeric metadata | Detection evidence for reporting/debugging. |
| `QC_ratio` | numeric metadata | QC detection evidence for reporting/debugging. |

`<analysis_group>_ratio` is dynamic. MA must not assume fixed group names such
as `exposure`, `normal`, or `control`.

For new Step4 handoff files, `is_Presence_Absence_Marker` is required. If it is
missing, MA should treat the input as a pre-contract or invalid file and enter
an explicit legacy path or raise a clear validation error. It should not
silently route all features to one imputation method.

## Primary Routing Rule

MA should treat `is_Presence_Absence_Marker` as the authoritative routing tag:

| Value | Meaning | Current imputation route |
| --- | --- | --- |
| `True` | Feature is not considered safely model-imputable by Step4. | `min positive / 5` |
| `False` | Feature is considered model-imputable by Step4. | selected model-based/default method, currently KNN in downstream presets |

Step4 owns the decision that produces this boolean. MA should not recompute the
boolean from detection ratios unless a future version explicitly changes the
contract.

MA should parse common Excel/CSV boolean encodings consistently:

- true values: `True`, `TRUE`, `true`, `1`, `1.0`
- false values: `False`, `FALSE`, `false`, `0`, `0.0`

Blank or unrecognized values should fail validation for that row. They should
not be coerced to either route.

## Reason Columns

`Feature_Filter_Keep_Reasons` explains why Step4 retained the feature.

Allowed tokens are defined by the upstream Step4 contract. Current tokens:

- `stable`
- `mnar`
- `intensity_fc`
- `ratio_rescue`
- `protected`
- `unfiltered`

`Imputation_Tag_Reasons` explains why
`is_Presence_Absence_Marker=True`.

Current tokens:

- `structural_absence`
- `low_overall_detection`

An empty `Imputation_Tag_Reasons` value is expected when
`is_Presence_Absence_Marker=False`.

MA may use reason columns for reporting, audit, plots, or future method
selection. The current routing contract still uses
`is_Presence_Absence_Marker` as the primary switch.

## Detection Evidence Metadata

Existing numeric ratio columns are the source of truth for detection evidence:

- `<analysis_group>_ratio`, for example `exposure_ratio`, `normal_ratio`,
  `control_ratio`
- `QC_ratio`, when QC samples are present

These columns can be useful for reporting and debugging why a feature was
tagged. They should not be treated as analyte intensity columns.

MA should not depend on `Detection_Profile`.

## Legacy Column

`Detection_Profile` is legacy display-only metadata.

New Step4 outputs must not emit it. If MA receives an older file that still
contains `Detection_Profile`, MA should ignore it for routing and treat it as
metadata only. Numeric `*_ratio` columns are the detection evidence source of
truth.

## Deleted-Feature Diagnostics

Deleted-feature sheets are audit diagnostics, not imputation input.

If MA imports deleted-feature diagnostics for reporting, it may read:

- `Feature_Filter_Delete_Reasons`
- `<analysis_group>_ratio`
- `QC_ratio`

Current delete-reason tokens are:

- `qc_zero`
- `qc_low`
- `no_keep_rule`

Deleted rows should not enter missing-value imputation.

## Missing-Value Method Boundary

The toolkit does not implement imputation. MA owns the actual implementation
of KNN, RF, `min positive / 5`, or any future method.

Current expectation:

- `is_Presence_Absence_Marker=True` routes to `min positive / 5`.
- `is_Presence_Absence_Marker=False` routes to the selected model-based or
  default imputation path.
- Model-based imputation should remain group-label agnostic unless MA
  deliberately changes that contract in a separate MA-side decision.

This contract chooses the route only. The exact implementation details of
`min positive / 5`, KNN, RF, or future methods remain in MA. If MA changes the
scope of `min positive / 5` or the selected model-based method, that should be
documented in MA without changing the Step4 tag semantics.

## Metadata Exclusion Rule

MA numeric analysis matrices must exclude:

- `is_Presence_Absence_Marker`
- `Feature_Filter_Keep_Reasons`
- `Imputation_Tag_Reasons`
- `Feature_Filter_Delete_Reasons`, when deleted diagnostics are loaded
- every Step4 `<analysis_group>_ratio` column
- `QC_ratio`
- legacy `Detection_Profile`, when present

Do not build an analysis matrix by selecting every numeric column. The ratio
columns are numeric metadata and must not be imputed as analytes.

If MA needs detection evidence for reports or plots, it should read the ratio
metadata from the side metadata frame or post-imputation annotation layer, not
from the imputation numeric matrix.

## Acceptance Checklist

An MA implementation is compatible when:

- `is_Presence_Absence_Marker=True` features route to `min positive / 5`.
- `is_Presence_Absence_Marker=False` features route to the selected
  model-based/default imputation method.
- Reason columns are preserved or exposed for audit, but do not override the
  primary boolean routing contract.
- Numeric `*_ratio` and `QC_ratio` columns are excluded from imputation and
  statistical feature matrices.
- Legacy `Detection_Profile`, if present, is ignored for routing.
- Arbitrary analysis group names are supported through dynamic `*_ratio`
  metadata detection.
- Missing or unparseable marker values are reported clearly instead of being
  silently coerced.
