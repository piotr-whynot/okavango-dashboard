import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Output,Input
from dash import get_relative_path

app = dash.Dash(__name__, 
                requests_pathname_prefix="/monitoring/okavango/",
                routes_pathname_prefix="/",
                use_pages=True, 
                external_stylesheets=[dbc.themes.FLATLY])

#app = dash.Dash(__name__, url_base_pathname="/monitoring/okavango/")

app.config.suppress_callback_exceptions = True

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavLink("Inundation", href=get_relative_path("/flood"), active="exact"),
        dbc.NavLink("Rainfall", href=get_relative_path("/"), active="exact"),
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
    app.run(host="0.0.0.0", port=8080, debug=False)



