from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pandas as pd
import streamlit as st


def _row_id():
    return f"tmp_{uuid4().hex[:10]}"


def _with_row_ids(rows):
    prepared = []
    for row in rows or []:
        item = dict(row)
        item["_row_id"] = item.get("_row_id") or _row_id()
        item["_delete"] = bool(item.get("_delete", False))
        prepared.append(item)
    return prepared


def _clean_row(row):
    clean = dict(row)
    clean.pop("_row_id", None)
    clean.pop("_delete", None)
    return clean


def _normalize_value(value):
    if pd.isna(value):
        return None
    return value


def _normalize_row(row, keys):
    return {key: _normalize_value(row.get(key)) for key in keys}


def _column_config(columns, allow_delete):
    config = {
        "_row_id": None,
    }
    if allow_delete:
        config["_delete"] = st.column_config.CheckboxColumn(
            "Eliminar",
            help="Marcar para eliminar al guardar.",
            width="small",
        )

    for col in columns:
        key = col["key"]
        label = col.get("label", key)
        kind = col.get("type", "text")
        required = bool(col.get("required", False))
        width = col.get("width", "medium")
        if kind == "number":
            config[key] = st.column_config.NumberColumn(
                label,
                required=required,
                min_value=col.get("min_value"),
                max_value=col.get("max_value"),
                step=col.get("step", 1),
                format=col.get("format"),
                width=width,
            )
        elif kind == "select":
            config[key] = st.column_config.SelectboxColumn(
                label,
                required=required,
                options=col.get("options", []),
                width=width,
            )
        elif kind == "checkbox":
            config[key] = st.column_config.CheckboxColumn(
                label,
                required=required,
                width=width,
            )
        else:
            config[key] = st.column_config.TextColumn(
                label,
                required=required,
                width=width,
            )
    return config


def render_operational_editable_table(
    title,
    rows,
    columns,
    key,
    help_text=None,
    allow_add=True,
    allow_delete=True,
    totals=None,
    height=320,
):
    """Renderiza una tabla editable de laboratorio y devuelve cambios detectados.

    Esta primera version usa st.data_editor para validar flujo antes de crear
    un custom component propio.
    """

    state_key = f"{key}_base_rows"
    if state_key not in st.session_state:
        st.session_state[state_key] = _with_row_ids(deepcopy(rows or []))

    base_rows = st.session_state[state_key]
    editable_rows = deepcopy(base_rows)
    visible_keys = [col["key"] for col in columns]
    editor_columns = (["_delete"] if allow_delete else []) + visible_keys
    disabled_columns = ["_row_id"] + [
        col["key"] for col in columns if bool(col.get("disabled", False))
    ]

    st.markdown(f"### {title}")
    if help_text:
        st.caption(help_text)

    df = pd.DataFrame(editable_rows)
    for col in ["_row_id", "_delete", *visible_keys]:
        if col not in df.columns:
            df[col] = False if col == "_delete" else None

    edited = st.data_editor(
        df[["_row_id", *editor_columns]],
        key=f"{key}_editor",
        hide_index=True,
        use_container_width=True,
        height=height,
        num_rows="dynamic" if allow_add else "fixed",
        column_config=_column_config(columns, allow_delete),
        disabled=disabled_columns,
    )

    edited_rows = edited.to_dict("records") if hasattr(edited, "to_dict") else list(edited)
    for row in edited_rows:
        row["_row_id"] = row.get("_row_id") or _row_id()
        row["_delete"] = bool(row.get("_delete", False))

    base_by_id = {row["_row_id"]: row for row in base_rows}
    edited_by_id = {row["_row_id"]: row for row in edited_rows}

    added = []
    updated = []
    deleted = []
    active_rows = []
    commit_rows = []

    for row in edited_rows:
        row_id = row["_row_id"]
        if row.get("_delete"):
            if row_id in base_by_id:
                deleted.append(_clean_row(row))
            continue

        active_rows.append(_clean_row(row))
        commit_rows.append(dict(row))
        if row_id not in base_by_id:
            if any(row.get(k) not in (None, "") for k in visible_keys):
                added.append(_clean_row(row))
            continue

        before = _normalize_row(base_by_id[row_id], visible_keys)
        after = _normalize_row(row, visible_keys)
        if before != after:
            updated.append(
                {
                    "_row_id": row_id,
                    "before": before,
                    "after": after,
                }
            )

    for row_id, row in base_by_id.items():
        if row_id not in edited_by_id:
            deleted.append(_clean_row(row))

    if totals:
        total_cols = st.columns(len(totals))
        for idx, total in enumerate(totals):
            col_key = total["key"]
            label = total.get("label", col_key)
            values = pd.to_numeric(
                pd.Series([row.get(col_key) for row in active_rows]),
                errors="coerce",
            ).fillna(0)
            total_cols[idx].metric(label, f"{values.sum():g}")

    return {
        "rows": active_rows,
        "commit_rows": commit_rows,
        "added": added,
        "updated": updated,
        "deleted": deleted,
        "has_changes": bool(added or updated or deleted),
    }
