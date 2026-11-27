import dash
from dash import dcc, html, Input, Output, State, callback
from dash_bootstrap_templates import load_figure_template
from dash import ctx
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import dash_mantine_components as dmc

from info import make_collapsible_text as _collapsible   # shared show/hide text (text in ./content)

import plotly.graph_objects as go
import pandas as pd
import numpy as np
import xarray as xr
import datetime
import os
import threading
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# First things first
# ---------------------------------------------------------------------------

#registering this page in the app
dash.register_page(__name__, path="/", name="Rainfall")


#setting up templates
figtemplate="flatly"
load_figure_template(figtemplate)   # matches dbc.themes


#dimensions of map
MAP_Y=500
MAP_X=500

#map margins
MAP_MT=60
MAP_MB=60

#map aspect - not used at the moment
#ASPECT = lat_range / lon_range
ASPECT = (MAP_Y+MAP_MB+MAP_MT+10) / MAP_X


#initialization - None picks up last date and a random station
#init_time=pd.to_datetime("2026-01-28")
init_basetime="day"
INIT_TIME=None   # None picks up the last available date at page load
init_siteID="XAKANARE001"
#init_siteID=None

#whether all or reporting only are shown at startup
init_gauge_set=["reporting-only"] #has to be a list
init_year_sort=[False]
init_onemon_sort=[False]
init_onemon_select=["Dec"]
init_accum_select=[]
init_basetime_select=init_basetime

monthabbr=np.array(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
#
# Data are cached per process and re-read whenever either CSV file changes on disk
# (checked with one stat() call per file whenever get_data() is called), so new data
# show up without restarting the service. Nothing here is a mutable global that
# callbacks overwrite: the aggregation level (day/month/year) is an argument, so users
# (and gunicorn workers) cannot interfere with each other.

DAY_PATH = "./data/rainfall/data_day.csv"
SITES_PATH = "./data/rainfall/sites.csv"

_lock = threading.Lock()
_cache = {"key": None, "base": None}


def _build_base():
    """Read the files and do the preprocessing that does not depend on basetime."""
    rain_dly = pd.read_csv(DAY_PATH, index_col=0, parse_dates=True)
    sites = pd.read_csv(SITES_PATH, index_col=0)
    rain_dly.columns.name = "siteID"

    # trimming to the period with data
    sel = ~np.isnan(rain_dly).all(axis=1)
    firstdataday = rain_dly.index[sel][0]
    lastdataday = rain_dly.index[sel][-1]
    rain_dly = rain_dly[firstdataday:lastdataday]

    return SimpleNamespace(
        rain_dly=rain_dly,
        sites=sites,
        nans_dly=np.isnan(rain_dly),
        meanrain_dly=rain_dly.mean(axis=1),
        views={},          # filled on demand, one entry per basetime
    )


def _build_view(base, basetime):
    """Data aggregated to the requested basetime ("day", "month" or "year")."""
    d, nans_d, mean_d = base.rain_dly, base.nans_dly, base.meanrain_dly

    if basetime == "day":
        rain, nans, meanrain = d, nans_d, mean_d
        n_days = pd.Series(1, index=d.index)
    else:
        rule = "MS" if basetime == "month" else "YS-OCT"
        rain = d.resample(rule).sum()
        nans = nans_d.resample(rule).sum()
        meanrain = mean_d.resample(rule).sum()
        n_days = d.resample(rule).size()

    return SimpleNamespace(
        rain=rain,
        nans=nans,
        meanrain=meanrain,
        n_days=n_days,
        time_values=pd.to_datetime(rain.index.values),
        rain_dly=base.rain_dly,     # daily data, whatever the basetime
        sites=base.sites,
    )


def get_data(basetime="day"):
    """Returns an object with .rain, .nans, .meanrain, .n_days, .time_values (at the given
    basetime) and .rain_dly, .sites. Treat the contents as read-only: they are shared
    between requests - use .copy() before modifying anything."""
    key = (os.path.getmtime(DAY_PATH), os.path.getmtime(SITES_PATH))
    with _lock:
        if key != _cache["key"]:            # files changed (or first call): rebuild
            _cache["base"] = _build_base()
            _cache["key"] = key
        base = _cache["base"]
        if basetime not in base.views:
            base.views[basetime] = _build_view(base, basetime)
        return base.views[basetime]


# ---------------------------------------------------------------------------
# Figure and table builders
# ---------------------------------------------------------------------------



def make_marker_map(sel_time,sel_site, basetime, gauge_set):
    # get values for selected time step

    # merging data array with sites array


    D = get_data(basetime)
    df_t = D.rain.T[[sel_time]].merge(D.sites, on="siteID")
    df_nans = D.nans.T[[sel_time]].merge(D.sites, on="siteID")
    ndays = D.n_days.T[[sel_time]].values[0]

    sel_time=basetime_date(sel_time, basetime)

    #print("marker map time", rain.index.values[0:5])

    if basetime=="year":
        size_scale = 100  # max marker size in pixels
        vmax = 1000
        vmin = 6
        daycount=365
    if basetime=="month":
        size_scale = 100  # max marker size in pixels
        vmax = 200
        vmin = 6
        daycount=28
    elif basetime=="day":
        size_scale = 100  # max marker size in pixels
        vmax = 100
        vmin = 6
        daycount=1


    df_t.rename(columns={df_t.columns[0]:"value"}, inplace=True)
    df_nans.rename(columns={df_nans.columns[0]:"value"}, inplace=True)

    #selecting only stations with data, i.e. no nans
    valid=df_nans["value"]==0
    partial=df_nans["value"]<ndays #partial and valid
    nodata=df_nans["value"]>=ndays

    # replacing values that are nans with nans
    df_t.loc[nodata,"value"]=np.nan

    if "reporting-only" in gauge_set:

        #showing only valid or partial
        df_t=df_t[partial]
        df_nans=df_nans[partial]
        nodata=nodata[partial]
        valid=valid[partial]
        partial=partial[partial]

   
    # scale marker size
    sizes = (df_t["value"] / vmax * size_scale).fillna(vmin).clip(lower=vmin)  # min size 3

    #colors = ["black" if np.isnan(s) else "steelblue" for s in df_t["value"]]

    FLAG_COLORS = {False: "lightblue", True: "steelblue"}   # choose your colours
    FLAG_LABELS = {False: "Some days missing", True: "All daily measurements"}   # legend text
    NODATA_COLOR = "black"

    colors = [NODATA_COLOR if n else FLAG_COLORS[f] for n,f in zip(nodata,valid)]

    fig = go.Figure()

    # white halo underneath
    fig.add_trace(go.Scattermap(
        lat=df_t["Latitude"], 
        lon=df_t["Longitude"],
        mode="markers",
        marker=dict(size=[s + 4 for s in sizes], color="white"),
        hoverinfo="skip",
        showlegend=False,
    ))

    # actual markers on top
    fig.add_trace(go.Scattermap(
        lat=df_t["Latitude"],
        lon=df_t["Longitude"],
        mode="markers+text",
        marker=dict(
            size=sizes, 
            color=colors,
        ),
        text=df_t["value"].round(1).astype(str),
        textposition="top center",
        textfont=dict(size=15, color="black"),
        showlegend=False,
        customdata=np.stack([
            df_t.index,
            df_t["Observer's Name"],
            df_t["Location"],
            df_t["value"],
            df_nans["value"]
        ], axis=1),
        hovertemplate="<b>%{customdata[0]}</b><br>value: %{customdata[3]} mm<br>Location: %{customdata[2]}<br>Owner: %{customdata[1]}<br>Missing days: %{customdata[4]}<extra></extra>",
    ))

    fig.update_layout(
        map=dict(
            style="open-street-map",
            zoom=7,
            center=dict(
                lat=-19.3,
                lon=22.7,
            ),
        ),
        height=700,
        margin=dict(l=0, r=0, t=0, b=0),
        autosize=True,
        uirevision="constant",
    )

    return fig


def make_time_string(sel_time,basetime):
    if basetime=="day":
        time_str="on "+pd.to_datetime(sel_time).strftime("%d %b %Y"),
    if basetime=="month":
        time_str="in "+pd.to_datetime(sel_time).strftime("%b %Y"),
    if basetime=="year":
        fyear=pd.to_datetime(sel_time).strftime("%Y")
        lyear=int(fyear)+1
        time_str=f"in Oct {fyear} - Sep {lyear}"
    return time_str



def make_time_selector(sel_time, basetime):

    if basetime=="year":
        daycount=365
    if basetime=="month":
        daycount=28
    elif basetime=="day":
        daycount=1

    D = get_data(basetime)
    data = D.meanrain.copy()
    flag = D.n_days>=daycount
    sel_time = basetime_date(sel_time, basetime)

    x = data.index
    y = data.values.flatten()

    fig = go.Figure()

    # connecting line, not in the legend
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines",
        line=dict(color="grey", width=1),
        showlegend=False, hoverinfo="skip",
    ))

    # one marker trace per value of the boolean -> one legend entry each
    for value, label, colour in [
        (True,  "full period",  "royalblue"),
        (False, "period partially covered by data", "orange"),
    ]:
        mask = (flag == value).values
        fig.add_trace(go.Scatter(
            x=x[mask], y=y[mask], mode="markers", name=label,
            marker=dict(color=colour, size=6, line=dict(color="black", width=1)),
        ))

    fig.add_vline(
        x=str(pd.Timestamp(sel_time))[:10],
        line=dict(color="red", width=2, dash="dash"),
    )
    fig.update_layout(
        yaxis_title="Rainfall (mm)",
        template=figtemplate,
        height=220,
        autosize=True,
        legend=dict(orientation="h", x=1, y=1, xanchor="right", yanchor="bottom"),
        margin=dict(l=0, r=0, t=25, b=10),
    )

    return fig

def basetime_date(sel_time, basetime):
    t = pd.to_datetime(sel_time)
    if basetime == "year":
        t = t.replace(month=10, day=1)
    elif basetime == "month":
        t = t.replace(day=1)
    return t


def picker_value(sel_time, basetime):
    """datetime -> string held by the date picker: 'YYYY-MM-DD', where month and year
    basetimes use the first day of the period. Always the same format the picker emits,
    so writing it back to the picker does not make the picker 'change'."""
    t = pd.Timestamp(sel_time)
    time_values = get_data(basetime).time_values
    t = min(max(t, pd.Timestamp(time_values.min())), pd.Timestamp(time_values.max()))
    if basetime == "year":
        t = t.replace(month=10, day=1)
    elif basetime == "month":
        t = t.replace(day=1)
    return str(t.date())


def dbg(name, *info):  # DEBUG
    print(f"[{datetime.datetime.now():%H:%M:%S.%f}] {name} <- {list(ctx.triggered_prop_ids)}", *info, flush=True)  # DEBUG


def picker_time(value):
    """string from the date picker -> Timestamp"""
    return pd.Timestamp(value)


def make_date_picker(sel_time, basetime):
    """The one date picker (always id='date-picker', property 'value'); its type
    follows basetime: day -> calendar, month -> month picker, year -> year picker."""
    time_values = get_data(basetime).time_values
    kwargs = dict(
        id="date-picker",
        value=picker_value(sel_time, basetime),
        minDate=str(pd.Timestamp(time_values.min()).date()),
        maxDate=str(pd.Timestamp(time_values.max()).date()),
        clearable=False,
        size="sm",
    )
    if basetime == "year":
        return dmc.YearPickerInput(valueFormat="YYYY", w=110, **kwargs)
    if basetime == "month":
        return dmc.MonthPickerInput(valueFormat="MMM YYYY", w=140, **kwargs)
    return dmc.DatePickerInput(valueFormat="YYYY-MM-DD", w=140, **kwargs)




def make_data_table(sel_time, basetime, gauge_set):

    if basetime=="year":
        daycount=365
    if basetime=="month":
        daycount=28
    elif basetime=="day":
        daycount=1


    # merging data array with sites array
    D = get_data(basetime)
    df_t=np.round(D.rain.T[[sel_time]],2)
    df_t =df_t.merge(D.sites, on="siteID")
    df_nans = D.nans.T[[sel_time]].merge(D.sites, on="siteID")
    sel_time=basetime_date(sel_time, basetime)

    ndays = D.n_days.T[[sel_time]].values[0]


    df_t.rename(columns={df_t.columns[0]:"value"}, inplace=True)
    df_nans.rename(columns={df_nans.columns[0]:"value"}, inplace=True)


    #selecting only stations with data, i.e. no nans
    valid=df_nans["value"]==0
    partial=df_nans["value"]<ndays
    nodata=df_nans["value"]==ndays

    # replacing values that are nans with nans
    df_t.loc[nodata,"value"]=np.nan

    if "reporting-only" in gauge_set:

        #showing only valid
        df_t=df_t[partial]



    df_t=df_t.reset_index()
    df_t=df_t[["value","siteID","Location"]]



    return dag.AgGrid(
        id="data-table-inner",
        className="ag-theme-alpine", 
        columnDefs=[
            {"headerName": "Value (mm)", "field": "value"},
            {"headerName": "Gauge ID", "field": "siteID"},
            {"headerName": "Location", "field": "Location"},

        ],
        rowData=df_t.to_dict("records"),
        columnSize="sizeToFit",
        dashGridOptions={
            "animateRows":True,
            "rowSelection": {"mode": "singleRow",
            "checkboxes": False,           # no checkbox column, click row directly
            "enableClickSelection": True,   # clicking the row selects it
             }, 
        },
    )





def make_gauge_info(siteID):
    D = get_data("day")
    ts = D.rain_dly[siteID].sort_index()
    sel=~np.isnan(ts)
    ts=ts[sel]
    tsmax=np.max(ts)

    i=np.where(ts==tsmax)
    maxdate=ts.iloc[i[0]].index.values[0]
    maxdate=pd.to_datetime(maxdate).strftime("%d %b %Y")

    firstdate=pd.to_datetime(ts.index[0]).strftime("%d %b %Y")
    lastdate=pd.to_datetime(ts.index[-1]).strftime("%d %b %Y")

    info = D.sites.loc[siteID].copy()
    obstime=info['Observation time']
    try:
        obstime=float(obstime)
        obstime=str(int(obstime*24)).zfill(2)
        obstime=f"{obstime}:00"
    except:
        cont=True

    if np.isnan(info["URL"]):
        info["URL"]="Not available"

    df_info = pd.DataFrame({
        "Property": ["Station ID", 
                    "Latitude", 
                    "Longitude", 
                    "Location",
                    "Observer's name",
                    "Status",
                    "Gauge type",
                    "URL",
                    "Observation time",
                    "Maximum recorded value",
                    "Observations start on",
                    "Most recent observaion"],
        "Value": [siteID, 
            f"{info['Latitude']:.3f}", 
            f"{info['Longitude']:.3f}", 
            f"{info['Location']}",
            f"{info['Observer\'s Name']}",
            f"{info['Status']}",
            f"{info['Gauge type']}",
            f"{info['URL']}",
            f"{obstime}",
            f"{tsmax:.0f} mm on {maxdate}", 
            f"{firstdate}", 
            f"{lastdate}", 
            ],
    })
    
     
    table = dbc.Table.from_dataframe(
        df_info,
        striped=True,
        bordered=False,
        hover=False,
        size="sm",
    )

    return table
    




def make_gauge_ts_day(siteID):

    ts = get_data("day").rain_dly[siteID].sort_index()

    fig = go.Figure(go.Scatter(
        x=pd.to_datetime(ts.index).tolist(),
        y=ts.tolist(),
        mode="lines",
        line=dict(color="steelblue", width=2),
    ))
    fig.update_layout(
        yaxis_title="Rainfall (mm/day)",
        height=200,
        autosize=True,
        margin=dict(l=0, r=0, t=0, b=0),
    )


    return fig


def make_gauge_accum_day(df,alllabels):

    fig = go.Figure()

    for col in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index.tolist(),
            y=df[col].cumsum().tolist(),
            mode="lines",
            marker_color="lightgrey",
            name=col,  # shows up in legend
            line=dict(width=2),
            hovertext=[alllabels[d] for d in df.index],
            hovertemplate="%{y}<br>%{hovertext}<br>%{fullData.name}<extra></extra>",
            showlegend=False,
        ))


    # Sparse ticks - every 30 days
    tick_offsets = list(range(0, 365, 30))
    tick_labels = [alllabels[d] for d in tick_offsets]

    fig.update_xaxes(
        tickmode="array",
        tickvals=tick_offsets,
        ticktext=tick_labels,
    )

    fig.update_layout(
        yaxis_title="Rainfall (mm)",
        height=500,
        autosize=True,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
    )

    return fig


def get_accum_data(siteID):

    ts = get_data("day").rain_dly[siteID].sort_index()

    start_month,start_day=10,1

    df=get_hy(ts,start_month,start_day)

    df= df.dropna(axis=1, how="all")
    

    date_labels = pd.date_range(start=f"2000-{start_month:02d}-{start_day:02d}", periods=366, freq="D")
    label_lookup = date_labels.strftime("%d %b")[:365]  # trim to 365 to match day_offset range
    day_offset_labels = pd.Series(label_lookup, index=range(365))

    return df,day_offset_labels






def make_gauge_ts_mon(siteID):

    ts = get_data("day").rain_dly[siteID].sort_index()

    validmon=np.invert(np.isnan(ts)).resample("MS").sum()
    ndaysmon=pd.Series(validmon.index.daysinmonth.values, index=validmon.index)

    percvalid=np.round((validmon/ndaysmon*100).astype(int),0)
    validdata=percvalid>98

    colors = ["steelblue" if flag else "lightblue" for flag in validdata]
    ts=ts.resample("MS").sum()

    fig = go.Figure(go.Bar(
        x=pd.to_datetime(ts.index).tolist(),
        y=ts.tolist(),
        marker_color=colors,
        showlegend=False,
        customdata=np.stack([
            ts.values,
            ts.index.strftime("%b %Y"),
            percvalid.values,
        ], axis=1),
        hovertemplate="value:<b>%{customdata[0]}</b>mm<br>period: %{customdata[1]}<br>valid daily data: %{customdata[2]} %<extra></extra>",

    ))

    # dummy traces just for the legend
    fig.add_trace(go.Bar(
        x=[None], y=[None],
        marker_color="steelblue",
        name="all valid data",
        showlegend=True,
    ))
    fig.add_trace(go.Bar(
        x=[None], y=[None],
        marker_color="lightblue",
        name="some missing daily data",
        showlegend=True,
    ))



    fig.update_layout(
        yaxis_title="Rainfall (mm/month)",
        xaxis_title=None,
        height=250,
        autosize=True,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )


    return fig



def make_gauge_ts_onemon(siteID, onemon_sort,onemon_select):

    selmon=np.where(monthabbr==onemon_select)[0][0]+1

    ts = get_data("day").rain_dly[siteID].sort_index()

    #monthly
    validmon=np.invert(np.isnan(ts)).resample("ME").sum()

    ndaysmon=pd.Series(validmon.index.daysinmonth.values, index=validmon.index)

    validmon[validmon.index.month.isin([4,5,6,7,8,9,10])]=0
    ndaysmon[ndaysmon.index.month.isin([4,5,6,7,8,9,10])]=0

    percvalid=np.round((validmon/ndaysmon*100),0)

    #percvalid=percvalid.astype(int)
    validdata=percvalid>98

    ts=ts.resample("ME").sum()
    ts=ts[ts.index.month==selmon]
    validdata=validdata[validdata.index.month==selmon]
    percvalid=percvalid[percvalid.index.month==selmon]

    colors = np.array(["steelblue" if flag else "lightblue" for flag in validdata])
    labels=ts.index.year.values

    if True in onemon_sort:
        sortidx=np.argsort(ts).values[::-1]
        sortedts=ts.iloc[sortidx]
        sortedcolors=colors[sortidx]
        sortedlabels=labels[sortidx]
        sortedpercvalid=percvalid.iloc[sortidx]
        x=list(range(len(ts)))
        fig = go.Figure(go.Bar(
            x=x,
            y=sortedts.tolist(),
            marker_color=sortedcolors,
            showlegend=False,
            customdata=np.stack([
                sortedts.values,
                sortedlabels,
                sortedpercvalid.values,
            ], axis=1),
            hovertemplate="value:<b>%{customdata[0]}</b>mm<br>year: %{customdata[1]}<br>valid daily data: %{customdata[2]} %<extra></extra>",
        ))

        fig.update_xaxes(
            tickmode="array",
            tickvals=x,
            ticktext=sortedlabels,
        )

    else:

        fig = go.Figure(go.Bar(
            x=pd.to_datetime(ts.index).tolist(),
            y=ts.tolist(),
            marker_color=colors,
            showlegend=False,
            customdata=np.stack([
                ts.values,
                labels,
                percvalid.values,
            ], axis=1),
            hovertemplate="value:<b>%{customdata[0]}</b>mm<br>year: %{customdata[1]}<br>valid daily data: %{customdata[2]} %<extra></extra>",
        ))

    # dummy traces just for the legend
    fig.add_trace(go.Bar(
        x=[None], y=[None],
        marker_color="steelblue",
        name="all valid data",
        showlegend=True,
    ))
    fig.add_trace(go.Bar(
        x=[None], y=[None],
        marker_color="lightblue",
        name="some missing daily data",
        showlegend=True,
    ))


    fig.update_layout(
        yaxis_title="Rainfall (mm/month)",
        xaxis_title=None,
        height=250,
        autosize=True,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
    )


    return fig








def make_gauge_ts_year(siteID, year_sort):

    ts = get_data("day").rain_dly[siteID].sort_index()
    #monthly
    validmon=np.invert(np.isnan(ts)).resample("MS").sum()
    ndaysmon=pd.Series(validmon.index.daysinmonth.values, index=validmon.index)

    validmon[validmon.index.month.isin([4,5,6,7,8,9,10])]=0
    ndaysmon[ndaysmon.index.month.isin([4,5,6,7,8,9,10])]=0

    validyear=validmon.resample("YS-OCT").sum()
    ndaysyear=ndaysmon.resample("YS-OCT").sum()

    sel=ndaysyear>0

    validyear=validyear[sel]
    ndaysyear=ndaysyear[sel]

    percvalid=np.round((validyear/ndaysyear*100).astype(int),0)
    validdata=percvalid>98
    
    ts=ts.resample("YS-OCT").sum()

    ts=ts[sel]

    colors = np.array(["steelblue" if flag else "lightblue" for flag in validdata])
    labels=np.array([f"{x.year}-{x.year+1}" for x in ts.index])

    if True in year_sort:
        sortidx=np.argsort(ts).values[::-1]
        sortedts=ts.iloc[sortidx]
        sortedcolors=colors[sortidx]
        sortedlabels=labels[sortidx]
        sortedpercvalid=percvalid.iloc[sortidx]
        x=list(range(len(ts)))
        fig = go.Figure(go.Bar(
            x=x,
            y=sortedts.tolist(),
            marker_color=sortedcolors,
            showlegend=False,
            customdata=np.stack([
                sortedts.values,
                sortedlabels,
                sortedpercvalid.values,
            ], axis=1),
            hovertemplate="value:<b>%{customdata[0]}</b>mm<br>year: %{customdata[1]}<br>valid daily data: %{customdata[2]} %<extra></extra>",
        ))

        fig.update_xaxes(
            tickmode="array",
            tickvals=x,
            ticktext=sortedlabels,
        )



    else:

        fig = go.Figure(go.Bar(
            x=pd.to_datetime(ts.index).tolist(),
            y=ts.tolist(),
            marker_color=colors,
            showlegend=False,
            customdata=np.stack([
                ts.values,
                labels,
                percvalid.values,
            ], axis=1),
            hovertemplate="value:<b>%{customdata[0]}</b>mm<br>year: %{customdata[1]}<br>valid daily data: %{customdata[2]} %<extra></extra>",
        ))

    # dummy traces just for the legend
    fig.add_trace(go.Bar(
        x=[None], y=[None],
        marker_color="steelblue",
        name="all valid data",
        showlegend=True,
    ))
    fig.add_trace(go.Bar(
        x=[None], y=[None],
        marker_color="lightblue",
        name="some missing daily data",
        showlegend=True,
    ))



    fig.update_layout(
        yaxis_title="Rainfall (mm/year)",
        xaxis_title=None,
        height=250,
        autosize=True,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
    )


    return fig




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_hy(ts, start_month=10, start_day=1):

    ts = ts.copy()
    ts.index = pd.to_datetime(ts.index)
    idx = ts.index


    doy = idx.dayofyear.to_numpy()

    # year is irrelevant, this is just to calcualate offset of the hydro year start
    start_doy = pd.Timestamp(2001, start_month, start_day).dayofyear
    day_offset = (doy - start_doy) % 365

    hydro_year_start = np.where(idx.month >= start_month, idx.year, idx.year - 1)

    labels = [f"{y}-{y+1}" for y in hydro_year_start]

    df = pd.DataFrame({"hydro_year": labels, "dohy": day_offset, "value": ts.values})

    wide = df.groupby(["dohy", "hydro_year"])["value"].mean().unstack("hydro_year")

    return wide.sort_index()



   

def make_collapsible_text(text_id, index=None):
    """Show/hide description under a figure; text is in content/figures/rainfall/<text_id>.md.
    (index is no longer needed but kept so the calls in the layout stay as they are)"""
    return _collapsible(f"figures/rainfall/{text_id}")



# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


layout = dbc.Container([

    # --- Page header ---
    dbc.Row([
        dbc.Col(html.H2("Region's Rainfall", className="text-center"), className="my-auto"),
    ], align="center", className="py-1 border-bottom mb-2"),



    # data-driven content
    dbc.Row([
        # map with markers
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(
                            html.H5(["Rainfall ",html.Span("", id="map-title-time")]),
                        ),
                    ]),
                    dbc.Row([
                        dbc.Col(
                            dbc.Checklist(
                                id="gauge-set",
                                options=[
                                    {"label": "Show reporting gauges only", "value": "reporting-only"},
                                ],
                                value=init_gauge_set,
                                switch=True,
                            ),
                        ),
                        dbc.Col(
                            dcc.Dropdown(
                                id="basetime-select",
                                options=["year","month","day"],
                                value=init_basetime_select,
                                multi=False,
                                clearable=False,
                                searchable=False,
                                style={"width": "400px", "marginBottom": "10px"},
                            ),
                        ),
                    ]),
                    html.P("Click on marker to show data for that gauge", className="text-muted small"),
                    dcc.Graph(
                        id="marker-map",
                        config={"responsive": True},
                    ),
                    make_collapsible_text("marker-map",0)
                ]),
            ],className="shadow-sm m-3 px-3"),
        ],xs=12,lg=6),




        dbc.Col([
            # time-selector chart - region's time series
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            
                            dbc.Col(
                                html.H5("Average across all reporting stations"),
                            ),
                            dbc.Col(dbc.Button("⏮\ufe0e", id="first-date", size="sm", color="secondary"), width="auto"),
                            dbc.Col(dbc.Button("◀", id="prev-date", size="sm", color="secondary"), width="auto"),
                            dbc.Col(
                                id="date-picker-container",
                                # placeholder with no data in it - the real picker (with bounds
                                # from the current data) is put here by init_page
                                children=dmc.DatePickerInput(id="date-picker", valueFormat="YYYY-MM-DD", w=140, clearable=False, size="sm"),
                                width="auto",
                            ),
                            dbc.Col(dbc.Button("▶\ufe0e", id="next-date", size="sm", color="secondary"), width="auto"),
                            dbc.Col(dbc.Button("⏭\ufe0e", id="last-date", size="sm", color="secondary"), width="auto"),
                        ], justify="center", align="center", className="g-2"),

                        html.P("Select date or click on the figure to select date", className="text-muted text-left small"),
                        html.Div( 
                            id="gauge-info-container",
                            children=dcc.Graph(
                                id="time-selector-chart",
                                config={"responsive": True},
                                ),
                        ),
                        make_collapsible_text("time-selector-chart",1)
                    ]),
                ],className="shadow-sm m-3 px-3"),


            # data table
                dbc.Card([
                    dbc.CardBody([
                        html.H5(["Rainfall ",html.Span("", id="table-title-time")]),

                        html.P("Click on row to show data for selected gauge. Click on header to sort table by column values.", className="text-muted small"),

                        html.Div(
                            id="data-table",   # filled by update_figures
                        ),
                        make_collapsible_text("data-table",2),
                    ]),
                ],className="shadow-sm m-3 px-3"),

        ],xs=12,lg=6),


    # closing first row
    ], className="g-5"),

    dbc.Row([
        dbc.Col(html.H2("Selected location's rainfall", className="text-center"), className="my-auto"),
    ], align="center", className="py-1 border-bottom mb-2"),




    #figures for individual gauge row
    dbc.Row([

        # station info
        dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5(["Info for gauge ", html.Span(init_siteID, id="gauge-info-title")], className="card-title"),
                        html.Div( 
                            id="gauge-info-container",
                            children=make_gauge_info(init_siteID),
                        ),
                    ]),
                ],className="shadow-sm m-3 px-3"),
        ],xs=12,lg=6),




        #station time series - daily
        dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5(["Daily time series for ", html.Span(init_siteID, id="gauge-ts-day-title")], className="card-title"),
                        html.Div( 
                            id="gauge-ts-day-container",
                            children=dcc.Graph(
                                    id="gauge-ts-day-chart",
                                    #className="resizable",
                                    #figure=make_gauge_ts_day(init_siteID),
                                    config={"responsive": True},
                            ),
                        ),
                        make_collapsible_text("gauge-ts-day",3)
                    ]),
                ],className="shadow-sm m-3 px-3"),
        ],xs=12,lg=6),


        #daily cumulative
        dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(
                                html.H5(["Accumulated rainfall for ", html.Span(init_siteID, id="gauge-accum-day-title")], className="card-title"),

                            ),
                        ]),
                        dbc.Row([
                            dbc.Col(
                                dcc.Dropdown(
                                    id="accum-select",
                                    options=[],
                                    value=[],
                                    multi=True,
                                    searchable=False,
                                    placeholder="Select hydro year(s) to highlight...",
                                    style={"width": "400px", "marginBottom": "10px"},
                                ),
                            ),
                        ]),

                        html.Div( 
                            id="gauge-accum-day-container",
                            children=dcc.Graph(
                                    id="gauge-accum-day-chart",
                                    #className="resizable",
                                    #figure=make_gauge_accum_day(init_siteID,init_accum_select),
                                    config={"responsive": True},
                            ),
                        ),
                        make_collapsible_text("gauge-accum-day",4)
                    ]),
                ],className="shadow-sm m-3 px-3"),
        ],xs=12,lg=6),



        #station time series - monthly
        dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5(["Monthly time series for ", html.Span(init_siteID, id="gauge-ts-mon-title")], className="card-title"),
                        html.Div( 
                            id="gauge-ts-mon-container",
                            children=dcc.Graph(
                                    id="gauge-ts-mon-chart",
                                    #className="resizable",
                                    #figure=make_gauge_ts_mon(init_siteID),
                                    config={"responsive": True},
                            ),
                        ),
                        make_collapsible_text("gauge-ts-mon",4)
                    ]),
                ],className="shadow-sm m-3 px-3"),
        ],xs=12,lg=6),



        #station time series - single month
        dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(
                            html.H5(["Time series for selected month for ", html.Span(init_siteID, id="gauge-ts-onemon-title")], className="card-title"),
                            ),
                        ]),
                        dbc.Row([
                            dbc.Col(
                                dbc.Checklist(
                                    id="onemon-sort",
                                    options=[
                                        {"label": "Sort by value", "value": True},
                                    ],
                                    value=init_onemon_sort,
                                    switch=True,
                                ),
                            ),
                            dbc.Col(
                                dcc.Dropdown(
                                    id="onemon-select",
                                    options=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
                                    value=init_onemon_select,
                                    multi=False,
                                    clearable=False,
                                    searchable=False,
                                    placeholder="Select month...",
                                    style={"width": "200px", "marginBottom": "10px"},
                                ),
                            ),
                        ]),

                        html.Div( 
                            id="gauge-ts-onemon-container",
                            children=dcc.Graph(
                                    id="gauge-ts-onemon-chart",
                                    config={"responsive": True},
                            ),
                        ),
                        make_collapsible_text("gauge-ts-onemon",5)
                    ]),
                ],className="shadow-sm m-3 px-3"),
        ],xs=12,lg=6),



        #station time series - annual
        dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(
                            html.H5(["Annual time series for ", html.Span(init_siteID, id="gauge-ts-year-title")], className="card-title"),
                            ),
                        ]),
                        dbc.Row([
                            dbc.Col(
                                dbc.Checklist(
                                    id="year-sort",
                                    options=[
                                        {"label": "Sort by value", "value": True},
                                    ],
                                    value=init_year_sort,
                                    switch=True,
                                ),
                            ),
                        ]),

                        html.Div( 
                            id="gauge-ts-year-container",
                            children=dcc.Graph(
                                    id="gauge-ts-year-chart",
                                    #className="resizable",
                                    #figure=make_gauge_ts_year(init_siteID, init_year_sort),
                                    config={"responsive": True},
                            ),
                        ),
                        make_collapsible_text("gauge-ts-year",5)
                    ]),
                ],className="shadow-sm m-3 px-3"),
        ],xs=12,lg=6),

    ], className="g-5"),


    # Store selected time in browser
    dcc.Store(id="selected-time"),   # set by init_page

    # Store selected site
    dcc.Store(id="selected-site", data=init_siteID),

    dcc.Store(id="basetime", data=init_basetime_select),

    dcc.Store(id="dummy-store", data=""),

    #init trigger
    dcc.Store(id="init-trigger", data=True),

    dcc.Store(id="init-ready"),   # set by init_page once selected-time and the date picker exist

], fluid=True, style={"minWidth": "360px","maxWidth": "1800px"})





# ---------------------------------------------------------------------------
# Server-side callbacks
# ---------------------------------------------------------------------------




# page initialisation: runs on every page load, so the starting date and the date picker bounds
# always reflect the current data
@callback(
    Output("selected-time", "data"),
    Output("date-picker-container", "children"),
    Output("init-ready", "data"),
    Input("init-trigger", "data"),
)
def init_page(_):
    dbg("init_page")  # DEBUG
    D = get_data("day")
    t = INIT_TIME if INIT_TIME is not None else D.time_values[-1]
    return str(pd.Timestamp(t)), make_date_picker(t, init_basetime), True


# change map when selected-time changes
@callback(
    Output("marker-map", "figure"),
    Output("map-title-time", "children"),
    Output("table-title-time", "children"),
    Output("data-table", "children"),
    Output("date-picker", "value"),
    Input("selected-time", "data"),
    Input("gauge-set", "value"),
    Input("basetime", "data"),
    State("selected-site", "data"),
)
def update_figures(selected_time, gauge_set,basetime,selected_site):
    dbg("update_figures", selected_time, basetime)  # DEBUG
    if not selected_time:       # init_page has not set it yet
        raise dash.exceptions.PreventUpdate
    selected_time=basetime_date(selected_time, basetime)
    return (
        make_marker_map(selected_time,selected_site,basetime,gauge_set), 
        make_time_string(selected_time, basetime),
        make_time_string(selected_time, basetime),
        make_data_table(selected_time, basetime, gauge_set),
        picker_value(selected_time, basetime),
    )


# basetime store: driven by the basetime selector only, so that selecting a time or a site
# does not redraw the time selector chart
@callback(
    Output("basetime", "data"),
    Input("basetime-select", "value"),
)
def set_basetime(basetime):
    dbg("set_basetime", basetime)  # DEBUG
    return basetime


# plotting time selector
@callback(
    Output("time-selector-chart", "figure"),
    Input("init-ready", "data"),
    Input("basetime", "data"),
    State("selected-time", "data"),
)
def update_figure(trigger,basetime,selected_time):
    dbg("update_figure(time selector)", basetime)  # DEBUG
    if not selected_time:       # init_page has not set it yet
        raise dash.exceptions.PreventUpdate
    return (
        make_time_selector(selected_time,basetime)
    )




# click on time selector chart
@callback(
    Output("selected-time", "data", allow_duplicate=True),
    Input("time-selector-chart", "clickData"),
    State("basetime", "data"),
    prevent_initial_call=True,
)
def on_ts_click(click_data, basetime):
    dbg("on_ts_click")  # DEBUG
    time_values = get_data(basetime).time_values
    if not click_data:
        return dash.no_update

    #picking up clicked time
    clicked_x = click_data["points"][0]["x"]
    clicked_ts = pd.Timestamp(clicked_x)
    clicked_time = min(time_values, key=lambda t: abs(pd.Timestamp(t) - clicked_ts))
    print("writing from time selector",clicked_time)
    return clicked_time



#date picker - handles previous and next buttons
@callback(
    Output("selected-time", "data", allow_duplicate=True),
    Output("date-picker", "value", allow_duplicate=True),
    Input("date-picker", "value"),
    Input("first-date", "n_clicks"),
    Input("prev-date", "n_clicks"),
    Input("next-date", "n_clicks"),
    Input("last-date", "n_clicks"),
    State("selected-time", "data"),
    State("basetime-select", "value"),
    prevent_initial_call=True,
)
def on_date_change(picked_date, first_click, prev_clicks, next_clicks, last_click, current_time, basetime):
    dbg("on_date_change", picked_date, current_time, basetime)  # DEBUG
    time_values = get_data(basetime).time_values

    current = pd.Timestamp(current_time)

    #print("picker time", time_values)

    if ctx.triggered_id == "date-picker":
        if not picked_date:
            return dash.no_update, dash.no_update
        nearest = min(time_values, key=lambda t: abs(pd.Timestamp(t) - picker_time(picked_date)))
    elif ctx.triggered_id == "first-date":
        nearest = time_values[0]
    elif ctx.triggered_id == "prev-date":
        earlier = [t for t in time_values if pd.Timestamp(t) < current]
        nearest = max(earlier) if earlier else current
    elif ctx.triggered_id == "next-date":
        later = [t for t in time_values if pd.Timestamp(t) > current]
        nearest = min(later) if later else current
    elif ctx.triggered_id == "last-date":
        nearest = time_values[-1]
    else:
        nearest = current

    return pd.to_datetime(nearest), picker_value(nearest, basetime)


# replacing the date picker (same id, different type) when basetime changes
@callback(
    Output("date-picker-container", "children", allow_duplicate=True),
    Input("basetime-select", "value"),
    State("selected-time", "data"),
    prevent_initial_call=True,
)
def swap_date_picker(basetime, selected_time):
    dbg("swap_date_picker", basetime, selected_time)  # DEBUG
    return make_date_picker(selected_time, basetime)


# plotting ts-onemon
@callback(
    Output("gauge-ts-onemon-chart", "figure"),
    Input("onemon-sort", "value"),
    Input("onemon-select", "value"),
    Input("selected-site", "data"),
)
def update_figure(onemon_sort,onemon_select,siteID):
    return (
        make_gauge_ts_onemon(siteID, onemon_sort,onemon_select)
    )


# plotting ts-year
@callback(
    Output("gauge-ts-year-chart", "figure"),
    Output("gauge-ts-year-title", "children"),
    Input("year-sort", "value"),
    Input("selected-site", "data"),
)
def update_figure(year_sort, siteID):
    return (
        make_gauge_ts_year(siteID, year_sort),
        siteID
    )


#updating accumulated daily rainfall when changing site
@callback(
    Output("accum-select", "options"),
    Output("accum-select", "value"),
    Output("gauge-accum-day-chart", "figure"),
    Output("gauge-accum-day-title", "children"),
    Input("selected-site", "data"),
)
def update_year_options(siteID):

    df,labels=get_accum_data(siteID)

    fig=make_gauge_accum_day(df,labels)

    years = list(df.columns)

    return (
        [{"label": y, "value": y} for y in years],
        [],
        fig,
        siteID
    )


# change in selected-site
@callback(
    Output("gauge-ts-day-chart", "figure"),
    Output("gauge-ts-mon-chart", "figure"),
    Output("gauge-info-container", "children"),
    Output("gauge-ts-day-title", "children"),
    Output("gauge-ts-mon-title", "children"),
    Output("gauge-ts-onemon-title", "children"),
    Output("gauge-info-title", "children"),
    Input("selected-site", "data"),
    #prevent_initial_call=True,
)
def update_figures(siteID):
    dbg("update_figures(site)", siteID)  # DEBUG
    return (
        make_gauge_ts_day(siteID),
        make_gauge_ts_mon(siteID),
        make_gauge_info(siteID),
        siteID,
        siteID,
        siteID,
        siteID,
    )



# clicking on station in the map
@callback(
    Output("selected-site", "data"),
    Input("marker-map", "clickData"),
    prevent_initial_call=True,
)
def on_gauge_click(click_data):
    dbg("on_gauge_click")  # DEBUG
    if not click_data:
        return dash.no_update


    pt = click_data["points"][0]
    siteID = pt["customdata"][0]  # siteID is first in customdata

    return siteID



#clicking on row in data table
@callback(
    Output("selected-site", "data", allow_duplicate=True),
    Input("data-table-inner", "selectedRows"),
    prevent_initial_call=True,
)
def on_table_row_click(selected_rows):
    dbg("on_table_row_click", selected_rows[0]["siteID"] if selected_rows else None)  # DEBUG
    if not selected_rows:
        return dash.no_update
    return selected_rows[0]["siteID"]



#updating table selection. Apparently it is tricky to do it on the client side, so its a server side callback
@callback(
    Output("data-table-inner", "selectedRows"),
    Output("data-table-inner", "scrollTo"),
    Input("selected-site", "data"),
    State("data-table-inner", "rowData"),
    prevent_initial_call=True,
)
def sync_grid_selection(selected_site, row_data):
    dbg("sync_grid_selection", selected_site)  # DEBUG
    if not selected_site or not row_data:
        return dash.no_update
    matching = [row for row in row_data if row["siteID"] == selected_site]
    if not matching:
        return dash.no_update, dash.no_update
    return matching, {"rowPosition": "middle", "data": matching[0]}


# ---------------------------------------------------------------------------
# Client side callbacks
# ---------------------------------------------------------------------------

# handling changes in siteID when it changes changes to the map, client side - data do not change, just styling changes
dash.clientside_callback(
    """
    function(selected_site) {
        if (!selected_site) {
            return [[], window.dash_clientside.no_update];
        }

        // --- table highlight ---
        // not handled by clientside callback

        // --- map marker highlight ---
        const el = document.getElementById('marker-map');
        const graphDiv = el ? el.getElementsByClassName('js-plotly-plot')[0] : null;

        if (graphDiv && graphDiv.data && graphDiv.data[1]) {
            const trace = graphDiv.data[1];   // data marker trace
            const ids = trace.customdata.map(d => d[0]);  // assuming station_id is customdata[0]
            const idx = ids.indexOf(selected_site);

            const n = ids.length;
            const haloColors = new Array(n).fill('white');
            if (idx >= 0) haloColors[idx] = 'black';

            Plotly.restyle(graphDiv, {'marker.color': [haloColors]}, [0]);  // trace 0 = halo
        }

        return [window.dash_clientside.no_update];
    }
    """,
    Output("dummy-store", "data"),   # dummy output, since map update is done via direct DOM manipulation, not a Dash prop
    Input("selected-site", "data"),
)





#moving the marker line on the time selector chart when selected-time changes - client side - data do not change, just the line is moved.
dash.clientside_callback(
    """
    function(selectedTime, basetime) {
        if (!selectedTime) return window.dash_clientside.no_update;
        const container = document.getElementById('time-selector-chart');
        const graphDiv = container && container.getElementsByClassName('js-plotly-plot')[0];
        if (!graphDiv || !graphDiv.layout) return window.dash_clientside.no_update;

        // selected-time is 'YYYY-MM-DD...'; snap to the start of the period shown on the chart
        let x = String(selectedTime).slice(0, 10);
        if (basetime === 'year') x = x.slice(0, 4) + '-10-01';
        else if (basetime === 'month') x = x.slice(0, 7) + '-01';

        Plotly.relayout(graphDiv, {
            shapes: [{
                type: 'line',
                x0: x, x1: x,
                y0: 0, y1: 1,
                yref: 'paper',
                line: {color: 'red', width: 2, dash: 'dash'}
            }]
        });
        return window.dash_clientside.no_update;
    }
    """,
    Output("time-selector-chart", "id"),   # dummy output, not actually used
    Input("selected-time", "data"),        # chart click, date picker, prev/next - anything that changes selected-time
    State("basetime-select", "value"),
)

# highlighting lines in accumulated plot
dash.clientside_callback(
    """
    function(selected_years, figure) {
        if (!figure || !figure.data) {
            return window.dash_clientside.no_update;
        }

        const selected = selected_years || [];

        // Distinct, visually separable colors - extend/replace as you like
        const palette = [
            "crimson", "royalblue", "seagreen", "darkorange",
            "purple", "deeppink", "teal", "goldenrod"
        ];

        const newData = figure.data.map(function(trace) {
            const selIdx = selected.indexOf(trace.name);
            const isSelected = selIdx !== -1;
            const color = isSelected ? palette[selIdx % palette.length] : "lightgrey";

            return {
                ...trace,
                line: {
                    ...trace.line,
                    color: color,
                    width: isSelected ? 2.5 : 1,
                },
                showlegend: isSelected,
                legendgroup: trace.name,
            };
        });

        return { ...figure, data: newData };
    }
    """,
    Output("gauge-accum-day-chart", "figure", allow_duplicate=True),
    Input("accum-select", "value"),
    State("gauge-accum-day-chart", "figure"),
    prevent_initial_call=True,
)
