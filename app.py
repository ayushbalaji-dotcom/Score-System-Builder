import json
import os
import uuid
from copy import deepcopy

import streamlit as st

DATA_PATH = os.path.join("data", "tools.json")

DEFAULT_TOOL = {
    "name": "New Tool",
    "description": "",
    "inputs": [
        {"id": "example_yes_no", "label": "Example Yes/No?", "type": "select", "options": ["Yes", "No", "Unknown"]}
    ],
    "scoring_rules": [
        {"input_id": "example_yes_no", "favor_values": ["Yes"], "against_values": ["No"], "invert_favor": False}
    ],
    "rules": [
        {
            "name": "Example Rule",
            "level": "info",
            "message": "Example: Rule matched",
            "conditions": [
                {"input_id": "example_yes_no", "op": "equals", "value": "Yes"}
            ],
        }
    ],
    "fallback": {"level": "warning", "message": "No rules matched."},
}

LEVELS = ["success", "info", "warning", "error"]
INPUT_TYPES = ["select", "number", "text"]


def load_tools():
    if not os.path.exists(DATA_PATH):
        return {"tools": {}}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tools(data):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def ensure_state():
    if "tools_data" not in st.session_state:
        st.session_state.tools_data = load_tools()
    if "selected_tool_id" not in st.session_state:
        tool_ids = list(st.session_state.tools_data.get("tools", {}).keys())
        st.session_state.selected_tool_id = tool_ids[0] if tool_ids else None
    if "editing_tool" not in st.session_state:
        st.session_state.editing_tool = None
    if "preview_values" not in st.session_state:
        st.session_state.preview_values = {}


def normalize_options(options_csv):
    if not options_csv:
        return []
    if isinstance(options_csv, list):
        return [str(o).strip() for o in options_csv if str(o).strip()]
    return [o.strip() for o in str(options_csv).split(",") if o.strip()]


def tool_to_input_rows(tool):
    rows = []
    for item in tool.get("inputs", []):
        rows.append(
            {
                "id": item.get("id", ""),
                "label": item.get("label", ""),
                "type": item.get("type", "select"),
                "options_csv": ", ".join(item.get("options", [])),
            }
        )
    return rows


def input_rows_to_tool(rows):
    inputs = []
    for row in rows:
        if not row.get("id"):
            continue
        inputs.append(
            {
                "id": row.get("id").strip(),
                "label": row.get("label", "").strip(),
                "type": row.get("type", "select"),
                "options": normalize_options(row.get("options_csv", "")),
            }
        )
    return inputs


def tool_to_scoring_rows(tool):
    rows = []
    for item in tool.get("scoring_rules", []):
        rows.append(
            {
                "input_id": item.get("input_id", ""),
                "favor_values_csv": ", ".join(item.get("favor_values", [])),
                "against_values_csv": ", ".join(item.get("against_values", [])),
                "invert_favor": bool(item.get("invert_favor", False)),
            }
        )
    return rows


def scoring_rows_to_tool(rows):
    rules = []
    for row in rows:
        if not row.get("input_id"):
            continue
        rules.append(
            {
                "input_id": row.get("input_id").strip(),
                "favor_values": normalize_options(row.get("favor_values_csv", "")),
                "against_values": normalize_options(row.get("against_values_csv", "")),
                "invert_favor": bool(row.get("invert_favor", False)),
            }
        )
    return rules


def tool_to_rule_rows(tool):
    rows = []
    for rule in tool.get("rules", []):
        conditions = rule.get("conditions", [])
        row = {
            "name": rule.get("name", ""),
            "level": rule.get("level", "info"),
            "message": rule.get("message", ""),
        }
        for idx in range(3):
            key_id = f"input_id_{idx + 1}"
            key_val = f"value_{idx + 1}"
            if idx < len(conditions):
                row[key_id] = conditions[idx].get("input_id", "")
                row[key_val] = conditions[idx].get("value", "")
            else:
                row[key_id] = ""
                row[key_val] = ""
        rows.append(row)
    return rows


def rule_rows_to_tool(rows):
    rules = []
    for row in rows:
        if not row.get("name"):
            continue
        conditions = []
        for idx in range(3):
            input_id = row.get(f"input_id_{idx + 1}", "").strip()
            value = row.get(f"value_{idx + 1}", "")
            if input_id and value != "":
                conditions.append({"input_id": input_id, "op": "equals", "value": value})
        rules.append(
            {
                "name": row.get("name", ""),
                "level": row.get("level", "info"),
                "message": row.get("message", ""),
                "conditions": conditions,
            }
        )
    return rules


def ensure_editing_tool():
    tool_id = st.session_state.selected_tool_id
    if tool_id is None:
        st.session_state.editing_tool = None
        return
    current = st.session_state.tools_data["tools"].get(tool_id)
    st.session_state.editing_tool = deepcopy(current)


def render_message(level, message):
    if level == "success":
        st.success(message)
    elif level == "info":
        st.info(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.error(message)


def evaluate_rules(tool, values):
    for rule in tool.get("rules", []):
        conditions = rule.get("conditions", [])
        if not conditions:
            continue
        matches = True
        for cond in conditions:
            input_id = cond.get("input_id")
            expected = cond.get("value")
            actual = values.get(input_id)
            if actual != expected:
                matches = False
                break
        if matches:
            return rule.get("level", "info"), rule.get("message", "")
    fallback = tool.get("fallback", {"level": "warning", "message": "No rules matched."})
    return fallback.get("level", "warning"), fallback.get("message", "No rules matched.")


def compute_scores(tool, values):
    plus = 0
    minus = 0
    for rule in tool.get("scoring_rules", []):
        input_id = rule.get("input_id")
        if not input_id:
            continue
        value = values.get(input_id)
        favor_values = rule.get("favor_values", [])
        against_values = rule.get("against_values", [])
        invert = rule.get("invert_favor", False)
        score = 0
        if value in favor_values:
            score = -1 if invert else 1
        elif value in against_values:
            score = 1 if invert else -1
        if score == 1:
            plus += 1
        elif score == -1:
            minus += 1
    return plus, minus


def main():
    st.set_page_config(page_title="Tool Builder", layout="wide")
    st.title("Tool Builder")
    st.caption("Build and run decision tools in the same app. Save multiple tools and preview live.")

    ensure_state()

    with st.sidebar:
        st.subheader("Tools")
        tool_items = st.session_state.tools_data.get("tools", {})
        tool_ids = list(tool_items.keys())
        tool_labels = [tool_items[tool_id]["name"] for tool_id in tool_ids]

        if tool_ids:
            selected_label = st.selectbox(
                "Select tool",
                options=tool_labels,
                index=tool_ids.index(st.session_state.selected_tool_id)
                if st.session_state.selected_tool_id in tool_ids
                else 0,
            )
            st.session_state.selected_tool_id = tool_ids[tool_labels.index(selected_label)]
        else:
            st.info("No tools yet. Create your first tool.")

        if st.button("New Tool"):
            new_id = f"tool_{uuid.uuid4().hex[:8]}"
            st.session_state.tools_data["tools"][new_id] = deepcopy(DEFAULT_TOOL)
            st.session_state.selected_tool_id = new_id
            save_tools(st.session_state.tools_data)
            st.rerun()

        if tool_ids:
            if st.button("Delete Tool"):
                del st.session_state.tools_data["tools"][st.session_state.selected_tool_id]
                save_tools(st.session_state.tools_data)
                remaining_ids = list(st.session_state.tools_data.get("tools", {}).keys())
                st.session_state.selected_tool_id = remaining_ids[0] if remaining_ids else None
                st.rerun()

    if st.session_state.selected_tool_id is None:
        st.stop()

    ensure_editing_tool()
    tool = st.session_state.editing_tool

    tabs = st.tabs(["Builder", "Preview"])

    with tabs[0]:
        st.subheader("Tool Details")
        tool["name"] = st.text_input("Tool name", value=tool.get("name", ""))
        tool["description"] = st.text_area("Description", value=tool.get("description", ""))

        st.divider()
        st.subheader("Inputs")
        input_rows = tool_to_input_rows(tool)
        input_rows = st.data_editor(
            input_rows,
            num_rows="dynamic",
            column_config={
                "id": st.column_config.TextColumn("ID"),
                "label": st.column_config.TextColumn("Label"),
                "type": st.column_config.SelectboxColumn("Type", options=INPUT_TYPES),
                "options_csv": st.column_config.TextColumn("Options (comma-separated)"),
            },
            key="inputs_editor",
        )
        tool["inputs"] = input_rows_to_tool(input_rows)

        st.divider()
        st.subheader("Scoring Rules")
        scoring_rows = tool_to_scoring_rows(tool)
        scoring_rows = st.data_editor(
            scoring_rows,
            num_rows="dynamic",
            column_config={
                "input_id": st.column_config.TextColumn("Input ID"),
                "favor_values_csv": st.column_config.TextColumn("Favor values"),
                "against_values_csv": st.column_config.TextColumn("Against values"),
                "invert_favor": st.column_config.CheckboxColumn("Invert (yes counts against)"),
            },
            key="scoring_editor",
        )
        tool["scoring_rules"] = scoring_rows_to_tool(scoring_rows)

        st.divider()
        st.subheader("Recommendation Rules")
        rule_rows = tool_to_rule_rows(tool)
        rule_rows = st.data_editor(
            rule_rows,
            num_rows="dynamic",
            column_config={
                "name": st.column_config.TextColumn("Rule name"),
                "level": st.column_config.SelectboxColumn("Level", options=LEVELS),
                "message": st.column_config.TextColumn("Message"),
                "input_id_1": st.column_config.TextColumn("Condition 1 Input"),
                "value_1": st.column_config.TextColumn("Condition 1 Value"),
                "input_id_2": st.column_config.TextColumn("Condition 2 Input"),
                "value_2": st.column_config.TextColumn("Condition 2 Value"),
                "input_id_3": st.column_config.TextColumn("Condition 3 Input"),
                "value_3": st.column_config.TextColumn("Condition 3 Value"),
            },
            key="rules_editor",
        )
        tool["rules"] = rule_rows_to_tool(rule_rows)

        st.subheader("Fallback Message")
        fallback_level = st.selectbox("Fallback level", LEVELS, index=LEVELS.index(tool.get("fallback", {}).get("level", "warning")))
        fallback_message = st.text_input("Fallback message", value=tool.get("fallback", {}).get("message", "No rules matched."))
        tool["fallback"] = {"level": fallback_level, "message": fallback_message}

        st.divider()
        if st.button("Save Tool"):
            st.session_state.tools_data["tools"][st.session_state.selected_tool_id] = deepcopy(tool)
            save_tools(st.session_state.tools_data)
            st.success("Tool saved.")

    with tabs[1]:
        st.subheader(tool.get("name", "Tool Preview"))
        if tool.get("description"):
            st.write(tool.get("description"))

        preview_values = st.session_state.preview_values.get(st.session_state.selected_tool_id, {})

        for item in tool.get("inputs", []):
            input_id = item.get("id")
            label = item.get("label", input_id)
            input_type = item.get("type", "select")
            key = f"preview_{st.session_state.selected_tool_id}_{input_id}"

            if input_type == "select":
                options = item.get("options", [])
                if not options:
                    options = [""]
                default = preview_values.get(input_id, options[0])
                value = st.selectbox(label, options, index=options.index(default) if default in options else 0, key=key)
            elif input_type == "number":
                default = preview_values.get(input_id, 0.0)
                value = st.number_input(label, value=float(default), key=key)
            else:
                default = preview_values.get(input_id, "")
                value = st.text_input(label, value=str(default), key=key)

            preview_values[input_id] = value

        st.session_state.preview_values[st.session_state.selected_tool_id] = preview_values

        st.divider()
        st.subheader("Results")
        level, message = evaluate_rules(tool, preview_values)
        render_message(level, message)

        plus, minus = compute_scores(tool, preview_values)
        st.write(f"✅ **Factors favoring intervention:** {plus}")
        st.write(f"❌ **Factors NOT favoring intervention:** {minus}")


if __name__ == "__main__":
    main()
