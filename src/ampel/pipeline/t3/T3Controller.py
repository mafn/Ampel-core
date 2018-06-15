#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/pipeline/t3/T3Controller.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 26.02.2018
# Last Modified Date: 14.06.2018
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

import schedule, time, threading
from ampel.pipeline.db.DBWired import DBWired
from ampel.pipeline.t3.T3Job import T3Job
from ampel.pipeline.t3.T3JobLoader import T3JobLoader
from ampel.pipeline.common.Schedulable import Schedulable
from ampel.pipeline.logging.LoggingUtils import LoggingUtils

class T3Controller(DBWired, Schedulable):
	"""
	"""

	def __init__(
		self, config=None, central_db=None, mongodb_uri=None, t3_job_names=None
	):
		"""
		'config': see ampel.pipeline.db.DBWired.load_config() docstring
		'central_db': see ampel.pipeline.db.DBWired.plug_central_db() docstring
		'mongodb_uri': URI of the server hosting mongod.
		   Example: 'mongodb://user:password@localhost:27017'
		't3_job_names': optional list of strings. If specified, only job with these names will be run.
		"""
		super(T3Controller, self).__init__()
		# Setup logger
		self.logger = LoggingUtils.get_logger(unique=True)
		self.logger.info("Setting up T3Controler")

		# Setup instance variable referencing ampel databases
		self.plug_databases(self.logger, mongodb_uri, config, central_db)

		for job_name in self.config["t3_jobs"].keys():

			if t3_job_names is not None and job_name not in t3_job_names:
				continue

			t3_job = T3JobLoader.load(job_name, self.logger)
			t3_job.schedule(self.scheduler)


def run():
	from ampel.pipeline.config.ConfigLoader import AmpelArgumentParser

	parser = AmpelArgumentParser()
	parser.require_resource('mongo', ['writer'])
	opts = parser.parse_args()

	mongo = opts.config['resources']['mongo']()['writer']

	controller = T3Controller(
		config=opts.config,
		mongodb_uri=mongo
	)
	controller.run()
