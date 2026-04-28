# Step1 Internal Boundary Refactor Spec

Date: 2026-04-28
Status: In progress (Phase 4 extracted)
Target branch: feature/step1-combined-tsv-preprocessor

## Goal

Keep the user-facing Step1 workflow as "data organization", but split its internal responsibilities into smaller modules with explicit contracts.

The current issue is not that Step1 performs multiple sub-steps. That is intentional and matches the real workflow. The issue is that many different responsibilities share `DataOrganizer`, so dataset-specific fixes accumulate in one large class and make future batches harder to reason about.

## Guiding Principle

- Workflow steps can stay broad when that matches the user workflow.
- Module and function boundaries should be narrow enough to match internal responsibilities.
- Data contracts must be explicit, especially where one sub-step feeds another.
- Step internals should communicate through clear intermediate objects rather than shared implicit state on one large class.

For Step1, the user-facing workflow remains one "data organization" step. The refactor goal is to stop treating `DataOrganizer` as the owner of every internal responsibility.

## Current Problems

### P1. Sample Identity Rules Are Mixed Into Data Organization

Current state:

- Raw column simplification, method-file matching, rerun suffix handling, EC/QC/ZBEE normalization, and SampleInfo output naming all live near `DataOrganizer`.
- Downstream steps have historically compensated for `SampleInfo.Sample_Name` not matching `RawIntensity` columns.
- A new dataset can require changing matching logic in the middle of Step1.

Impact:

- The output contract is fragile.
- It is easy to confuse a matching key with an exported sample name.
- Future sample metadata fields such as sex, cohort, or correction factors may inherit the same ambiguity.

Current partial fix:

- `sample_identity.py` now separates matching-key normalization from exported SampleInfo identity fields.
- `SampleInfo.Sample_Name` should remain the RawIntensity join key.
- `Method_Sample_Name` should remain a traceability field from the method file.

### P2. Method File Parsing Is Coupled To Matrix Transformation

Current state:

- DOCX table extraction, fallback XML parsing, injection row parsing, sample type mapping, and matrix column ordering are implemented inside `DataOrganizer`.
- Method-file parser failures are handled close to matrix transformation code.

Impact:

- Parser changes risk Step1 matrix behavior.
- It is hard to test method-file parsing without constructing Step1 matrix fixtures.
- Adding future metadata columns to SampleInfo will likely increase `DataOrganizer` size.

### P3. SampleInfo Construction Does Too Much At Once

Current state:

- `_build_sample_info()` filters injection rows, re-numbers injection order, matches columns to method rows, infers sample type, injects empty downstream fields, and carries internal `_col_name`.

Impact:

- SampleInfo output columns, matching confidence, and ordering behavior are not independently testable.
- Manual fields such as `Batch` and correction-factor columns are created by Step1 even though downstream tools own their semantic meaning.

### P4. Combined TSV And False-Positive Fix Live Inside DataOrganizer

Current state:

- Combined FH/MZmine split, statistics-mode processing, pre-VBA layout, VBA replacement logic, MZmine area scaling, and final combined_fix output are methods on `DataOrganizer`.

Impact:

- Step1 core organization and combined TSV preprocessing evolve together even though they are different input providers.
- Combined TSV support is hard to test or modify without loading the entire DataOrganizer context.

### P5. Similar Boundary Smells Exist Elsewhere

Observed but lower priority:

- Step3 `DuplicateRemover` owns duplicate/overlap merge behavior, protected row propagation, intensity merge policy, top-N filtering, Pearson correlation checks, adduct table loading, and degeneracy/adduct annotation. Degeneracy annotation is closer to feature annotation than duplicate removal, but should be split only after Step1 data contracts are stable.
- Step4 `FeatureFilter` owns group/QC detection, detection ratio calculation, Wilson lower bound, stable/MNAR/QC ratio/intensity FC gates, deleted-feature export shape, zero-to-NaN cleanup, and marker column insertion. This is more coherent than Step1, but the gate decision table and export post-processing are likely future extraction points.
- GUI `event_handlers.py` owns file loading, extra sheet loading, combined TSV preprocessing, Run All orchestration, async thread/UI queue handling, autosave, final export, downstream handoff reminders, busy state, and step switching. This should eventually split into controller/service layers, but not in this core data-contract branch.
- CLI `run_cli()` duplicates GUI workflow responsibilities around validation, parameter resolution, loading, session metadata, auxiliary sheet preservation, Step1-4 orchestration, parquet handoff, output naming, and final export. A shared workflow runner is valuable, but should be a separate branch.

These should not be mixed into the Step1 refactor unless they block the work.

## Proposed Architecture

The external workflow stays the same:

```text
GUI/CLI Step1: Data Organization
```

Internally split responsibility like this:

```text
DataOrganizer.process()
  -> RawMatrixNormalizer
  -> MethodSequenceParser
  -> SampleIdentityMatcher
  -> SampleInfoBuilder
  -> ColumnOrderer

Combined TSV control / CLI mode
  -> CombinedTsvPreprocessor
       -> DataOrganizer-compatible core organization
       -> FalsePositiveFixer
```

## Proposed Contracts

### Sample Identity

Module:

```text
ms_core.preprocessing.sample_identity
```

Responsibilities:

- Normalize names for matching only.
- Preserve raw matrix column names for output.
- Provide identity fields used by SampleInfo.

Contract:

| Field | Meaning |
| --- | --- |
| `Sample_Name` | RawIntensity column name and downstream join key. |
| `Method_Sample_Name` | Method-file sample name used for traceability. Empty when unmatched. |
| `Canonical_Sample_ID` | Optional future field. Normalized biological/sample ID, not a join key. |
| `Sample_Match_Status` | Optional future field. `matched`, `unmatched`, `ambiguous`, or `inferred`. |
| `Sample_Match_Reason` | Optional future field. Human-readable reason for matching decision. |

Rule:

- Never overwrite `Sample_Name` with a method-file name.
- Never require downstream correction/calibration code to guess RawIntensity column names from SampleInfo.

### Method Sequence Parser

Possible module:

```text
ms_core.preprocessing.method_sequence
```

Responsibilities:

- Read DOCX or fallback XML.
- Extract injection rows.
- Preserve source order.
- Parse injection volume.
- Return typed `InjectionInfo` records.

Non-responsibilities:

- It should not know RawIntensity matrix shape.
- It should not create SampleInfo.
- It should not reorder matrix columns.

### SampleInfo Builder

Possible module:

```text
ms_core.preprocessing.sample_info_builder
```

Responsibilities:

- Accept matrix column metadata and parsed injection records.
- Match raw columns to method rows.
- Build SampleInfo fields.
- Preserve internal ordering hints only until `DataOrganizer` finishes column reordering.

Contract:

- Required output: `Sample_Name`, `Method_Sample_Name`, `Sample_Type`, `Injection_Order`, `Batch`, `Injection_Volume`, correction-factor placeholder.
- `Batch` and correction-factor columns are placeholders. Their values are filled manually or by downstream projects.
- Future metadata columns should be additive and not change the `Sample_Name` join contract.

### Combined TSV Preprocessor

Possible module:

```text
ms_core.preprocessing.combined_tsv
```

Responsibilities:

- Detect FH/MZmine split.
- Run the two-side preparation needed for combined TSV.
- Apply false-positive fix and MZmine area scaling.
- Return combined_fix output plus metadata.

Non-responsibilities:

- It should not own method-file parsing.
- It should call shared DataOrganizer or SampleInfo helpers rather than duplicating identity rules.

## Migration Plan

### Phase 1: Stabilize Identity Boundary

- Keep current `sample_identity.py`.
- Move shared sample token extraction, raw header simplification, method sample simplification, and matching-key normalization into `sample_identity.py`.
- Add missing tests for BC, EC, QC, ZBEE, program-prefix, and rerun suffix cases.
- Add regression tests proving `SampleInfo.Sample_Name` equals RawIntensity sample columns after Step1.
- Add optional trace fields only if they help debugging real datasets.

Current branch status:

- Done: `sample_identity.py` now centralizes matching-key normalization and identity helper behavior.
- Done: BC, EC, QC, ZBEE, nested program-prefix, and rerun suffix regression coverage has been added.
- Done: Step1 regression coverage proves SampleInfo names remain RawIntensity join keys while method names remain traceability fields.

### Phase 2: Extract MethodSequenceParser

- Move DOCX table parsing and injection row extraction out of `DataOrganizer`.
- Keep `DataOrganizer._parse_injection_sequence()` as a thin compatibility wrapper during migration.
- Test parser fixtures without full Step1 matrix setup.

Current branch status:

- Done: `ms_core.preprocessing.method_sequence` owns `InjectionInfo`, DOCX fallback table extraction, injection row extraction, injection table selection, and injection volume parsing.
- Done: `DataOrganizer` keeps compatibility wrappers so existing callers and tests can migrate gradually.
- Done: focused parser tests cover direct table parsing, BC source-order renumbering, and injection-volume parsing.

### Phase 3: Extract SampleInfoBuilder

- Move matching and SampleInfo row construction out of `DataOrganizer`.
- Keep DataOrganizer responsible for calling builder and reordering columns.
- Add tests for unmatched, ambiguous, and duplicate method rows.

Current branch status:

- Done: `ms_core.preprocessing.sample_info_builder` owns SampleInfo row construction, method-to-column matching, metadata-column exclusion, and display-column ordering.
- Done: `DataOrganizer._build_sample_info()` is now a compatibility wrapper that delegates to `SampleInfoBuilder`.
- Done: builder-focused tests cover unmatched raw columns, duplicate method matching keys, ambiguous BC DNA/RNA variant matching, metadata-column exclusion, and non-mutating injection-order renumbering.

### Phase 4: Extract CombinedTsvPreprocessor

- Move combined TSV split and false-positive fix out of `DataOrganizer`.
- Keep GUI/CLI behavior unchanged.
- Make combined_fix an input-provider path that reuses shared identity and method sequence contracts.

Current branch status:

- Done: `ms_core.preprocessing.combined_tsv` now owns combined TSV split detection, beforeVBA construction, false-positive filtering, MZmine area scaling, and post-VBA cleanup.
- Done: `DataOrganizer` keeps compatibility wrappers for `process_combined()`, `false_positive_fix()`, `post_vba_cleanup()`, and `process_combined_and_fix()`.
- Done: focused tests cover combined side splitting, MZmine ID order restoration, trailing unnamed MZmine-column cleanup, false-positive zero handling, and marker ownership.

### Phase 5: Revisit Other Boundary Smells

Only after Step1 boundaries are stable:

- Consider extracting Step3 degeneracy annotation.
- Consider extracting Step4 gate decision table.
- Consider a shared workflow runner for GUI and CLI.

Current branch status:

- Not in scope. These are documented follow-up candidates, not part of the current Step1 core-data-contract branch.

## Non-Goals

- Do not change the Step1 GUI/CLI user workflow.
- Do not rename workflow steps.
- Do not rewrite Step1 algorithms in one pass.
- Do not move DNP/calibration responsibilities back into this project.
- Do not require support for legacy ISTD record formats.

## Done When

- Step1 still produces the same user-facing outputs for existing fixtures.
- Sample identity, method parsing, SampleInfo building, and combined TSV preprocessing each have focused tests.
- `DataOrganizer` becomes an orchestration layer rather than the only implementation owner.
- Future dataset naming adjustments can be added to identity/parser tests without editing unrelated matrix logic.
