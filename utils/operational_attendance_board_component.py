from pathlib import Path

import streamlit.components.v1 as components


_COMPONENT_DIR = (
    Path(__file__).resolve().parent.parent
    / "components"
    / "operational_attendance_board"
    / "frontend"
    / "build"
)

_attendance_board_component = components.declare_component(
    "operational_attendance_board_component",
    path=str(_COMPONENT_DIR),
)


def operational_attendance_board(
    title,
    subtitle=None,
    blocks=None,
    people=None,
    assignments=None,
    save_label=None,
    copy_label=None,
    validate_label=None,
    key=None,
):
    parsed_blocks = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        block_id = block.get("id") or block.get("id_obra")
        if block_id is None:
            continue
        parsed_blocks.append(
            {
                "id": str(block_id),
                "line1": str(block.get("line1") or block.get("title") or ""),
                "line2": str(block.get("line2") or block.get("subtitle") or ""),
                "fixed": bool(block.get("fixed", False)),
            }
        )

    parsed_people = []
    for person in people or []:
        if not isinstance(person, dict):
            continue
        person_id = person.get("id") or person.get("id_personal")
        if person_id is None:
            continue
        name = str(person.get("name") or "").strip()
        if not name:
            name = f"{person.get('apellido', '')}, {person.get('nombre', '')}".strip(", ")
        parsed_people.append({"id": str(person_id), "name": name})

    parsed_assignments = []
    for assignment in assignments or []:
        if not isinstance(assignment, dict):
            continue
        person_id = assignment.get("person_id") or assignment.get("id_personal")
        block_id = assignment.get("block_id") or assignment.get("id_obra")
        if person_id is None or block_id is None:
            continue
        parsed_assignments.append(
            {
                "person_id": str(person_id),
                "block_id": str(block_id),
                "status": str(assignment.get("status") or assignment.get("estado") or "Sin marcar"),
            }
        )

    return _attendance_board_component(
        title=title or "Asistencias del dia",
        subtitle=subtitle or "",
        blocks=parsed_blocks,
        people=parsed_people,
        assignments=parsed_assignments,
        copy_label=copy_label or save_label or "Copiar parte",
        save_label=save_label or "Guardar asistencia",
        validate_label=validate_label or "Validar asistencia",
        component_version="2026-06-09-attendance-board-absent-report",
        key=key or "operational_attendance_board",
        default=None,
    )
