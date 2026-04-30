# Step4 Imputation Tag Implementation Plan

Status: implementation plan v2 (plan only — not yet executed)
Date: 2026-04-30 (v1) / 2026-05-01 (v2 revision)
Contract source of truth: `docs/plans/2026-04-30-step4-tag-contract.md` (v2)

> **For Claude (when asked to execute):** REQUIRED SUB-SKILL:
> `superpowers:executing-plans`. Tasks must be executed in order with the
> red-green-refactor discipline noted on each task.

## Revision Notes (v2)

- **Architecture boundary restored**: Task 2 no longer puts string
  composition (`keep_reason_tokens`, `tag_reason_tokens`,
  `detection_profile`) into the decision dataclass. Decisions now return
  masks only. Output builder (Task 3) composes strings from masks +
  group info. This restores the boundary established by
  `2026-04-28-pipeline-boundary-step4-core.md`.
- **Task 1 widened**: explicit flip-direction tests for the two verified
  flip cases (`0.42/0.35/0.20` and `0.25/0.22/0.18`), plus boundary
  patterns (`0.20/0.20/0.20`).
- **Task 3 widened**: deleted-features path now emits `Detection_Profile`
  plus `Feature_Filter_Delete_Reasons` per the contract.
- **Review fixes applied**: structural absence now requires a non-zero
  contrast group; low-overall reason masks can co-exist with structural
  reason masks; `Detection_Profile` is treated as display/audit metadata,
  not a parseable precision source; background-threshold tagging remains
  active even when the background keep gate is disabled.
- **Unfiltered mode specified**: the existing all-keep-gates-disabled
  fallback now emits an explicit `unfiltered` keep reason through a
  decision-layer mask, so every kept feature has at least one reason token.
- **Downstream completion tightened**: metadata exclusion is a ship blocker.
  If the audit exceeds the stop criterion, the branch is not done until the
  shared-constant refactor lands and focused tests pass.
- **Task 6 stop criterion added**: bound the downstream audit so it does
  not silently expand into a sprawling exclusion-list edit.
- **Task 7 message preservation requirement added**: the GUI copy must
  retain existing rules text (mnar gate, ratio rescue 10% floor) rather
  than replacing it with the tier model.
- **Convention removed**: token / group ordering moved out of this plan's
  "Conventions" section because it is now part of the contract.
- **Downstream boundary corrected**: KNN/RF imputation behavior belongs to
  the external `Metaboanalyst_clone` consumer. This toolkit plan validates
  Step4 tag/schema compatibility, not downstream imputer internals.

## Goal

Implement the Step4 imputation tag contract defined in
`2026-04-30-step4-tag-contract.md` v2:

- Replace the hard-coded
  `is_Presence_Absence_Marker = mnar_keep OR ratio_rescue_keep` rule
  with the contract's `model_imputable` rule.
- Emit three new feature-level metadata columns on kept features
  (`Feature_Filter_Keep_Reasons`, `Imputation_Tag_Reasons`,
  `Detection_Profile`) and two columns on deleted-feature diagnostic rows
  (`Feature_Filter_Delete_Reasons`, `Detection_Profile`).
- Update downstream metadata exclusion paths so the new columns are not
  treated as numeric feature data.

This plan changes Step4 output **schema** (additive) and Step4 tag
**semantics** (existing column flips for some patterns in both
directions). Per the toolkit's ms-core bump SOP, this requires a `minor`
ms-core tag.

## Architecture Anchors

| Layer | Owner module | Role for this plan |
| --- | --- | --- |
| ms-core decisions | `feature_filter_decisions.py` | Compute `all_groups_pass_background`, `any_group_zero`, `any_group_nonzero`, `imputation_tag`, tag-reason masks, and `unfiltered_keep`; expose analysis ratio matrix and analysis group names |
| ms-core output | `feature_filter_output.py` | Compose audit strings from decision masks; emit boolean tag + 3 audit columns on kept features; attach `Feature_Filter_Delete_Reasons` and `Detection_Profile` to deleted-feature rows |
| ms-core facade | `ms_quality_filter.py` | Forward new metadata; ensure no leakage into legacy paths |
| toolkit adapter | `adapters/feature_filter.py`, `adapters/__init__.py` | Pass through new columns into adapter result and preserve deleted-feature DataFrame shape |
| toolkit downstream | various (audited in Task 6) | Add kept/deleted metadata exclusion sets to numeric-matrix paths |
| GUI copy | `gui/widgets/feature_filter_widget.py` | Add three-tier description while preserving existing keep-rule text |

## Ownership And Boundaries

May modify:

- `ms-core/src/ms_core/preprocessing/feature_filter_decisions.py`
- `ms-core/src/ms_core/preprocessing/feature_filter_output.py`
- `ms-core/src/ms_core/preprocessing/ms_quality_filter.py`
- `ms-core/tests/test_feature_filter_decisions.py`
- `ms-core/tests/test_feature_filter_output.py`
- `ms-core/tests/test_feature_filter.py`
- `ms-core/tests/test_feature_filter_small_n.py`
- `src/ms_preprocessing/adapters/feature_filter.py`
- `src/ms_preprocessing/adapters/__init__.py`
- `src/ms_preprocessing/gui/widgets/feature_filter_widget.py`
- `tests/adapters/test_adapter_feature_filter.py`
- additional toolkit consumers identified in Task 6's audit
  (one-line exclusion-list edits only)

May not modify within this plan:

- Step1–Step3 modules
- Keep gate thresholds or keep gate evaluation order
- ms-core feature_filter detection ratio computation modules
- Any imputation method implementation (`min/5`, KNN, future RF)
- `Metaboanalyst_clone` files. They are a downstream reference/consumer for
  this contract, not part of this repository's implementation scope.
- `ms-core/tests/testing_markers.py` or `tests/testing_markers.py`,
  unless a new marker-owned test file is added and repo policy requires
  updating the marker map. Prefer adding tests to existing files.

## Conventions Applied To All Tasks

- TDD red-green: write failing tests first, run them to confirm red,
  then implement; rerun to confirm green.
- Use repo fixtures from `tests/conftest.py` and
  `ms-core/tests/conftest.py` for any temp paths. Never use `Path.cwd()`.
- After every code change inside `ms-core/`, run the focused ms-core
  tests.
- After every code change inside the toolkit, run with
  `$env:PYTHONPATH='ms-core/src'` from PowerShell.
- All token order and group order rules come from the contract's
  "Token And Group Ordering" section. This plan does not redefine them.

## Task 1: Lock Down The Contract Through Decision-Level Tests

**File:** `ms-core/tests/test_feature_filter_decisions.py`

Add failing tests that encode the contract's representative cases at the
decision-table level (no output frame yet). Tests must reference the
mask outputs only, not the string outputs (strings live in the output
layer per Task 3).

Required tests, all parameterized on detection patterns
(A/B/C analysis groups, QC excluded, `background_threshold == 0.20`):

1. `test_imputation_tag_structural_absence_when_zero_group_with_contrast`
   - Patterns: `0.80/0.42/0.00`, `0.45/0.42/0.00`, `0.80/0.00/0.00`.
   - Asserts: `imputation_tag` mask True; structural reason mask True;
      low-overall reason mask True because the zero group is below
      `background_threshold`.

2. `test_imputation_tag_low_overall_when_below_background_without_zero`
   - Patterns: `0.42/0.35/0.08`, `0.32/0.16/0.11`.
   - Asserts: `imputation_tag` True; structural mask False;
     low-overall mask True.

3. `test_imputation_tag_false_when_all_groups_meet_background_no_zero`
   - Patterns: `0.42/0.35/0.20`, `0.80/0.42/0.42`, `0.20/0.20/0.20`.
   - Asserts: `imputation_tag` False; both reason masks False.

4. `test_imputation_tag_flips_true_to_false_for_ratio_rescue_with_threshold_pass`
   - Pattern: `0.42/0.35/0.20`.
   - Asserts: `ratio_rescue_keep` mask True (legacy would tag True);
     `imputation_tag` False (contract).
   - Comment in test references the contract's flip case explanation.

5. `test_imputation_tag_flips_false_to_true_for_marginal_stable_keep`
   - Pattern: `0.25/0.22/0.18`.
   - Asserts: `mnar_keep` False, `ratio_rescue_keep` False (legacy would
     tag False); `stable_keep` True (kept); `imputation_tag` True
     (contract); low-overall reason True.
   - Comment in test references the contract's flip case explanation.

6. `test_imputation_tag_single_group_uses_allow_single_group_stable_path`
   - Single analysis group; assert `structural_absence_applies` is False
     for any single-group case (regardless of detection); `imputation_tag`
     follows `all_groups_pass_background` only.

7. `test_imputation_tag_excludes_qc_group`
   - QC column with detection 0; analysis groups all >= background.
   - Asserts: `imputation_tag` False, regardless of QC value.

8. `test_imputation_tag_emits_both_reason_masks_when_applicable`
   - Pattern: `0.80/0.15/0.00`.
   - Asserts: `imputation_tag` True; structural mask True; low-overall
     mask True (group B at 0.15 fails background, group C at 0.00 is the
     zero group).

9. `test_structural_absence_requires_nonzero_contrast_group`
   - Protected all-zero pattern: `0.00/0.00/0.00`.
   - Asserts: kept by protected mask; structural mask False; low-overall
     mask True; `imputation_tag` True.

10. `test_imputation_tag_still_uses_background_when_background_keep_disabled`
    - Disable `enable_background`; keep the feature via `ratio_rescue` or
      `protected`.
    - Pattern `0.42/0.35/0.20`: all groups pass background; assert
      `imputation_tag` False even though `stable_keep` is disabled.
    - Pattern `0.32/0.16/0.11`: at least one group fails background; assert
      `imputation_tag` True.

11. `test_unfiltered_keep_reason_mask_when_all_positive_gates_disabled`
    - Disable background, MNAR, intensity FC, and ratio rescue.
    - Assert ordinary kept rows have `unfiltered_keep` True and protected
      rows have `protected_mask` True but `unfiltered_keep` False.

12. `test_inclusive_threshold_comparison_at_boundary`
   - Pattern: `0.20/0.20/0.20`.
   - Asserts: `all_groups_pass_background` True; `imputation_tag`
     False.

Run red:

```powershell
Push-Location ms-core
$env:PYTHONPATH = 'src'
python -m pytest tests\test_feature_filter_decisions.py -v --tb=short
Pop-Location
```

Expect these tests to fail because the new fields/masks do not exist
yet.

## Task 2: Extend Decision Result To Carry Tag Masks Only

**File:** `ms-core/src/ms_core/preprocessing/feature_filter_decisions.py`

Decision layer returns **masks only**. No string composition here. This
preserves the layering established by
`2026-04-28-pipeline-boundary-step4-core.md`.

1. Extend `FeatureFilterDecisionResult` with the following numpy mask
   fields (length = n_features, dtype bool unless noted):
   - `all_groups_pass_background`
   - `any_group_zero`
   - `any_group_nonzero`
   - `imputation_tag`
   - `tag_reason_structural`
   - `tag_reason_low_overall`
   - `unfiltered_keep`

2. Also expose context needed by the output layer to compose strings:
   - `analysis_ratio_matrix` (already computed internally; promote to
     result) — shape `(n_features, n_analysis_groups)`, float
   - `analysis_group_names: list[str]` — order matches the matrix
     columns and matches the original `Sample_Type` row order

   These context fields enable Task 3 to format `Detection_Profile`
   without re-deriving group structure.

3. Inside `decide()`, compute (analysis groups only, QC excluded):
   - `all_groups_pass_background = (ratio_matrix >= thresholds.background).all(axis=1)`
   - `any_group_zero = (ratio_matrix == 0.0).any(axis=1)`
   - `any_group_nonzero = (ratio_matrix > 0.0).any(axis=1)`
   - `structural_absence_applies = (n_analysis_groups >= 2) AND any_group_zero AND any_group_nonzero`
   - `model_imputable = all_groups_pass_background & ~structural_absence_applies`
   - `imputation_tag = ~model_imputable`
   - `tag_reason_structural = structural_absence_applies & keep_mask`
   - `tag_reason_low_overall = (~all_groups_pass_background) & keep_mask`
   - `positive_keep_reason = stable_keep | mnar_keep | intensity_fc_keep | ratio_rescue_keep`
   - `unfiltered_keep = keep_mask & ~protected_mask & ~positive_keep_reason`

   `all_groups_pass_background` is always computed from
   `thresholds.background`, even when `options.enable_background` is
   False. The enable flag disables `stable_keep` as a keep reason only; it
   does not disable the imputation tag's model-imputable detection floor.

4. Add an explicit guard:
   - If `n_analysis_groups == 0`, raise `ValueError` early. The contract
     declares this case undefined; do not silently emit features.

5. Do not add string lists, do not add token-joining helpers, do not
   pre-format `Detection_Profile`. All string work is Task 3's
   responsibility.

Run green for Task 1 tests, then run the full ms-core feature-filter
test suite to confirm no decision-level regressions:

```powershell
Push-Location ms-core
$env:PYTHONPATH = 'src'
python -m pytest tests\test_feature_filter_decisions.py tests\test_feature_filter.py tests\test_feature_filter_small_n.py -v --tb=short
Pop-Location
```

## Task 3: Output Builder — Replace Tag Wiring, Compose Strings, Handle Both Output Paths

**File:** `ms-core/src/ms_core/preprocessing/feature_filter_output.py`
**Tests:** `ms-core/tests/test_feature_filter_output.py`

This task owns all string composition and frame shaping for the new
schema. It also owns the deleted-features `Detection_Profile`
attachment.

1. Add failing tests:

   **Kept-feature schema:**
   - `test_output_emits_three_new_metadata_columns_in_order`
     - After `is_Presence_Absence_Marker`, the result frame must contain
       in order: `Feature_Filter_Keep_Reasons`, `Imputation_Tag_Reasons`,
       `Detection_Profile`.
   - `test_output_tag_value_uses_decision_imputation_tag_not_legacy_or`
     - Use the contract's verified flip cases: `0.42/0.35/0.20` (legacy
       True, contract False) and `0.25/0.22/0.18` (legacy False,
       contract True). Assert the `is_Presence_Absence_Marker` column
       reflects the contract value.
   - `test_output_keep_reasons_token_order_matches_contract`
      - Construct a feature triggering all positive masks; assert string
        equals `stable|mnar|intensity_fc|ratio_rescue`. Add a feature
        triggering all positive masks plus `protected`; assert
        `stable|mnar|intensity_fc|ratio_rescue|protected`. Add a
        `protected`-only feature; assert `protected`. Add an
        `unfiltered` feature from the all-gates-disabled path; assert
        `unfiltered`.
   - `test_output_tag_reasons_token_order_matches_contract`
      - Construct features hitting low-overall only and structural plus
        low-overall. Assert `low_overall_detection` and
        `structural_absence|low_overall_detection` respectively. Assert
        Tier 1 features carry empty string `""`.
   - `test_output_detection_profile_format_two_decimals_pipe_joined`
      - Group order matches input `Sample_Type` order; values formatted
        with two decimals.
      - Use non-alphabetical group order, e.g. `B`, `A`, `C`, so the test
        fails if implementation sorts groups alphabetically.
   - `test_output_qc_column_does_not_appear_in_detection_profile`

   **Deleted-feature schema:**
   - `test_deleted_features_carry_delete_reasons_and_detection_profile_only`
      - Construct an input where one feature fails all keep rules (e.g.,
        `0.18/0.18/0.18`).
      - Assert deleted feature row has `Feature_Filter_Delete_Reasons`
        and `Detection_Profile` columns attached.
      - Assert `Feature_Filter_Keep_Reasons` and
        `Imputation_Tag_Reasons` are NOT attached to deleted rows.
      - Assert `Feature_Filter_Delete_Reasons == "no_keep_rule"`.
      - Assert `Detection_Profile` value matches the original detection
        pattern.
   - `test_deleted_features_capture_qc_force_delete_reason`
      - Construct a row that matches a positive keep rule but is deleted
        by `qc_force_delete`.
      - Assert `Feature_Filter_Delete_Reasons` is `qc_zero` or `qc_low`
        according to the QC pattern, without `no_keep_rule` when a
        positive keep rule fired.
   - `test_deleted_features_capture_qc_and_no_keep_rule_combined_reason`
      - Construct a row with QC low/zero and no positive keep rule.
      - Assert fixed-order delete reason is `qc_zero|no_keep_rule` or
        `qc_low|no_keep_rule`.

   **Regression:**
   - `test_zero_to_nan_conversion_does_not_touch_audit_columns`
     - Confirm `_convert_sample_zeros_to_nan` skips the new string
       columns.

2. Update `FeatureFilterOutputBuilder.build` to:
   - Read `decision.imputation_tag` for the `is_Presence_Absence_Marker`
     column instead of the legacy `mnar_keep OR ratio_rescue_keep`.
   - Implement small private helpers for token composition:
     - `_compose_keep_reasons(masks_for_feature) -> str` honoring the
       contract's fixed token order
     - `_compose_tag_reasons(masks_for_feature) -> str` same pattern
     - `_compose_detection_profile(ratio_row, group_names) -> str` two
       decimals, pipe-joined
   - Insert the three new columns immediately after
     `is_Presence_Absence_Marker` in the kept-feature result frame.
   - Header row 0 stores the column name; data rows store composed
     strings sliced by `rows_to_keep[1:]`.
   - For each row appended to `deleted_features`, attach
     `Feature_Filter_Delete_Reasons` and `Detection_Profile` (the same
     profile string the kept-feature path would have produced) by
     widening the Series index before appending. Do not rely on
     `Series.name`; the adapter builds DataFrame columns from
     `Series.index`.
   - `unfiltered` is emitted from `decision.unfiltered_keep`; do not
     infer it by string-layer fallthrough.

3. Confirm `_convert_sample_zeros_to_nan` does not interact with the new
   string columns; assert via the regression test above.

Run green for Task 3 tests and re-run Task 1 ms-core suite.

## Task 4: Update FeatureFilter Facade Integration Tests

**Files:**
- `ms-core/tests/test_feature_filter.py`
- `ms-core/tests/test_feature_filter_small_n.py`

1. Identify any test that asserts the legacy
   `is_Presence_Absence_Marker = mnar OR ratio_rescue` rule.
   For each such test, mark the previous expected value with a
   `# CONTRACT_FLIP:` inline comment showing the legacy expectation
   alongside the new contract expectation. This produces an auditable
   diff during code review for every flip.

2. Replace the expected value with the contract value. Specifically the
   patterns from the contract's representative cases table; only the
   two flip cases will produce different values:
   - `0.42/0.35/0.20` (T -> F)
   - `0.25/0.22/0.18` (F -> T) — only if previously fixtured

3. Add an integration assertion that the FeatureFilter facade returns
   the three new metadata columns end-to-end (decision -> output ->
   facade) and that deleted-feature rows carry
   `Feature_Filter_Delete_Reasons` plus `Detection_Profile`.

4. `ms_quality_filter.py` should require minimal or no change: it
   already delegates to decision + output. Confirm via test, do not
   modify unless a test forces it.

Run:

```powershell
Push-Location ms-core
$env:PYTHONPATH = 'src'
python -m pytest tests\test_feature_filter.py tests\test_feature_filter_small_n.py -v --tb=short
Pop-Location
```

## Task 5: ms-core Commit And Tag Boundary

After Tasks 1–4 are green:

1. Verify the full ms-core test suite:

   ```powershell
   Push-Location ms-core
   $env:PYTHONPATH = 'src'
   python -m pytest tests\ -q --tb=short
   Pop-Location
   ```

2. Commit on a `feature/step4-imputation-tag-contract` branch in
   ms-core. Commit message references the contract document path and
   lists both flip directions
   (`0.42/0.35/0.20` T->F, `0.25/0.22/0.18` F->T) as the semantic
   change.

3. Open PR in ms-core repo, wait for CI green, merge to master.

4. Tag with **minor bump** (per the contract's Versioning Note). Tag
   message:
   `vX.Y.0: Step4 imputation tag contract — schema additive, tag semantics updated in both flip directions`.

**Do not proceed to Task 6 until the ms-core tag is pushed.** Toolkit
work must pin to the new tag, not to a master HEAD.

## Task 6: Toolkit Adapter And Downstream Audit

**Files:**
- `src/ms_preprocessing/adapters/feature_filter.py`
- `src/ms_preprocessing/adapters/__init__.py`
**Test:** `tests/adapters/test_adapter_feature_filter.py`

1. Add failing test asserting the adapter result frame contains the
   three new metadata columns in the contract-defined order, immediately
   after `is_Presence_Absence_Marker`.

2. Add tests for the contract's verified flip cases via the adapter to
   confirm the new semantics propagate end-to-end.

3. Add a test asserting deleted-feature rows surfaced through the
    adapter carry `Feature_Filter_Delete_Reasons` plus
    `Detection_Profile`.

4. Update the adapter only as needed to surface the columns. If the
    adapter already passes the result frame through unchanged, no code
    edit is required — only test additions.

   Deleted-feature DataFrame conversion must be verified at
   `deleted_features_to_dataframe()`. That helper builds columns from
   `Series.index` and currently swallows conversion errors by returning
   `None`, so the test must fail if the new deleted diagnostic columns are
   lost.

5. **Audit pass** for downstream metadata exclusion. Search the toolkit
    for places that:
   - hardcode the column name `is_Presence_Absence_Marker` as a sole
     metadata marker;
   - assume "exactly one trailing metadata column";
   - construct the numeric feature matrix for calibration / stats /
     final export.

    Likely audit targets (verify each by adding a focused test, not
    grep-only):
   - `src/ms_preprocessing/workflow/export_service.py`
   - `src/ms_preprocessing/utils/output_writer.py`
   - `src/ms_preprocessing/gui/final_export_controller.py`
   - `src/ms_preprocessing/utils/excel_formatting_writer.py`
   - `src/ms_preprocessing/utils/results.py`
   - `src/ms_preprocessing/workflow/pipeline_session.py`
   - `ms-core/src/ms_core/utils/sample_classification.py`
   - calibration entry points covered by `ms-core/tests/test_pipeline.py`
     (`_dataset_to_calibration_df`, `_calibration_df_to_dataset`,
     `_calibration_wrapper`)
    - statistics/data-organizer mode covered by
      `ms-core/tests/test_data_organizer_facade_contract.py`

    For each hit, extend the kept-output metadata exclusion list to include
    `Feature_Filter_Keep_Reasons`, `Imputation_Tag_Reasons`,
    `Detection_Profile`. `Feature_Filter_Delete_Reasons` applies only to
    deleted-feature diagnostic rows; include it only in code paths that
    construct numeric matrices from deleted-feature sheets. Add a focused
    test per touched module asserting the new columns are excluded from the
    numeric matrix.

    Required acceptance tests for this audit:
    - Calibration conversion/wrapper tests prove the four kept-output
      metadata columns are not included as feature intensity values.
    - Statistics/data-organizer mode tests prove the metadata columns are
      not treated as sample columns or numeric feature values.
    - Final export/deleted-feature tests prove `Feature_Filter_Delete_Reasons`
      is treated as deleted-sheet metadata, not numeric data.

    Cross-repo note: `Metaboanalyst_clone` already owns the missing-value
    imputation router and group-agnostic KNN/RF behavior. This toolkit task
    should not add current-repo tests for KNN/RF internals. If release
    validation wants downstream evidence, run that as a separate
    `Metaboanalyst_clone` compatibility check using the exported Step4
    schema.

   **Stop criterion:** if the audit reveals more than 8 modules need
   exclusion-list edits, halt and surface the count to the user before
   continuing. The right next step in that scenario is to extract a
   shared `STEP4_METADATA_COLUMNS` constant (e.g., in
   `src/ms_preprocessing/config/`) and refactor consumers to import
   from it, instead of editing 9+ scattered lists. That refactor is a
   separate prerequisite change and this implementation is **not done**
   until the refactor lands and the focused downstream tests above pass.

6. Submodule pointer bump: pin `ms-core` to the new tag created in
   Task 5.

Run:

```powershell
$env:PYTHONPATH = 'ms-core/src'
python -m pytest tests\ -q --tb=short
```

## Task 7: GUI Copy Update

**File:** `src/ms_preprocessing/gui/widgets/feature_filter_widget.py`
**Test:** `tests/test_feature_filter_widget.py` (existing)

1. Augment the narrative text inside the widget that currently
   describes `is_Presence_Absence_Marker = True` only in MNAR + ratio
   rescue terms. Add the three-tier mental model description in plain
   Chinese:
   - Tier 1 model-imputable: 全組 detection >= background_threshold 且無零檢出組。
   - Tier 2 low overall detection: 至少一組 < background_threshold，但無零檢出組。
   - Tier 3 structural absence: 至少一組 detection = 0，且其他組有 evidence。
   - Tier 2 與 Tier 3 共用 `is_Presence_Absence_Marker = True`，下游同樣走
     `min positive / 5`。

2. **Preserve, do not replace**, existing rule descriptions:
   - the `mnar gate` explanation
   - the `ratio rescue` 10% floor rule
   - the existing description of `is_Presence_Absence_Marker = True`
     for mnar and ratio-rescue cases
   The new tier model is an addition, not a substitute. Position the
   tier description as a "downstream imputation routing" subsection
   that follows the existing keep-rule descriptions.

3. Mention the three new audit columns by name and that they are
   metadata, not analysis features. State that QC group does not
   appear in `Detection_Profile`.

4. Apply the project's Text And UI Copy Rules from CLAUDE.md:
   - UTF-8, no mojibake, no `??` placeholders.
   - Plain-text labels, no emoji.
   - After editing, scan the file for replacement characters.
   - Run the GUI smoke check: startup, step switching, step
     description visibility, action button labels.

5. Update widget tests:
   - Assert the new tier-tier description appears in the rendered help
     text.
   - **Assert preservation**: existing keywords still appear in the
     rendered help text. At minimum:
     `"10%"`, `"檢出率倍數救援"` (or `"ratio rescue"` if that is the
     existing wording), and the mnar gate explanation token. The
     specific assertion list should be derived from the file's current
     content at the time of execution, not assumed from this plan.

Run:

```powershell
$env:PYTHONPATH = 'ms-core/src'
python -m pytest tests\test_feature_filter_widget.py -v --tb=short
```

## Task 8: Top-Level Verification

Run the toolkit's standard pre-merge command:

```powershell
$env:PYTHONPATH = 'ms-core/src'
python -m pytest tests\ -v --tb=short -x
```

If green, the implementation is ready for the toolkit-side commit and
PR that bumps the ms-core submodule pointer and ships the contract.

Commit message format on toolkit side:

```
chore: bump ms-core to vX.Y.0 for Step4 imputation tag contract

ms-core changes:
- Replace hardcoded mnar OR ratio_rescue tag rule with contract's
  model_imputable rule.
- Emit Feature_Filter_Keep_Reasons, Imputation_Tag_Reasons,
  Detection_Profile metadata columns on kept features.
- Emit `unfiltered` keep reason for the existing all-gates-disabled
  retain-all mode.
- Attach Detection_Profile to deleted-feature diagnostic rows.
- Attach Feature_Filter_Delete_Reasons to deleted-feature diagnostic rows.
- Tag semantics flip in both directions for two pattern families
  (see contract Versioning Note).

Toolkit changes:
- Extend metadata exclusion lists for new columns.
- Update GUI tag description with three-tier mental model while
  preserving existing keep-rule explanations.
```

## Risks And Mitigations

1. **Existing fixtures with hardcoded tag values flip semantics in
   both directions.**
   Mitigation: Task 4 explicitly rewrites these with `# CONTRACT_FLIP:`
   inline comments. No fixture is allowed to pass through unchanged if
   its detection pattern matches a flip case.

2. **Downstream module silently consumes string column as numeric.**
   Mitigation: Task 6 audit pass requires per-module focused test, not
   just greps. Stop criterion at 8 modules blocks PR readiness until a
   shared metadata-column constant/refactor is completed and verified.

3. **Single-group runs degrade unexpectedly.**
   Mitigation: Task 1 includes single-group test; Task 2 adds explicit
   guard; contract has explicit single-group clause.

4. **GUI copy churn introduces encoding regression or loses existing
   rule explanations.**
   Mitigation: Task 7 follows the Text And UI Copy Rules including
   post-edit UTF-8 scan and GUI smoke check; widget test asserts both
   new tier descriptions and preserved existing keywords.

5. **Toolkit work begins before ms-core tag is published.**
   Mitigation: Task 5 explicitly gates Task 6 on the ms-core tag being
   pushed.

6. **Decision layer leaks string composition responsibility.**
   Mitigation: Task 2 explicitly forbids string fields and helpers in
   `feature_filter_decisions.py`. Task 3 owns all string work. Code
   review must reject any string formatting in the decision module.

7. **Cross-repo imputation behavior drifts after this contract ships.**
   Mitigation: this plan treats `Metaboanalyst_clone` as the downstream
   owner of KNN/RF and marker-aware routing. The toolkit PR must keep the
   exported Step4 schema stable and documented; downstream imputation
   regressions are validated and fixed in the downstream repository.

## Out Of Scope (Reaffirmed)

- Random Forest, GSimp, QRILC implementations.
- `Metaboanalyst_clone` imputation/router changes.
- `Imputation_Method_Hint` column.
- Calibration or statistical analysis algorithm changes; only their
  metadata exclusion paths are touched.
- Threshold parameter additions. The model-imputable detection floor reuses
  `background_threshold` and remains active even when the background keep
  gate is disabled.
- Keep gate semantic changes.
- Any extraction of a shared `STEP4_METADATA_COLUMNS` constant
  (triggered conditionally by Task 6 stop criterion; if triggered, this
  branch is not done until the separate prerequisite refactor lands).

## Done Definition

- All ms-core tests green; ms-core minor tag pushed.
- All toolkit tests green; submodule pointer bumped.
- Three new metadata columns visible in Step4 kept-feature output for
  every preset.
- `Detection_Profile` visible on deleted-feature diagnostic rows.
- `Feature_Filter_Delete_Reasons` visible on deleted-feature diagnostic rows.
- `is_Presence_Absence_Marker` matches the contract's representative
  cases table for all listed patterns, including both flip cases.
- GUI widget describes the three-tier model AND retains existing
  keep-rule explanations.
- Downstream metadata exclusion paths cover the kept-output metadata set
  and deleted-diagnostic metadata set with focused tests.
- Downstream imputation behavior is documented as an external
  `Metaboanalyst_clone` compatibility assumption, not implemented or audited
  inside this repository.
- If Task 6's stop criterion fires, this plan is paused and not shippable
  until the shared-constant refactor is implemented, verified, and merged
  back into this branch.
