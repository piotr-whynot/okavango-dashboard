import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Output,Input

app = dash.Dash(__name__, use_pages=True, external_stylesheets=[dbc.themes.FLATLY])

app.config.suppress_callback_exceptions = True

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavLink("Inundation", href="/flood", active="exact"),
        dbc.NavLink("Rainfall", href="/", active="exact"),
    ],
    brand="Okavango Data Dashboard",
    color="primary",
    dark=True,
)

app.layout = html.Div([
    navbar,
    dcc.Location(id="url", refresh=False),
    dash.page_container,   # renders the active page here
])


if __name__ == "__main__":
    app.run(port=8080, debug=True)



