from pathlib import Path

import streamlit.components.v1 as components
import re


_COMPONENT_DIR = (
    Path(__file__).resolve().parent.parent
    / "components"
    / "operational_card"
    / "frontend"
    / "build"
)

_operational_card_component = components.declare_component(
    "operational_card_component",
    path=str(_COMPONENT_DIR),
)


def operational_card(
    title,
    subtitle=None,
    status=None,
    priority=None,
    meta=None,
    description=None,
    footer=None,
    variant="default",
    card_key=None,
    selectable=False,
    selected=False,
    clickable=False,
    actions=None,
    actions_layout="footer",
    selectable_label="Seleccionar",
    accent_color=None,
    key=None,
):
    valid_variants = {"default", "highlight", "success", "warning", "danger", "muted"}
    valid_kinds = {"primary", "secondary", "success", "warning", "danger"}

    variant = variant if variant in valid_variants else "default"
    meta = list(meta or [])
    actions_in = list(actions or [])

    parsed_actions = []
    for idx, action in enumerate(actions_in[:3]):
        if not isinstance(action, dict):
            continue
        label = str(action.get("label") or "Accion")
        akey = str(action.get("key") or f"action_{idx}")
        kind = str(action.get("kind") or "secondary")
        if kind not in valid_kinds:
            kind = "secondary"
        parsed_actions.append({"label": label, "key": akey, "kind": kind})

    component_key = key or f"op_card_{card_key or title}"
    accent_color = str(accent_color or "").strip()
    if accent_color and not re.fullmatch(r"#[0-9a-fA-F]{6}", accent_color):
        accent_color = ""

    return _operational_card_component(
        title=title or "",
        subtitle=subtitle or "",
        status=status or "",
        priority=priority or "",
        meta=meta,
        description=description or "",
        footer=footer or "",
        variant=variant,
        card_key=card_key or "",
        selectable=bool(selectable),
        selected=bool(selected),
        selectable_label=selectable_label or "Seleccionar",
        clickable=bool(clickable),
        actions=parsed_actions,
        actions_layout=actions_layout if actions_layout in {"footer", "corner"} else "footer",
        accent_color=accent_color,
        component_version="2026-06-02-events",
        key=component_key,
        default=None,
    )
