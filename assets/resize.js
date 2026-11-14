function resizePlot(graphId) {

    const el = document.querySelector(`#${graphId} .js-plotly-plot`);
    if (!el || !el._fullLayout)
        return;

    const aspect = el._fullLayout.meta?.aspect_ratio || 0.5;

    console.log(aspect)

    const width = el.clientWidth;
    const height = width * aspect;

    Plotly.relayout(el, {
        width,
        height
    });
}


function resizeAll() {

    const graphs = document.querySelectorAll(".resizable");

    graphs.forEach(g => {
        const id = g.id;
        resizePlot(id);
    });
}


function waitForPlotsThenResize() {

    const graphs = document.querySelectorAll(".resizable .js-plotly-plot");

    if (!graphs.length) {
        setTimeout(waitForPlotsThenResize, 50);
        return;
    }

    // ensure Plotly internal state exists
    for (const g of graphs) {
        if (!g._fullLayout) {
            setTimeout(waitForPlotsThenResize, 50);
            return;
        }
    }

    resizeAll();
}


window.addEventListener("DOMContentLoaded", () => {
    waitForPlotsThenResize();
});

window.addEventListener("resize", resizeAll);
window.addEventListener("orientationchange", resizeAll);
