import dash
import os
from datetime import datetime

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import html, dcc, callback, Output, Input, State, ctx, ALL
from dash import get_relative_path

from info import read_md, make_collapsible_text

#PREFIX = os.environ.get("DASH_PREFIX", "/monitoring/okavango/")
PREFIX = os.environ.get("DASH_PREFIX", "/")

app = dash.Dash(__name__,
                requests_pathname_prefix=PREFIX,
                routes_pathname_prefix="/",
                use_pages=True,
                external_stylesheets=[dbc.themes.FLATLY])

app.config.suppress_callback_exceptions = True


# --------------------------------------:-------------------------------------
# Info popups: one modal, text read from ./content/<name>.md
# To add an entry: drop a new .md file in ./content and add a line here.
# ---------------------------------------------------------------------------

DOCS = {
    "about":      "About us",
    "links":      "Useful links",
    "disclaimer": "Disclaimer",
    "terms":      "Terms of use",
    "contact":    "Contact",
}

NAVBAR_DOCS = ["about"]                              # shown in the "About" dropdown
FOOTER_DOCS = ["disclaimer", "terms", "contact"]  # shown in the footer


def doc_trigger_id(name):
    return {"type": "doc-link", "name": name}


# "About this page" text for each page: page path -> file in ./content/pages
# When you add a page, add one line here and one .md file.
PAGE_INFO = {
    "/":      "rainfall",
    "/flood": "inundation",
}


def page_path(pathname):
    """Page path without the deployment prefix, e.g. '/monitoring/okavango/flood' -> '/flood'."""
    base = PREFIX.rstrip("/")
    path = pathname[len(base):] if base and pathname.startswith(base) else pathname
    return "/" + path.strip("/") if path.strip("/") else "/"


# ---------------------------------------------------------------------------
# Layout pieces
# ---------------------------------------------------------------------------

navbar = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand(
            [
                html.Img(src=app.get_asset_url("CSAG_web-logo.png"), height="25px",
                         className="bg-white rounded px-1 me-2"),
                "Okavango Data Dashboard",
            ],
            href=get_relative_path("/"),
            className="d-flex align-items-center",
        ),
        dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
        dbc.Collapse(
            dbc.Nav([
                dbc.NavLink("Inundation", href=get_relative_path("/flood"), active="exact"),
                dbc.NavLink("Rainfall", href=get_relative_path("/"), active="exact"),
                dbc.DropdownMenu(
                    [dbc.DropdownMenuItem(DOCS[n], id=doc_trigger_id(n), n_clicks=0)
                     for n in NAVBAR_DOCS],
                    label="About",
                    nav=True,
                    in_navbar=True,
                    align_end=True,
                ),
            ], className="ms-auto", navbar=True),
            id="navbar-collapse",
            navbar=True,
        ),
    ], fluid=True),
    color="primary",
    dark=True,
    expand="md",
)

# "About this page" bar under the navbar; filled in by a callback when the page changes
# page_info = dbc.Container(id="page-info-bar", fluid=True, className="py-1")

#html.Span(f"© {datetime.now().year} CSAG", className="text-muted small me-3"),
footer = html.Footer(
    dbc.Container(
        [
            *[dbc.Button(DOCS[n], id=doc_trigger_id(n), n_clicks=0,
                         color="link", size="sm", className="text-muted")
              for n in FOOTER_DOCS],
        ],
        className="text-center",
    ),
    className="border-top mt-4 py-2",
)

doc_modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle(id="doc-modal-title")),
        dbc.ModalBody(dcc.Markdown(id="doc-modal-body", link_target="_blank")),
        dbc.ModalFooter(dbc.Button("Close", id="doc-modal-close", color="secondary")),
    ],
    id="doc-modal",
    size="lg",
    scrollable=True,
    is_open=False,
)

# MantineProvider is required by dash_mantine_components (date pickers) and has to wrap the whole app
app.layout = dmc.MantineProvider(
    html.Div([
        navbar,
        dcc.Location(id="url", refresh=False),
        #page_info,
        dash.page_container,   # renders the active page here
        footer,
        doc_modal,
    ]),
    forceColorScheme="light",   # keep Mantine light, matching the Flatly theme
)


# ---------------------------------------------------------------------------
# Callback: open the modal with the requested text, or close it
# ---------------------------------------------------------------------------

@callback(
    Output("doc-modal", "is_open"),
    Output("doc-modal-title", "children"),
    Output("doc-modal-body", "children"),
    Input({"type": "doc-link", "name": ALL}, "n_clicks"),
    Input("doc-modal-close", "n_clicks"),
    prevent_initial_call=True,
)
def show_doc(link_clicks, close_clicks):
    trig = ctx.triggered_id
    if trig == "doc-modal-close":
        return False, dash.no_update, dash.no_update
    if not ctx.triggered or not ctx.triggered[0]["value"]:   # ignore spurious triggers
        return dash.no_update, dash.no_update, dash.no_update
    name = trig["name"]
    return True, DOCS[name], read_md(name)


# ---------------------------------------------------------------------------
# Callback: "About this page" link, text follows the current page
# ---------------------------------------------------------------------------

@callback(
    Output("page-info-bar", "children"),
    Output("page-info-bar", "style"),
    Input("url", "pathname"),
)
def update_page_info(pathname):
    key = PAGE_INFO.get(page_path(pathname or "/"))
    if key is None:                       # page without a description: no link
        return None, {"display": "none"}
    # rebuilding the block on each page change also resets it to collapsed
    return make_collapsible_text(f"pages/{key}", show_label="About this page",
                                 hide_label="Hide", button_first=True), {}


# ---------------------------------------------------------------------------
# Callback: hamburger button on narrow screens
# ---------------------------------------------------------------------------

@callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler", "n_clicks"),
    State("navbar-collapse", "is_open"),
)
def toggle_navbar(n_clicks, is_open):
    return (not is_open) if n_clicks else is_open


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
