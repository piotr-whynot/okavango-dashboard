import dash
import os
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import html, dcc, callback, Output,Input
from dash import get_relative_path

PREFIX = os.environ.get("DASH_PREFIX", "/") 

app = dash.Dash(__name__, 
                requests_pathname_prefix=PREFIX,
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

# MantineProvider is required by dash_mantine_components (date pickers) and has to wrap the whole app
app.layout = dmc.MantineProvider(
    html.Div([
        navbar,
        dcc.Location(id="url", refresh=False),
        dash.page_container,   # renders the active page here
    ]),
    forceColorScheme="light",   # keep Mantine light, matching the Flatly theme
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)



