from pathlib import Path

import streamlit.components.v1 as components


_COMPONENT_DIR = (
    Path(__file__).resolve().parent.parent
    / "components"
    / "operational_list_editor"
    / "frontend"
    / "build"
)

_operational_list_editor_component = components.declare_component(
    "operational_list_editor_component",
    path=str(_COMPONENT_DIR),
)


def operational_list_editor(
    title,
    rows=None,
    catalog=None,
    help_text=None,
    add_label="Agregar fila",
    save_label="Guardar cambios",
    item_label="Material",
    mode="build",
    show_status=False,
    status_label="Ejecutada",
    show_unit=True,
    allow_delete=True,
    mark_deleted=False,
    embedded=False,
    key=None,
):
    valid_modes = {"build", "progress", "partial", "read"}
    mode = mode if mode in valid_modes else "build"

    parsed_catalog = []
    for idx, item in enumerate(catalog or []):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("material") or "").strip()
        if not label:
            continue
        parsed_catalog.append(
            {
                "id": str(item.get("id") or item.get("id_material") or label),
                "label": label,
                "unit": str(item.get("unit") or item.get("unidad") or ""),
            }
        )

    parsed_rows = []
    for idx, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        parsed_rows.append(
            {
                "id": str(row.get("id") or f"row_{idx}"),
                "item_id": str(row.get("item_id") or row.get("id_material") or row.get("item") or ""),
                "item_label": str(row.get("item_label") or row.get("item") or row.get("Material") or ""),
                "unit": str(row.get("unit") or row.get("unidad") or ""),
                "quantity": row.get("quantity", row.get("cantidad", "")),
                "delivered": row.get("delivered", row.get("entregado", row.get("cantidad_entregada", ""))),
                "status": bool(row.get("status", row.get("estado_tarea", False))),
                "deleted": bool(row.get("deleted", row.get("Eliminar", False))),
            }
        )

    return _operational_list_editor_component(
        title=title or "Lista operativa",
        rows=parsed_rows,
        catalog=parsed_catalog,
        help_text=help_text or "",
        add_label=add_label,
        save_label=save_label,
        item_label=item_label or "Material",
        mode=mode,
        show_status=bool(show_status),
        status_label=status_label or "Ejecutada",
        show_unit=bool(show_unit),
        allow_delete=bool(allow_delete),
        mark_deleted=bool(mark_deleted),
        embedded=bool(embedded),
        component_version="2026-06-04-list-editor-read-scroll",
        key=key or f"operational_list_editor_{title}",
        default=None,
    )
