import dash
from dash import dcc, html, Input, Output, State, callback
from dash_bootstrap_templates import load_figure_template
from dash import ctx
import dash_bootstrap_components as dbc
import dash_ag_grid as dag

import plotly.graph_objects as go
import pandas as pd
import numpy as np
import xarray as xr
import datetime

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
init_time=pd.to_datetime("2026-01-28")
#init_time=None
init_siteID="XAKANARE001"
#init_siteID=None

#whether all or reporting only are shown at startup
init_gauge_set=["reporting-only"] #has to be a list
init_year_sort=[False]
init_onemon_sort=[False]
init_onemon_select=["Dec"]
init_accum_select=[]
init_basetime_select="year"

monthabbr=np.array(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def load_data():
    data_day = pd.read_csv("/work/projects/okavango_rainfall/data/data_day.csv", index_col=0,parse_dates=True)
    sites = pd.read_csv("/work/projects/okavango_rainfall/data/sites.csv", index_col=0)
    data_day.columns.name="siteID"
    return data_day,sites


rain,sites = load_data()

#making sure data do not extend beyond yesterday
yesterday=(datetime.datetime.today()-pd.offsets.Day(1)).normalize()

rain=rain[rain.index<=yesterday]

time_values = pd.to_datetime(rain.index.values)

if init_time is None:
    init_time=time_values[-1]


# Pre-compute mean time series
meanrain = rain.mean(axis=1)
 




# ---------------------------------------------------------------------------
# Figure and table builders
# ---------------------------------------------------------------------------



def make_marker_map(sel_time,sel_site, basetime, gauge_set):
    # get values for selected time step

    # merging data array with sites array
    if basetime=="year":
        sel_time=pd.to_datetime(sel_time).replace(day=1, month=10)
        df_t = rain.resample("YS-OCT").sum()
        print(df_t.index, sel_time)
        df_t=df_t.T[[sel_time]].merge(sites, on="siteID")
        size_scale = 100  # max marker size in pixels
        vmax = 1000
        vmin = 30
    if basetime=="month":
        sel_time=pd.to_datetime(sel_time).replace(day=1)
        df_t = rain.resample("MS").sum().T[[sel_time]].merge(sites, on="siteID")
        size_scale = 100  # max marker size in pixels
        vmax = 200
        vmin = 6
    elif basetime=="day":
        df_t = rain.T[[sel_time]].merge(sites, on="siteID")
        size_scale = 100  # max marker size in pixels
        vmax = 100
        vmin = 6

    df_t.rename(columns={df_t.columns[0]:"value"}, inplace=True)
    #selecting only stations with data, i.e. no nans
    if "reporting-only" in gauge_set:
        sel=~np.isnan(df_t["value"])
        df_t=df_t[sel]

    

    # scale marker size
    sizes = (df_t["value"] / vmax * size_scale).fillna(vmin).clip(lower=vmin)  # min size 3

    colors = ["black" if np.isnan(s) else "steelblue" for s in df_t["value"]]

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
        ], axis=1),
        hovertemplate="<b>%{text}</b><br>value: %{customdata[3]} mm<br>Location: %{customdata[2]}<br>Owner: %{customdata[1]}<extra></extra>",
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





def make_time_selector(sel_time,basetime):
    if basetime=="day":
        data=meanrain.copy()
    if basetime=="month":
        data=meanrain.resample("MS").sum()
        sel_time=pd.to_datetime(sel_time).replace(day=1)
    if basetime=="year":
        data=meanrain.resample("YS").sum()
        sel_time=pd.to_datetime(sel_time).replace(day=1,month=1)

    fig = go.Figure(go.Scatter(
        x=data.index,
        y=list(data.values.flatten()),
        marker=dict(
            line=dict(color="black",width=1)
        )
    ))

    fig.add_vline(
        x=str(pd.Timestamp(sel_time))[:10],
        line=dict(color="red", width=2, dash="dash"),
    )
    fig.update_layout(
        yaxis_title="Rainfall (mm)",
        template=figtemplate,
        height=200,
        autosize=True,
        legend=dict(orientation="h", x=0.5, y=-0.15, xanchor="center", yanchor="top"),
        margin=dict(l=0, r=0, t=0, b=10),
    )

    return fig 




def make_data_table(sel_time, gauge_set):

    df_t = rain.T[[sel_time]].merge(sites, on="siteID")
    df_t.rename(columns={df_t.columns[0]:"value"}, inplace=True)


    if "reporting-only" in gauge_set:
        sel=~np.isnan(df_t["value"])
        df_t=df_t[sel]

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
    ts = rain[siteID].sort_index()
    sel=~np.isnan(ts)
    ts=ts[sel]
    tsmax=np.max(ts)

    i=np.where(ts==tsmax)
    maxdate=ts.iloc[i[0]].index.values[0]
    maxdate=pd.to_datetime(maxdate).strftime("%d %b %Y")

    firstdate=pd.to_datetime(ts.index[0]).strftime("%d %b %Y")
    lastdate=pd.to_datetime(ts.index[-1]).strftime("%d %b %Y")

    info = sites.loc[siteID]
    obstime=info['Observation time']
    try:
        obstime=float(obstime)
        obstime=str(int(obstime*24)).zfill(2)
        obstime=f"{obstime}:00"
    except:
        cont=True

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

    ts = rain[siteID].sort_index()

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

    ts = rain[siteID].sort_index()

    start_month,start_day=10,1

    df=get_hy(ts,start_month,start_day)

    df= df.dropna(axis=1, how="all")
    

    date_labels = pd.date_range(start=f"2000-{start_month:02d}-{start_day:02d}", periods=366, freq="D")
    label_lookup = date_labels.strftime("%d %b")[:365]  # trim to 365 to match day_offset range
    day_offset_labels = pd.Series(label_lookup, index=range(365))

    return df,day_offset_labels






def make_gauge_ts_mon(siteID):

    ts = rain[siteID].sort_index()

    validmon=np.invert(np.isnan(ts)).resample("ME").sum()
    ndaysmon=pd.Series(validmon.index.daysinmonth.values, index=validmon.index)

    percvalid=np.round((validmon/ndaysmon*100).astype(int),0)
    validdata=percvalid>98

    colors = ["steelblue" if flag else "lightblue" for flag in validdata]
    ts=ts.resample("ME").sum()

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

    ts = rain[siteID].sort_index()

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

    ts = rain[siteID].sort_index()
    #monthly
    validmon=np.invert(np.isnan(ts)).resample("ME").sum()
    ndaysmon=pd.Series(validmon.index.daysinmonth.values, index=validmon.index)

    validmon[validmon.index.month.isin([4,5,6,7,8,9,10])]=0
    ndaysmon[ndaysmon.index.month.isin([4,5,6,7,8,9,10])]=0

    validyear=validmon.resample("YE-JUL").sum()
    ndaysyear=ndaysmon.resample("YE-JUL").sum()

    percvalid=np.round((validyear/ndaysyear*100).astype(int),0)
    validdata=percvalid>98
    
    ts=ts.resample("YE-JUL").sum()
    colors = np.array(["steelblue" if flag else "lightblue" for flag in validdata])
    labels=np.array([f"{x.year-1}-{x.year}" for x in ts.index])

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



   

def make_collapsible_text(text_id, index):
    text=text_dict[text_id]
    return html.Div([
        dbc.Collapse(
            html.P(text, className="text-muted small"),
            id={"type": "card-collapse", "index": index},
            is_open=False,
        ),
        dbc.Button(
            "Read about this figure/table...",
            id={"type": "card-toggle", "index": index},
            color="link",
            size="sm",
            className="p-0",
        ),
    ])



text_dict={
"time-selector-chart":"Note: This graph is only vaguely informative as the number of stations changes in time, so rainfall values for 2003 are calculated based on one or two gauges while those in 2025 based on about 40. As a result - one cannot really compare 2003 with 2025. This graph is used here to show when it rains and when it doesn't to allow for selecting date for further inspection.",

"gauge-ts-mon":"Monthly data are calculated from daily measurements. In this we assume that if there is no reported values for some days in the month it means that it was not raining on those days, i.e. that missing data is equivalent to the value of 0. We do, however, flag months for which data are missing.",

"gauge-accum-day":"Daily data for the selected gauge.",
"gauge-ts-onemon":"Daily data for the selected gauge.",

"gauge-ts-day":"Daily data for the selected gauge. Note that missing data are not explicitly shown.",

"marker-map":"Map shows location of rain gauges and rainfall amounts for the selected day. Note that by default only gauges that have data for the selecte date are shown, but you can show location of all stations using the toggle. Some sites report data only when it rains. When it does not rain - they report nothing. When we receive no data for a given day, We do not know, unfortunately, whether this means that there was no rain, or perhaps that there was no measurement done on that day. It is possible that there was no rainfall over gagues with no data, but it is not 100% sure.",

"data-table":"Data table shows all values reported on the selected day. Note that empty value means that there was no rainfall reported by given gauge on that day. It might have been 0mm, i.e. no rain, and the observer simply did not bother to report. But it might have been raining, but gauge was broken, or the observer was away, or for some reason they did not report the actual measurement.",

"gauge-ts-year":"This chart illustrates total rainfall measured over a year. It uses a hydrological year that starts in October and finishes in September. Note that bars have two colours that signify the robustness of data. It is only natural that some measurements are missing. Observers might have not recorded data, or rain gauge was broken etc. Additionally, often, observers report data only when it rains, and do not report 0s when it does'nt. This creates a bit of a problem because if there is no data reported, we do not know if this is because there was no rain, or perhaps rain wasn't measured. In many cases we make an educated guess that missing data are simply 0s, but we cannot always do that. This way or nother - we count how many days have missing values and if there is more than 10% of such days (i.e. more than 36 days in a year), we flag the year's total as not-robust"
}




# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


layout = dbc.Container([

    # --- Page header ---
    dbc.Row([
        dbc.Col(html.Img(src="./assets/CSAG_web-logo.png", height="25px"), width="auto"),
        dbc.Col(html.H2("Okavango Delta Rainfall", className="text-center"), className="my-auto"),
    ], align="center", className="py-1 border-bottom mb-2"),



    # data-driven content
    dbc.Row([
        # map with markers
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(
                            html.H5(["Rainfall on ",html.Span(init_time.strftime("%d %b %Y"), id="map-title-time")]),
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
                                html.H5("Select date"),
                            ),
                            dbc.Col(dbc.Button("◀", id="prev-date", size="sm", color="secondary"), width="auto"),
                            dbc.Col(
                                dcc.DatePickerSingle(
                                    id="date-picker",
                                    min_date_allowed=pd.Timestamp(time_values.min()).date(),
                                    max_date_allowed=pd.Timestamp(time_values.max()).date(),
                                    date=pd.Timestamp(init_time).date(),
                                    display_format="YYYY-MM-DD",
                                ),
                                width="auto",
                            ),
                            dbc.Col(dbc.Button("▶", id="next-date", size="sm", color="secondary"), width="auto"),
                        ], justify="center", align="center", className="g-2"),

                        html.P("or click on the figure to select date", className="text-muted text-left small"),
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
                        html.H5(["Rainfall on ",html.Span(init_time.strftime("%d %b %Y"), id="table-title-time")]),

                        html.P("Click on row to show data for selected gauge. Click on header to sort table by column values.", className="text-muted small"),

                        html.Div(
                            id="data-table",
                            children=make_data_table(init_time,init_gauge_set),
                        ),
                        make_collapsible_text("data-table",2),
                    ]),
                ],className="shadow-sm m-3 px-3"),

        ],xs=12,lg=6),


    # closing first row
    ], className="g-5"),


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
    dcc.Store(id="selected-time", data=str(pd.Timestamp(init_time))),

    # Store selected site
    dcc.Store(id="selected-site", data=init_siteID),

    dcc.Store(id="basetime", data=init_basetime_select),

    dcc.Store(id="dummy-store", data=""),

    #init trigger
    dcc.Store(id="init-trigger", data=True)

], fluid=True, style={"minWidth": "360px","maxWidth": "1800px"})





# ---------------------------------------------------------------------------
# Server-side callbacks
# ---------------------------------------------------------------------------




# change map when selected-time changes
@callback(
    Output("marker-map", "figure"),
    Output("map-title-time", "children"),
    Output("table-title-time", "children"),
    Output("data-table", "children"),
    Output("date-picker", "date"),
    Output("basetime", "data"),
    Input("selected-time", "data"),
    Input("gauge-set", "value"),
    Input("basetime-select", "value"),
    State("selected-site", "data"),
)
def update_figures(selected_time, gauge_set,basetime,selected_site):
    return (
        make_marker_map(pd.to_datetime(selected_time),selected_site,basetime,gauge_set), 
        pd.to_datetime(selected_time).strftime("%d %b %Y"),
        pd.to_datetime(selected_time).strftime("%d %b %Y"),
        make_data_table(selected_time, gauge_set),
        selected_time,
        basetime,
    )


# plotting time selector
@callback(
    Output("time-selector-chart", "figure"),
    Input("init-trigger", "data"),
    Input("basetime", "data"),
)
def update_figure(trigger,basetime):
    return (
        make_time_selector(init_time,basetime)
    )




# click on time selector chart
@callback(
    Output("selected-time", "data", allow_duplicate=True),
    Input("time-selector-chart", "clickData"),
    prevent_initial_call=True,
)
def on_ts_click(click_data):
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
    Output("date-picker", "date", allow_duplicate=True),
    Input("date-picker", "date"),
    Input("prev-date", "n_clicks"),
    Input("next-date", "n_clicks"),
    State("selected-time", "data"),
    prevent_initial_call=True,
)
def on_date_change(picked_date, prev_clicks, next_clicks, current_time):

    current = pd.Timestamp(current_time)

    if ctx.triggered_id == "date-picker":
        nearest = min(time_values, key=lambda t: abs(pd.Timestamp(t) - pd.Timestamp(picked_date)))
    elif ctx.triggered_id == "prev-date":
        earlier = [t for t in time_values if pd.Timestamp(t) < current]
        nearest = max(earlier) if earlier else current
    elif ctx.triggered_id == "next-date":
        later = [t for t in time_values if pd.Timestamp(t) > current]
        nearest = min(later) if later else current
    else:
        nearest = current

    return pd.to_datetime(nearest), pd.Timestamp(nearest).date()


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
    Output("gauge-info-title", "children"),
    Input("selected-site", "data"),
    #prevent_initial_call=True,
)
def update_figures(siteID):
    return (
        make_gauge_ts_day(siteID),
        make_gauge_ts_mon(siteID),
        make_gauge_info(siteID),
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
    if not selected_site or not row_data:
        return dash.no_update
    matching = [row for row in row_data if row["siteID"] == selected_site]
    if not matching:
        return dash.no_update, dash.no_update
    return matching, {"rowPosition": "middle", "data": matching[0]}


# toggling collapses
@callback(
    Output({"type": "card-collapse", "index": dash.ALL}, "is_open"),
    Output({"type": "card-toggle", "index": dash.ALL}, "children"),
    Input({"type": "card-toggle", "index": dash.ALL}, "n_clicks"),
    State({"type": "card-collapse", "index": dash.ALL}, "is_open"),
    prevent_initial_call=True,
)
def toggle_cards(n_clicks_list, is_open_list):
    idx = ctx.triggered_id["index"]
    new_states = is_open_list.copy()
    new_states[idx] = not new_states[idx]
    labels = ["Hide description" if s else "Read about this figure/table..." for s in new_states]
    return new_states, labels


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





#updating time selector chart when clicked - client side - data do not change, just styling changes, i.e. line is added.
dash.clientside_callback(
    """
    function(clickData) {
        if (!clickData || !clickData.points || !clickData.points.length) {
            return window.dash_clientside.no_update;
        }
        const x = clickData.points[0].x;
        const graphDiv = document.getElementById('time-selector-chart').getElementsByClassName('js-plotly-plot')[0];
        
        if (!graphDiv) return window.dash_clientside.no_update;
        
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
    Input("time-selector-chart", "clickData"),
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
