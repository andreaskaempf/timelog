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
@route('/')
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
    dHrs = dBillable = 0.0
    wHrs = wBillable = 0.0
    mHrs = mBillable = 0.0
    totalHrs = totalBillable = 0

    # TODO: don't hard-code date, and use previous year if before March
    this_year = 2017

    # Get the time log records for the current year
    # PROBLEM: the counters will be out or missed, if there are gaps in the dates
    q = 'select work.id, project_id, client, name, work_date, hours, work.billable, work.description '
    q += ' from work, project where work.project_id = project.id'
    q += " and substr(work_date,1,4) >= '%d'" % this_year
    q += ' order by work_date'  # desc limit 400'
    cur.execute(q)
    work = cur.fetchall()

    # Show each time log record
    data = 0
    for w in work:

        wid, pid, client, projName, wdate, hrs, billable, descr = w
        project = '%s - %s' % (client, projName)
        wdate = parseDate(wdate)

        # If date has changed, show summary for the date, and the week if has changed,
        # and end of month
        if lastDate and lastDate != wdate:

            # Summary for this date
            summaryRow(s, 'dtotal', formatDate(lastDate), dHrs, dBillable)
            dHrs = dBillable = data = 0.0

            # If just finished a Friday, show summary for the date
            if lastDate.weekday() == 4:   # 0 = Monday
                summaryRow(s, 'wtotal', 'Week subtotal:', wHrs, wBillable)
                wHrs = wBillable = 0.0

            # If will be starting a new month, show summary for the date
            if lastDate.month != wdate.month:
                summaryRow(s, 'mtotal', 'Month subtotal', mHrs, mBillable)
                mHrs = mBillable = 0.0

        # Update counters
        lastDate = wdate
        dHrs += hrs
        wHrs += hrs
        mHrs += hrs
        totalHrs += hrs
        if billable:
            dBillable += hrs
            wBillable += hrs
            mBillable += hrs
            totalBillable += hrs

        # Show row for this timelog entry
        s.write('  <tr>\n')
        s.write('    <td><a href="project.py?id=%s">%s</a></td>\n' % (pid, project))
        s.write('    <td align="right"><a href="editlog.py?id=%s">%.1f</a></td>\n' % (wid, hrs))
        if billable:
            s.write('    <td align="right">%.1f</td>\n' % hrs)
        else:
            s.write('    <td>&nbsp;</td>\n')
        s.write('<td>%s</td>' % descr)
        s.write('  </tr>\n')

    # Final subtotals, by day, week, month, and grand total
    summaryRow(s, 'dtotal', formatDate(lastDate), dHrs, dBillable)
    summaryRow(s, 'wtotal', 'Week subtotal:', wHrs, wBillable)
    summaryRow(s, 'mtotal', 'Month subtotal', dHrs, dBillable)
    summaryRow(s, 'total', 'Total', totalHrs, totalBillable)
    s.write('</table>\n')

    # Finish page
    footer(s)
    return s.getvalue()


# Print a summary row, every time the date, week, or month changes, and at the end
def summaryRow(s, cls, title, hours, billable):
    if cls == 'total':
        rid = 'href="#totals"'
    else:
        rid = ''
    s.write('  <tr class="%s" %s>\n' % (cls, rid))
    s.write('    <td>%s</td>\n' % title)
    s.write('    <td align="right">%.1f</td>\n' % hours)
    s.write('    <td align="right">%.1f</td>\n' % billable)
    billPcnt = billable / hours * 100.0 if hours > 0.0 else 0.0
    s.write('    <td>%.1f%% productive</td>\n' % billPcnt)
    s.write('  </tr>\n')

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
    if dt:
        dow = dnames[dt.weekday()]
        return '%s %02d/%02d/%d' % (dow, dt.day, dt.month, dt.year)
    else:
        return '(no date)'

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

