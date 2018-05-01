# TimeLog

This is a simple browser-based time tracking system that I have used for a
number of years. It allows you to set up projects, log time to them, and
display reports, such as the total amount of time spent
on each project.

It is written in Python 3, using the simple bottle.py framework (available and
documented at bottlepy.org, but included in the repository).  To run it, 
just run timelog.py and then browse to http://localhost:8080

The data is stored in an SQLite database called timelog.db in the project
directory. If the database does not exist, and empty one is automatically
created when you start the application.

Andreas Kaempf
Munich, Germany
December 2017

