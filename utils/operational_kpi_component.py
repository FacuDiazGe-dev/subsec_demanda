from pathlib import Path

import streamlit.components.v1 as components


_COMPONENT_DIR = (
    Path(__file__).resolve().parent.parent
    / "components"
    / "operational_kpi"
    / "frontend"
    / "build"
)

_operational_kpi_component = components.declare_component(
    "operational_kpi_component",
    path=str(_COMPONENT_DIR),
)


def operational_kpis(items, key=None):
    parsed_items = []
    for idx, item in enumerate(list(items or [])[:8]):
        if not isinstance(item, dict):
            continue
        parsed_items.append(
            {
                "label": str(item.get("label") or ""),
                "value": str(item.get("value") if item.get("value") is not None else "0"),
                "tone": str(item.get("tone") or "green"),
                "caption": str(item.get("caption") or ""),
                "icon": str(item.get("icon") or ""),
                "key": str(item.get("key") or f"kpi_{idx}"),
            }
        )

    return _operational_kpi_component(
        items=parsed_items,
        component_version="2026-06-10-operational-kpi",
        key=key or "operational_kpis",
        default=None,
    )
