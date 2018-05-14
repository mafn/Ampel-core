#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/pipeline/t0/AlertProcessor.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 10.10.2017
# Last Modified Date: 12.05.2018
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

import pymongo, time, numpy as np

from ampel.pipeline.t0.AmpelAlert import AmpelAlert
from ampel.pipeline.t0.alerts.AlertSupplier import AlertSupplier
from ampel.pipeline.t0.alerts.ZIAlertShaper import ZIAlertShaper
from ampel.pipeline.t0.ingesters.ZIAlertIngester import ZIAlertIngester
from ampel.pipeline.logging.LoggingUtils import LoggingUtils
from ampel.pipeline.logging.DBJobReporter import DBJobReporter
from ampel.pipeline.logging.DBLoggingHandler import DBLoggingHandler
from ampel.pipeline.logging.InitLogBuffer import InitLogBuffer
from ampel.pipeline.db.DBWired import DBWired
from ampel.pipeline.db.MongoStats import MongoStats
from ampel.pipeline.db.GraphiteFeeder import GraphiteFeeder
from ampel.pipeline.config.ChannelLoader import ChannelLoader

from ampel.flags.AlDocTypes import AlDocTypes
from ampel.flags.AlertFlags import AlertFlags
from ampel.flags.LogRecordFlags import LogRecordFlags
from ampel.flags.JobFlags import JobFlags


class AlertProcessor(DBWired):
	""" 
	Class handling T0 pipeline operations.

	For each alert, following tasks are performed:
		* Load the alert
		* Filter alert based on the configured filter
		* Set policies
		* Ingest alert based on the configured ingester
	"""
	version = 0.5
	iter_max = 5000

	def __init__(
		self, channels=None, source="ZTFIPAC", db_host='localhost', config_db=None, 
		base_dbs=None, stats={'graphite', 'jobs'}, load_ingester=True
	):
		"""
		Parameters:
		'source': name of input stream (string - see set_stream() docstring)
		'db_host': dns name or ip address (plus optinal port) of the server hosting mongod
		'channels': 
			- None: all the available channels in the config database will be loaded
			- String: channel with the provided id will be loaded
			- List of strings: channels with the provided ids will be loaded 
		'config_db': see ampel.pipeline.db.DBWired.plug_config_db() docstring
		'base_dbs': see ampel.pipeline.db.DBWired.plug_base_dbs() docstring
		'stats': record performance stats in the database:
				* jobs: include t0 metrics in job document
				* graphite: send db metrics and t0 metrics to graphite 
				  (graphite server must be defined in Ampel_config)
		"""

		# Setup logger
		self.logger = LoggingUtils.get_logger(unique=True)
		self.ilb = InitLogBuffer()
		self.logger.addHandler(self.ilb)
		self.logger.info("Setting up new AlertProcessor instance")

		# Setup instance variable referencing ampel databases
		self.plug_databases(self.logger, db_host, config_db, base_dbs)

		# Load channels
		cl = ChannelLoader(self.config_db, source=source, tier=0)
		self.channels = cl.load_channels(channels, self.logger);
		self.chan_enum = list(enumerate(self.channels))

		# Setup source dependant parameters
		self.set_source(source, load_ingester=load_ingester)

		# Which stats to publish (see doctring)
		self.publish_stats = stats

		self.logger.info("AlertProcessor initial setup completed")


	def get_channels(self):
		return self.channels


	def set_source(self, source, load_ingester=True):
		"""
		Depending on which instrument and institution the alerts originate,
		(as of March 2018 only ZTF & IPAC), this method performs the following:
		-> defines the alert loading function.
		-> sets required static settings in AmpelAlert
		-> instantiates the adequate ingester class
		"""

		if source == "ZTFIPAC":

			# TODO: log something ? 

			# Reference to function shaping alert dicts
			self.alert_shaper = ZIAlertShaper(self.logger)

			# Set static AmpelAlert alert flags
			AmpelAlert.add_class_flags(
				AlertFlags.INST_ZTF | AlertFlags.SRC_IPAC
			)

			# Set static AmpelAlert dict keywords
			AmpelAlert.set_alert_keywords(
				self.global_config['photoPoints']['ZTFIPAC']['dictKeywords']
			)
	
			# Instantiate ingester
			ingest_conf = self.global_config['alertIngestion']['source']['ZTFIPAC']

			if load_ingester:
				self.ingester = ZIAlertIngester(
					self.channels, self.config_db['t2_units'], self.get_tran_col(),
					check_reprocessing = ingest_conf['checkReprocessing'],
					alert_history_length = ingest_conf['alertHistoryLength'],
					logger = self.logger
				)
	
		else:
			# more streams may be defined later
			raise ValueError("Source '%s' not supported yet" % source)


	def set_ingester_instance(self, ingester_instance):
		"""
		Sets custom ingester instance to be used in the method run().
		If unspecified, a new instance of ZIAlertIngester() is used
		Known ingester (as for Sept 2017) are:
			* t0.ingesters.MemoryIngester
			* t0.ingesters.ZIAlertIngester
		"""
		self.ingester = ingester_instance


	def process_alert_folder(
		self, base_dir="/Users/hu/Documents/ZTF/Ampel/alerts/", 
		extension="*.avro", max_entries=None, console_logging=True
	):
		"""
		Process alerts in a given directory (using ampel.pipeline.t0.AlertFileList)

		Parameters:
		base_dir: input directory where alerts are stored
		extension: extension of alert files (default: *.avro. Alternative: *.json)
		max_entries: limit number of files loaded 
		  max_entries=5 -> only the first 5 alerts will be processed
		
		alert files are sorted by date: sorted(..., key=os.path.getmtime)
		"""

		from ampel.pipeline.t0.alerts.DirAlertLoader import DirAlertLoader

		# Container class allowing to conveniently iterate over local avro files 
		alert_loader = DirAlertLoader(self.logger)
		alert_loader.set_folder(base_dir)
		alert_loader.set_extension(extension)

		if max_entries is not None:
			alert_loader.set_max_entries(max_entries)
		
		self.logger.info("Returning iterable for file paths in folder: %s" % base_dir)

		als = AlertSupplier(alert_loader, self.alert_shaper, serialization="avro")
		ret = AlertProcessor.iter_max
		count = 0

		while ret == AlertProcessor.iter_max:
			ret = self.run(als, console_logging)
			count += ret

		return count


	def run(self, alert_supplier, console_logging=True):
		"""
		For each alert:
			* Load the alert
			* Filter alert and set policies for every configured channels (defined by load_config())
			* Ingest alert based on PipelineIngester (default) 
			or the ingester instance set by the method set_ingester(obj)
		"""

		# Save current time to later evaluate how low was the pipeline processing time
		time_now = time.time
		start_time = time_now()


		# Part 1: Setup logging 
		#######################

		self.logger.info("Executing run method")

		if getattr(self, "ingester", None) is None:
			raise ValueError("No ingester instance was loaded")

		if not console_logging:
			self.logger.propagate = False

		# Remove logger saving "log headers" before job(s) 
		self.logger.removeHandler(self.ilb)

		# Create JobReporter instance
		db_job_reporter = DBJobReporter(
			self.get_job_col(), JobFlags.T0
		)

		# Create new "job" document in the DB
		db_job_reporter.insert_new(
			params = {
				"alertProc": str(self.version),
				"ingesterClass": str(self.ingester.__class__)
			},
			tier = 0
		)
	
		# Create DB logging handler instance (logging.Handler child class)
		# This class formats, saves and pushes log records into the DB
		db_logging_handler = DBLoggingHandler(
			db_job_reporter, 
			previous_logs=self.ilb.get_logs()
		)

		# Add db logging handler to the logger stack of handlers 
		self.logger.addHandler(db_logging_handler)




		# Part 2: divers
		################

		# Create array
		scheduled_t2_units = len(self.channels) * [None]
		filter_tran_counter = len(self.channels) * [0]

		# Save ampel 'state' and get list of tran ids required for autocomplete
		tran_ids_before = self.get_tran_ids()

		# Forward jobId to ingester instance 
		# (will be inserted in the transient documents)
		self.ingester.set_job_id(
			db_job_reporter.get_job_id()
		)

		# Loop variables
		iter_max = AlertProcessor.iter_max
		iter_count = 0

		# metrics dict
		loop_stats = {}

		# stat with variable length
		for key in ('ingestTime', 'dbBulkTime', 'dbOpTime'):
			loop_stats[key] = []

		# stat with fixed length
		for i, channel in self.chan_enum: 
			# loop_stats[channel.name] records filter performances
			# nan will remain only if exception occur for particular alerts
			loop_stats[channel.name] = np.empty(iter_max) * np.nan

		# The (standard) ingester will update DB insert operations
		self.ingester.set_stats_dict(loop_stats)

		# Publish general stats to graphite
		if "graphite" in self.publish_stats:
			self.gather_and_send_stats(tran_ids_before)

		# python micro-optimization
		loginfo = self.logger.info
		logdebug = self.logger.debug
		dblh_set_tranId = db_logging_handler.set_tranId
		dblh_set_channel = db_logging_handler.set_channels
		dblh_unset_tranId = db_logging_handler.unset_tranId
		dblh_unset_channel = db_logging_handler.unset_channels
		ingest = self.ingester.ingest
		chan_enum = self.chan_enum
		add_ingest_stat = loop_stats['ingestTime'].append
		tran_col = self.get_tran_col()



		# Part 3: Process alerts
		########################

		self.logger.info("#######     Processing alerts     #######")

		# Iterate over alerts
		for parsed_alert in alert_supplier.get_alerts():

			if iter_count == iter_max:
				self.logger.info("Reached max number of iterations")
				break

			# Associate upcoming log entries with the current transient id
			tran_id = parsed_alert['tran_id']
			dblh_set_tranId(tran_id)

			# Feedback
			loginfo("Processing alert: %s" % parsed_alert['alert_id'])

			# Create AmpelAlert instance
			ampel_alert = AmpelAlert(
				tran_id, parsed_alert['ro_pps'], parsed_alert['ro_uls']
			)

			# Loop through initialized channels
			for i, channel in chan_enum:

				# Associate upcoming log entries with the current channel
				dblh_set_channel(channel.name)

				try:

					start = time_now()
					# Apply filter (returns None in case of rejection or t2 runnable ids in case of match)
					scheduled_t2_units[i] = channel.filter_func(ampel_alert)
					loop_stats[channel.name][iter_count] = time_now() - start

					# Log feedback and count
					if scheduled_t2_units[i] is not None:
						filter_tran_counter[i] += 1
						loginfo(channel.log_accepted)
					else:
						# Autocomplete required for this channel
						if tran_ids_before[i] is not None and tran_id in tran_ids_before[i]:
							loginfo(channel.log_auto_complete)
							scheduled_t2_units[i] = channel.t2_units
						else:
							loginfo(channel.log_rejected)

				except:

					self.report_exception(
						{
							'section': 'filter',
							'channel': channel.name,
							'tranId': tran_id,
							'jobId':  db_job_reporter.get_job_id(),
						},
						parsed_alert = parsed_alert
					)

				# Unset channel id <-> log entries association
				dblh_unset_channel()

			if any(scheduled_t2_units):

				# Ingest alert
				loginfo(" -> Ingesting alert")

				start = time_now()

				# TODO: build tran_id <-> alert_id map (replayibility)
				#processed_alert[tran_id]

				# Ingest alert content

				try: 
					ingest(
						tran_id, parsed_alert['pps'], parsed_alert['uls'], scheduled_t2_units
					)
				except:
					self.report_exception(
						{
							'section': 'ingest',
							'tranId': tran_id,
							'jobId':  db_job_reporter.get_job_id(),
						},
						parsed_alert = parsed_alert
					)

				# Save stats
				add_ingest_stat(time_now() - start)

				# Unset log entries association with transient id
				dblh_unset_tranId()

			iter_count += 1

		# Post run section
		try: 

			# Save ampel 'state' and get list of tran ids required for autocomplete
			tran_ids_after = self.get_tran_ids()
	
			# Check post auto-complete
			for i, channel in chan_enum:
				if type(tran_ids_after[i]) is set:
					auto_complete_diff = tran_ids_after[i] - tran_ids_before[i]
					if auto_complete_diff:
						# TODO: implement post-processing-autocomplete
						pass 
	
			# Total duration in seconds
			duration = int(time_now() - start_time)
			job_info = {'duration': duration}
	
			if self.publish_stats is not None and iter_count > 0:
	
				self.logger.info("Computing job stats")
	
				job_info['processed'] = iter_count
				job_info['ingested'] = len(loop_stats['ingestTime'])
	
				# Ingest metrics: mean time & std dev in microseconds
				for key in ('ingestTime', 'dbBulkTime', 'dbOpTime'):
					if len(loop_stats[key]) > 0: 
						job_info[key] = self.compute_stat(loop_stats[key])
	
				# Filter metrics
				len_non_nan = lambda x: iter_max - np.count_nonzero(np.isnan(x))
				for i, channel in chan_enum:
					mylen = len_non_nan(loop_stats[channel.name])
					job_info[channel.name] = {
						'ingested': filter_tran_counter[i],
						'filterTime': (
							(0, 0) if len_non_nan(loop_stats[channel.name]) == 0
							else self.compute_stat(
								loop_stats[channel.name], 
								mean=np.nanmean, 
								std=np.nanstd
							)
						)
					}

				job_info = self.gather_and_send_stats(tran_ids_after, job_info)

			# Insert job info into job document
			db_job_reporter.set_job_stats("t0Stats", job_info)

		except:

			self.report_exception(
				{
					'section': 'run_end',
					'jobId':  db_job_reporter.get_job_id(),
				}
			)
			

		# re-add initial log buffer
		self.logger.addHandler(self.ilb)

		loginfo("Alert processing completed (time required: %ss)" % duration)

		# Restore console logging if it was removed
		if not console_logging:
			self.logger.propagate = True

		# Remove DB logging handler
		db_job_reporter.set_flush_job_info()
		db_logging_handler.flush()
		self.logger.removeHandler(db_logging_handler)
		
		# Return number of processed alerts
		return iter_count


	def gather_and_send_stats(self, tran_ids, t0_stats=None):
		"""
		"""

		stat_dict = {
			'db': {},
			'tranCount': {}
		}

		# Global metrics
		tran_col = self.get_tran_col()
		stat_dict['db']['tranCol'] = MongoStats.get_col_stats(tran_col)
		stat_dict['db']['jobCol'] = MongoStats.get_col_stats(self.get_job_col())
		stat_dict['db']['daemon'] = MongoStats.get_server_stats(tran_col.database)
		stat_dict['tranCount']['all'] = MongoStats.get_tran_count(tran_col)

		# Channel specific metrics
		for i, channel in self.chan_enum:
			stat_dict['tranCount'][channel.name] = (
				len(tran_ids[i]) if tran_ids[i] is not None 
				else MongoStats.get_tran_count(tran_col, channel.name)
			)

		if t0_stats is not None:
			stat_dict['t0'] = t0_stats

		# Publish metrics to graphite
		if "graphite" in self.publish_stats:

			self.logger.info("Sending stats to Graphite")

			# Re-using GraphiteClient results in: 
			# GraphiteSendException: Socket closed before able to send data to ('localhost', 52003), 
			# with error: [Errno 32] Broken pipe
			# So we re-create a GraphiteClient every time we send something to graphite...
			gfeeder = GraphiteFeeder(self.global_config['graphite']) 

			gfeeder.add_stats(stat_dict['db']['daemon'], suffix='db.deamon.')
			gfeeder.add_stats(stat_dict['db']['tranCol'], suffix='db.col.tran.')
			gfeeder.add_stats(stat_dict['db']['jobCol'], suffix='db.col.jobs.')
			gfeeder.add_stat('ampel.tran_count.all', stat_dict['tranCount']['all'])
			gfeeder.add_stat('db.col.troubles.count', self.get_trouble_col().find({}).count())

			for channel in self.channels:
				gfeeder.add_stat(
					'ampel.tran_count.%s' % channel.name, 
					stat_dict['tranCount'][channel.name]
				)
			
			if t0_stats is not None:
				gfeeder.add_stats_with_mean_std(t0_stats, suffix='ampel.t0.')
	
			gfeeder.send()

		return stat_dict


	def report_exception(self, further_info=None, parsed_alert=None):
		"""
		further_info: non-nested dict instance
		"""
		import traceback

		self.logger.propagate = True
		self.logger.critical("Exception occured", exc_info=1)

		exception_str = traceback.format_exc().replace("\"", "'")

		insert_dict = {
			'tier': 0,
			'exception': exception_str.split("\n")
		}

		if parsed_alert is not None:

			if 'alert_id' in parsed_alert:
				insert_dict['alertId'] = parsed_alert['alert_id'] 
	
			if "KeyboardInterrupt" not in exception_str:
	
				if (
					'pps' in parsed_alert and 
					len(parsed_alert['pps']) > 0 and 
					'jd' in parsed_alert['pps'][0]
				):
					insert_dict['alertDt'] = parsed_alert['pps'][0]['jd']
		
				if further_info is not None:
					for key in further_info:
						insert_dict[key] = further_info[key]
		
				insert_dict['alertPPS'] = parsed_alert['pps']
				insert_dict['alertULS'] = parsed_alert['uls']

		self.get_trouble_col().insert_one(insert_dict)
		self.logger.propagate = False


	def compute_stat(self, seq, mean=np.mean, std=np.std):
		"""
		"""
		# mean time & std dev in microseconds
		np_seq = np.array(seq)
		return (
			int(round(mean(seq) * 1000000)),
			int(round(std(seq) * 1000000)) 
		)


	def get_tran_ids(self):
		"""
		Return value:
		Array - whose length equals len(self.channels) - possibly containing sets of transient ids.
		If channel[i] is the channel with index i wrt the list of channels 'self.channels', 
		and if channel[i] was configured to make use of the ampel auto_complete feature, 
		then tran_ids[i] will hold a {set} of transient ids listing all known 
		transients currently available in the DB for this particular channel.
		Otherwise, tran_ids_before[i] will be None
		"""

		col = self.get_tran_col()
		tran_ids = len(self.channels) * [None]

		# Loop through activated channels
		for i, channel in self.chan_enum:

			if channel.get_config("parameters.autoComplete"):

				# Build set of transient ids for this channel
				tran_ids[i] = {
					el['tranId'] for el in self.get_tran_col().find(
						{
							'alDocType': AlDocTypes.TRANSIENT, 
							'channels': channel.name
						},
						{
							'_id':0, 'tranId':1
						}
					)
				}

		return tran_ids


def init_db():
	"""
	Initialize a MongoDB for use with Ampel
	"""
	import os, glob
	from os.path import basename, dirname
	pattern = os.path.abspath(os.path.dirname(os.path.realpath(__file__)) + '/../../../../config/hu/*/*.json')
	
	from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
	parser = ArgumentParser(description=__doc__, formatter_class=ArgumentDefaultsHelpFormatter)
	parser.add_argument('--host', default='localhost:27017',
	    help='MongoDB server address and port')
	parser.add_argument('-d', '--database', default='Ampel_config',
	    help='Configuration database name')
	parser.add_argument('--config', nargs='+', default=glob.glob(pattern),
	    help='JSON files to be inserted into the "config" collection')
	
	opts = parser.parse_args()

	dbs = create_databases(opts.host, opts.database, opts.config)
	dbs[0].add_user("ampel-readonly", read_only=True, password="password")

def create_databases(host, database_name, configs):
	
	import os
	from os.path import basename, dirname
	from pymongo import MongoClient, ASCENDING
	from bson import ObjectId
	import json
	from ampel.archive import docker_env
	client = MongoClient(host, username=os.environ.get('MONGO_INITDB_ROOT_USERNAME', 'root'), password=docker_env('MONGO_INITDB_ROOT_PASSWORD'))
	
	def get_id(blob):
		if isinstance(blob['_id'], dict) and '$oid' in blob['_id']:
			return ObjectId(blob['_id']['$oid'])
		else:
			return blob['_id']
	
	config_db = client.get_database(database_name)
	for config in configs:
		collection_name = basename(dirname(config))
		collection = config_db[collection_name]
		with open(config) as f:
			for blob in json.load(f):
				blob['_id'] = get_id(blob)
				collection.replace_one({'_id':blob['_id']}, blob, upsert=True)
	
	return client.get_database('admin'), config_db

def _ingest_slice(host, archive_host, infile, start, stop):
	from ampel.archive import ArchiveDB, docker_env
	from ampel.pipeline.t0.alerts.TarballWalker import TarballWalker
	archive = ArchiveDB('postgresql://ampel:{}@{}/ztfarchive'.format(docker_env('POSTGRES_PASSWORD'), archive_host))
	
	def loader():
		tbw = TarballWalker(infile, start, stop)
		for alert in tbw.get_files():
			archive.insert_alert(alert, 0, 0)
			yield alert
	processor = AlertProcessor(db_host=host)
	return processor.run(loader())

def _worker(idx, mongo_host, archive_host, bootstrap_host, group_id, chunk_size=5000):
	from ampel.archive import ArchiveDB, docker_env
	from ampel.pipeline.t0.ZIAlertFetcher import ZIAlertFetcher
	from pymongo import MongoClient

	archive = ArchiveDB('postgresql://ampel:{}@{}/ztfarchive'.format(docker_env('POSTGRES_PASSWORD'), archive_host))
	mongo = 'mongodb://{}:{}@{}/'.format(docker_env('MONGO_INITDB_ROOT_USERNAME'), docker_env('MONGO_INITDB_ROOT_PASSWORD'), mongo_host)

	fetcher = ZIAlertFetcher(archive, bootstrap_host, group_name=group_id)

	import time
	t0 = time.time()

	count = 0
	for i in range(10):
		processor = AlertProcessor(db_host=mongo)
		count += processor.run(fetcher.alerts(chunk_size), console_logging=False)
		t1 = time.time()
		dt = t1-t0
		t0 = t1
		print('({}) {} alerts in {:.1f}s; {:.1f}/s'.format(idx, chunk_size, dt, chunk_size/dt))
	return count

def run_alertprocessor():

	import os, time, uuid
	from concurrent import futures
	from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
	parser = ArgumentParser(description=__doc__, formatter_class=ArgumentDefaultsHelpFormatter)
	parser.add_argument('--host', default='mongo:27017')
	parser.add_argument('--archive-host', default='archive:5432')
	parser.add_argument('--broker', default='epyc.astro.washington.edu:9092')
	parser.add_argument('--procs', type=int, default=1, help='Number of processes to start')
	parser.add_argument('--chunksize', type=int, default=5000, help='Number of alerts in each process')
	
	opts = parser.parse_args()
	
	executor = futures.ProcessPoolExecutor(opts.procs)

	group = uuid.uuid1()
	
	start_time = time.time()
	step = opts.chunksize
	count = 0
	jobs = [executor.submit(_worker, idx, opts.host, opts.archive_host, opts.broker, group, opts.chunksize) for idx in range(opts.procs)]
	for future in futures.as_completed(jobs):
		print(future.result())
		count += future.result()
	duration = int(time.time()) - start_time
	print('Processed {} alerts in {:.1f} s ({:.1f}/s)'.format(count, duration, float(count)/duration))
	
