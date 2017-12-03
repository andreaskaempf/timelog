#!/bin/python3

import os, io
from sqlite3 import dbapi2 as sql
from datetime import date, datetime
from bottle import route, run, template, static_file

# Hello world example
@route('/hello/<name>')
def hello(name):
    return template('<b>Hello {{name}}</b>!', name = name)

# Serve static files
@route('/static/<filename:path>')
def serve_static(filename):
    return static_file(filename, root = os.getcwd() + '/static')


# Show time log, most recent at the top
@route('/log')
def log():

    # Connect to database
    db = getDB()
    cur = db.cursor()

    # Start page
    s = io.StringIO()
    header(s)

    # Start table
    s.write('<h1>Time Record</h1>\n')
    s.write('<table>\n')
    s.write('  <tr>')
    for h in ['Project', 'Hours', 'Billable', 'Description']:
        s.write('    <th>%s</th>\n' % h)
    s.write('  </tr>\n')

    # Initialize counters, etc.
    lastDate = None
    dateHrs = dateBillable = totalHrs = totalBillable = 0

    # Get all time log records
    q = 'select work.id, project_id, client, name, work_date, hours, work.billable, work.description '
    q += ' from work, project where work.project_id = project.id'
    q += ' order by work_date desc limit 400'
    cur.execute(q)
    work = cur.fetchall()

    # Show each time log record
    data = 0
    for w in work:

        wid, pid, client, projName, wdate, hrs, billable, descr = w
        project = '%s - %s' % (client, projName)
        wdate = parseDate(wdate)

        # New header if date changes
        if lastDate and lastDate != wdate:
            s.write('  <tr class="subtotal">\n')
            s.write('    <td>%s:</td>\n' % formatDate(lastDate))
            s.write('    <td align="right">%.1f</td>\n' % dateHrs)
            s.write('    <td align="right">%.1f</td>\n' % dateBillable)
            billPcnt = dateBillable / dateHrs * 100.0 if dateHrs > 0.0 else 0.0
            s.write('    <td>%.1f%% productive</td>\n' % billPcnt)
            s.write('  </tr>\n')
            dateHrs = dateBillable = data = 0

        # Update counters
        lastDate = wdate
        dateHrs += hrs
        if billable:
            dateBillable += hrs
            totalBillable += hrs
        totalHrs += hrs

        # Show one row
        s.write('  <tr>\n')
        s.write('    <td><a href="project.py?id=%s">%s</a></td>\n' % (pid, project))
        s.write('    <td align="right"><a href="editlog.py?id=%s">%.1f</a></td>\n' % (wid, hrs))
        if billable:
            s.write('    <td align="right">%.1f</td>\n' % hrs)
        else:
            s.write('    <td>&nbsp;</td>\n')
        s.write('<td>%s</td>' % descr)
        s.write('  </tr>\n')

    # Final subtotal
    s.write('  <tr class="subtotal">\n')
    s.write('    <td>%s:</td>\n' % formatDate(lastDate))
    s.write('    <td align="right">%.1f</td>\n' % dateHrs)
    s.write('    <td align="right">%.1f</td>\n' % dateBillable)
    s.write('    <td>&nbsp;</td>\n')
    s.write('  </tr>\n')

    # Final total, finish table
    s.write('  <tr class="total">\n')
    s.write('    <td>Total:</td>\n')
    s.write('    <td align="right">%.1f</td>\n' % totalHrs)
    s.write('    <td align="right">%.1f</td>\n' % totalBillable)
    s.write('    <td>&nbsp;</td>\n')
    s.write('  </tr>\n')
    s.write('</table>\n')

    # Finish page
    footer(s)
    return s.getvalue()



# Common functions, formerly in common.py

# Menu options
menu = [
    ['History', 'log.py'],
    ['New log', 'editlog.py'],
    ['Calendar', 'calendar.py'],
    ['Projects', 'projects.py'], #['Contacts', 'contacts.py'],
    ['Graphs', 'graphs.py']]


# Get database handler, new version using SQLite
def getDB():
    return sql.connect('timelog.db')


# Get next ID for a table
def nextId(table, cur):
    cur.execute('select max(id) from ' + table)
    r = cur.fetchone()
    nid = int(r[0])
    return nid + 1


# Start page
def header(s):

    # Static page header
    s.write('Content-Type: text/html\n\n')
    s.write(open('static/header.html').read())

    # Show menu
    s.write('<div id="menu">\n')
    for m in menu:
        if m != menu[0]:
            s.write(' | ')
        s.write('<a href="%s">%s</a>\n' % (m[1], m[0]))
    s.write('</div>\n')


# Finish page
def footer(s):
    s.write('</body>\n</html>\n')

# Print table cell
def td(s, c):
    s.write('<td>%s</td>' % c)


# Parse "yyyy-mm-dd" into a date object
def parseDate(s):
    try:
        y, m, d = [int(x) for x in s.split('-')]
        return date(y,m,d)
    except:   # Exception, e:
        return('(Invalid date)')


# Format date as "Mon 23/04/2015" 
dnames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

def formatDate(dt):
    dow = dnames[dt.weekday()]
    return '%s %02d/%02d/%d' % (dow, dt.day, dt.month, dt.year)

# Today's date
def today():
    return datetime.now().date()

# Determine whether page is POST, i.e., has form arguments
def isPost():
    return os.environ['REQUEST_METHOD'] == 'POST'

# Determine a value looks like boolean TRUE
def isTrue(v):
    return str(v).lower() in ['1', '1.0', 'true', 'yes']

# End of common.py

# Start server
run(host = 'localhost', port = 8080)

