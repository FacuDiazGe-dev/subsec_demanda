from pathlib import Path

import streamlit.components.v1 as components


_COMPONENT_DIR = (
    Path(__file__).resolve().parent.parent
    / "components"
    / "visit_followup_card"
    / "frontend"
    / "build"
)

_visit_followup_card_component = components.declare_component(
    "visit_followup_card_component",
    path=str(_COMPONENT_DIR),
)


def visit_followup_card(
    title,
    subtitle=None,
    address=None,
    contact=None,
    priority=None,
    scheduled_date=None,
    rows=None,
    selectable=False,
    selected=False,
    card_key=None,
    key=None,
):
    parsed_rows = []
    for row in list(rows or [])[:2]:
        if not isinstance(row, dict):
            continue
        parsed_rows.append(
            {
                "label": str(row.get("label") or ""),
                "program_status": str(row.get("program_status") or ""),
                "visit_status": str(row.get("visit_status") or ""),
                "report_status": str(row.get("report_status") or ""),
                "report_checked": bool(row.get("report_checked")),
                "report_enabled": bool(row.get("report_enabled")),
                "target": str(row.get("target") or ""),
            }
        )

    component_key = key or f"visit_card_{card_key or title}"
    return _visit_followup_card_component(
        title=title or "",
        subtitle=subtitle or "",
        address=address or "",
        contact=contact or "",
        priority=priority or "",
        scheduled_date=scheduled_date or "",
        rows=parsed_rows,
        selectable=bool(selectable),
        selected=bool(selected),
        card_key=card_key or "",
        component_version="2026-06-10-visit-card-bulk-program",
        key=component_key,
        default=None,
    )
