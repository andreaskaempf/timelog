/* 
 * Script to draw stacked area chart of weekly project hours
 */

// Get the SVG, and its dimensions
var svg = d3.select("#graph"),
    width = svg.attr("width"),
    height = svg.attr("height"),
    margin = {top: 20, right: 20, bottom: 30, left: 50};

// Maximum number of projects to show
var nproj = 50;

// Only show projects that where active on or after this date
var pdate = new Date(2019, 1, 1);

// Filter projects for those that were active on or after a certain date
var dd = [];
for ( var i = 0; i < data.length; ++i ) {
    var active = false;
    for ( var j = 1; j < data[i].length; ++j ) {
        var p = data[i][j], x = p[0], y = p[1];
        if ( x >= pdate ) {
            active = true;
            break;
        }
    }
    if ( active )
        dd.push(data[i]);
}

// Limit to the last n projects
if ( nproj >= dd.length )
    nproj = dd.length;

// Get the min/max X and Y values
var minDate = null, maxDate = null, minVal = null, maxVal = null;
for ( var i = dd.length - nproj; i < dd.length; ++i ) {
    for ( var j = 1; j < dd[i].length; ++j ) {
        var p = dd[i][j], x = p[0], y = p[1];
        if ( minDate == null || x < minDate ) minDate = x;
        if ( maxDate == null || x > maxDate ) maxDate = x;
        if ( minVal == null || y < minVal ) minVal = y;
        if ( maxVal == null || y > maxVal ) maxVal = y;
    }
}

// Only look at dates after specified start
if ( minDate < pdate )
    minDate = pdate;
if ( maxDate < pdate )
    maxDate = pdate;

// Define scales
var xScale = d3.scaleTime().domain([minDate, maxDate]).range([margin.left, width - margin.right]);
var yScale = d3.scaleLinear().domain([minVal, maxVal]).range([height - margin.bottom, margin.top]);

// Draw the axes
var xAxis = d3.axisBottom().scale(xScale);
var yAxis = d3.axisLeft().scale(yScale);
svg.append("g").attr("transform", "translate(0, " + (height - margin.bottom) + ")").call(xAxis);
svg.append("g").attr("transform", "translate(" + margin.left + ",0)").call(yAxis);

// Comparison function for sorting list of points by date
function cmp(a, b) { return a[0] < b[0] ? -1 : (a[0] > b[0] ? 1 : 0) };

// List of color names (will circle if more that these many lines)
var colors = ["#c93f38", "#a59344", "#7b463b", "#dd3366", "#191970",
        "#ab7f46", "#225577", "#c0a98e", "#d2d2c0", "#9bafad",
        "#990066", "#3d1c02", "#ffaabb", "#d1edee", "#d3dde4",
        "#456789", "#f6ecde", "#ffbcc5", "#bfaf92", "#f3e9d9",
        "#88ffcc", "#00b89f", "#05a3ad"];

// Graph the series
for ( var i = dd.length - nproj; i < dd.length; ++i ) {

    // Data is an array of arrays, each with name project,
    // followed by (x, y) pairs
    var series = dd[i],
        label = series[0],
        points = series.slice(1);

    // Add series name to each point, for tooltip
    for ( var j = 0; j < points.length; ++j )
        points[j].push(label);

    // Color for this series
    var ci = i;
    while ( ci >= colors.length )
        ci -= colors.length;
    var color = colors[ci];

    // Filter the points to only include on or after desired start date, and sort them
    points = points.filter(p => p[0] >= pdate);
    points = points.sort(cmp);

    // Create a tooltip div
    var tooltip = d3.select("body").append("div")
        .attr("id", "tooltip")
        .attr("width", "100px")
        .style("background-color", "#cef")
        .style("padding", "8px")
        .style("position", "fixed")
        .style("top", "140px")
        .style("left", "100px") //.text("Mouseover line to see project");
        .style("visibility", "hidden");
        
    // Draw a line graph of the series
    svg.append("path").datum(points)
        .attr("fill", "none")
        .attr("id", label)   // For tooltip
        .attr("stroke", color)
        .attr("stroke-width", 2)
        .on("mouseover", function(e) { 
            tooltip.style("visibility", "visible");
            console.log(e);
            tooltip.style("top", e.clientY - 4);
            tooltip.style("left", e.clientX + 4);
            tooltip.text(this.id);
        })
        .on("mouseout", function(d) { 
            tooltip.style("visibility", "hidden");
        })
        .attr("d", d3.line()
            .x(p => xScale(p[0]))
            .y(p => yScale(p[1])));
}


