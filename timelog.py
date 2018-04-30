#!/bin/python3

import os, io
from sqlite3 import dbapi2 as sql
from datetime import date, datetime
from bottle import route, post, run, request, static_file, redirect


#--------------------------------------------------------------------#
#                            SHOW LOG                                #
#--------------------------------------------------------------------#


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

        # Show row for this timelog entry, with link to edit
        s.write('  <tr>\n')
        s.write('    <td><a href="/project/%d">%s</a></td>\n' % (pid, project))
        s.write('    <td align="right"><a href="edit/%s">%.2f</a></td>\n' % (wid, hrs))
        if billable:
            s.write('    <td align="right">%.2f</td>\n' % hrs)
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
    s.write('    <td align="right">%.2f</td>\n' % hours)
    s.write('    <td align="right">%.2f</td>\n' % billable)
    billPcnt = billable / hours * 100.0 if hours > 0.0 else 0.0
    s.write('    <td>%.1f%% productive</td>\n' % billPcnt)
    s.write('  </tr>\n')


#--------------------------------------------------------------------#
#                            EDIT LOG                                #
#--------------------------------------------------------------------#


# Edit/create a log entry
@route('/edit/<lid:int>')
def edit_log(lid = 0):

    # Connect to database
    db = getDB()
    cur = db.cursor()

    # Start page
    s = io.StringIO()
    header(s)

    # Initialize fields
    if lid:
        s.write('<h1>Edit Log Entry</h1>\n')
        cur.execute('select * from work where id = %s' % lid)
        w = cur.fetchone()
        lid, project, wdate, hours, billable, description = w 
        d = parseDate(wdate)
    else:
        s.write('<h1>New Log Entry</h1>\n')
        project = wdate = description = ''
        hours = 1.0
        billable = 0
        d = today()
    ds = '%d-%02d-%02d' % (d.year, d.month, d.day)

    # Start form
    s.write('<form method="post" action="/save">\n')
    s.write('<input type="hidden" name="lid" value="%s" />\n' % lid)
    s.write('<table width="100%">\n')

    # Date
    tr(s, ['Date:\n', '<input type="text" name="date" value="%s" class="field">\n' % ds])

    # Drop-down list with active projects
    s.write('<tr>\n')
    td(s, 'Project')
    s.write('<td>\n')
    s.write('<select name="project" class="field" style="font-family: monospace">\n')
    cur.execute('select * from project where active order by client, name')
    for p in cur.fetchall():
        selected = 'selected' if p[0] == project else ''
        s.write('<option %s value="%s">%s - %s</option>\n' % (selected, p[0], p[1], p[2]))
    s.write('</select>\n')
    s.write('</td>\n')
    s.write('</tr>\n')

    # Hours
    tr(s, ['Hours:', '<input type="text" name="hours" value="%.2f" class="field" style="font-family: monospace">\n' % hours])

    # Billable
    checked = 'checked="y"' if billable else ''
    tr(s, ['Billable:', '<input type="checkbox" name="billable" %s />' % checked])

    # Description
    tr(s, ['Description:', '<textarea name="description" class="field" style="width: 600px; height: 80px; font-family: monospace">%s</textarea>' % description])

    # Buttons
    s.write('<tr>\n <td>&nbsp;</td>\n <td>')
    s.write('<input type="submit" class="button" style="color: white; background-color: #0c0;" value="Save" />')
    if id:
        s.write(' <input type="submit" name="delete" class="button" value="Delete" style="color: white; background-color: #c00;"> ')
    s.write('</td></tr>\n')

    # End of form
    s.write('</table>\n')
    s.write('</form>\n')

    # Finish page
    footer(s)
    return s.getvalue()


# Save new or changed log entry, assumes everything is valid
@post('/save')
def save_log(lid = 0):

    # Connect to database
    db = getDB()
    cur = db.cursor()

    # Get the form fields
    lid = int(request.forms.lid)
    pid = int(request.forms.project)
    wdate = parseDate(request.forms.date)
    hours = float(request.forms.hours)
    billable = 1 if 'billable' in request.forms else 0
    descr = request.forms.description
    descr = descr.replace("'", "\\'")   # TODO: encoding?

    # TODO: validate

    # Save form
    if id:
        q = "update work set project_id = %d, work_date = '%s', hours = %.2f, "
        q += "billable = %d, description = '%s' where id = %d"
        q = q % (pid, wdate, hours, billable, descr, lid)
    else:
        wid = nextId('work', cur)
        q = "insert into work values (%d, '%s', '%s', %f , '%s', '%s')" 
        q = q % (wid, pid, wdate, hours, billable, descr)
    print('---')
    print(q)
    print('---')
    #cur.execute(q)
    #db.commit()
    #return('<p>Changes saved, <a href="/">continue</a></p>')
    redirect('/')


# Delete log entry, ask confirmation first
#if field('delete'):
#    confirm = field('confirm') 
#    if confirm == 'yes':
#        cur.execute('delete from work where id = %s' % id)
#        db.commit()
#        print '<p>Log entry %s deleted, <a href="log.py">continue</a></p>' % id
#    elif confirm:
#        print '<p>Log entry retained, <a href="log.py">continue</a></p>'
#    else:
#        print '<p>Are you sure? <a href="editlog.py?delete=1&id=%d&confirm=yes">yes</a> ' % id
#        print '/ <a href="editlog.py?delete=1&id=%d&confirm=no">no</a></p>' % id
#    footer()


#--------------------------------------------------------------------#
#                             PROJECTS                               #
#--------------------------------------------------------------------#


# Default is to show just active projects, if no state specified
@route('/projects')
def projects1():
    return projects('active')


# Show list of projects: all, active, ...
@route('/projects/<show>')
def projects(show):

    # Connect to database
    db = getDB()
    cur = db.cursor()

    # Get hours per project into a dictionary
    project_hours = {}  # keyed by project id
    cur.execute('select project_id, sum(hours) from work group by project_id')
    for r in cur.fetchall():
        p, h = r
        project_hours[p] = float(h)

    # Start page
    s = io.StringIO()
    header(s)
    s.write('<h1>Project</h1>\n')
    s.write('<p><a href="/edit_project" class="button">Add project</a> | Show: ')
    for x in ['active', 'inactive', 'all']:
        if x == show:
            s.write('<b>%s</b> ' % x)
        else:
            s.write('<a href="/projects/%s">%s</a> ' % (x, x))
    s.write('</p>\n')

    # Start table
    s.write('<table width="100%" border="1">\n')
    s.write('  <tr class="heading">\n')
    for h in ['Client', 'Name', 'Description', 'Billable', 'Active', 'Total hours', 'Fees', 'Effective rate']:
        s.write('    <th>%s</th>\n' % h)
    s.write('  </tr>\n')

    # Get projects and show in table
    count = 0
    cur.execute('select id, client, name, description, billable, active, fees from project order by client, name')
    for p in cur.fetchall():

        pid, client, name, descr, billable, active, fees = p

        hours = project_hours.get(pid, 0.0)
        if (active and show == 'inactive') or (not active and show == 'active'):
            continue
        count += 1

        if active:
            s.write('<tr>\n')
        else:
            s.write('<tr style="color: #888; background: #ccc;">\n')

        td(s, client)
        td(s, '<a href="/project/%s">%s</a>' % (pid, name))
        td(s, descr)
        if billable:
            s.write('<td style="background: green">Yes</td>\n')
        else:
            td(s, 'No')

        td(s, 'Yes' if active else 'No')

        s.write('<td align="right">%.1f</td>\n' % hours)
        if fees:
            fees = float(fees)
            s.write('<td align="right">%.2f</td>\n' % fees)
        else:
            s.write('<td align="right" style="color: #ccc;">n/a</td>\n')

        if hours and fees and hours > 0 and fees > 0:
            rate = fees / (hours / 10.0)
            s.write('<td align="right">%.2f</td>\n' % rate)
        else:
            s.write('<td align="right" style="color: #ccc;">n/a</td>\n')
        s.write('</tr>\n')

    # Finish table and page
    s.write('</table>\n')
    s.write('<p>%d projects</p>\n' % count)
    footer(s)
    return(s.getvalue())


#--------------------------------------------------------------------#
#                         SUPPORT FUNCTIONS                          #
#--------------------------------------------------------------------#

# Common functions, formerly in common.py

# Menu options
menu = [
    ['History', '/'],
    ['New log', 'edit'],
    ['Calendar', 'calendar'],
    ['Projects', 'projects'], #['Contacts', 'contacts.py'],
    ['Graphs', 'graphs']]


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
    #s.write('Content-Type: text/html\n\n')
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


# Print a table row
def tr(s, cells):
    s.write('<tr style="vertical-align: top">\n')
    for c in cells:
        td(s, c)
    s.write('</tr>\n')

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

# Format a date as "Tue 21/02/2016"
def formatDate(dt):
    if dt:
        dow = dnames[dt.weekday()]
        return '%s %02d/%02d/%d' % (dow, dt.day, dt.month, dt.year)
    else:
        return '(no date)'

# Today's date
def today():
    return datetime.now().date()


#--------------------------------------------------------------------#
#                            START SERVER                            #
#--------------------------------------------------------------------#


# Hello world example
@route('/hello/<name>')
def hello(name):
    return template('<b>Hello {{name}}</b>!', name = name)

# Serve static files
@route('/static/<filename:path>')
def serve_static(filename):
    return static_file(filename, root = os.getcwd() + '/static')


# Start server
run(host = 'localhost', port = 8080)

