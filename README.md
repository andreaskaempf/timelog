# TimeLog

This is a simple browser-based time tracking system that I have used for a
number of years. The core was originally written over just a couple of hours in
August 2004, as a set of CGI scripts. It allows you to set up projects, log
time to them, and display reports, such as the total amount of time spent on
each project.

It has now been translated to Python 3, using the simple bottle.py framework
(available and documented at bottlepy.org, but included in the repository).  To
run it, just run timelog.py and then browse to http://localhost:8080

The data is stored in an SQLite database called timelog.db in the project
directory. If the database does not exist, an empty one is automatically
created when you start the application for the first time.

To get started, add a couple of projects, then log time to them, then look
at the project pages to see the total time on the project, or the calendar
to see an overview.

Graphs are still being ported from the CGI version, and will use a Javascript
library rather than raster graphics as in the old version.

Andreas Kaempf,
Munich, Germany,
December 2017

