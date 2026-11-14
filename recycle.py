#clicking on map
app.clientside_callback(
    """
    function(clickData) {
        if (!clickData || !clickData.points || !clickData.points.length) {
            return window.dash_clientside.no_update;
        }
        
        const clickedIdx = clickData.points[0].pointIndex;
        const graphDiv = document.getElementById('marker-map').getElementsByClassName('js-plotly-plot')[0];
        
        if (!graphDiv) return window.dash_clientside.no_update;

        const n = graphDiv.data[0].lat._inputArray.length;
        const colors = new Array(n).fill('steelblue');
        
        colors[clickedIdx] = 'red';
        Plotly.restyle(graphDiv, {
            'marker.color': [colors],
        });
        
        return window.dash_clientside.no_update;
    }
    """,
    Output("dummy-store", "data"),
    Input("marker-map", "clickData"),
)



# slider
# ---------------------------------------------------------------------------
# 

timestamps = [int(pd.Timestamp(t).timestamp() * 1000) for t in time_values]

slider=dcc.Slider(
    id="time-slider",
    min=timestamps[0],
    max=timestamps[-1],
    step=timestamps[1]-timestamps[0],
    value=timestamps[-1],   # start at last time step
    marks={ts: "" for ts in timestamps[::len(timestamps)//10]},
    tooltip={"placement": "bottom", "always_visible": True,"transform":"timestampToDate"},
    allow_direct_input=False,
)


#clicking on slider with dates

@app.callback(
    Output("marker-map", "figure"),
    Output("map-title-time", "children"),
    Output("data-table", "children"),
    Output("selected-time", "data"),
    Input("time-slider", "value"),
    State("selected-site", "data"),
    prevent_initial_call=True,
)
def update_map(ts,selected_site):
    print(ts)
    clicked_time = pd.to_datetime(ts, unit="ms")

    return (
        make_marker_map(clicked_time,selected_site), 
        clicked_time.strftime("%d %b %Y"),
        make_data_table(clicked_time),
        clicked_time,
    )



# clicking on regional time series
@app.callback(
    Output("ts-chart", "figure"),
    Output("marker-map", "figure"),
    Output("map-title-time", "children"),
    Output("data-table", "children"),
    Output("selected-time", "data"),
    Input("ts-chart", "clickData"),
    State("selected-site", "data"),
    prevent_initial_call=True,
)
def on_ts_click(click_data, selected_site):
    """Click on time series — move vline and update map."""
    if not click_data:
        return dash.no_update, dash.no_update, dash.no_update

    #picking up clicked time
    clicked_x = click_data["points"][0]["x"]
    clicked_ts = pd.Timestamp(clicked_x)
    clicked_time = min(time_values, key=lambda t: abs(pd.Timestamp(t) - clicked_ts))

    return (
        make_ts_figure(clicked_time), 
        make_marker_map(clicked_time,selected_site), 
        pd.to_datetime(clicked_time).strftime("%d %b %Y"),
        make_data_table(clicked_time),
        clicked_time,
    )

#resizing element on load
app.clientside_callback(
    """
    function(id) {
        setTimeout(() => {
            const el = document.getElementById(id);
            if (!el) return;
            const graphDiv = el.getElementsByClassName('js-plotly-plot')[0];
            if (!graphDiv) return;
            
            Plotly.Plots.resize(graphDiv);
        }, 200);
        return id;
    }
    """,
    Output("marker-map", "id"),
    Input("marker-map", "id"),
)




#clicking on map
dash.clientside_callback(
    """
    function(clickData) {
        if (!clickData || !clickData.points || !clickData.points.length) {
            return window.dash_clientside.no_update;
        }

        const pt = clickData.points[0];
        if (pt.curveNumber !== 1) {  // only react to clicks on the top (data) trace
            return window.dash_clientside.no_update;
        }
        
        const clickedIdx = pt.pointIndex;
        const graphDiv = document.getElementById('marker-map').getElementsByClassName('js-plotly-plot')[0];
        if (!graphDiv) return window.dash_clientside.no_update;
        
        const n = graphDiv.data[1].lat._inputArray.length;  // top trace length
        const haloColors = new Array(n).fill('white');
        haloColors[clickedIdx] = 'black';
        
        Plotly.restyle(graphDiv, {
            'marker.color': [haloColors],
        }, [0]);  // target trace index 0 (the halo)
        
        return window.dash_clientside.no_update;
 
    }
    """,
    Output("dummy-store", "data"),
    Input("marker-map", "clickData"),
)

#data table events
@callback(
    Output("selected-site", "data", allow_duplicate=True),
    Input("data-table-inner", "selected_rows"),
    State("data-table-inner", "data"),
    prevent_initial_call=True,
)
def on_table_row_select(selected_rows, table_data):
    if not selected_rows:
        return dash.no_update

    siteID = table_data[selected_rows[0]]["siteID"]
    return siteID

#removing selected cell class in data table
dash.clientside_callback(
    """
    function(active_cell) {
        if (!active_cell) {
            console.log('no update...')
            return window.dash_clientside.no_update;
        }
        console.log('removing...')
        setTimeout(() => {
            const cells = document.querySelectorAll('.dash-cell.cell--selected');
            cells.forEach(cell => cell.classList.remove('cell--selected'));
        }, 0);
        return window.dash_clientside.no_update;
    }
    """,
    Output("dummy-store", "data", allow_duplicate=True),
    Input("data-table-inner", "active_cell"),
    prevent_initial_call=True,
)

