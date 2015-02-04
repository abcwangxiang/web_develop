"""
Need to implement following commands
pip install flask
pip install django
pip install MySQLdb
"""

from Bugzilla_webservice import *
from BAR_Rules import *
from BAR import gRecordSchema
from flask import request
from flask import render_template
from flask import flash, jsonify
from flask import Flask, session, redirect, url_for, escape, request, send_file
from werkzeug.contrib.cache import SimpleCache
import MySQLdb
import hashlib
import os
import time
import logging
import traceback
import string
import re
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from collections import OrderedDict
from calendar import month_name


"""
    Important, the relativedelta should be modified by config if the user want to modified the eta period
    shinyeh 0718
"""

BUGZILLA_DATABASE_HOST = "bz3-db3.eng.vmware.com"
BUGZILLA_DATABASE_PORT = 3306
BUGZILLA_DATABASE_USER ="mts"
BUGZILLA_DATABASE_PW="mts"
BUGZILLA_DATABASE_DATABASE="bugzilla"
bzdb_conn = MySQLdb.connect(host=BUGZILLA_DATABASE_HOST, port=BUGZILLA_DATABASE_PORT, user=BUGZILLA_DATABASE_USER, passwd=BUGZILLA_DATABASE_PW, db=BUGZILLA_DATABASE_DATABASE)

LOCAL_DATABASE_HOST = "localhost"
LOCAL_DATABASE_PORT = 3306
LOCAL_DATABASE_USER = "root"
LOCAL_DATABASE_PW = "vmware"
LOCAL_DATABASE_DATABASE = "cpdtools"
#local_conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, port=LOCAL_DATABASE_PORT, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)


PATCHTOOL_DATABASE_HOST = "patchtool.eng.vmware.com"
PATCHTOOL_DATABASE_PORT = 3306
PATCHTOOL_DATABASE_USER = "read"
PATCHTOOL_DATABASE_PW = "read"
PATCHTOOL_DATABASE_DATABASE = "rmtool"
#pttl_conn = MySQLdb.connect(host=PATCHTOOL_DATABASE_HOST, port=PATCHTOOL_DATABASE_PORT, user=PATCHTOOL_DATABASE_USER, passwd=PATCHTOOL_DATABASE_PW, db=PATCHTOOL_DATABASE_DATABASE)

app = Flask(__name__)
app.secret_key = 'B1Z298g/3y2 R~lHHbjaN]LWX/,?RT'
cache = SimpleCache(default_timeout=300)
BUGZILLA_URL = 'https://bugzilla.eng.vmware.com/xmlrpc.cgi'
SCRIPTS_DIR = os.path.abspath(os.path.dirname(__file__))
BAR_OPTION_DIRECTORY = os.path.join(SCRIPTS_DIR, "BAR_option/")
CUSTOM_OPTION_DIRECTORY = os.path.join(SCRIPTS_DIR, "Custom_Setting/")

BAR_OFILENAME = BAR_OPTION_DIRECTORY + "option.p"
BAR_ADMINFILE = BAR_OPTION_DIRECTORY + "admin.p"


FMT_YMDHMS  = "%Y-%m-%d %H:%M:%S"
NO_LOGIN = 'Please login before register/edit tools'
ADMINI_ADDRS = ['chenh@vmware.com', 'fangchiw@vmware.com', 'xiangw@vmware.com', 'myildirim@vmware.com', 'sgadi@vmware.com', 'hillzhao@vmware.com']
FROM_ADDR = "fangchiw@vmware.com"

EMAIL_MESSAGE_TOOL_UPDATE = """\
\nThanks
CPDTools Committe
--------------------------------
\nThis Email is sent by CPDtools website automatically.
If you have any questions, please contact: fangchiw@vmware.com, xiangw@vmware.com
"""

with app.test_request_context('/hello', method='POST'):
    # now you can do something with the request until the
    # end of the with block, such as basic assertions:
    assert request.path == '/hello'
    assert request.method == 'POST'


@app.route('/')
def index():
    visited_file = os.path.join(SCRIPTS_DIR, 'log/visited.log')
    new = os.popen('touch %s; echo 1 >> %s'%(visited_file, visited_file)).read()
    return Tools_Catalog(0)

@app.route('/Login', methods=['GET', 'POST'])
def Login():
    """
    This function handles login function.
    The login procedure is connected with bugzilla
    After successfully login, the function will check for the admin privilege and record username into data
    The transmission is crypted, and the password is not recorded in the system
    """
    error = None
    if 'USERPROFILE' in os.environ:
        homepath = os.path.join(os.environ["USERPROFILE"], "Local Settings",
                                "Application Data")
    elif 'HOME' in os.environ:
        homepath = os.environ["HOME"]
    else:
        homepath = ''

    cookie_file = os.path.join(homepath, ".bugzilla-cookies.%s.txt"%str(request.form['BG_account']))
    #bugzilla_url = options.bugzilla_url
    server = BugzillaServer(BUGZILLA_URL, cookie_file)
    login_result = server.login(str(request.form["BG_account"]), str(request.form["BG_password"]))
    if not login_result:
        logging.warning("{} fails to login into the bugzilla.".format(str(request.form["BG_account"])))
        return render_template('query.html', error = "Error Account/Password, Please Login again")

    session['username'] = request.form['BG_account']
    if session['username']:
        session['username'] = session['username'].split('@')[0]
    session['password'] = request.form['BG_password']
    session['cookie_file'] = cookie_file

    session['logged_in'] = True

    admin_file_path = open(BAR_ADMINFILE, "r")
    admin_members = []
    for line in admin_file_path:
        admin_members.append(line.rstrip())
    if session['username'] in admin_members:
        session['admin'] = True
    else:
        session['admin'] = False

    #cache.set('username', str(request.form["BG_account"]))
    #cache.set('cookie', cookie_file)
    logging.warning("{} login into the bugzilla successfully.".format(session['username']))

    return index()
    #return render_template('query.html')

@app.route('/Tools_Catalog_Query')
def Tools_Catalog_Query():
    res = {}
    res['res'] = 'internal error'
    para = request.args
    tool_tab_id = para.get('id', '').strip()
    conn = get_conn()
    cursor = conn.cursor()
    ss_month = ''
    template = "tools_catalog_table_frag.html"
    if tool_tab_id == '100_m':
        sql="""
            SELECT *
            from tools
            where
            maturity like 'Ship%'
            """
    elif tool_tab_id == "all":
        sql="""
            SELECT *
            from tools
            """
    elif tool_tab_id == "active":
        sql="""
            select tools.*, active_tools.*
            from tools
            INNER JOIN active_tools
            on tools.tool_id = active_tools.tool_id
            where active_tools.flag=1
            """
        template = "tools_active_table_frag.html"
        res['spec'] = "active"
        ss_month = 'NOW'
    elif tool_tab_id == "backlog":
        sql="""
            select tools.*, active_tools.*
            from tools
            INNER JOIN active_tools
            on tools.tool_id = active_tools.tool_id
            where active_tools.flag=0
            """
    if sql:
        cursor.execute(sql)
        columns = [column[0] for column in cursor.description]
        impure_results = []
        for row in cursor.fetchall():
            impure_results.append(dict(zip(columns, row)))
        #print impure_results[0]
        data = impure_results
        res['res'] = 'success'
        res['data'] = render_template(template, tools=impure_results, ss_month_ret = ss_month)

    cursor.close()
    conn.commit()
    conn.close()
    return jsonify(res)

@app.route('/Tools_Catalog')
def Tools_Catalog(active_view = 0):
    """
    This should be modified to match the database
    """
    conn = get_conn()
    sql = """SELECT * from tools"""
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    impure_results = []
    for row in cursor.fetchall():
        impure_results.append(dict(zip(columns, row)))
    cursor.close()
    conn.commit()
    conn.close()
    return render_template('tools_catalog.html', tools=impure_results, catalog=2, active_view=active_view)

@app.route('/Tools_Send_Mail')
def Tools_Send_Mail():
    if (request.host != "localhost"):
        return index()
    conn = get_conn()
    sql = """
            SELECT active_track.*
            from active_track
            INNER JOIN active_tools
            on active_track.tool_id = active_tools.tool_id
            where active_tools.flag=1
          """
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    impure_results = []
    for row in cursor.fetchall():
        impure_results.append(dict(zip(columns, row)))
    cursor.close()
    conn.commit()
    conn.close()

    #find the active tools' last update in active_track
    latest_act_tools = []
    all_act_tools_id = get_tools_all_id()
    for act_tool_id in all_act_tools_id:
        last_update_date = ''
        temp = {}
        for row in impure_results:
            if row['tool_id'] == act_tool_id:
                if row['date'] >= last_update_date:
                #find the the last change
                    temp = row
                    last_update_date = row['date']
        if len(temp) != 0:
            latest_act_tools.append(temp)

    now = datetime.now()
    for row in latest_act_tools:
        date = datetime.strptime(row['date'],"%Y-%m-%d, %H:%M:%S PST")
        day_dist = (now - date).days
        if (row['new_progress'] != '100%') and day_dist >= 6:
            to_addr = row['username'] + "@vmware.com"
            from_addr = FROM_ADDR
            toolname = get_tool_attr(row['tool_id'], 'tool_name')

            ############   The message   ###########
            subject = "[Your CPD Tool * " + toolname + " * No Update Reminder]"
            message = "Hello,\n"
            tool_id_str = `row['tool_id']`
            message += "\nYour Project *" + toolname
            message += "* at : http://cpdtools.eng.vmware.com/Show_Tool_Details?id="
            message += tool_id_str[0:len(tool_id_str)-1] + " hasn't been updated for " + str((now - date).days) + " days."
            message += "\nYour last update is at " + str(date) + ".\nNow "

            #get the tools' builder's emails
            mail_addrs = get_tool_attr(row['tool_id'], 'emails')
            real_mail_addrs = re.findall(r'[\w\._-]+@vmware\.com', mail_addrs)
            if to_addr not in real_mail_addrs: #the one who last update the tool
                real_mail_addrs.append(to_addr)

            #change list to a string
            to_addr_string = ', '.join(real_mail_addrs)
            cc_addr_string = ', '.join(ADMINI_ADDRS)

            if (day_dist== 6):
                message += "it will be marked orange tomorrow.\n"
                message += EMAIL_MESSAGE_TOOL_UPDATE
                send_email(from_addr, real_mail_addrs, ADMINI_ADDRS, subject, message)
                record_email_send_info(row['tool_id'], 'xiangw', to_addr_string, cc_addr_string, 1)
                continue
            if (day_dist >= 7) and (day_dist < 13) :
                message += "it has been marked orange .\n"
                message += EMAIL_MESSAGE_TOOL_UPDATE
                send_email(from_addr, real_mail_addrs, ADMINI_ADDRS, subject, message)
                record_email_send_info(row['tool_id'], 'xiangw', to_addr_string, cc_addr_string, 2)
                continue
            if (day_dist == 13):
                message += "it will be marked red tomorrow.\n"
                message += EMAIL_MESSAGE_TOOL_UPDATE
                send_email(from_addr, real_mail_addrs, ADMINI_ADDRS, subject, message)
                record_email_send_info(row['tool_id'], 'xiangw', to_addr_string, cc_addr_string, 3)
                continue
            if (day_dist >= 14):
                message += "it has been marked red.\n"
                message += EMAIL_MESSAGE_TOOL_UPDATE
                send_email(from_addr, real_mail_addrs, ADMINI_ADDRS, subject, message)
                record_email_send_info(row['tool_id'], 'xiangw', to_addr_string, cc_addr_string, 4)

    return index()

@app.route('/Register_Tool', methods=['GET', 'POST'])
def Register_Tool():
    if not ('logged_in' in session.keys() and session['logged_in']):
        return render_template('tools_login.html', previous_url=request.path, error=NO_LOGIN)
    if request.method == 'GET':
        return render_template('tools_register.html', catalog=0)
    else:
        tool_name = str(request.form["tool_name"])
        authors = str(request.form["authors"])
        team = str(request.form["team"])
        keywords = str(request.form["keywords"])
        maturity = str(request.form["maturity"])
        url = str(request.form["url"])
        wiki = str(request.form["wiki"])
        description = request.form["description"]
        emails = str(request.form["emails"])
        source = str(request.form["source"])

        conn = get_conn()
        cursor = conn.cursor()
        sql="""
        INSERT INTO tools
                    (authors,team,tool_name,description,keywords,url,wiki,maturity,emails,source)
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

        cursor.execute(sql, (authors,team,tool_name,description,keywords,url,wiki,maturity,emails,source))

        cursor.close()
        conn.commit()
        conn.close()
        return Tools_Catalog()

@app.route('/Active_Tools')
def Tools_Active_Tools():
    return Tools_Catalog(1)

@app.route('/Tools_Active_Snapshots')
def Tools_Active_Snapshots():
    res = {}
    res['res'] = 'internal error'
    para = request.args
    ss_month = para.get('ss_month', '').strip()

    # change the ss_month to ss_date for complare, such as :
    # 201411 to 20141132
    # 201412 to 20141232
    # 201501 to 20150132
    ss_date = ss_month + '32'

    template = "tools_active_table_frag.html"
    conn = get_conn()
    cursor = conn.cursor()
    sql="""
        select tools.*, active_track.*
        from
            tools
                INNER JOIN
            active_tools
            on tools.tool_id = active_tools.tool_id
                INNER JOIN
            active_track
            on active_tools.tool_id = active_track.tool_id
            where active_tools.flag = 1
        """
    if sql:
        cursor.execute(sql)
        columns = [column[0] for column in cursor.description]
        impure_results = []
        snap_res = []
        for row in cursor.fetchall():
            impure_results.append(dict(zip(columns, row)))
        all_act_tools_id = get_tools_all_id()

        for act_tool_id in all_act_tools_id:
            temp = {}
            last_act_eta = ''
            last_act_date = ''
            for row in impure_results:
                if row['tool_id'] == act_tool_id:
                    row['progress'] = row['new_progress']
                    if row['eta']:
                        act_eta = row['eta'][0:4] + row['eta'][5:7] + row['eta'][8:10]
                        #cut the eta: '2014-12-12,...'
                        if act_eta < ss_date:
                        #filter the eta > ss_date
                            if act_eta >= last_act_eta:
                            #find the the last change before ss_date
                                temp = row
                                last_act_eta = act_eta
            if len(temp) == 0:
                for row in impure_results:
                    if row['tool_id'] == act_tool_id:
                        row['progress'] = row['new_progress']
                        if not row['date']:
                            continue
                        act_date = row['date'][0:4] + row['date'][5:7] + row['date'][8:10]
                        #cut the date: '2014-12-12,...'
                        if act_date < ss_date:
                        #filter the date > ss_date
                            if act_date >= last_act_date:
                            #find the the last change before ss_date
                                temp = row
                                last_act_date = act_date
            if len(temp) != 0:
                snap_res.append(temp)

        data = snap_res
        res['res'] = 'success'
        #print snap_res
        res['data'] = render_template(template, tools=snap_res, ss_month_ret=ss_month)
        res['spec'] = "active"

    cursor.close()
    conn.commit()
    conn.close()
    return jsonify(res)


@app.route('/Tools_Stats')
def Tools_Stats():
    res = dict()
    stats = dict()
    #stats['visited'] = int(os.popen('cat /etc/httpd/logs/access* | grep "GET / " | wc -l').read())+1769
    visited_file = os.path.join(SCRIPTS_DIR, 'log/visited.log')
    stats['visited'] = os.popen('cat %s'%visited_file).read().split('\n')
    stats['visited'] = str(sum(map(int, filter(None, stats['visited']))))

    log_file = os.path.join(SCRIPTS_DIR, 'log/query_and_logging.log')
    stats['user'] = os.popen('cat %s| grep "login into" | grep "successfully" | cut -d" " -f 8 | sort -u | wc -l'%log_file).read()

    stats['app'], stats['wiki'] = get_stats_on_app_wiki()
    res['res'] = 'success'
    res['data'] = render_template('tools_catalog_stats_popover_table.html', stats=stats)

    return jsonify(res)


@app.route('/Tool_Activate')
def Tool_Activate():
    res = {}
    if not ('logged_in' in session.keys() and session['logged_in']):
        res['res'] = 'Please Login before activate/edit'
    else:
        para = request.args
        tool_id = int(para.get('id', '').strip())
        active_info = check_tool_actvie(tool_id, force=True)
        if not active_info:
            active_info = dict()
            active_info['tool_id'] = tool_id
        res['data'] = render_template('tool_active_edit_frag.html', active_info=active_info)
        res['res'] = 'success'
        try:
            logging.warning("user: %s activated tool: %s."%(session['username'], tool_id))
        except:
            pass
    return jsonify(res)

@app.route('/Tool_Deactivate')
def Tool_Deactivate():
    res = {}
    if not ('logged_in' in session.keys() and session['logged_in']):
        res['res'] = 'Please Login before this operation'
    else:
        para = request.args
        tool_id = int(para.get('id', '').strip())
        active_info = check_tool_actvie(tool_id)
        if active_info:
            conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE, charset='utf8')
            cursor = conn.cursor()
            sql = """update active_tools
                     set `flag`=0
                     where tool_id = %(tool_id)s """
            cursor.execute(sql, {"tool_id":tool_id})

            cursor.close()
            conn.commit()
            conn.close()
            try:
                logging.warning("user: %s deactivated tool: %s."%(session['username'], tool_id))
            except:
                pass

        res['res'] = 'success'
    return jsonify(res)

@app.route('/Tool_Active_Info_Edit', methods=['GET', 'POST'])
def Tool_Active_Info_Edit():
    res = {}
    if not ('logged_in' in session.keys() and session['logged_in']):
        res['res'] = 'Please Login before edit'
    else:
        tool_id = str(request.form["id"])
        progress = str(request.form["progress"])
        update = request.form["update"]
        master_pr = request.form["master_pr"]
        e_return = request.form["e_return"]
        e_resource = request.form["e_resource"]
        e_timeline = request.form["e_timeline"]
        deliverables = request.form["deliverables"]
        flag = '1'

        if "backlog_check" in request.form.keys():
            backlog = True
            flag = '0'
        else:
            backlog = False

        if not backlog and not all([master_pr, e_return, e_resource, e_timeline, deliverables]):
            res['res'] = 'Missing one or more mandatory fields'
            return jsonify(res)

        def has_changed():
            current_info = check_tool_actvie(tool_id)
            if current_info:
                if progress!=current_info['progress']:
                    return True
                if master_pr!=current_info['master_pr']:
                    return True
                if e_return!=current_info['return']:
                    return True
                if e_timeline!=current_info['eta']:
                    return True
                if e_resource!=current_info['resource']:
                    return True
                if deliverables!=current_info['deliverables']:
                    return True
            return False

        v_has_changed = has_changed()

        if update:
            conn = get_conn()
            cursor = conn.cursor()
            sql="""
                INSERT INTO active_tools
                (`tool_id`, `master_pr`, `return`, `eta`, `resource`, `deliverables`, `progress`, `flag`)
                VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                `master_pr`=%s,`return`=%s,eta=%s,resource=%s,deliverables=%s,progress=%s,flag=%s
                """
            cursor.execute(sql, (tool_id, master_pr, e_return, e_timeline, e_resource, deliverables, progress, flag, master_pr, e_return, e_timeline, e_resource, deliverables, progress, flag))

            username = session['username']
            new_progress = progress
            date = datetime.now().strftime("%Y-%m-%d, %H:%M:%S PST")
            sql="""
                   INSERT INTO active_track
                    (`tool_id`, `username`, `date`, `update`, `new_progress`, `master_pr`, `eta`, `resource`, `return`, `deliverables`)
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
            cursor.execute(sql, (tool_id, username, date, update, new_progress, master_pr, e_timeline, e_resource, e_return, deliverables ))
            cursor.close()
            conn.commit()
            conn.close()
            res['res'] = 'success'
        elif v_has_changed:
            res['res'] = 'Please leave some update on this INFO change'
        else:
            res['res'] = 'success'

        try:
            logging.warning("user: %s modified active tool: %s."%(session['username'], tool_id))
        except:
            pass

    return jsonify(res)


@app.route("/Tool_Edit_Frag", methods=['GET', 'POST'])
def Tool_Edit_Frag():
    res = {}
    if not ('logged_in' in session.keys() and session['logged_in']):
        res['res'] = 'Please Login before edit'
    else:
        if request.method == 'GET':
            para = request.args
            tool_id = para.get('id', '').strip()
            conn = get_conn()
            sql = """SELECT * from tools where tool_id = %(tool_id)s"""
            cursor = conn.cursor()
            cursor.execute(sql, {"tool_id":tool_id})
            columns = [column[0] for column in cursor.description]
            impure_results = []
            for row in cursor.fetchall():
                impure_results.append(dict(zip(columns, row)))
            #print impure_results[0]

            #if it is active tool
            active = 0
            sql = """SELECT * from active_tools where tool_id = %(tool_id)s"""
            cursor.execute(sql, {"tool_id":tool_id})
            if cursor.fetchone():
                active = 1
            cursor.close()
            conn.commit()
            conn.close()
            res['data'] = render_template('tools_edit_form.html', tool=impure_results[0], catalog=1, active=active)
            res['res'] = 'success'
        else:
            success, tool_item, message = edit_tool_details()
            if success:
                res['data'] = render_template('tools_detail_form.html', tool=tool_item, catalog=1)
                res['res'] = 'success'
            else:
                res['res'] = message
    return jsonify(res)


@app.route("/Edit_Tool_Details", methods=['GET', 'POST'])
def Edit_Tool_Details():
    if not ('logged_in' in session.keys() and session['logged_in']):
        return render_template('tools_login.html', previous_url=request.path, error=NO_LOGIN)
    if request.method == 'GET':
        para = request.args
        tool_name = para.get('name', '').strip()
        tool_id = para.get('id', '').strip()
        conn = get_conn()
        sql = """SELECT * from tools where tool_id = %(tool_id)s"""
        cursor = conn.cursor()
        cursor.execute(sql, {"tool_id":tool_id})
        columns = [column[0] for column in cursor.description]
        impure_results = []
        for row in cursor.fetchall():
            impure_results.append(dict(zip(columns, row)))
        #print impure_results[0]

        #if it is active tool
        active = 0
        sql = """SELECT * from active_tools where tool_id = %(tool_id)s"""
        cursor.execute(sql, {"tool_id":tool_id})
        if cursor.fetchone():
            active = 1
        return render_template('tools_edit.html', tool=impure_results[0], catalog=1, active=active)
    elif request.method == 'POST':
        tool_name = str(request.form["tool_name"])
        authors = str(request.form["authors"])
        team = str(request.form["team"])
        keywords = str(request.form["keywords"])
        maturity = str(request.form["maturity"])
        url = str(request.form["url"])
        wiki = str(request.form["wiki"])
        description = request.form["description"]
        original_name = str(request.form["original_name"])
        emails = str(request.form["emails"])
        tool_id = str(request.form["id"])
        source = str(request.form["source"])

        conn = get_conn()
        cursor = conn.cursor()
        sql="""
        INSERT INTO tools
                    (tool_id, authors,team,tool_name,description,keywords,url,wiki,maturity,emails,source)
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    authors=%s, team=%s,tool_name=%s,description=%s,keywords=%s,url=%s,wiki=%s, maturity=%s,emails=%s,source=%s
                    """

        cursor.execute(sql, (tool_id, authors,team,tool_name,description,keywords,url,wiki,maturity,emails,source, authors,team,tool_name,description,keywords,url,wiki,maturity,emails,source))
        cursor.close()
        conn.commit()
        conn.close()

        logging.warning("user: %s edit tool: %s."%(session['username'], tool_id))
        return Tools_Catalog(0)

@app.route("/Show_Tool_Details")
def Show_Tool_Details():
    para = request.args
    tool_name = para.get('name', '').strip()
    tool_id = int(para.get('id', '').strip())
    conn = get_conn()
    sql = """SELECT * from tools where tool_id = %(tool_id)s"""
    cursor = conn.cursor()
    cursor.execute(sql, {"tool_id": tool_id})
    columns = [column[0] for column in cursor.description]
    impure_results = []
    for row in cursor.fetchall():
        impure_results.append(dict(zip(columns, row)))

    cursor.close()
    conn.commit()
    conn.close()
    return render_template('tools_detail.html', tool=impure_results[0], catalog=1)

@app.route('/Tool_Active_Info_Frag')
def Tool_Active_Info_Frag():
    res = {}
    para = request.args
    tool_id = int(para.get('id', '').strip())
    active_flag = False
    act_pro_info = []
    active_info = check_tool_actvie(tool_id)
    if active_info:
        active_flag = True
        act_pro_info = get_act_pro_info(tool_id)
        for progress in act_pro_info:
            progress['username'] = get_realname(progress['username'])

        for i in range(len(act_pro_info) - 1):
            keys = act_pro_info[i].keys()
            for key in keys:
                if act_pro_info[i][key] != act_pro_info[i+1][key]:
                    #mark the modified item in active_track and highlight it
                    act_pro_info[i][str(key)+'_f'] = 1
                else:
                    act_pro_info[i][str(key)+'_f'] = 0

    res['data'] = render_template('tools_active_info_frag.html',
                            active_flag=active_flag, active_info=active_info,
                            active_progress_info=act_pro_info)
    res['res'] = 'success'
    return jsonify(res)

@app.route('/Tool_Active_Lasr_Query')
def Tool_Active_Lasr_Query():
    res = {}
    para = request.args
    tool_id = int(para.get('id', '').strip())
    conn = get_conn()
    cursor = conn.cursor()
    sql = """SELECT * from active_track
             where tool_id = %(tool_id)s
             ORDER BY id DESC
             LIMIT 1
          """
    cursor.execute(sql, {"tool_id": tool_id})
    columns = [column[0] for column in cursor.description]
    row = cursor.fetchone()
    if row:
        track = dict(zip(columns, row))
        res['data'] = track['date']
        date = datetime.strptime(track['date'],"%Y-%m-%d, %H:%M:%S PST")
        now = datetime.now()
        # if the progress is 100%, don't highlight it
        if ((now - date).days >= 14) and (track['new_progress'] != '100%'):
            res['flag'] = 1
        elif ((now - date).days >= 7) and (track['new_progress'] != '100%'):
            res['flag'] = 2
        else:
            res['flag'] = 0
    else:
        res['data'] = 'N/A'
        res['flag'] = 1

    res['res'] = 'success'
    cursor.close()
    conn.commit()
    conn.close()

    return jsonify(res)


@app.route('/Tool_Like', methods=['GET', 'POST'])
def Tool_Like():
    res = {}
    res['res'] = 'Please login first'
    if not ('logged_in' in session.keys() and session['logged_in']):
        res['res'] = 'Please login first'
    else:
        username = session['username']
        para = request.args
        tool_id = int(para.get('id', '').strip())
        conn = get_conn()
        sql="""
        INSERT INTO likes
                    (username, tool_id)
                    VALUES
                    (%s, %s)
                    """
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (username, tool_id))
            res['res'] = 'success'
        except:
            res['res'] = 'already'
        cursor.close()
        conn.commit()
        conn.close()
    return jsonify(res)

@app.route('/Tool_Unlike', methods=['GET', 'POST'])
def Tool_Unlike():
    if not ('logged_in' in session.keys() and session['logged_in']):
        return 'please login first'
    else:
        try:
            username = session['username']
            para = request.args
            tool_id = int(para.get('id', '').strip())
            conn = get_conn()
            sql="""
                DELETE FROM likes
                WHERE tool_id=%(tool_id)s
                AND
                username = %(username)s
                """
            cursor = conn.cursor()
        except:
            return
        try:
            cursor.execute(sql, {'tool_id':tool_id, 'username':username})
            cursor.close()
            conn.commit()
            conn.close()
        except:
            return "you have already liked it"
        return "success"


@app.route('/Tool_Like_Query', methods=['GET', 'POST'])
def Tool_Like_Query():
    #username = session['username']
    res = {}
    para = request.args
    tool_id = int(para.get('id', '').strip())
    conn = get_conn()
    sql="""
        SELECT COUNT(tool_id)
                from likes
                where
                tool_id = %(tool_id)s
                """
    cursor = conn.cursor()
    cursor.execute(sql, {"tool_id":tool_id})
    columns = [column[0] for column in cursor.description]
    impure_results = []
    for row in cursor.fetchall():
        impure_results.append(dict(zip(columns, row)))
    #print impure_results[0]
    data = impure_results[0]
    res['data'] = str(data['COUNT(tool_id)'])
    if not ('logged_in' in session.keys() and session['logged_in']):
        res['liked'] = 0
    else:
        username = session['username']
        sql = """
            SELECT *
                    from likes
                    where
                    tool_id = %(tool_id)s
                    AND
                    username = %(username)s
            """
        cursor.execute(sql, {"tool_id":tool_id, 'username':username})
        if cursor.fetchall():
            res['liked'] = 1
        else:
            res['liked'] = 0

    res['res'] = 'success'
    cursor.close()
    conn.commit()
    conn.close()

    return jsonify(res)


COMMENT_INNER_TEMPLATE = '''
     <div class='comment'>
     <div class='comment-meta clearfix row'><!---->
     <div class='col-md-1 cpdtools_no_padding_left'>
     <a href="https://vmwaresearch.vmware.com/search?proxystylesheet=vmlinksearch_frontend&getfields=*&site=People&q=%s@vmware.com"><img class='avatar-small' src='/static/images/default_avatar.png'></div></a>
     <div class='col-md-11 cpdtools_no_padding_right'>
     <a><span class='author'>%s</span></a>
     <span class='date' style="float:right;">%s</span>
     <div class='comment-content'>%s</div>
     </div><!--name&content-->
     </div><!--comment-meta-->
     </div><!--comment-->
'''


@app.route('/Tool_Post_Comment', methods=['POST'])
def Tool_Post_Comment():
    res = {}
    res['res'] = 'Please login first'
    if not ('logged_in' in session.keys() and session['logged_in']):
        res['res'] = 'Please login first'
    else:
        username = session['username']
        tool_id = str(request.form["comment_tool_id"])
        utf8 = request.form["utf8"]
        comment = request.form["comment_content"]
        mydate = datetime.now()
        date_str = mydate.strftime("%b %d, %Y")
        realname = get_realname(username)
        conn = get_conn()
        cursor = conn.cursor()
        sql="""
        INSERT INTO comments
                    (username,tool_id,text,date,realname)
                    VALUES
                    (%s, %s, %s, %s, %s)
                    """
        cursor.execute(sql, (username,tool_id,comment,date_str,realname))
        cursor.close()
        conn.commit()
        conn.close()
        res['res'] = 'success'
        res['data'] = {'username':username, 'realname':realname, 'comment':comment, 'date':date_str}
        res['new_div'] = render_template('comment.html', data=res['data'])
        #print res

    return jsonify(res)

@app.route('/Tool_Get_Comments', methods=['GET'])
def Tool_Get_Comments():
    res = {}
    res['new_div'] = ''
    para = request.args
    tool_id = int(para.get('id', '').strip())
    conn = get_conn()
    cursor = conn.cursor()
    sql="""
        Select * from comments
        Where tool_id = %(tool_id)s
        ORDER BY id ASC
        """
    cursor.execute(sql, {'tool_id': tool_id})

    columns = [column[0] for column in cursor.description]
    impure_results = []
    for row in cursor.fetchall():
        impure_results.append(dict(zip(columns, row)))
    cursor.close()
    conn.commit()
    conn.close()

    for comment in impure_results:
        comment['comment'] = comment['text']
        res['new_div'] += render_template('comment.html', data=comment)

    res['res'] = 'success'
    return jsonify(res)

@app.route('/Tool_Activity', methods=['GET'])
def Tool_Activity():
    res = {}
    res['new_div'] = ''
    tool_id = 0
    para = request.args
    paratuple = para.get('activity', '').strip().split("_")
    if len(paratuple) > 1:
        tool_id = int(paratuple[1])
    activity = paratuple[0]
    try:
        update_activity(activity, tool_id)
        res['res'] = 'success'
    except:
        res['res'] = 'internal error'

    return jsonify(res)


def update_activity(activity='', tool_id=0):
    if not ('logged_in' in session.keys() and session['logged_in']):
        username = request.remote_addr
    else:
        username = session['username']
    if not activity:
        activity = str(request)
    mydate = datetime.now()
    date_str = mydate.strftime("%b %d %H:%M:%S, %Y")
    conn = get_conn()
    cursor = conn.cursor()
    sql="""
        INSERT INTO activity
        (username,tool_id,time,activity)
        VALUES
        (%s, %s, %s, %s)
        """
    cursor.execute(sql, (username,tool_id,date_str,activity))
    cursor.close()
    conn.commit()
    conn.close()


def get_conn():
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE, charset='utf8')
    return conn

def get_realname(username):
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db='TriageRobot', charset='utf8')
    cursor = conn.cursor()
    sql="""
        SELECT realname FROM profiles
        Where login_name = %(login_name)s
        """
    cursor.execute(sql, {'login_name':username})
    username = cursor.fetchone()[0]
    cursor.close()
    conn.commit()
    conn.close()
    return username

def record_email_send_info(tool_id, sender, receiver, cc_addrs, reason):

    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d, %H:%M:%S PST")
    sql="""
           INSERT INTO email_track
            (`tool_id`, `send_time`, `sender`, `receiver_addrs`, `cc_addrs`, `send_reason`)
            VALUES
            (%s, %s, %s, %s, %s, %s)
        """
    # the send_reason
    # 1: 6 days not update
    # 2: 7~12 days not upate
    # 3: 13 days not update
    # 4: >=14 days not update
    cursor.execute(sql, (tool_id, now, sender, receiver, cc_addrs, reason))
    cursor.close()
    conn.commit()
    conn.close()
    return 0

def get_tool_attr(g_tool_id, g_tool_attr):
    conn = get_conn()
    sql = """SELECT """ + g_tool_attr
    sql += """ from tools where tool_id = %(g_tool_id)s """
    cursor = conn.cursor()
    cursor.execute(sql, {'g_tool_id': g_tool_id})
    toolname = cursor.fetchone()[0]
    cursor.close()
    conn.commit()
    conn.close()
    return toolname

def get_tools_all_id():
    conn = get_conn()
    sql = """SELECT * from active_tools"""
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    impure_results = []
    for row in cursor.fetchall():
        impure_results.append(dict(zip(columns, row)))
    cursor.close()
    conn.commit()
    conn.close()
    all_id = []
    for data in impure_results:
        all_id.append(data['tool_id'])
    return all_id

def get_stats_on_app_wiki():
    conn = get_conn()
    cursor = conn.cursor()
    sql = """
          SELECT
            SUM(activity= 'app') AS app,
            SUM(activity = 'wiki') AS wiki
          FROM activity
          """
    cursor.execute(sql)
    row = cursor.fetchone()
    #print row

    cursor.close()
    conn.commit()
    conn.close()
    return int(row[0])+1532, int(row[1])+1431

def check_tool_actvie(tool_id, force=False):
    conn = get_conn()
    cursor = conn.cursor()
    sql = """SELECT * from active_tools where tool_id = %(tool_id)s"""
    if not force:
        sql += """ and flag = 1"""
    cursor.execute(sql, {"tool_id":tool_id})

    columns = [column[0] for column in cursor.description]
    row = cursor.fetchone()
    if row:
        res = dict(zip(columns, row))
    else:
        res = ""
    cursor.close()
    conn.commit()
    conn.close()
    #print res
    return res

def get_act_pro_info(tool_id):
    conn = get_conn()
    cursor = conn.cursor()
    sql = """SELECT * from active_track where tool_id = %(tool_id)s
             ORDER BY id DESC"""
    cursor.execute(sql, {"tool_id":tool_id})

    columns = [column[0] for column in cursor.description]
    progress_results = []
    for row in cursor.fetchall():
        progress_results.append(dict(zip(columns, row)))
    cursor.close()
    conn.commit()
    conn.close()
    #for row in progress_results:
    #    for key in row:
    #        if row[key] is None:
    #            row[key] = ''
    #print progress_results
    return progress_results

def edit_tool_details():
    tool_name = str(request.form["tool_name"])
    authors = str(request.form["authors"])
    team = str(request.form["team"])
    keywords = str(request.form["keywords"])
    maturity = str(request.form["maturity"])
    url = str(request.form["url"])
    wiki = str(request.form["wiki"])
    description = request.form["description"]
    original_name = str(request.form["original_name"])
    emails = str(request.form["emails"])
    tool_id = str(request.form["id"])
    source = str(request.form["source"])

    conn = get_conn()
    cursor = conn.cursor()

    sql="""
    INSERT INTO tools
                (tool_id, authors,team,tool_name,description,keywords,url,wiki,maturity,emails,source)
                VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                authors=%s, team=%s,tool_name=%s,description=%s,keywords=%s,url=%s,wiki=%s, maturity=%s,emails=%s,source=%s
                """

    cursor.execute(sql, (tool_id, authors,team,tool_name,description,keywords,url,wiki,maturity,emails,source, authors,team,tool_name,description,keywords,url,wiki,maturity,emails,source))

    sql = """SELECT * from tools where tool_id = %(tool_id)s"""
    cursor.execute(sql, {"tool_id": tool_id})
    columns = [column[0] for column in cursor.description]
    impure_results = []
    for row in cursor.fetchall():
        impure_results.append(dict(zip(columns, row)))

    cursor.close()
    conn.commit()
    conn.close()

    logging.warning("user: %s edit tool: %s."%(session['username'], tool_id))

    return True, impure_results[0], ""

@app.route('/Logout', methods=['GET', 'POST'])
def Logout():
    """
    This function helps user to log out.
    All the session will be left
    """

    try:
        logging.warning("{} logout successfully.".format(session['username']))
    except:
        pass
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('admin', None)
    return Tools_Catalog(0)


def send_email(from_addr, to_addrs, cc_addrs, subject, body):
    # to_addrs and  cc_addrs must be email_address list
    SMTP_SERVER='smtp.vmware.com'
    import smtplib
    from email.mime.text import MIMEText
    msg_subject = subject
    msg_body = body
    msg = MIMEText(msg_body)
    msg['Subject'] = msg_subject
    msg['From'] = from_addr
    msg['To'] = ', '.join(to_addrs)
    print msg['To']
    if cc_addrs:
        msg['Cc'] = ', '.join(cc_addrs)
        receivers = to_addrs + cc_addrs
    else:
        receivers = to_addrs
    try:
        server = smtplib.SMTP(SMTP_SERVER)
        server.sendmail(from_addr, receivers, msg.as_string())
        server.quit()
    except SMTPException:
        print "Unable send email with SMTP"
    return 0


@app.route('/test_error')
def test_error():
    print dir(session)
    print session.keys()
    error['1'] = 1
    return "index"

@app.errorhandler(500)
def internal_error(error):
    try:
        from_addr = session["username"] + "@vmware.com"
    except:
        from_addr = FROM_ADDR
    to_addr = ["xiangw@vmware.com"]
    subject = """[CPD Tools Problem Report] {}""".format(datetime.now().strftime(FMT_YMDHMS))
    message = traceback.format_exc()
    message += '\n\n'+str(request)+'\n\n'
    send_email(from_addr, to_addr, [], subject, message) # no CC_addrs
    return render_template('error.html', error="OOPS! There is an internal error occured, a report has been filed.")

def initialize_logger(output_dir):
    """
    This function helps to trigger logger
    In order to log too much garbage message in flask, the message level is lifted into warning
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to info
    handler = logging.StreamHandler()
    #handler.setLevel(logging.INFO)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # create debug file handler and set level to debug
    handler = logging.FileHandler(os.path.join(output_dir, "query_and_logging.log"),"a")
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(levelname)s - %(asctime)s - %(process)d - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    """
    https://docs.python.org/2/howto/logging-cookbook.html
    """

initialize_logger(os.path.join(SCRIPTS_DIR,'log'))

if __name__ == '__main__':
    #logging.basicConfig(filename='query_and_logging.log',level=logging.DEBUG,format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    #logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    initialize_logger(os.getcwd())
    logging.warning("Python Server is Initiated")
    #if not app.run(host='triagerobot.eng.vmware.com', debug=True):
    try:
        if not app.run(host="0.0.0.0", debug=True):
            logging.warning("Python Server is Terminated")
    except:
        import traceback
        traceback.print_exc()
