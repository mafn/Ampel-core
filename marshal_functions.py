#!/usr/local/bin/python
from __future__ import print_function

import urllib, urllib2,base64,pickle
from bs4 import BeautifulSoup
import re, os, datetime, json

marshal_root = 'http://skipper.caltech.edu:8080/cgi-bin/growth/'
listprog_url = marshal_root + 'list_programs.cgi'
scanning_url = marshal_root + 'growth_treasures_transient.cgi'
saving_url = marshal_root + 'save_cand_growth.cgi?candid=%s&program=%s'
rawsaved_url = marshal_root + 'list_sources_bare.cgi'
annotate_url = marshal_root + 'edit_comment.cgi'

class PTFConfig(object) :
	def __init__(self) :
		import ConfigParser
		self.fname = os.path.expanduser('~/.ptfconfig.cfg')
		self.config = ConfigParser.SafeConfigParser()
		self.config.read(self.fname)
	def get(self,*args,**kwargs) :
		return self.config.get(*args,**kwargs)

def get_marshal_html(weblink):
	request = urllib2.Request(weblink)
	conf = PTFConfig()
	base64string = base64.encodestring('%s:%s' % (conf.get('Marshal', 'user'), conf.get('Marshal', 'passw'))).replace('\n', '')
	request.add_header("Authorization", "Basic %s" % base64string)
	return urllib2.urlopen(request).read()

def soup_obj(url):
	return BeautifulSoup(get_marshal_html(url), 'lxml')

def save_source(candid, progid):
	return BeautifulSoup(get_marshal_html(saving_url %(candid, progid)), 'lxml') 

today = datetime.datetime.now().strftime('%Y-%m-%d')

class Sergeant(object):
	
	def __init__(self, program_name='Nuclear Transients',start_date=today, end_date=today) :
		
		self.start_date = start_date
		self.end_date = end_date
		self.program_name = program_name
		self.cutprogramidx = None

		soup = soup_obj(listprog_url)

		for x in json.loads(soup.find('p').text.encode("ascii")):
			if x['name'] == self.program_name:
				self.cutprogramidx = x['programidx']
		
		if self.cutprogramidx is None:
			print ('ERROR, program_name={0} not found'.format(self.program_name))
			print ('Options for this user are:', self.program_options)
			return None
	
	def list_scan_sources(self, hardlimit=200):
		if self.cutprogramidx is None:
			print('ERROR, first fix program_name upon init')
			return []
	   	self.scan_soup = soup_obj(scanning_url + "?cutprogramidx=%s&startdate=%s&enddate=%s&HARDLIMIT=%s" %(self.cutprogramidx, self.start_date, self.end_date, hardlimit))

		
	   	table = self.scan_soup.findAll('table')
	   	table_rows = table[1].findAll('tr')[1:]
	   	
	   	# this fails if no sources are present on the scanning page...

	   	# for x in self.table_rows[0].findAll('td')[5].findAll('select')[0].findAll('option'):
		  	# if self.program_name in x.text:
			 	# self.program = x["value"]

		sources = []
		for source in table_rows:
			sources.append({})
			sources[-1]["candid"] = source.findAll('td')[5].findAll('input', {"name":'candid'})[0]["value"]
			for x in source.findAll('td')[5].findAll('b'):
				if x.text.strip() == 'ID:':
					sources[-1]["name"] = x.next_sibling.strip()
				elif x.text.strip() == 'Coordinate:':
					sources[-1]["ra"], sources[-1]["dec"] = x.next_sibling.split()
		
			for tag in table_rows[0].findAll('td')[-1].findAll('b'):
				key = tag.text.replace(u'\xa0', u'')
				sources[-1][key.strip(':')] = tag.next_sibling.strip()
		return sources

	def list_saved_sources(self):
		if self.cutprogramidx is None:
			print('ERROR, first fix program_name upon init')
			return []
		self.saved_soup = soup_obj(rawsaved_url + "?cutprogramidx=%s" %(self.cutprogramidx))
		
		#print ('saved soup:',self.saved_soup)

		table = self.saved_soup.findAll('table')
		table_rows = table[1].findAll('tr')[1:]
		sources = []

		for tr in table_rows:
			if len(tr.findAll('td'))>6:
				name_lc = tr.findAll('td')[6].findAll('a')[0] # contain name and light curve
				name = name_lc.decode().split('name=')[1][0:12] # perhaps there's a better way
				comments = table_rows[1].findAll('td') # this contains some comments, but only the automated ones
				#print (name)
				sources.append(name) # today, make dict, with light curve data and current annotations

		#for sl in str(self.saved_soup.contents[1]).split('plot_lc.cgi?name='):
		return sources


def annotate(comment,sourcename, comment_type="info"):
	soup = soup_obj(marshal_root + 'view_source.cgi?name=%s' %sourcename)
	cmd = {}
	for x in soup.find('form', {'action':"edit_comment.cgi"}).findAll('input'):
		if x["type"] == "hidden":
			cmd[x['name']] =x['value']
	cmd["comment"] = comment
	cmd["type"] = comment_type
	params = urllib.urlencode(cmd)
	return soup_obj(marshal_root + 'edit_comment.cgi?%s' %s)

# testing
def testing():
	progn = 'ZTF Science Validation'
	progn = 'Nuclear Transients'
	inst = Sergeant(progn, start_date = '2018-04-03', end_date = '2018-04-03')
	print (inst.cutprogramidx)

	scan_sources = inst.list_scan_sources()
	saved_sources = inst.list_saved_sources()
	print (saved_sources)
	print (len(saved_sources)) # this is always hundred so it doesn't quite work yet 

