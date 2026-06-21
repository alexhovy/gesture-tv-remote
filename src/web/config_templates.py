from html import escape

from src.shared.config import CONFIG_FIELDS, AppConfig, get_config_value
from src.web.config_forms import BOOLEAN_FIELD_MARKER

_READONLY_FIELDS = {"config_db_file"}
_TV_ADAPTERS = ("androidtv", "samsung", "webos", "roku")


def render_config_page(
    config: AppConfig,
    status_message: str | None = None,
    error_message: str | None = None,
) -> str:
    status = ""
    if error_message:
        status = f'<div class="status error">{escape(error_message)}</div>'
    elif status_message:
        status = f'<div class="status">{escape(status_message)}</div>'

    fields_html = "\n".join(
        _render_field(config, field.name) for field in CONFIG_FIELDS
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gesture TV Remote Config</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #667085;
      --line: #d7dce2;
      --accent: #14745f;
      --danger: #b42318;
      font-family: Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 18px;
    }}
    h1 {{ font-size: 28px; line-height: 1.2; margin: 0; }}
    .status {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 6px;
      padding: 10px 12px;
      margin-bottom: 14px;
      color: var(--muted);
    }}
    .error {{ border-color: #f3b0aa; color: var(--danger); }}
    form {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      padding: 18px;
    }}
    label {{ display: grid; gap: 7px; font-size: 13px; color: var(--muted); }}
    input, select {{
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
      color: var(--ink);
      background: #fff;
    }}
    input[readonly] {{ background: #eef1f4; color: var(--muted); }}
    .check {{ display: flex; align-items: center; gap: 10px; min-height: 38px; }}
    .check input {{ width: 18px; min-height: 18px; }}
    .actions {{
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      border-top: 1px solid var(--line);
      padding: 14px 18px;
    }}
    button {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 14px;
      font: inherit;
      background: #fff;
      color: var(--ink);
      cursor: pointer;
    }}
    button.primary {{
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }}
    button.danger {{ color: var(--danger); }}
    @media (max-width: 640px) {{
      main {{ padding: 14px; }}
      header, .actions {{ align-items: stretch; flex-direction: column; }}
      button {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Gesture TV Remote Config</h1>
    </header>
    {status}
    <form method="post" action="/settings">
      <div class="grid">
        {fields_html}
      </div>
      <div class="actions">
        <button class="primary" type="submit">Save</button>
        <button class="danger" type="submit" formaction="/reset">Reset</button>
      </div>
    </form>
  </main>
</body>
</html>
"""


def saved_status_message() -> str:
    return (
        "Saved. Live settings reload automatically; "
        "integration changes require restart."
    )


def reset_status_message() -> str:
    return (
        "Reset. Live settings reload automatically; "
        "integration changes require restart."
    )


def _render_field(config: AppConfig, name: str) -> str:
    value = get_config_value(config, name)
    label = escape(name.replace("_", " ").title())
    if isinstance(value, bool):
        checked = " checked" if value else ""
        return f"""
        <label>
          {label}
          <input type="hidden" name="{BOOLEAN_FIELD_MARKER}" value="{escape(name)}">
          <span class="check">
            <input type="checkbox" name="{escape(name)}"{checked}>
          </span>
        </label>"""
    if name == "tv_adapter":
        options = "\n".join(
            _render_option(adapter, adapter == value) for adapter in _TV_ADAPTERS
        )
        return f"""
        <label>
          {label}
          <select name="{escape(name)}">{options}</select>
        </label>"""

    input_type = "number" if isinstance(value, int | float) else "text"
    step = ' step="any"' if isinstance(value, float) else ""
    readonly = " readonly" if name in _READONLY_FIELDS else ""
    return f"""
        <label>
          {label}
          <input
            type="{input_type}"
            name="{escape(name)}"
            value="{escape(str(value))}"{step}{readonly}
          >
        </label>"""


def _render_option(value: str, selected: bool) -> str:
    selected_attribute = " selected" if selected else ""
    return (
        f'<option value="{escape(value)}"{selected_attribute}>'
        f"{escape(value)}</option>"
    )
