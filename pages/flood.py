import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import xarray as xr

dash.register_page(__name__, path="/flood", name="Inundation")

# ---------------------------------------------------------------------------
# Data loading — runs once at startup
# ---------------------------------------------------------------------------

def load_data():
    ds1 = xr.open_dataset("./data/flood/inundation_modis_int8.nc")
    return ds1["inundation"].sortby("lat")


def derive_products(da1):
    # -99 = cloud, 0 = dry, 1 = wet
    dacloud = (da1 == 0).astype(np.int8)
    daflood = (da1 == 1).astype(np.int8)

    tscloud = dacloud.sum(["lat", "lon"]) / 4
    tsflood  = daflood.sum(["lat", "lon"]) / 4

    tsflood[tscloud > 1000] = np.nan

    tsfloodbad = daflood.sum(["lat", "lon"]) / 4
    tsfloodbad[tscloud <= 1000] = np.nan

    return daflood, dacloud, tsflood, tscloud, tsfloodbad


da1 = load_data()
daflood, dacloud, tsflood, tscloud, tsfloodbad = derive_products(da1)

time_values = daflood["time"].values


lat_range = float(da1["lat"].max() - da1["lat"].min())
lon_range = float(da1["lon"].max() - da1["lon"].min())

nt,ny,nx=da1.shape

MAP_MT=60
MAP_MB=60

#ASPECT = lat_range / lon_range
ASPECT = (ny+MAP_MB+MAP_MT+10) / nx


# Pre-compute static frequency map
freq = daflood.mean("time") * 100
freq = np.round(freq.where(freq >= 0),0)


#daflood=daflood.where(freq>0.01)

# ---------------------------------------------------------------------------
# Figure builders
# ---------------------------------------------------------------------------

def make_ts_figure(sel_time):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=tsflood.time.data,
        y=list(tsflood.data.flatten()),
        mode="lines",
        line=dict(color="grey", width=2),
        name="inundated area",
    ))
    fig.add_trace(go.Scatter(
        x=tsfloodbad.time.data,
        y=list(tsfloodbad.data),
        mode="lines",
        line=dict(color="lightgrey", width=2),
        name="inundated area in images with cloud",
    ))
    fig.add_vline(
        x=str(pd.Timestamp(sel_time))[:10],
        line=dict(color="red", width=2, dash="dash"),
    )
    fig.update_layout(
        title=dict(
            text="Okavango Delta Inundated area <br>click to select date",
            x=0.5,
            xanchor="center",
            pad=dict(b=50),
        ),
        height=300,
        legend=dict(orientation="h", x=0.5, y=-0.15, xanchor="center", yanchor="top"),
        margin=dict(l=0, r=0, t=100, b=60),
    )
    return fig


def make_map_figure(sel_time):
    slice_1 = daflood.sel(time=sel_time)
    slice_1 = slice_1.where(slice_1 >= 0)
    fig = go.Figure(go.Heatmap(
        z=slice_1.values,
        x=slice_1["lon"].values,
        y=slice_1["lat"].values,
        colorscale=[[0, "azure"], [0.5, "azure"], [0.5, "navy"], [1, "navy"]],
        zmin=0, zmax=1,
        colorbar=dict(
            title="inundation",
            orientation="h",
            x=0.5, y=-0.08,
            xanchor="center", yanchor="top",
            len=0.5, thickness=15,
            title_side="bottom",
            tickvals=[0.25,0.5],
            ticktext=["dry","flooded"],
        ),
    ))

    fig.update_layout(
        title=dict(
            text=f"Okavango Delta inundation map for {pd.to_datetime(sel_time).strftime('%d %b %Y')}<br>click anywhere on map to see time series",
            x=0.5,
            xanchor="center",
            y=0.95,          # position from bottom (0-1)
            yanchor="top",
        ),
        autosize=False,
        yaxis_scaleanchor="x",
        margin=dict(l=0, r=0, t=MAP_MT, b=MAP_MB),
        xaxis=dict(visible=True),
        yaxis=dict(visible=True),
        meta={"aspect_ratio": ASPECT}
    )

    fig.update_xaxes(
        automargin=True,
        showticklabels=True,
        showgrid=True,
        zeroline=True,
        constrain="domain",
    )

    fig.update_yaxes(
        automargin=True,
        showticklabels=True,
        showgrid=True,
        zeroline=True,
        constrain="domain",
        scaleanchor="x",
        scaleratio=1,
    )


    return fig


def make_freq_figure():
    fig = go.Figure(go.Heatmap(
        z=freq.values,
        x=freq["lon"].values,
        y=freq["lat"].values,
        colorscale="Blues",
        zmin=0, zmax=100,
        colorbar=dict(
            title="inundation",
            orientation="h",
            x=0.5, y=-0.08,
            xanchor="center", yanchor="top",
            len=0.5, thickness=15,
            title_side="bottom",
        ),
        showscale=True,
    ))

    fig.update_layout(
        title=dict(
            text=f"Frequency of inundation during 2000-2026 period",
            x=0.5,
            xanchor="center",
            y=0.95,          # position from bottom (0-1)
            yanchor="top",
        ),
        autosize=False,
        yaxis_scaleanchor="x",
        margin=dict(l=0, r=0, t=MAP_MT, b=MAP_MB),
        xaxis=dict(visible=True),
        yaxis=dict(visible=True),
        meta={"aspect_ratio": ASPECT}
    )

    fig.update_xaxes(
        automargin=True,
        showticklabels=True,
        showgrid=True,
        zeroline=True,
        constrain="domain",
    )

    fig.update_yaxes(
        automargin=True,
        showticklabels=True,
        showgrid=True,
        zeroline=True,
        constrain="domain",
        scaleanchor="x",
        scaleratio=1,
    )


    return fig


def make_point_ts_figure(lat, lon):
    ts_point = daflood.sel(lat=lat, lon=lon, method="nearest")
    x=pd.to_datetime(ts_point.time.values).tolist();

    fig = go.Figure(go.Scatter(
        x=x,
        y=list(ts_point.values.flatten()),
        mode="lines",
        line=dict(color="steelblue", width=2),
    ))
    fig.update_layout(
        title=f"Pixel time series at ({lat:.2f}°, {lon:.2f}°)",
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


# ---------------------------------------------------------------------------
# App & layout
# ---------------------------------------------------------------------------

#app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

layout = dbc.Container([

    # Header
    dbc.Row(dbc.Col(
        html.H2("Okavango Delta Inundation", className="text-center"),
    )),


    # Time series
    dbc.Row(
        dbc.Col(
            dcc.Graph(
                id="ts-chart",
                figure=make_ts_figure(time_values[-1]),
                config={"responsive": True},
            ),
            width=True,
        )
    ),


    # Inundation map
    dbc.Row(
        dbc.Col(
            dcc.Graph(
                id="flood-map",
                className="resizable",
                figure=make_map_figure(time_values[-1]),
                config={"responsive": True},
            )
        )
    ),

    # Point time series — hidden until map is clicked
    dbc.Row(dbc.Col(
        dcc.Graph(id="point-ts-chart", style={"display": "none"}),
    )),


    # Frequency map
    dbc.Row(
        dbc.Col(
            dcc.Graph(
                id="freq-map",
                className="resizable",
                figure=make_freq_figure(),
                config={"responsive": True},
            ),
            width=True,
        )
    ),



    # Store selected time in browser
    dcc.Store(id="selected-time", data=str(pd.Timestamp(time_values[-1]))),

], fluid=True, style={"maxWidth": "700px", "minWidth": "360px"})



# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("ts-chart", "figure"),
    Output("flood-map", "figure"),
    Output("selected-time", "data"),
    Input("ts-chart", "clickData"),
    State("selected-time", "data"),
    prevent_initial_call=True,
)
def on_ts_click(click_data, current_time):
    """Click on time series — move vline and update map."""
    if not click_data:
        return dash.no_update, dash.no_update, dash.no_update

    clicked_x = click_data["points"][0]["x"]
    clicked_time = pd.Timestamp(clicked_x)
    nearest = min(time_values, key=lambda t: abs(pd.Timestamp(t) - clicked_time))

    return make_ts_figure(nearest), make_map_figure(nearest), str(nearest)


@callback(
    Output("point-ts-chart", "figure"),
    Output("point-ts-chart", "style"),
    Input("flood-map", "clickData"),
    prevent_initial_call=True,
)
def on_map_click(click_data):
    """Click on map — show pixel time series."""
    if not click_data:
        return dash.no_update, dash.no_update

    pt = click_data["points"][0]
    lat, lon = pt["y"], pt["x"]

    return make_point_ts_figure(lat, lon), {"display": "block"}



