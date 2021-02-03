#!/bin/python3

import os, io, uuid, socket
from sqlite3 import dbapi2 as sql
from datetime import date, datetime, timedelta
from bottle import route, post, run, request, static_file, redirect

# Name of SQLite database 
dbname = 'timelog.db'

# The time log should only include the last 6 months (180 days)
t0 = datetime.now() - timedelta(180)
this_month = '%d-%02d' % (t0.year, t0.month)

# If database does not yet exist, create it
if not os.path.exists(dbname):
    print('Database %s not found, creating it' % dbname)
    db = sql.connect(dbname)
    cur = db.cursor()
    for r in open('create_database.sql'):
        print(r)
        cur.execute(r)
    db.commit()
    db.close()

# List of project IDs to ignore when calculating utilization (e.g., holidays)
# TODO: don't hardcode this, or use names instead of IDs
ignoreProjectIDs = [8,  # Personal: Time off
    84,                 # Personal: Weekends
    193]                # ThinkBig: Sick

# Where sessions go (NOT USED YET)
session_dir = '/tmp/sessions'
if not os.path.exists(session_dir):
    print('Creating session directory:', session_dir)
    os.mkdir(session_dir)


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

    # Title, with link to go to bottom
    s.write('<h1>Time Record')
    s.write('<a href="#bottom" style="font-size: 0.5em; float:right">Go to bottom</a>')
    s.write('</h1>\n')

    # Start table
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

    # Get the time log records for the current year
    # PROBLEM: the counters will be out or missed, if there are gaps in the dates
    q = 'select work.id, project_id, client, name, work_date, hours, work.billable, work.description '
    q += ' from work, project where work.project_id = project.id'
    q += " and substr(work_date,1,7) >= '%s'" % this_month
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
        ignoreRow = pid in ignoreProjectIDs
        if not ignoreRow:
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
        if ignoreRow:
            s.write('  <tr style="background-color: #fdd">\n')
        else:
            s.write('  <tr>\n')
        s.write('    <td><a href="/project/%d">%s</a></td>\n' % (pid, project))
        s.write('    <td align="right"><a href="edit_log/%s">%.2f</a></td>\n' % (wid, hrs))
        if billable:
            s.write('    <td align="right">%.2f</td>\n' % hrs)
        else:
            s.write('    <td>&nbsp;</td>\n')
        s.write('<td>%s</td>' % descr)
        s.write('  </tr>\n')

    # Final subtotals, by day, week, month, and grand total
    summaryRow(s, 'dtotal', formatDate(lastDate), dHrs, dBillable)
    summaryRow(s, 'wtotal', 'Week subtotal:', wHrs, wBillable)
    summaryRow(s, 'mtotal', 'Month subtotal', mHrs, mBillable)
    summaryRow(s, 'total', 'Total', totalHrs, totalBillable)
    s.write('</table>\n')

    # href to bottom, hyperlink to top
    s.write('<a name="bottom"></a>')
    s.write('<p style="font-size: 0.8em; font-weight: bold; float: right"><a href="#top">Go to top</a></p>\n')

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
#                         EDIT LOG ENTRY                             #
#--------------------------------------------------------------------#


# Editing a log entry with no idea: create new log entry (id 0)
@route('/new_log')
def new_log():
    redirect('/edit_log/0')


# Edit/create a log entry
@route('/edit_log/<lid:int>')
def edit_log(lid):

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
    s.write('<form method="post" action="/save_log">\n')
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

    # Otherfields
    tr(s, ['Hours:', '<input type="text" name="hours" value="%.2f" class="field" style="font-family: monospace">\n' % hours])
    checked = 'checked="y"' if billable else ''
    tr(s, ['Billable:', '<input type="checkbox" name="billable" %s />' % checked])
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
@post('/save_log')
def save_log():

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

    # Save data
    if lid > 0:
        q = "update work set project_id = %d, work_date = '%s', hours = %.2f, "
        q += "billable = %d, description = '%s' where id = %d"
        q = q % (pid, wdate, hours, billable, descr, lid)
    else:
        wid = nextId('work', cur)
        q = "insert into work values (%d, '%s', '%s', %f , '%s', '%s')" 
        q = q % (wid, pid, wdate, hours, billable, descr)
    cur.execute(q)
    db.commit()
    redirect('/#bottom')


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
    s.write('<h1>Projects</h1>\n')
    s.write('<p><a href="/edit_project/0" class="button">Add project</a> | Show: ')
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


# Show info for one project
@route('/project/<pid:int>')
def project(pid):

    # Start page
    s = io.StringIO()
    header(s)
    s.write('<h1>Project</h1>\n')

    # Get the project to show, exit if not found
    db = getDB()
    cur = db.cursor()
    cur.execute('select id, client, name, description, billable, active, complete, fees from project where id = %d' % pid)
    p = cur.fetchone()
    if not p:
        s.write('<p>Project id %d not found</p>' % pid)
        footer(s)
        return s.getvalue()

    # Show project summary info
    pid, client, name, description, billable, active, complete, fees = p 
    s.write('<table width="100%" border="1">\n')
    tr(s, ['Client:', client])
    tr(s, ['Project Name:', name])
    tr(s, ['Description:', description])
    tr(s, ['Billable:', billable])
    tr(s, ['Active:', active])
    tr(s, ['% complete:', complete])
    tr(s, ['Fees:', fees])
    s.write('</table>\n')

    # Buttons to edit project
    s.write('<p><a href="/edit_project/%d" class="button">Edit</a></p>\n<hr/>\n' % pid)

    # Start table
    s.write('<table width="100%" border="1">\n')

    # Display log entries for this project
    totHrs = totBHrs = totRecs = 0
    totMthHrs = {}
    totMthBHrs = {}
    prevMonth = -1
    cur.execute('select * from work where project_id = %d order by work_date' % pid)
    ww = cur.fetchall()
    for w in ww:

        wid, pid, wdate, hours, billable, descr = w
        wdate = parseDate(wdate)
        hrs = float(hours)

        # Heading at beginning of each month
        if wdate.month != prevMonth:
            s.write('<tr class="heading">')
            s.write('<td width=150>Date</td>')
            td(s, 'Hours')
            td(s, 'Billable')
            td(s, 'Description')
            s.write('</tr>')
            prevMonth = wdate.month

        # Totals
        mth = '%d-%02d' % (wdate.year, wdate.month)
        if not mth in totMthHrs:
            totMthHrs[mth] = totMthBHrs[mth] = 0
        totMthHrs[mth] += hrs
        totHrs += hrs
        if billable:
            totBHrs += hrs
            totMthBHrs[mth] += hrs

        # Show row
        s.write('<tr class="data">')
        td(s, '<a href="/edit_log/%d">%s</a>' % (wid, formatDate(wdate)))
        s.write('<td align="right">%.1f</td>' % hrs)
        if billable:
            s.write('<td style="text-align: center; background: #5f5">Yes</td>')
        else:
            s.write('<td style="text-align: center; color: #aaa">No</td>')
        td(s, descr)
        s.write('</tr>')

    # Totals row
    s.write('<tr class="total"><td>Total</td><td align="right">%.1f</td><td>&nbsp;</td><td>%.1f days</td></tr>' % (totHrs, totHrs / 8.0))
    if totBHrs:
        pcntB = totBHrs / totHrs * 100.0
        s.write('<tr class="total"><td>Billable</td><td align="right">%.1f</td><td align="right">%.1f%%</td><td>%.1f days</td></tr>' % (totBHrs, pcntB, totBHrs / 8.0))
    s.write('</table>')

    # Display stats by month
    s.write('<h2>Project Statistics</h2>\n')
    s.write('<table border="1">')
    s.write('<tr>')
    for h in ['Month', 'Billable', 'Non-billable', 'Total']:
        s.write('<th>%s</th>' % h)
    s.write('</tr>')
    mths = totMthHrs.keys()
    mths = sorted(mths)
    for m in mths:
        th = totMthHrs[m]
        bh = totMthBHrs[m]
        nbh = th - bh
        s.write('<tr>')
        s.write('<td>%s</td>' % m)
        s.write('<td align="right">%.1f hrs = %.1f days</td>' % (bh, bh / 8.0))
        s.write('<td align="right">%.1f hrs = %.1f days</td>' % (nbh, nbh / 8.0))
        s.write('<td align="right">%.1f hrs = %.1f days</td>' % (th, th / 8.0))
        s.write('</tr>')
    s.write('</table>')

    # Display effective hourly rate
    if totHrs > 0 and fees > 0:
        days = totHrs / 8.0
        rate = fees / days
        s.write('<br /><p>Effective daily rate based on total hrs so far (%.1f days @ 8 hrs/day) = %.2f</p>' % (days, rate))
        bdays = totBHrs / 8.0
        brate = fees / bdays
        s.write('<p>Billable time only (%.1f days @ 8 hrs/day) = %.2f</p>' % (bdays, brate))
        if complete > 0 and fees > 0:
            rate = fees / (days / (complete / 100.0))
            brate = fees / (bdays / (complete / 100.0))
            s.write('<p>Effective daily rate based on %.1f%% complete = %.2f</p>' % (complete, rate))
            s.write('<p>Billable only = %.2f</p>' % brate)

    # Show contacts on this project (both colleagues and clients)
    s.write('<h2>Contacts on this Project</h2>\n')
    q = 'select c.last_name, c.first_name, c.company, c.title '
    q += 'from contact as c, project_contact as pc '
    q += 'where pc.project_id = %d and c.id = pc.contact_id ' % pid
    q += 'order by c.last_name'
    cur.execute(q)
    pcc = cur.fetchall()
    if len(pcc) == 0:
        s.write('<p>No people on this project</p>\n')
    else:
        s.write('<ul>\n')
        for pc in pcc:
            lname, fname, co, title = pc
            s.write('<li>%s %s (%s, %s)</li>\n' % (fname, lname, title, co))
        s.write('</ul>\n')
    s.write('<p><a class="button" href="/project_contacts/%d">Edit list</a></p>\n' % pid)

    # Finish page
    footer(s)
    return(s.getvalue())


# Show form to edit/create a project
@route('/edit_project/<pid:int>')
def edit_project(pid):

    # Start page
    s = io.StringIO()
    header(s)
    s.write('<h1>Edit Project</h1>\n')

    # Connect to database
    db = getDB()
    cur = db.cursor()

    #for e in errs:  # show error messages
    #    print '<p class="message">%s</p>' % e

    s.write('<form method="post" action="/save_project"\n>')
    s.write('<input type="hidden" name="id" value="%d" />' % pid)
    s.write('<table width="100%">\n')

    # Get existing values if editing a project
    if pid > 0:
        cur.execute('select client, name, description, billable, active, complete, fees from project where id = %d' % pid)
        client, name, description, billable, active, complete, fees = cur.fetchone()
        complete = float(complete) if complete else 0.0
        fees = float(fees) if fees else 0.0
        billable = isTrue(billable)
        active = isTrue(active)
    else:
        client = name = description = ''
        billable = active = True 
        complete = fees = 0.0

    tr(s, ['Client:', '<input type="text" name="client" value="%s">' % client])
    tr(s, ['Project name:', '<input type="text" name="name" value="%s">' % name])
    tr(s, ['Description:', '<textarea name="description" cols=80 rows=8>%s</textarea>' % description])
    checked = 'checked="y"' if billable else ''
    tr(s, ['Billable:', '<input type="checkbox" name="billable" %s>' % checked])
    checked = 'checked="y"' if active else ''
    tr(s, ['Active:', '<input type="checkbox" name="active" %s>' % checked])
    tr(s, ['Percent complete:', '<input type="text" name="complete" value="%.1f">' % complete])
    tr(s, ['Fees GBP:', '<input type="text" name="fees" value="%.2f">' % fees])

    # End of table and form and page
    s.write('</table>')
    s.write('<input type="submit" value="Save" class="button">')
    s.write('</form>')

    db.close()

    footer(s)
    return s.getvalue()


# Save project from editing form
@post('/save_project')
def save_project():
    
    # Get fields from form
    pid = int(request.forms.id)
    client = clean(request.forms.client)
    name = clean(request.forms.name)
    description = clean(request.forms.description)
    billable = 1 if 'billable' in request.forms else 0
    active = 1 if 'active' in request.forms else 0
    complete = request.forms.complete
    fees = request.forms.fees

    # Check for errors
    # TODO: NEED TO SHOW THE ERRORS, MAYBE DO VALIDATION IN JAVASCRIPT INSTEAD
    errs = []
    if not client:
        errs.append('Please enter a client name')
    if not name:
        errs.append('Please enter a project name')
    if complete:
        try:
            complete = float(complete)
            if complete < 0 or complete > 100:
                errs.append('Percent complete must be 0 to 100')
        except:
            errs.append('Percent complete must be a number')
            complete = 0
    else:
        complete = 0
    if fees:
        try:
            fees = float(fees)
            if fees < 0:
                errs.append('Fees cannot be negative')
        except:
            fees = 0
            errs.append('Fees must be a number')
    else:
        fees = 0

    # Save in database, either new or update existing
    if not errs:
        db = getDB()
        cur = db.cursor()
        if pid > 0:
            q = "update project set client = '%s', name = '%s', description = '%s' , billable = %d , active = %d, complete = %.1f, fees = %.2f where id = %s" % (client, name, description, billable, active, complete, fees, pid)
        else:
            pid = nextId('project', cur)
            q = "insert into project values (%d, '%s', '%s', '%s' , %d , %d, %.1f, %.2f)" % \
                    (pid, client, name, description, billable, active, complete, fees)
        cur.execute(q)
        db.commit()
        db.close()
        redirect('/project/%d' % pid)

    # Show validation errors
    # TODO: show this on the original form, maybe by doing validation with
    # Javascript
    s = io.StringIO()
    header(s)
    s.write('<h1>%d Errors Editing Project</h1>\n<ul>\n' % len(errs))
    for e in errs:
        s.write(' <li>%s</li>\n' % e)
    s.write('</ul>\n<p>Click back button to fix errors.</p>\n')
    footer(s)
    return s.getvalue()


# For to add/remove people from a project
@route('/project_contacts/<pid:int>')
def project_contacts(pid):

    # Start page
    s = io.StringIO()
    header(s)
    s.write('<h1>Project Contacts</h1>\n')

    # Connect to database
    db = getDB()
    cur = db.cursor()

    # Process additions
    if 'add' in request.query:
        cid = int(request.query.add)
        pcid = nextId('project_contact', cur)
        cur.execute('insert into project_contact values (%d, %d, %d)' % (pcid, pid, cid))
        db.commit()

    # Process removals
    if 'remove' in request.query:
        pcid = int(request.query.remove)
        cur.execute('delete from project_contact where id = %d' % pcid)
        db.commit()

    # Show contacts on this project (both colleagues and clients), with links to remove
    q = 'select pc.id, c.id, c.last_name, c.first_name, c.company, c.title '
    q += 'from contact as c, project_contact as pc '
    q += 'where pc.project_id = %d and c.id = pc.contact_id ' % pid
    q += 'order by c.last_name'
    cur.execute(q)
    pcc = cur.fetchall()
    already = []
    s.write('<h3>People on this project</h3>\n')
    if len(pcc) == 0:
        s.write('<p>There are no people on this project</p>\n')
    else:
        s.write('<ul>\n')
        for pc in pcc:
            pcid, cid, lname, fname, co, title = pc
            already.append(cid)
            s.write('<li>%s %s (%s, %s) <a href="/project_contacts/%d?remove=%d" class="button">Remove</a></li>\n' % (fname, lname, title, co, pid, pcid))
        s.write('</ul>\n')

    # Links to add people not already on project
    s.write('<h3>People who can be added to this project</h3>\n')
    s.write('<p>Click on the button to add a person to the project:</p>\n')
    q = 'select id, last_name, first_name, company, title '
    q += 'from contact order by last_name'
    cur.execute(q)
    s.write('<ul>\n')
    for c in cur.fetchall():
        cid, lname, fname, co, title = c
        if not cid in already:
            s.write('<li>%s %s (%s, %s) <a href="/project_contacts/%d?add=%d" class="button">Add</a></li>\n' % (fname, lname, title, co, pid, cid))
    s.write('</ul>\n')

    db.close()

    footer(s)
    return s.getvalue()


#--------------------------------------------------------------------#
#                           CALENDAR                                 #
#--------------------------------------------------------------------#

# Save project from editing form
@route('/calendar')
def calendar():




    # Connect to database and get cursor
    db = getDB()
    cur = db.cursor()

    # Optional month/year, default current
    tdy = today()
    month = int(request.query.month) if 'month' in request.query else tdy.month
    year = int(request.query.year) if 'year' in request.query else tdy.year

    # Start page
    s = io.StringIO()
    header(s)
    s.write('<h1>Calendar for %d/%d</h1>\n' % (month, year))

    # Hyperlinks for next/prev month
    nextMonth = month + 1
    prevMonth = month - 1
    nextYear = prevYear = year
    if nextMonth > 12:
        nextMonth = 1
        nextYear += 1
    if prevMonth < 1:
        prevMonth = 12
        prevYear -= 1
    s.write('<a href="/calendar?month=%d&year=%d" class="button">&lt;&lt;&nbsp;Previous</a>\n' % (prevMonth, prevYear))
    s.write('<a href="/calendar?month=%d&year=%d" class="button">This month</a>\n' % (tdy.month, tdy.year))
    s.write('<a href="/calendar?month=%d&year=%d" class="button">Next&nbsp;&gt;&gt;</a>\n' % (nextMonth, nextYear))

    # Display calendar heading
    s.write('<table width="100%" border="1">\n')
    s.write('<tr class="heading">\n')
    weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for d in weekdays:
        s.write('<td width="14%%">%s</td>\n' % d)
    s.write('</tr>\n')

    # Get data: total hours worked each day on each project
    # Date format is "yyyy-mm-dd", so 
    #   year =  substr(d, 1, 4)
    #   month = substr(d, 6, 2)
    #   day =   substr(d, 9, 2)
    #   year-month = substr(d, 1, 7)
    q = "select substr(work_date,9,2), p.id, p.name, sum(w.hours), w.billable"
    q += " from project as p, work as w"
    q += " where p.id = w.project_id"
    q += " and substr(work_date, 1, 7) = '%d-%02d'" % (year, month)
    q += " group by substr(work_date,9,2), p.id, p.name, w.billable"
    cur.execute(q)
    ww = cur.fetchall()

    # Assign a colour to each project, and remember each colour's name
    colors = ['#abc', '#cab', '#cba', '#bca', '#acb', '#bac', '#cde', '#dec', '#edc', '#ced', 
            'yellow', 'green', 'red', 'blue', 'cyan', 'magenta', 'olive']
    projCol = {}
    projName = {}
    cn = 0
    for w in ww:
        day, pid, pname, hrs, billable = w
        day = int(day)
        pid = int(pid)
        if not pid in projCol:
            if cn >= len(colors):
                cn = 0
            projCol[pid] = colors[cn]
            cn += 1
        if not pid in projName:
            projName[pid] = pname

    # Get starting day of week
    d = date(year, month, 1)
    dow = d.weekday()

    # Display dates
    day = 1
    c = 0
    dim = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    while day <= dim[month]:

        # Start/finish row
        if day == 1 or dow == 0:
            s.write('<tr style="height: 100px">\n')
        if dow == 7:
            s.write('<tr style="height: 100px">\n')
            dow = 0
        if day == 1 and dow > 0:
            for i in range(dow):
                td(s, '&nbsp;')

        # Accumulate hours on each project for this day
        projHrs = {}  # key is project id, value = hours
        billable = {}
        for w in ww:
            d, pid, pname, hrs, b = w
            d = int(d)
            pid = int(pid)
            if d == day:
                projHrs[pid] = hrs
                if b:
                    billable[pid] = True

        # s.write(day info
        s.write(' <td>')
        s.write('%d<br>' % day)
        for p in projHrs.keys():
            rh = max(int(projHrs[p] * 10), 15)
            style = 'background: %s; height: %dpx;' % (projCol[p], rh)
            pname = projName[p]
            if billable.get(p, False):
                style += ' background-image: url(billable.png); background-repeat: repeat;'
            s.write('<div class="tiny" style="%s">' % style)
            s.write('<a href="project.py?id=%d">%s</a> (%.1f)</div>' % (p, pname, projHrs[p]))
        s.write('</td>\n')

        # Prepare for next
        day += 1
        dow += 1
        if dow == 7:
            s.write('</tr>\n')

    # Finish last row
    while dow < 7:
        td(s, '&nbsp;')
        dow += 1

    # Finish table and page
    s.write('</tr>\n</table>\n')
    footer(s)
    return s.getvalue()


#--------------------------------------------------------------------#
#                             CONTACTS                               #
#--------------------------------------------------------------------#


# Show list of contacts
@route('/contacts')
def contacts():

    # Connect to database
    db = getDB()
    cur = db.cursor()

    # Start page
    s = io.StringIO()
    header(s, 'contacts')
    s.write('<h1>Contacts</h1>\n')
    s.write('<p><a href="/edit_contact/0" class="button">Add contact</a></p>\n')

    # Start table
    s.write('<table width="100%" border="1">\n')
    s.write('  <tr class="heading">\n')
    for h in ['Name', 'Company/Title', 'Phones', 'Address']:
        s.write('    <th>%s</th>\n' % h)
    s.write('  </tr>\n')

    # Get contacts and show in table
    count = 0
    cur.execute('select id, last_name, first_name, company, title, phones, address, active from contact order by last_name')
    for c in cur.fetchall():

        cid, lname, fname, company, title, phones, address, active = c
        count += 1

        style = 'vertical_align: top'
        if not active:
            style += '; color: #888; background: #ccc'
        s.write('<tr style="%s">\n' % style)

        td(s, '<a href="/contact/%d">%s %s</a>' % (cid, fname, lname))
        td(s, '%s<br/>%s' % (company, title))
        td(s, phones.replace('\n', '<br/>'))
        td(s, address.replace('\n', '<br/>'))

    # Finish table and page
    s.write('</table>\n')
    s.write('<p>%d contacts</p>\n' % count)
    footer(s)
    return(s.getvalue())


# Show info for one contact
@route('/contact/<cid:int>')
def contact(cid):

    # Start page
    s = io.StringIO()
    header(s, 'contacts')
    s.write('<h1>Contact Details</h1>\n')

    # Get the contact to show, exit if not found
    db = getDB()
    cur = db.cursor()
    cur.execute('select id, last_name, first_name, company, title, phones, address, comments, active from contact where id = %d' % cid)
    c = cur.fetchone()
    if not c:
        s.write('<p>Contact id %d not found</p>' % cid)
        footer(s)
        return s.getvalue()

    # Show contact summary info
    cid, lname, fname, company, title, phones, address, comments, active = c
    s.write('<table width="100%" border="1">\n')
    tr(s, ['Name:', '%s %s' % (fname, lname)])
    tr(s, ['Company:', company])
    tr(s, ['Title:', title])
    tr(s, ['Phone numbers:', phones.replace('\n', '<br/>')])
    tr(s, ['Address:', address.replace('\n', '<br/>')])
    tr(s, ['Comments:', comments.replace('\n', '<br/>')])
    tr(s, ['Active:', active])
    s.write('</table>\n')

    # Buttons to edit contact
    s.write('<p><a href="/edit_contact/%d" class="button">Edit</a></p>\n<hr/>\n' % cid)

    # Show projects for this contact
    s.write('<h2>Projects for this contact</h2>\n')
    q = 'select p.id, p.client, p.name, p.active '
    q += 'from project as p, project_contact as pc '
    q += 'where pc.contact_id = %d and p.id = pc.project_id ' % cid
    q += 'order by p.name'
    cur.execute(q)
    pcp = cur.fetchall()
    already = []
    if len(pcp) == 0:
        s.write('<p>There are no projects for this contact</p>\n')
    else:
        s.write('<ul>\n')
        for pc in pcp:
            pid, client, pname, pactive = pc
            s.write('<li>%s: <a href="/project/%d">%s</a></li>\n' % (client, pid, pname))
        s.write('</ul>\n')


    # Finish page
    footer(s)
    return(s.getvalue())


# Show form to edit/create a project
@route('/edit_contact/<cid:int>')
def edit_contact(cid):

    # Start page
    s = io.StringIO()
    header(s)
    s.write('<h1>Edit Contact</h1>\n')

    # Connect to database
    db = getDB()
    cur = db.cursor()

    s.write('<form method="post" action="/save_contact"\n>')
    s.write('<input type="hidden" name="id" value="%d" />' % cid)
    s.write('<table width="100%">\n')

    # Get existing values if editing a contact
    # CREATE TABLE contact (id integer NOT NULL, last_name character(32), first_name character(32), 
    # company character(32), title character(32), phones text, address text, comments text, active boolean);
    if cid > 0:
        cur.execute('select id, last_name, first_name, company, title, phones, address, comments, active from contact where id = %d' % cid)
        cid, lname, fname, company, title, phones, address, comments, active = cur.fetchone()
        active = isTrue(active)
    else:
        lname = fname = company = title = phones = address = comments = ''
        active = True 

    tr(s, ['Last Name:', '<input type="text" name="last_name" value="%s">' % lname])
    tr(s, ['First Name:', '<input type="text" name="first_name" value="%s">' % fname])
    tr(s, ['Company:', '<input type="text" name="company" value="%s">' % company])
    tr(s, ['Title:', '<input type="text" name="title" value="%s">' % title])

    tr(s, ['Phone numbers:', '<textarea name="phones" cols=80 rows=5>%s</textarea>' % phones])
    tr(s, ['Address:', '<textarea name="address" cols=80 rows=5>%s</textarea>' % address])
    tr(s, ['Comments:', '<textarea name="comments" cols=80 rows=5>%s</textarea>' % comments])

    checked = 'checked="y"' if active else ''
    tr(s, ['Active:', '<input type="checkbox" name="active" %s>' % checked])


    # End of table and form and page
    s.write('</table>')
    s.write('<input type="submit" value="Save" class="button">')
    s.write('</form>')

    db.close()

    footer(s)
    return s.getvalue()


# Save contact from editing form
@post('/save_contact')
def save_contact():
    
    # Get fields from form
    cid = int(request.forms.id)
    lname = clean(request.forms.last_name)
    fname = clean(request.forms.first_name)
    company = clean(request.forms.company)
    title = clean(request.forms.title)
    phones = clean(request.forms.phones)
    address = clean(request.forms.address)
    comments = clean(request.forms.comments)
    active = 1 if 'active' in request.forms else 0

    # TODO: Check for errors
    errs = []

    # Save in database, either new or update existing
    # CREATE TABLE contact (id integer NOT NULL, last_name character(32), first_name character(32), 
    # company character(32), title character(32), phones text, address text, comments text, active boolean);
    if not errs:
        db = getDB()
        cur = db.cursor()
        if cid > 0:
            q = "update contact set last_name = '%s', first_name = '%s', company = '%s', title = '%s', phones = '%s', address = '%s', comments = '%s', active = %d  where id = %d" % (lname, fname, company, title, phones, address, comments, active, cid)
        else:
            cid = nextId('contact', cur)
            q = "insert into contact values (%d, '%s', '%s', '%s', '%s', '%s', '%s', '%s', %d)" % (cid, lname, fname, company, title, phones, address, comments, active)
        cur.execute(q)
        db.commit()
        db.close()
        redirect('/contact/%d' % cid)

    footer(s)
    return s.getvalue()


#--------------------------------------------------------------------#
#                            REPORTS                                 #
#--------------------------------------------------------------------#

# Save project from editing form
@route('/reports')
def reports():

    # Start page
    s = io.StringIO()
    header(s, 'reports')
    s.write('<h1>Reports</h1>')

    # Menu of reports
    s.write('<ul>')
    for g in ['utilization', 'monthly_report', 'project_graph']:
        s.write('<li><a href="%s">%s</li>' % (g, g.replace('_', ' ').title()))
    s.write('</ul>')

    # Finish page
    footer(s)
    return s.getvalue()


# Weekly & Monthly utilization report
@route('/utilization')
def utilization():

    # Connect to database
    db = getDB()
    cur = db.cursor()

    # Start page
    s = io.StringIO()
    header(s, 'reports')
    s.write('<div style="padding: 32px">\n')
    s.write('<h1>Utilization Report</h1>\n')

    # Get the time log records for the current year
    # PROBLEM: the counters will be out or missed, if there are gaps in the dates
    q = 'select work.id, project_id, client, name, work_date, hours, work.billable, work.description '
    q += ' from work, project where work.project_id = project.id'
    q += " and substr(work_date,1,7) >= '%s'" % this_month
    q += ' order by work_date'  # desc limit 400'
    cur.execute(q)
    work = cur.fetchall()

    # Initialize counters
    dHrs = {}
    dBillable = {}
    wHrs = {}
    wBillable = {} 
    mHrs =  {}
    mBillable = {} 

    # Do counters, by week and month
    for w in work:

        wid, pid, client, projName, wdate, hrs, billable, descr = w
        wdate = parseDate(wdate)

        # Ignore rows for some projects
        if pid in ignoreProjectIDs:
            continue

        # Get keys for week/month
        wkey = wdate - timedelta(wdate.weekday())   # Monday of this week
        mkey = date(wdate.year, wdate.month, 1)     # Beginning of month

        # Update counters
        dHrs[wdate] = dHrs.get(wdate, 0) + hrs
        wHrs[wkey] = wHrs.get(wkey, 0) + hrs
        mHrs[mkey] = mHrs.get(mkey, 0) + hrs
        if billable:
            dBillable[wdate] = dBillable.get(wdate, 0) + hrs
            wBillable[wkey] = wBillable.get(wkey, 0) + hrs
            mBillable[mkey] = mBillable.get(mkey, 0) + hrs

    # Show in a table (for now, graph to do)
    s.write('<h2>Weekly Utilization</h2>\n')
    kk = sorted(wHrs.keys())
    for k in kk:
        h = wHrs.get(k, 0.0)
        b = wBillable.get(k, 0.0)
        pcnt = 0.0 if h == 0 else b / h * 100.0
        s.write('<p style="font-family: monospace">%s: %4.1f / %4.1f = %3.1f%%</p>\n' % (k, b, h, pcnt))

    s.write('<h2>Monthly Utilization</h2>\n')
    kk = sorted(mHrs.keys())
    for k in kk:
        h = mHrs.get(k, 0.0)
        b = mBillable.get(k, 0.0)
        pcnt = 0.0 if h == 0 else b / h * 100.0
        s.write('<p style="font-family: monospace">%s: %4.1f / %4.1f = %3.1f%%</p>\n' % (k, b, h, pcnt))

    # Finish page
    s.write('</div>\n')
    footer(s)
    return s.getvalue()


@route('/monthly_report')
@route('/monthly_report/<yyyymm>')
def monthly_report(yyyymm = None):

    # Connect to database
    db = getDB()
    cur = db.cursor()

    # Start page
    s = io.StringIO()
    header(s, 'reports')

    # Get month
    if yyyymm:
        y = int(yyyymm[:4])
        m = int(yyyymm[4:])
    else:
        d = today()
        y = d.year 
        m = d.month 

    # Get next/prev month
    nextY = prevY = y
    nextM = m + 1
    if nextM > 12:
        nextY += 1
        nextM = 1
    prevM = m - 1
    if prevM < 1:
        prevY -= 1
        prevM = 12

    # Heading with selected month, links to next/prev
    s.write('<div style="padding: 32px">\n')
    s.write('<h1>Monthly Report for %d/%d</h1>\n' % (m, y))
    s.write('<p style="font-size: 0.8em; margin-bottom: 32px;">Go to <a href="/monthly_report/%d%02d">&lt;&lt; previous</a> ' % (prevY, prevM))
    s.write('/ <a href="/monthly_report/%d%02d">next &gt;&gt;</a> month</p>' % (nextY, nextM))

    # Get hours by project for that month
    # TODO: billable vs. non-billable
    q = 'select p.client, p.name, sum(w.hours)'
    q += ' from work as w, project as p'
    q += ' where w.project_id = p.id'
    q += " and substr(w.work_date,1,7) = '%d-%02d'" % (y, m)
    q += ' group by p.client, p.name order by client'
    cur.execute(q)

    # Start table
    s.write('<table>\n')
    s.write('<tr>\n')
    for h in ['Client', 'Project', 'Hours', 'Days']:
        s.write('  <th>%s</th>\n' % h)
    s.write('</tr>\n')

    # Show stats
    totHrs = 0
    for r in cur.fetchall():
        client, projName, hrs = r
        totHrs += hrs
        s.write('<tr>\n')
        #s.write('<p>%s / %s : %.1f hrs = %.1f days</p>\n' % (client, projName, hrs, hrs / 9.0))
        s.write('<td>%s</td>\n' % client)
        s.write('<td>%s</td>\n' % projName)
        s.write('<td align="right">%.1f</td>\n' % hrs)
        s.write('<td align="right">%.1f</td>\n' % (hrs / 8.0))
        s.write('</tr>\n')

    # Show totals
    s.write('<tr style="font-weight: bold">\n')
    s.write('<td>TOTAL</td>\n')
    s.write('<td>&nbsp;</td>\n')
    s.write('<td align="right">%.1f</td>\n' % totHrs)
    s.write('<td align="right">%.1f</td>\n' % (totHrs / 8.0))

    # Finish table & page
    s.write('</table>\n')
    s.write('<p style="margin-top: 32px; font-size: 0.8em">Note: day = 8 hours</p>\n')
    s.write('</div>\n')
    footer(s)
    return s.getvalue()


# Stacked area graph of daily/weekly time on projects
@route('/project_graph')
#@route('/monthly_report')
#@route('/monthly_report/<yyyymm>')
def project_graph():

    # Connect to database
    db = getDB()
    cur = db.cursor()

    # Start page
    s = io.StringIO()
    header(s, 'reports')
    s.write('<div style="padding: 32px">\n')
    s.write('<h1>Project Activity Graph</h1>\n')

    # Get daily hours by project
    # TODO: date range
    q = 'select w.work_date, p.client, p.name, w.hours'
    q += ' from work as w, project as p'
    q += ' where w.project_id = p.id'
    #q += " and substr(w.work_date,1,7) = '%d-%02d'" % (y, m)
    cur.execute(q)

    # Group by week or month
    ghrs = {}  # Key = project, value = {period: hours}
    for r in cur.fetchall():
        ds, c, p, hrs = r  # Date is "yyyy-mm-dd"
        d = datetime.strptime(ds, '%Y-%m-%d').date()
        wd = d - timedelta(d.weekday())  # Beginning of week
        cp = c + ': ' + p  # Client & project
        if not cp in ghrs:
            ghrs[cp] = {}
        ghrs[cp][wd] = ghrs[cp].get(wd,0) + hrs

    # Create the SVG tag with ID
    s.write('<svg id="graph" width="800" height="400" style="border: 1px solid #ccc" />\n')

    # Show data in script tag, an array of arrays, each the
    # project name followed by [x,y] pairs
    s.write('<script>\n')
    s.write('var data = [\n')
    first = True
    for cp in ghrs.keys():
        if first:
            first = False
        else:
            s.write(',\n')
        s.write('  ["%s"' % cp)
        wh = ghrs[cp]  # for this project, weekdate => hours
        for d in wh.keys():
            s.write(', [new Date(%d,%d,%d), %.2f]' % (d.year, d.month, d.day, wh[d]))
        s.write(' ]')
    s.write(' ];\n')
    s.write('</script>\n')

    # Embed script tags for D3 and the graph
    s.write('<script language="JavaScript" type="text/javascript" src="/static/d3.min.js"></script>\n')
    s.write('<script language="JavaScript" type="text/javascript" src="/static/script.js"></script>\n')

    # Finish page
    s.write('</div>\n')
    footer(s)
    return s.getvalue()


#--------------------------------------------------------------------#
#                         SUPPORT FUNCTIONS                          #
#--------------------------------------------------------------------#


# Menu options
menu = [
    ['History', ''],
    ['New log', 'new_log'],
    ['Calendar', 'calendar'],
    ['Projects', 'projects'], 
    ['Contacts', 'contacts'],
    ['Reports', 'reports']]


# Get database handler, new version using SQLite
def getDB():
    return sql.connect(dbname)


# Get next ID for a table
def nextId(table, cur):
    cur.execute('select max(id) from ' + table)
    r = cur.fetchone()
    nid = r[0] if r and r[0] else 0
    return nid + 1


# Return contents of a file, closing it first
def readFile(fname):
    f = open(fname)
    data = f.read()
    f.close()
    return data


# Start page
def header(s, current = None):  # TODO: highlight current selection

    # Static page header
    #s.write('Content-Type: text/html\n\n')
    s.write(readFile('static/header.html'))

    # Anchor to go to top of page
    s.write('<a name="top"></a>')

    # Show menu
    s.write('<div id="menu">\n')
    for m in menu:
        if m != menu[0]:
            s.write(' | ')
        label, href = m
        if label == 'History':
            href += '#bottom'
        s.write('<a href="/%s">%s</a>\n' % (href, label))
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

# Clean a string prior to inserting into SQL statement, i.e., remove leading
# trailing blanks and apostrophes
def clean(s):
    return s.strip().replace("'", "\\'")


#--------------------------------------------------------------------#
#                         SESSION HANDLER                            #
#--------------------------------------------------------------------#


# Simple session handling. Session ID is stored in a cookie, and
# the session data is stored in a JSON file with that name in /tmp
def get_session():

    # Get the current session ID from cookie, create if not there
    sid = request.cookies.get('sid')
    if not sid:
        sid = uuid.uuid4().hex
        response.set_cookie('sid', sid)

    # Get the session file and return as a dictionary; if no session
    # file yet, just return an empty dictionary
    sfile = session_dir + '/' + sid
    if os.path.exists(sfile):
        return json.loads(readFile(sfile))
    else:
        return { 'sid' : sid }


# Save the session, creates a new session ID if current one is not found
def save_session(sdata):
    sid = sdata['sid']
    f = open(session_dir + '/' + sid, 'w')
    f.write(json.dumps(sdata))
    f.close()


# Save the session ID in the next cookie (NOT USED)
def remember_session():
    sess = get_session()
    if sess: 
        response.set_cookie('sid', sess['sid'])


# Determine a value looks like boolean TRUE
def isTrue(v):
    return str(v).lower() in ['1', '1.0', 'true', 'yes']

#--------------------------------------------------------------------#
#                            START SERVER                            #
#-------------------------------------------------------------------#


# Serve static files
@route('/static/<filename:path>')
def serve_static(filename):
    return static_file(filename, root = os.getcwd() + '/static')


# Start server, debug options on workstations
wks = socket.gethostname() in ['shuttle', 'brix']
#print("Host name:", socket.gethostname(), wks)
run(host = 'localhost', port = 8082, reloader = wks, debug = wks, quiet = not wks)

