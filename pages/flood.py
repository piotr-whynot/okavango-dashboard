import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import xarray as xr
import os
import threading
from types import SimpleNamespace

dash.register_page(__name__, path="/flood", name="Inundation")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
#
# The file is opened lazily (nothing big is held in memory) and the products that are
# needed on every page load - the time series and the frequency map - are computed in
# blocks of time steps. Maps and pixel time series are read from the file on demand.
# The result is cached per process and rebuilt when the file's modification time changes,
# so a new file shows up without restarting the service.

NC_PATH = "./data/flood/flood_MCD453A4_okavango_merged_int8.nc"
BLOCK = 256          # number of time steps processed at a time (ideally a multiple of the file's time chunk)

MAP_MT=60
MAP_MB=60

_lock = threading.Lock()
_cache = {"key": None, "data": None}


def _build():
    # -99 = cloud, 0 = dry, 1 = wet
    # mask_and_scale=False keeps the raw int8 values (no conversion to float)
    ds = xr.open_dataset(NC_PATH, mask_and_scale=False)
    da1 = ds["inundation"].sortby("lat")
    nt, ny, nx = da1.shape

    nflood = np.zeros(nt)
    ncloud = np.zeros(nt)
    wet = np.zeros((ny, nx), dtype=np.int32)

    for i in range(0, nt, BLOCK):
        blk = da1.isel(time=slice(i, i + BLOCK)).values
        isflood = blk == 1
        nflood[i:i + BLOCK] = isflood.sum(axis=(1, 2)) / 4
        ncloud[i:i + BLOCK] = (blk == 0).sum(axis=(1, 2)) / 4
        wet += isflood.sum(axis=0, dtype=np.int32)

    time = da1["time"].values
    tsraw = xr.DataArray(nflood, coords={"time": time}, dims="time")
    tscloud = xr.DataArray(ncloud, coords={"time": time}, dims="time")

    # frequency of inundation, in %
    freq = xr.DataArray(
        np.round(100.0 * wet / nt, 0),
        coords={"lat": da1["lat"].values, "lon": da1["lon"].values},
        dims=("lat", "lon"),
    )

    return SimpleNamespace(
        ds=ds,                                  # keeps the file open for the on-demand reads
        da1=da1,                                # lazy, raw values
        time_values=time,
        tsflood=tsraw.where(tscloud <= 1000),   # inundated area, images with little cloud
        tsfloodbad=tsraw.where(tscloud > 1000), # inundated area in images with a lot of cloud
        freq=freq,
        aspect=(ny + MAP_MB + MAP_MT + 10) / nx,
    )


def get_data():
    """Returns the cached data, rebuilding it first if the file has changed. Read-only."""
    key = os.path.getmtime(NC_PATH)
    with _lock:
        if key != _cache["key"]:
            _cache["data"] = _build()
            _cache["key"] = key
        return _cache["data"]


# ---------------------------------------------------------------------------
# Figure builders
# ---------------------------------------------------------------------------

def make_ts_figure(sel_time):
    D = get_data()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=D.tsflood.time.data,
        y=list(D.tsflood.data.flatten()),
        mode="lines",
        line=dict(color="grey", width=2),
        name="inundated area",
    ))
    fig.add_trace(go.Scatter(
        x=D.tsfloodbad.time.data,
        y=list(D.tsfloodbad.data),
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
    D = get_data()
    slice_1 = (D.da1.sel(time=sel_time) == 1).astype(np.int8)
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
        meta={"aspect_ratio": D.aspect}
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
    D = get_data()
    y0, y1 = pd.to_datetime(D.time_values[[0, -1]]).year
    fig = go.Figure(go.Heatmap(
        z=D.freq.values,
        x=D.freq["lon"].values,
        y=D.freq["lat"].values,
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
            text=f"Frequency of inundation during {y0}-{y1} period",
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
        meta={"aspect_ratio": D.aspect}
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
    D = get_data()
    ts_point = (D.da1.sel(lat=lat, lon=lon, method="nearest") == 1).astype(np.int8)
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

def layout():
    # rebuilt on every page load, so the initial date and figures reflect the current data
    t = get_data().time_values[-1]
    return dbc.Container([

        # Header
        dbc.Row(dbc.Col(
            html.H2("Okavango Delta Inundation", className="text-center"),
        )),


        # Time series
        dbc.Row(
            dbc.Col(
                dcc.Graph(
                    id="ts-chart",
                    figure=make_ts_figure(t),
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
                    figure=make_map_figure(t),
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
        dcc.Store(id="selected-time", data=str(pd.Timestamp(t))),

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
    time_values = get_data().time_values
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



