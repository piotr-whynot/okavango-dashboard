window.dccFunctions = window.dccFunctions || {};
window.dccFunctions.timestampToDate = function(value) {
     return new Date(value).toISOString().slice(0, 10);
}
