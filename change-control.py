#!/usr/bin/env python
"""Use the RT REST API to retrieve contemporary change-control tickets.
Refer: http://wiki.bestpractical.com/view/REST
"""

import sys
import getpass
import textwrap
import urllib
import urllib2
from datetime import date
from optparse import OptionParser
from string import Template
from smtplib import SMTP

__author__	= "Max Parmer"
__email__	= "maxp@pdx.edu"

RT_BASE		= 'https://support.oit.pdx.edu'
RT_API		= RT_BASE + '/REST/1.0'
RT_SEARCH	= RT_API + '/search/ticket?%s'
RT_SHOW		= RT_API + '/%s/show'
#RT_INDENT is the signifier of a multiline field in (l)ong format
RT_INDENT	= "    "
DEFAULT_QUERY	= "Created < 'Today 15:00:00' AND Starts > 'Today 15:00:00' AND Queue='change-control' AND (Status = 'new' OR Status = 'open')"
DEFAULT_DOMAIN	= "pdx.edu"
FROM_ADDR	= "change-control-owner@lists.pdx.edu"

def session(username, password, rt_base=RT_BASE):
	"""Get an auth token for this session.

	username: rt username
	
	password: rt password

	rt_base: rt base url, i.e. https://rt.example.com
	"""
	auth = urllib2.build_opener(urllib2.HTTPCookieProcessor())
	urllib2.install_opener(auth)
	credentials	= urllib.urlencode({'user': username, 'pass': password})
	try:
		session	= auth.open(rt_base, credentials)
		auth.close()
		return session
	except urllib2.URLError:
		print "Failed to contact RT."
		exit()

def fetch(url):
	try:
		responder	= urllib2.urlopen(url)
		response	= responder.read()
		responder.close()
		return trim_header(response)
	except urllib2.URLError:
		sys.exit("Failed to contact RT while fetching %s" % url)

def search(query, orderby, format="i"):
	"""Build an RT query string.

	query:	your RT style pseudo-SQL query

	orderby: Any RT key. Can be prefixed with + or -, i.e. -Created
		 would list tickets in descending order by creation.
	format:	i: ticket/<ticket-id> (good for further queries)
		s: <ticket-id>: <ticket-subject>
		l: all ticket attributes
	"""
	query = urllib.urlencode({	'query':	query,
					'orderby':	orderby,
					'format':	format,
				})
	return fetch(RT_SEARCH % query)

def show(ticket):
	"""Perform a query to retrieve the full details of a ticket.

	ticket: A reference to an RT ticket, i.e.: ticket/1234567
	"""
	return fetch(RT_SHOW % ticket)

def trim_header(response):
	"""Remove the RT response header, which is a statusline and newline."""
	response = response.splitlines()
	return response[2:]

def row_split(row):
	"""Split rows into fields"""
	row = row.partition(":")
	if "CF-" in row[0]: #strip CF- marker since it complicates templating
		return row[0][3::], row[2].strip()
	else:
		return row[0], row[2].strip()

def ticket_to_dict(ticket):
	"""Parse a ticket and it's fields to a dict for later fun."""
	ticket_dict = dict()
	for index, row in enumerate(ticket):
		if row is RT_INDENT: pass
		elif row is "": pass
		elif RT_INDENT in row:
			#append to the last named field
			key, value = row_split(ticket[last_known_field])
			ticket_dict[key] = ticket_dict[key] + " " + row.strip()
		else:
			#strip ticket/ to present this in the historical way
			if "id" in row: row = row.replace("ticket/", "")
			#wrap and store in dict
			key, value = row_split(row)
			ticket_dict[key] = textwrap.fill(value)
			last_known_field = index
		
	return ticket_dict

def template(object, template='change-control.txt'):
	file = open("templates/"+template, "r")
	template = file.read()
	file.close()
	template = Template(template)
	return template.substitute(object)

def make_mail(query, orderby="+Starts"):
	mail = str()	
	for ticket in search(query, orderby):
		ticket = ticket_to_dict(show(ticket))
		mail += template(ticket)
	mail = template({'changes': mail, 
			 'date': date.today()}, 'change-control-preamble.txt')
	return mail

def send_mail(from_addr, toaddr, content, server='mailhost.pdx.edu'):
	server = SMTP(server)
	server.sendmail(from_addr, toaddr, content)
	server.quit()
	return content

def main():
	usage = "usage: %prog [options]"
	parser = OptionParser(usage=usage)
	parser.add_option("-u", dest="user", default=getpass.getuser(), help="RT username, defaults to current user: %default")
	parser.add_option("-t", dest="to_addr", default=False, help="Email address to send mail to, default: print to stdout.")
	parser.add_option("-f", dest="from_addr", default=FROM_ADDR, help="Mail origin, default: %default.")
	parser.add_option("-s", action="store_false", dest="echo", default=True, help="Silence output.")
	parser.add_option("-q", action="store", type="string", dest="query",
			  default=DEFAULT_QUERY, help="An alternative query. Default: '%default'")
	
	(options, args) = parser.parse_args()
	
	#print these first 'cause make_mail() is going to take a minute
	if options.echo:
		print options.query
	if options.echo and options.to_addr:
		print "Sending mail to:", options.to_addr
	
	#get password and open a session	
	password = getpass.getpass("Password for %s on %s: " % (options.user, RT_BASE))
	session(options.user, password)
	
	#generate the message
	mail = make_mail(options.query)
	
	if options.echo:
		print mail
	if options.to_addr:	
		send_mail(options.from_addr, options.to_addr, mail)

if __name__ == "__main__":
		main()
