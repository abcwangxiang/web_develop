# bzutils -- Python module to interact with bugzilla servers.
# Copyright (C) 2007  Gustavo R. Montesino
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import cookielib
import csv
import urllib
import urllib2
import re
from BeautifulSoup import BeautifulSoup

import bchart
from bug import Bug
from exceptions import *

class CGI:
    """Access bugzilla servers through cgi/parsing"""

    def __init__(self, baseurl, username="shinyeht", password="VMware123"):
        
        self.baseurl = baseurl.rstrip("/")
        self.usearname = username
        self.password = password

        # Bugzilla's cookies setup
        self.cookies = cookielib.CookieJar()
        self.urlopener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookies))
        
        # bugs.kde.org doesn't work wihtout user-agent set...
        self.urlopener.addheaders = [("User-agent", "bzutils")]
        return
        # Set columns to return on query
        columndata = "column_bug_severity=on"
        columndata = columndata + "&column_severity=on"  # KDE equivalent to bug_severity
        columndata = columndata + "&column_priority=on"
        columndata = columndata + "&column_assigned_to=on"
        columndata = columndata + "&column_owner=on" # KDE equivalent to assigned_to
        columndata = columndata + "&column_reporter=on"
        columndata = columndata + "&column_bug_status=on"
        columndata = columndata + "&column_status=on" # KDE equivalent of bug_status
        columndata = columndata + "&column_resolution=on"
        columndata = columndata + "&column_product=on"
        columndata = columndata + "&column_component=on"
        columndata = columndata + "&column_version=on"
        columndata = columndata + "&column_short_desc=on"
        columndata = columndata + "&column_summaryfull=on" # KDE equivalent of short_desc

        url = "%s/colchange.cgi?rememberedquery=&%s" % (self.baseurl, columndata)
        print url
        self.urlopener.open(url)

        # Get valid values for some fields in this server
        f = self.urlopener.open("%s/query.cgi?format=advanced" % self.baseurl)
        soup = BeautifulSoup(f.read())

        # Products, components and versions
        for script in soup.findAll("script"):
            if unicode(script).find("cpts[0]") != -1:
                buffer = unicode(script)
                break

        self.products = []
        products = soup.find("select", attrs = { "name": "product" })
        i = 0

        for product in products.findAll("option"):
            self.products.append((product.string, [], []))

            """The following string sanitizations should probably be offloaded to
            another function"""
            matches = re.findall("cpts\[%d\].=.\[(.*)\];" % i, buffer)
            for component in matches[0].split(','):
                self.products[i][1].append(component.strip("' ").replace("\\", ""))

            matches = re.findall("vers\[%d\].=.\[(.*)\];" % i, buffer)
            for version in matches[0].split(','):
                self.products[i][2].append(version.strip("' ").replace("\\", ""))

            i = i + 1
    
    def get_products(self):
        """Return a list of the valid products in this bugzilla server"""

        list = []
        for product in self.products:
            list.append(product[0])
        return list

    def get_components(self, query_product):
        """Return a list of the valid components for a given product"""

        for product in self.products:
            if product[0] == query_product:
                return product[1]
    
    def get_versions(self, query_product):
        """Return a list of the valid versions for a given product"""

        for product in self.products:
            if product[0] == query_product:
                return product[2]

    def parse(self, handle):
        """Parses a bugzilla bug list generated by bugzilla.cgi

        Checks to see what kind of page was returned (ie, csv, html, etc)
        and calls the right function to handle it, returning a list
        of bugs if we can parse it or throwin an exception otherwise."""

        type = handle.info()["Content-Type"]

        if "text/plain" in type or "text/csv" in type:
            return self.parse_csv(handle)
        elif "text/html" in type:
            return self.parse_html(handle)
        else:
            raise BugListParseError, "Couldn't parse bug list: unknown format"

    def parse_csv(self, file):
        """Parses a bugzilla-generated csv file

        This function gets a bugzilla-generated csv file and returns a list
        of bug objects."""

        data = csv.reader(file)
        data.next() # skips the header

        bugs = []

        for report in data: 
            bug = Bug(report[0], self)
            bug.set_severity(report[1])
            bug.set_priority(report[2])
            bug.set_assignee(report[3])
            bug.set_reporter(report[4])
            bug.set_status(report[5])
            bug.set_resolution(report[6])
            bug.set_product(report[7])
            bug.set_component(report[8])
            bug.set_version(report[9])
            bug.set_summary(report[10])
            bug.set_url("%s/show_bug.cgi?id=%s" % (self.baseurl, bug.get_id()))
            bugs.append(bug)

        return bugs

    def parse_html(self, handle):
        """Parses a bugzila-generated html file

        This functions gets a bugzilla-generated html file and returns
        a list of bug objects"""

        soup = BeautifulSoup(handle.read())
        bugs = []

        rows = soup.find("table", attrs = { "class" : "bz_buglist" })
        if not rows:
            # no bugs?
            if soup.find(text = lambda(str): str.find("Zarro") == 0):
                return bugs
            else:
                raise BugListParseError, "Couldn't find the bugs table"
        rows = rows.findAll("tr")[1:]

        for row in rows:
            cells = row.findAll("td")
            
            bug = Bug(cells[0].a.string, self)

            # Bug severity 
            if cells[1].string != None:
                severity = cells[1].string.strip()
            elif cells[1].nobr.string != None: # KDE's bugzilla
                severity = cells[1].nobr.string.strip()
            else:
                raise BugListParseError, "Couldn't get bug severity"

            if severity == "blo":
                bug.set_severity("blocker")
            elif severity == "cri":
                bug.set_severity("critical")
            elif severity == "maj":
                bug.set_severity("major")
            elif severity == "nor":
                bug.set_severity("normal")
            elif severity == "min":
                bug.set_severity("minor")
            elif severity == "tri":
                bug.set_severity("trivial")
            elif severity == "enh":
                bug.set_severity("enhancement")
            elif severity == "gra":  # KDE's bugzilla
                bug.set_severity("grave")
            elif severity == "cra":  # KDE's bugzilla
                bug.set_severity("crash")
            elif severity == "wis":
                bug.set_severity("wishlist")
            else:
                bug.set_severity(severity) 
            
            # Bug priority
            if cells[2].string:
                bug.set_priority(cells[2].string.strip())
            elif cells[2].nobr.string: # KDE's bugzilla
                bug.set_priority(cells[2].nobr.string.strip())
            else:
                raise BugListParseError, "Couldn't get bug priority"

            # Bug owner
            if cells[3].string:
                bug.set_assignee(cells[3].string.strip())
            elif cells[3].nobr.string: # KDE's bugzilla
                bug.set_assignee(cells[3].nobr.string.strip())
            else:
                raise BugListParseError, "Couldn't get bug owner"

            # Bug reporter
            if cells[4].string:
                bug.set_reporter(cells[4].string.strip())
            elif cells[4].nobr.string: # KDE's bugzilla
                bug.set_reporter(cells[4].nobr.string.strip())
            else:
                raise BugListParseError, "Couldn't get bug reporter"

            # Bug status
            if cells[5].string:
                status = cells[5].string.strip()
            elif cells[5].nobr.string: # KDE's bugzilla
                status = cells[5].nobr.string.strip()
            else:
                raise BugListParseError, "Couldn't get bug status"

            if status == "UNCO":
                bug.set_status("UNCONFIRMED")
            elif status == "ASSI":
                bug.set_status = ("ASSIGNED")
            elif status == "REOP":
                bug.set_status = ("REOPENED")
            elif status == "RESO":
                bug.set_status("RESOLVED")
            elif status == "VERI":
                bug.set_status("VERIFIED")
            elif status == "CLOS":
                bug.set_status("CLOSED")
            elif status == "NEED": # Gnome's Bugzilla
                bug.set_status("NEEDINFO")
            else:
                bug.set_status(status)
    
            # Bug resolution
            if cells[6].string:
                resolution = cells[6].string.strip()
            elif cells[6].nobr.string: # KDE's bugzilla
                resolution = cells[6].nobr.string.strip()
            else:
                if bug.get_status() in ["RESOLVED", "VERIFIED", "CLOSED"]:
                    raise BugListParseError, "Couldn't get bug resolution"
                else:
                    resolution = ""

            if resolution == "FIXE":
                bug.set_resolution("FIXED")
            elif resolution == "INVA":
                bug.set_resolution("INVALID")
            elif resolution == "WONT":
                bug.set_resolution("WONTFIX")
            elif resolution == "LATE":
                bug.set_resolution("LATER")
            elif resolution == "REMI":
                bug.set_resolution("REMIND")
            elif resolution == "DUPL":
                bug.set_resolution("DUPLICATE")
            elif resolution == "WORK":
                bug.set_resolution("WORKSFORME")
            elif resolution == "MOVE":
                bug.set_resolution("MOVED")
            elif resolution == "NOTA":  # Gnome's Bugzilla
                bug.set_resolution("NOTABUG")
            elif resolution == "NOTG":  # Gnome's Bugzilla
                bug.set_resolution("NOTGNOME")
            elif resolution == "INCO":  # Gnome's Bugzilla
                bug.set_resolution("INCOMPLETE")
            elif resolution == "GNOM":  # Gnome's Bugzilla
                bug.set_resolution("GNOME1.X")
            elif resolution == "OBSO":  # Gnome's Bugzilla
                bug.set_resolution("OBSOLETE")
            elif resolution == "NOTX":  # Gnome's Bugzilla
                bug.set_resolution("NOTXIMIAN")
            else:
                bug.set_resolution(resolution)

            # Bug product
            if cells[7].string:
                bug.set_product(cells[7].string.strip())
            elif cells[7].nobr.string: # KDE's bugzilla
                bug.set_product(cells[7].nobr.string.strip())
            else:
                raise BugListParseError, "Couldn't get bug product"

            # Bug component
            if cells[8].string:
                bug.set_component(cells[8].string.strip())
            elif cells[8].nobr.string: # KDE's bugzilla
                bug.set_component(cells[8].nobr.string.strip())
            else:
                raise BugListParseError, "Couldn't get bug component"

            # Bug version
            if cells[9].string:
                bug.set_version(cells[9].string.strip())
            elif cells[9].nobr.string: # KDE's bugzilla
                bug.set_version(cells[9].nobr.string.strip())
            else:
                raise BugListParseError, "Couldn't get bug version"

            # Bug summary
            if cells[10].string:
                bug.set_summary(cells[10].string.strip())
            elif cells[10].nobr.string: # KDE's bugzilla
                bug.set_summary(cells[10].nobr.string.strip())
            else:
                raise BugListParseError, "Couldn't get bug summary"

            # Bug URL
            bug.set_url("%s/show_bug.cgi?id=%s" % (self.baseurl, bug.get_id()))

            bugs.append(bug)

        return bugs

    def query_boogle(self, querystr):
        """Query the bugzilla server using gnome's bugzilla boogle"""

        url = "%s/buglist.cgi?query=%s&ctype=csv" % (self.baseurl.rstrip("/"), querystr)
        f = self.urlopener.open(url)

        return self.parse(f)

    def query_bchart(self, charts=None, str=None):
        """Query the bugzilla server through boolean charts

        This function queries bugzilla through boolean charts.
        The boolean charts to use must be passed as a chart
        list or as a string representation, see the functions
        to_url and str_to_charts on bchart.py for the syntax.
        
        This function will return a list of bugs which match the
        conditions of all charts."""

        if str:
            charts = bchart.str_to_chart(str)

        url = self.baseurl.rstrip("/") + "/buglist.cgi?query_format=advanced&ctype=csv"
        url = url + "&" + urllib.urlencode(bchart.to_url(charts))

        f = self.urlopener.open(url)
        return self.parse(f)

# vim: tabstop=4 expandtab shiftwidth=4
