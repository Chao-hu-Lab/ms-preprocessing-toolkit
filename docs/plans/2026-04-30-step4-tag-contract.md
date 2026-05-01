# Step4 Imputation Tag Contract

Status: contract v3
Date: 2026-04-30 (v1) / 2026-05-01 (v2/v3 revisions)
Supersedes: `2026-04-30-step4-tag-contract.md` v1 (in-place revision)
Sits alongside: `2026-04-30-step4-imputation-tag-discussion.md`

## Revision Notes (v3)

- **Detection evidence source-of-truth clarified**: `Detection_Profile` is
  removed from the formal output contract. It duplicated existing numeric
  `<analysis_group>_ratio` columns, rounded values to two decimals, and
  created a second source of truth.
- **Numeric ratio metadata retained**: Step4 must preserve
  `<analysis_group>_ratio` columns and `QC_ratio` as feature-level metadata.
  These columns are the audit source for detection evidence.
- **Downstream responsibility boundary corrected**: DNP does not interpret
  Step4 tags. DNP must exclude these metadata columns from calibration
  matrices and pass them through to MA. MA owns imputation routing.

## Revision Notes (v2)

- **Critical fix**: representative cases table v1 misclaimed three tag-flip
  cases. Re-derivation against the existing keep gate thresholds shows the
  actual flips occur on different patterns. Table now includes one verified
  `True -> False` flip (`0.42/0.35/0.20`) and one verified `False -> True`
  flip (`0.25/0.22/0.18`), with both directions traceable to specific
  decision-rule clauses. The Versioning Note rationale is rewritten.
- **Schema clarification**: deleted-feature diagnostic rows now have an
  explicit audit policy (carry `Feature_Filter_Delete_Reasons`; numeric
  ratio columns remain on the original row).
- **Ordering decisions promoted**: token order for
  `Feature_Filter_Keep_Reasons`, `Imputation_Tag_Reasons`, and
  `Feature_Filter_Delete_Reasons` is now part of the contract instead of an
  open item, since these are public string outputs.
- **Single-group guard**: explicit clause that `structural_absence` does not
  apply when `n_analysis_groups < 2`.
- **Review fixes**: deleted-feature diagnostics now distinguish QC override
  deletion from no-keep-rule deletion; `structural_absence` now requires a
  non-zero contrast group; background threshold semantics are explicit when
  `enable_background_threshold=False`.
- **Unfiltered mode**: the existing all-keep-gates-disabled retain-all
  behavior now has an explicit `unfiltered` keep-reason token.

## Scope

This document defines the **contract** for Step4 imputation tagging. It does
not describe implementation steps, file edits, or test plans; those belong
to a separate implementation plan that should reference this contract as
the source of truth for expected behavior.

In scope:

- Definition of keep gate vs evidence reason vs imputation tag.
- Decision rule for `is_Presence_Absence_Marker`.
- Output schema additions and their semantics, including kept and deleted
  feature paths.
- Token and group ordering in public string columns.
- Expected values for representative detection patterns, including
  verified tag-flip cases.
- Compatibility boundary for downstream consumers such as
  `Metaboanalyst_clone`.

Out of scope:

- Random Forest, GSimp, QRILC, or any non-`min/N` imputation method.
- KNN/RF imputation implementation or verification inside this repository.
  The toolkit emits the tag and audit schema; downstream projects own the
  actual imputation behavior.
- An `Imputation_Method_Hint` column. The current contract keeps the
  existing boolean tag and only enriches the audit metadata.
- Calibration or statistical analysis module changes (only the rule that
  they must exclude the new metadata columns from numeric feature
  matrices).

## Concept Separation

Step4 has historically conflated two questions. This contract separates
them into three:

1. **Keep gate** — should this feature survive Step4?
   Driven by the existing `stable_keep`, `mnar_keep`, `intensity_fc_keep`,
   `ratio_rescue_keep`, and `protected_mask` rules. **Not changed by this
   contract.**

2. **Evidence reason** — *why* was this feature kept?
   Captured as a pipe-joined string. Multiple reasons may apply.

3. **Imputation tag** — should the downstream imputer treat this feature as
   model-imputable, or fall back to `min positive / 5`?
   Captured as the existing boolean `is_Presence_Absence_Marker` plus a
   new reason audit column.

The existing rule
`is_Presence_Absence_Marker = mnar_keep OR ratio_rescue_keep` is replaced
by the rule defined below.

## Decision Rule

### Definitions

Let `analysis_ratio_matrix` be the per-group detection ratio matrix
restricted to **analysis groups only** (QC group is excluded). Let
`n_analysis_groups` be the number of analysis groups.

```
all_groups_pass_background  = analysis_ratio_matrix >= background_threshold
                              evaluated for every analysis group
                              (boolean per feature)

any_group_zero              = any analysis group has detection_ratio == 0.0
                               (exact equality; upstream fillna(0) guarantees
                               exact zero for missing/absent groups)

any_group_nonzero           = any analysis group has detection_ratio > 0.0

structural_absence_applies  = (n_analysis_groups >= 2)
                              AND any_group_zero
                              AND any_group_nonzero
                              i.e. zero only counts as structural absence
                              when at least one contrast group has observed
                              detection

model_imputable             = all_groups_pass_background
                              AND NOT structural_absence_applies
```

### Tag rule

```
is_Presence_Absence_Marker = NOT model_imputable
```

Equivalently, tag is True when **either** of these holds:

- structural_absence_applies (a zero analysis group exists and at least
  one other analysis group has non-zero detection)
- some analysis group has detection_ratio < background_threshold

### Single analysis group

When `n_analysis_groups == 1`:

- `structural_absence_applies` is False by construction. A single group
  cannot be "structurally absent" because there is no contrast group.
  A zero-detection single-group feature is normally not retained by the
  positive keep gates, but it can still be retained by `protected_mask` or
  by the existing "all keep gates disabled" unfiltered mode.
- `all_groups_pass_background` degrades to "the single analysis group
  passes background_threshold".
- This applies if and only if `allow_single_group_stable` is enabled (the
  existing option that already governs positive single-group stable keep
  behavior).
- If `allow_single_group_stable` is disabled, single-group runs do not
  produce features through the stable keep gate, but protected rows and
  unfiltered mode can still produce kept rows and must still receive a tag.

### Background enable flag

`enable_background_threshold` controls the keep gate's `stable_keep` rule
only. It does **not** disable the imputation tag's model-imputable
detection floor.

The tag rule always evaluates `all_groups_pass_background` against
`background_threshold` for kept features, regardless of whether
`stable_keep` was enabled as a keep reason. This is intentional: the same
threshold is used as a methodological reliability floor for model
imputation, not only as a keep rule.

### QC group

QC group **does not participate** in the imputation tag rule. QC handling
is limited to the existing `qc_force_delete` logic in the keep gate. QC
detection ratios never feed `all_groups_pass_background` or
`any_group_zero`.

## Three-Tier Mental Model

The decision rule produces three tiers, even though only two routing paths
exist downstream:

| Tier | Condition | Tag | Downstream routing today | Possible routing later |
| --- | --- | --- | --- | --- |
| 1 model-imputable | all analysis groups >= background AND not structural_absence | False | selected default/model-based method (KNN in current downstream presets) | KNN or RF |
| 2 left-censored | not structural_absence, but at least one group < background | True | `min/5` | `min/5` or RF |
| 3 structural-absence | structural_absence applies | True | `min/5` | `min/5` |

Tier 2 and Tier 3 collapse into the same boolean today. They are
distinguished by `Imputation_Tag_Reasons` so future routing can
differentiate them without breaking the boolean contract.

## Output Schema Additions

### Kept Features

Step4 retains:

- `is_Presence_Absence_Marker` (existing, boolean).

Step4 adds two feature-level metadata columns, inserted in this order
immediately after `is_Presence_Absence_Marker`:

1. **`Feature_Filter_Keep_Reasons`** (string, pipe-joined)
   - At least one token whenever `keep_mask == True`.
   - The existing "all keep gates disabled" mode satisfies this through
     the `unfiltered` token defined below.

2. **`Imputation_Tag_Reasons`** (string, pipe-joined; empty when tag is
   False)
   - Possible tokens listed under "Token And Group Ordering" below.

`Detection_Profile` is **not** part of the formal contract. Detection
evidence is represented by numeric ratio metadata columns already produced
by Step4:

- `<analysis_group>_ratio`, for example `exposure_ratio`, `normal_ratio`,
  `control_ratio`
- `QC_ratio`, when QC samples are present

These ratio columns are feature-level metadata, not sample intensity
columns. They are the source of truth for detection audit and must not be
replaced by a rounded display string.

These two audit columns are always emitted (not gated behind a profile flag)
so downstream schema is stable.

### Deleted Features

The diagnostic `deleted_features` list carries one additional column:

1. **`Feature_Filter_Delete_Reasons`** (string, pipe-joined)

`Feature_Filter_Keep_Reasons` and `Imputation_Tag_Reasons` are
kept-feature concepts and do not apply to deleted rows.

Rationale:

- Some deleted rows fail all keep rules. Others can first match a positive
  keep rule such as `stable` or `intensity_fc`, then be deleted by
  `qc_force_delete`. A delete-reason column keeps those cases
  diagnosable without overloading kept-feature reason columns.
- `Imputation_Tag_Reasons` is a routing concept for kept features only;
  applying it to deleted features is a category error.
- Existing numeric ratio columns remain on deleted rows and provide the
  per-feature detection evidence for deletion diagnostics.

The deleted-feature output schema therefore extends the original feature
row schema by exactly one column (`Feature_Filter_Delete_Reasons`).

## Token And Group Ordering

These ordering decisions are part of the contract because they appear in
public string output that downstream parsers may depend on. They are
**not** open items.

### Feature_Filter_Keep_Reasons

Token order is fixed:

```
stable | mnar | intensity_fc | ratio_rescue | protected | unfiltered
```

Tokens appear only when the corresponding mask is True for that feature.
Joined by `|` with no spaces. Examples:

- `stable|mnar` (a Tier 3 feature kept by both rules)
- `ratio_rescue` (a Tier 2 feature kept only by ratio rescue)
- `protected` (a feature kept by the protected-rows mechanism even when
  no positive rule fired)
- `unfiltered` (a feature retained only because all positive keep gates
  were disabled, causing the existing retain-all Step4 behavior)

`unfiltered` is mutually exclusive with the positive keep-rule tokens. If
a feature is protected in unfiltered mode, `protected` is emitted instead
of `unfiltered`.

### Imputation_Tag_Reasons

Token order is fixed:

```
structural_absence | low_overall_detection
```

Same join rule. Examples:

- `low_overall_detection` (Tier 2)
- `structural_absence|low_overall_detection` (Tier 3; the zero group is
  itself below background, so structural absence also carries the
  low-overall reason)
- `""` (empty; Tier 1, model-imputable)

### Feature_Filter_Delete_Reasons

Token order is fixed:

```
qc_zero | qc_low | no_keep_rule
```

Tokens appear only for deleted-feature diagnostic rows:

- `qc_zero`: deleted by QC force-delete because QC detection is exactly 0.
- `qc_low`: deleted by QC force-delete because QC detection is below
  `qc_ratio`.
- `no_keep_rule`: deleted because no positive keep rule and no protected
  rule retained the feature.

Examples:

- `no_keep_rule`
- `qc_low`
- `qc_low|no_keep_rule`

## Representative Cases

Background threshold = 0.20. Three analysis groups (A, B, C) unless
otherwise noted. QC excluded. Other thresholds at preset defaults
(`high_det_thresh=0.30`, `low_det_thresh=0.10`, `ratio_rescue=2.0`,
`ratio_rescue floor=0.10`).

| Detection (A/B/C) | Keep? | Keep Reasons | Tag (legacy `mnar OR ratio_rescue`) | Tag (this contract) | Flip? | Tag Reasons | Tier |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `0.80/0.42/0.00` | True | `stable\|mnar` | True | True | — | `structural_absence\|low_overall_detection` | 3 |
| `0.45/0.42/0.00` | True (loose) | `stable\|mnar` | True | True | — | `structural_absence\|low_overall_detection` | 3 |
| `0.42/0.35/0.08` | True | `stable\|mnar` | True | True | — | `low_overall_detection` | 2 |
| `0.32/0.16/0.11` | True | `ratio_rescue` | True | True | — | `low_overall_detection` | 2 |
| `0.42/0.35/0.20` | True | `stable\|ratio_rescue` | **True** | **False** | **True -> False** | `""` | 1 |
| `0.80/0.42/0.42` | True | `stable` | False | False | — | `""` | 1 |
| `0.80/0.00/0.00` | True | `mnar` | True | True | — | `structural_absence\|low_overall_detection` | 3 |
| `0.25/0.22/0.18` | True | `stable` | **False** | **True** | **False -> True** | `low_overall_detection` | 2 |
| `0.20/0.20/0.20` | True | `stable` | False | False | — | `""` | 1 |
| `0.18/0.18/0.18` | False | n/a | n/a | n/a | n/a | n/a | n/a |

### Notes On Flip Cases

`0.42/0.35/0.20` (legacy True -> contract False):

- Legacy: `ratio_rescue_keep` is True (max/min = 2.1 >= 2.0; min = 0.20 >=
  0.10 floor). Legacy OR rule sets tag True.
- Contract: all three groups >= background_threshold (0.20 == 0.20 passes
  by inclusive comparison) AND no zero group, so `model_imputable` is
  True; tag is False.
- Methodological reading: this feature has even, marginal detection across
  groups with no structural absence. Routing to the downstream
  default/model-based imputation path is now considered appropriate; the
  legacy rule was overly aggressive in marking it as presence/absence.

`0.25/0.22/0.18` (legacy False -> contract True):

- Legacy: `mnar_keep` False (no group >= high_det 0.30); `ratio_rescue`
  False (max/min = 1.39 < 2.0). Legacy OR rule sets tag False.
- Contract: group C at 0.18 fails `background_threshold`, no zero group;
  tag True with reason `low_overall_detection`.
- Methodological reading: previously this feature would have been routed
  to the downstream default/model-based imputation path despite all three
  groups being marginal, where model-based estimates are less reliable. New
  rule routes it to `min/5`.

### Notes On Boundary Cases

- `0.42/0.35/0.20`: group C is exactly at threshold; the rule uses
  `>= background_threshold`, so this passes Tier 1.
- `0.20/0.20/0.20`: all groups exactly at threshold. Same comparison rule
  applies; Tier 1, tag False. Included to verify inclusive comparison
  semantics.
- `0.32/0.16/0.11`: kept only by `ratio_rescue`. The keep reason is
  `ratio_rescue`, but the tag reason is `low_overall_detection`. The tag
  describes imputation risk, not keep mechanism.
- `0.18/0.18/0.18`: no keep rule fires. Does not reach the tag stage.
  Appears in `deleted_features` with `Feature_Filter_Delete_Reasons`; the
  existing ratio columns remain on the diagnostic row.
- A protected all-zero feature (`0.00/0.00/0.00`) is kept by
  `protected`, is not `structural_absence`, and is tagged True via
  `low_overall_detection`. This prevents "structural absence" from being
  assigned when there is no non-zero contrast group.

## Boundary Conditions

- `n_analysis_groups == 1` and `allow_single_group_stable == True`:
  - Tag is False if and only if that group's detection >=
    background_threshold.
  - `Imputation_Tag_Reasons` is `low_overall_detection` if the single
    group is below background; `structural_absence` does not apply.

- `n_analysis_groups == 0` (degenerate): contract is undefined; Step4
  must not silently emit features. Implementations should raise.

- Detection ratio exactly equal to `background_threshold`: counts as
  "passes" (inclusive `>=`).

- Detection ratio NaN (missing column or all-zero divisor): treated as 0
  by the existing `pd.to_numeric(...).fillna(0)` upstream. The tag rule
  sees this as a zero group and produces `structural_absence` if there is
  a contrast group.

- Floating-point near-zero values: the contract specifies exact equality
  with 0.0. Upstream is responsible for ensuring detection ratios are
  produced as exact zero when no samples in a group have signal. If
  upstream introduces sub-epsilon noise (e.g., `1e-15`), it must be
  rounded or clamped before reaching the decision rule. This is not the
  decision rule's responsibility.

- `enable_background_threshold == False`: disables `stable_keep` as a keep
  reason only. It does not disable the tag rule's use of
  `background_threshold` as the model-imputable detection floor.

## Downstream Contract

1. Toolkit Step4 emits feature-level metadata. DNP is a calibration
   pipeline and must not interpret this metadata for imputation decisions.
   DNP's responsibility is to exclude the metadata from numeric
   calibration matrices, preserve it row-by-row, and pass it through to MA.

2. The external downstream imputation router, currently
   `Metaboanalyst_clone` / MA, reads `is_Presence_Absence_Marker` as the
   boolean switch between `min/5` and the selected model-based/default
   imputation method. MA may additionally use `Imputation_Tag_Reasons` and
   ratio metadata for reporting/audit.

3. Kept-feature outputs define this metadata exclusion/pass-through set:
   - `is_Presence_Absence_Marker`
   - `Feature_Filter_Keep_Reasons`
   - `Imputation_Tag_Reasons`
   - every `<analysis_group>_ratio` column
   - `QC_ratio`

4. Deleted-feature diagnostic outputs define this metadata
   exclusion/pass-through set:
   - `Feature_Filter_Delete_Reasons`
   - every `<analysis_group>_ratio` column
   - `QC_ratio`

5. Calibration, statistical analysis, final export modules, and any
   numeric feature-matrix builder must exclude the appropriate metadata
   set for the sheet/path they consume.

6. `Detection_Profile` is legacy display-only metadata. New Step4 outputs
   must not emit it. If an older file still contains it, consumers must
   treat it as metadata and never as a sample intensity column.

7. Any code that previously assumed "exactly one trailing metadata
   column" must be updated to either name-based exclusion or a metadata
   column set.

8. Downstream imputation compatibility is owned by MA. Toolkit and DNP do
   not validate KNN/RF internals in this branch.

## Non-Goals For This Contract

- No new threshold parameters beyond the existing `background_threshold`,
  `high_det_thresh`, `low_det_thresh`, `qc_ratio`, `intensity_fc`,
  `ratio_rescue`. The model-imputable detection floor deliberately reuses
  `background_threshold` rather than introducing a new knob, and it remains
  active even when `enable_background_threshold=False`.

- No method hint column. When a future change introduces RF or another
  method, it can add `Imputation_Method_Hint` separately. That change is
  out of scope here.

- No imputation implementation audit in this repository. Cross-repo checks
  against `Metaboanalyst_clone` are useful release evidence, but they are
  not part of this toolkit PR's required implementation scope.

- No changes to keep gate semantics or thresholds.

## Open Items For Implementation Plan

These are deferred to a follow-up implementation plan, not decided here:

1. Pipeline boundary: contract tests live in `ms-core/tests/` (decision
   level) and `tests/` (output and downstream propagation). The
   implementation plan must specify the exact test files and red-green
   order.

2. Migration: existing fixtures with no audit columns need a fixture
   refresh strategy. The implementation plan must decide whether to add
   columns in-place or regenerate fixtures from scratch.

(Items previously listed as "deferred" — token order, group order — have
been promoted into the contract proper under "Token And Group Ordering".)

## Versioning Note

This contract change is a **public schema addition** for Step4 output and
introduces a **tag semantic change** for two distinct pattern families.
Per the toolkit's `ms-core` bump SOP, this requires a `minor` bump.

The semantic change is observable in two directions:

- **legacy True -> contract False**: features kept by `ratio_rescue` that
  also pass `all_groups >= background_threshold` and have no zero group
  (e.g., `0.42/0.35/0.20`). These were previously routed to `min/5` and
  will now be routed to the downstream default/model-based imputation path.
- **legacy False -> contract True**: features kept by `stable_keep` alone
  with at least one group below `background_threshold` and no zero group
  and no rescue/mnar firing (e.g., `0.25/0.22/0.18`). These were
  previously routed to the downstream default/model-based imputation path
  and will now be routed to `min/5`.

Both flip directions are methodologically intentional (see the discussion
document), but they constitute a behavior change visible to downstream
consumers and to any saved Step4 outputs from previous runs that are
re-validated against the new rule.
