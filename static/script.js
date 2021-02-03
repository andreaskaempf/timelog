/* Script to draw stacked area chart of weekly project hours */

// Get the SVG, and its dimensions
var svg = d3.select("#graph"),
    width = svg.attr("width"),
    height = svg.attr("height"),
    margin = {top: 20, right: 20, bottom: 30, left: 50};

// Do the last n projects
nproj = 30;

// Filter projects for those that were active on or after a certain date
var pdate = new Date(2019, 1, 1);
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

// List of color names
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

    // Sort the series by date
    points = points.sort(cmp);

    // Create a tooltip div
    var tooltip = d3.select("body").append("div")
        .attr("id", "tooltip")
        .attr("width", "100px")
        .style("position", "fixed")
        .style("top", "100px")
        .style("left", "50px")
        .style("border", "1px solid #ccc"); // .text("-");
        
    // Draw a line graph of the series
    svg.append("path").datum(points)
        .attr("fill", "none")
        .attr("id", label)   // For tooltip
        .attr("stroke", color)
        .attr("stroke-width", 2)
        .on("mouseover", function(d) { tooltip.text(this.id) })
        .attr("d", d3.line()
            .x(p => xScale(p[0]))
            .y(p => yScale(p[1])));
}


/*
var area = d3.svg.area()
    .x(function(d) { return x(d.date); })
    .y0(function(d) { return y(d.y0); })
    .y1(function(d) { return y(d.y0 + d.y); });

var stack = d3.layout.stack()
    .values(function(d) { return d.values; });


d3.csv("data.csv", function(error, data) {
  color.domain(d3.keys(data[0]).filter(function(key) { return key !== "date"; }));
  data.forEach(function(d) {
  	d.date = parseDate(d.date);
  });

  var browsers = stack(color.domain().map(function(name) {
    return {
      name: name,
      values: data.map(function(d) {
        return {date: d.date, y: d[name] * 1};
      })
    };
  }));

  // Find the value of the day with highest total value
  var maxDateVal = d3.max(data, function(d){
    var vals = d3.keys(d).map(function(key){ return key !== "date" ? d[key] : 0 });
    return d3.sum(vals);
  });

  // Set domains for axes
  x.domain(d3.extent(data, function(d) { return d.date; }));
  y.domain([0, maxDateVal])

  var browser = svg.selectAll(".browser")
      .data(browsers)
    .enter().append("g")
      .attr("class", "browser");

  browser.append("path")
      .attr("class", "area")
      .attr("d", function(d) { return area(d.values); })
      .style("fill", function(d) { return color(d.name); });

  browser.append("text")
      .datum(function(d) { return {name: d.name, value: d.values[d.values.length - 1]}; })
      .attr("transform", function(d) { return "translate(" + x(d.value.date) + "," + y(d.value.y0 + d.value.y / 2) + ")"; })
      .attr("x", -6)
      .attr("dy", ".35em")
      .text(function(d) { return d.name; });

  svg.append("g")
      .attr("class", "x axis")
      .attr("transform", "translate(0," + height + ")")
      .call(xAxis);

  svg.append("g")
      .attr("class", "y axis")
      .call(yAxis);
});
*/
