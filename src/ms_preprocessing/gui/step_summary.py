"""Small user-facing summaries for GUI step results."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _value_from(*sources: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value is not None:
                return value
    return None


def _append_value(lines: list[str], label: str, value: Any) -> None:
    if value is not None:
        lines.append(f"{label}: {value}")


def _basename(value: Any) -> str:
    return Path(str(value)).name


def _format_bool_enabled(value: Any) -> str:
    return "enabled" if bool(value) else "disabled"


def summarize_step_result(
    step_name: str,
    statistics: dict | None,
    metadata: dict | None,
    parameters: dict | None = None,
) -> list[str]:
    """Convert raw step result dictionaries into compact GUI summary lines."""

    stats = statistics or {}
    meta = metadata or {}
    params = parameters or {}
    normalized_step = step_name.lower()

    if normalized_step in {"data_organizer", "step1"}:
        return _summarize_step1(stats, meta, params)
    if normalized_step in {"istd_marker", "step2"}:
        return _summarize_step2(stats, meta, params)
    if normalized_step in {"duplicate_remover", "step3"}:
        return _summarize_step3(stats, meta, params)
    if normalized_step in {"feature_filter", "step4"}:
        return _summarize_step4(stats, meta, params)

    lines = ["Result: completed"]
    if stats:
        lines.append(f"Statistics: {len(stats)} fields")
    return lines


def _summarize_step1(stats: dict[str, Any], meta: dict[str, Any], params: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    _append_value(lines, "Features", _value_from(stats, meta, keys=("features", "feature_count")))
    _append_value(lines, "Samples", _value_from(stats, meta, keys=("samples", "sample_count")))

    sample_info = _value_from(meta, stats, keys=("sample_info", "sample_info_df"))
    lines.append(f"SampleInfo: {'available' if sample_info is not None else 'not available'}")

    method_file = _value_from(params, meta, keys=("method_file",))
    lines.append(f"Method: {_basename(method_file) if method_file else 'not selected'}")
    return lines


def _summarize_step2(stats: dict[str, Any], meta: dict[str, Any], params: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    record_file = _value_from(meta, params, keys=("istd_record_file",))
    lines.append(f"Record: {_basename(record_file) if record_file else 'not selected'}")

    _append_value(lines, "Date", _value_from(meta, params, keys=("istd_record_date",)))
    _append_value(lines, "Source", _value_from(meta, stats, keys=("istd_record_source",)))
    _append_value(lines, "Format", _value_from(meta, stats, keys=("istd_record_format",)))
    _append_value(lines, "Targets", _value_from(meta, stats, keys=("istd_target_count",)))
    _append_value(lines, "Pairs", _value_from(meta, stats, keys=("istd_pair_count",)))
    _append_value(lines, "Samples", _value_from(meta, stats, keys=("istd_sample_count",)))
    _append_value(lines, "Marked", _value_from(meta, stats, keys=("istd_marked_count", "marked_count")))
    _append_value(
        lines,
        "Duplicate ISTD",
        _value_from(meta, stats, keys=("istd_duplicate_count", "duplicate_istd_count")),
    )
    _append_value(lines, "Warnings", _value_from(meta, stats, keys=("istd_warning_count",)))

    confidence = _value_from(meta, stats, keys=("istd_confidence_summary",))
    if isinstance(confidence, dict) and confidence:
        parts = [f"{key}={value}" for key, value in sorted(confidence.items())]
        lines.append(f"Confidence: {', '.join(parts)}")
    return lines


def _summarize_step3(stats: dict[str, Any], meta: dict[str, Any], params: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    _append_value(lines, "Merge mode", _value_from(stats, params, keys=("merge_mode",)))
    _append_value(
        lines,
        "Duplicates removed",
        _value_from(stats, meta, keys=("removed_duplicates", "duplicates_removed")),
    )
    _append_value(lines, "Groups merged", _value_from(stats, meta, keys=("merged_groups",)))
    _append_value(
        lines,
        "Recovered points",
        _value_from(stats, meta, keys=("recovered_data_points", "recovered_points")),
    )
    return lines or ["Duplicates removed: 0"]


def _summarize_step4(stats: dict[str, Any], meta: dict[str, Any], params: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    _append_value(lines, "Kept", _value_from(stats, meta, keys=("kept_features", "features_kept")))
    _append_value(
        lines,
        "Deleted",
        _value_from(stats, meta, keys=("deleted_features", "features_deleted")),
    )
    _append_value(lines, "QC deleted", _value_from(stats, meta, keys=("qc_deleted_count",)))
    _append_value(lines, "MNAR kept", _value_from(stats, meta, keys=("mnar_kept_count",)))

    export_deleted = _value_from(
        params,
        meta,
        keys=("export_deleted_feature_sheet", "include_deleted_feature_sheet"),
    )
    lines.append(f"deleted_feature sheet: {_format_bool_enabled(export_deleted)}")
    return lines
