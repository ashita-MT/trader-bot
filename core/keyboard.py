import json


def build_keyboard(buttons):
    rows = []
    for row in buttons:
        btns = []
        for btn in row:
            btns.append({
                "id": btn.get("id", ""),
                "render_data": {
                    "label": btn.get("label", ""),
                    "visited_label": btn.get("label", ""),
                    "style": btn.get("style", 0),
                },
                "action": {
                    "type": 2,
                    "permission": {"type": 2, "specify_role_ids": [], "specify_user_ids": []},
                    "data": btn.get("data", ""),
                },
            })
        rows.append({"buttons": btns})
    return {"rows": rows}
