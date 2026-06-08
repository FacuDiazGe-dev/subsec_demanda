import html

import streamlit as st


def _esc(v):
    return html.escape("" if v is None else str(v))


def _load_op_card_css():
    st.markdown(
        """
        <style>
        .op-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 16px;
            padding: 14px 16px;
            margin-bottom: 12px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
            position: relative;
            overflow: hidden;
        }
        .op-card-clickable { transition: transform .12s ease, box-shadow .12s ease; }
        .op-card-clickable:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08); }
        .op-card-selected {
            border-color: #60A5FA !important;
            background: #F8FBFF;
            box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.25), 0 4px 12px rgba(15, 23, 42, 0.06);
        }
        .op-card-embedded {
            border: none !important;
            box-shadow: none !important;
            margin-bottom: 6px !important;
            border-radius: 12px;
            padding-bottom: 10px;
        }
        .op-card::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 5px;
            background: #94A3B8;
        }
        .op-card-default::before { background: #94A3B8; }
        .op-card-highlight::before { background: #2563EB; }
        .op-card-success::before { background: #16A34A; }
        .op-card-warning::before { background: #D97706; }
        .op-card-danger::before { background: #DC2626; }
        .op-card-muted::before { background: #64748B; }

        .op-card-default { border-color: #E2E8F0; }
        .op-card-highlight { border-color: #BFDBFE; }
        .op-card-success { border-color: #BBF7D0; }
        .op-card-warning { border-color: #FDE68A; }
        .op-card-danger { border-color: #FECACA; }
        .op-card-muted { border-color: #CBD5E1; background: #F8FAFC; }

        .op-card-header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
        .op-card-title { margin: 0; font-size: 16px; line-height: 1.25; font-weight: 700; color: #0F172A; }
        .op-card-subtitle { margin-top: 4px; font-size: 13px; color: #64748B; }
        .op-card-badges { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }

        .op-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 3px 9px;
            font-size: 11px;
            line-height: 1;
            font-weight: 700;
            border: 1px solid #CBD5E1;
            background: #F8FAFC;
            color: #334155;
            white-space: nowrap;
        }
        .op-badge-status { background: #EEF2FF; border-color: #C7D2FE; color: #3730A3; }
        .op-badge-priority { background: #FFF7ED; border-color: #FED7AA; color: #9A3412; }

        .op-meta { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
        .op-meta-item {
            font-size: 12px;
            color: #475569;
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 2px 8px;
        }
        .op-description {
            margin-top: 10px;
            font-size: 13px;
            color: #1E293B;
            line-height: 1.35;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .op-footer {
            margin-top: 10px;
            padding-top: 8px;
            border-top: 1px solid #E2E8F0;
            font-size: 12px;
            color: #64748B;
            font-weight: 600;
        }
        .op-actions-wrap { margin-top: -4px; margin-bottom: 12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_operational_card(
    title: str,
    subtitle: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    meta: list[str] | None = None,
    description: str | None = None,
    footer: str | None = None,
    variant: str = "default",
    clickable: bool = False,
    selected: bool = False,
    actions: list[dict] | None = None,
    card_key: str | None = None,
):
    _load_op_card_css()
    v = variant if variant in {"default", "highlight", "success", "warning", "danger", "muted"} else "default"
    base_key = _esc(card_key or title or "card").replace(" ", "_").lower()
    classes = [f"op-card op-card-{v}"]
    if clickable:
        classes.append("op-card-clickable")
    if selected:
        classes.append("op-card-selected")

    status_html = f'<span class="op-badge op-badge-status">{_esc(status)}</span>' if status else ""
    priority_html = f'<span class="op-badge op-badge-priority">{_esc(priority)}</span>' if priority else ""
    subtitle_html = f'<div class="op-card-subtitle">{_esc(subtitle)}</div>' if subtitle else ""
    desc_html = f'<div class="op-description">{_esc(description)}</div>' if description else ""
    footer_html = f'<div class="op-footer">{_esc(footer)}</div>' if footer else ""

    meta_html = ""
    if meta:
        items = "".join([f'<span class="op-meta-item">{_esc(x)}</span>' for x in meta if x])
        if items:
            meta_html = f'<div class="op-meta">{items}</div>'

    has_actions = bool(actions)
    if has_actions:
        classes.append("op-card-embedded")

    def _render_card_markup():
        st.markdown(
            f"""
<div class="{' '.join(classes)}">
<div class="op-card-header">
<div>
<h4 class="op-card-title">{_esc(title)}</h4>
{subtitle_html}
</div>
<div class="op-card-badges">
{status_html}
{priority_html}
</div>
</div>
{meta_html}
{desc_html}
{footer_html}
</div>
            """,
            unsafe_allow_html=True,
        )

    if not has_actions:
        _render_card_markup()
        return None

    pressed = None
    secundarios = [a for a in actions if (a or {}).get("kind") not in {"primary", "danger"}]
    primarios = [a for a in actions if (a or {}).get("kind") == "primary"]
    peligros = [a for a in actions if (a or {}).get("kind") == "danger"]
    ordered_actions = secundarios + primarios + peligros

    left_actions = [a for a in ordered_actions if (a or {}).get("kind") != "primary"]
    right_actions = [a for a in ordered_actions if (a or {}).get("kind") == "primary"]

    with st.container(border=True):
        _render_card_markup()
        st.markdown('<div class="op-actions-wrap">', unsafe_allow_html=True)
        c_left, c_right = st.columns([3, 2])
        with c_left:
            if left_actions:
                cols = st.columns(len(left_actions))
                for col, action in zip(cols, left_actions):
                    label = str((action or {}).get("label") or "Accion")
                    kind = str((action or {}).get("kind") or "secondary")
                    action_key = str((action or {}).get("key") or label).strip().lower().replace(" ", "_")
                    shown = f"⚠ {label}" if kind == "danger" and "⚠" not in label else label
                    with col:
                        if st.button(
                            shown,
                            key=f"{base_key}_{action_key}",
                            type="secondary",
                            use_container_width=True,
                        ):
                            pressed = (action or {}).get("key") or action_key
        with c_right:
            if right_actions:
                cols = st.columns(len(right_actions))
                for col, action in zip(cols, right_actions):
                    label = str((action or {}).get("label") or "Accion")
                    action_key = str((action or {}).get("key") or label).strip().lower().replace(" ", "_")
                    with col:
                        if st.button(
                            label,
                            key=f"{base_key}_{action_key}",
                            type="primary",
                            use_container_width=True,
                        ):
                            pressed = (action or {}).get("key") or action_key
        st.markdown("</div>", unsafe_allow_html=True)
    return pressed

