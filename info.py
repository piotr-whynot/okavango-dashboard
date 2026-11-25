"""Shared show/hide text blocks, with the text kept in ./content/<path>.md

Used for the per-figure descriptions on the pages and for the "About this page" bar.
Importing this module registers the toggle callback, so it works for every page.
"""
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import dcc, html, callback, ctx, Input, Output, State, MATCH

CONTENT_DIR = Path(__file__).parent / "content"


def read_md(relpath):
    """Read ./content/<relpath>.md (relpath given without the extension)."""
    try:
        return (CONTENT_DIR / f"{relpath}.md").read_text(encoding="utf-8")
    except OSError:
        return f"*Text not found: `content/{relpath}.md`*"


def make_collapsible_text(md_path, show_label="Read about this figure/table...",
                          hide_label="Hide description", button_first=False):
    """A link-style button that shows/hides the text of ./content/<md_path>.md.

    md_path doubles as the component id, so it must be unique on a page.
    """
    button = dbc.Button(
        show_label,
        id={"type": "info-toggle", "index": md_path},
        name=show_label,       # remembered here so the callback can restore it
        value=hide_label,
        n_clicks=0,
        color="link",
        size="sm",
        className="p-0",
    )
    text = dbc.Collapse(
        dcc.Markdown(read_md(md_path), id={"type": "info-body", "index": md_path},
                     link_target="_blank", className="text-muted small mb-0 pt-1"),
        id={"type": "info-collapse", "index": md_path},
        is_open=False,
    )
    return html.Div([button, text] if button_first else [text, button])


@callback(
    Output({"type": "info-collapse", "index": MATCH}, "is_open"),
    Output({"type": "info-toggle", "index": MATCH}, "children"),
    Output({"type": "info-body", "index": MATCH}, "children"),
    Input({"type": "info-toggle", "index": MATCH}, "n_clicks"),
    State({"type": "info-collapse", "index": MATCH}, "is_open"),
    State({"type": "info-toggle", "index": MATCH}, "name"),
    State({"type": "info-toggle", "index": MATCH}, "value"),
    prevent_initial_call=True,
)
def toggle_info(n_clicks, is_open, show_label, hide_label):
    is_open = not is_open
    # text is re-read on every click, so edits to the .md files show up without a restart
    return is_open, (hide_label if is_open else show_label), read_md(ctx.triggered_id["index"])
