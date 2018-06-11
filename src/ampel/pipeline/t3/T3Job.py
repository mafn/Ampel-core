#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/pipeline/t3/T3Job.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 06.03.2018
# Last Modified Date: 11.06.2018
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from functools import reduce

class T3Job:
	"""
	"""

	def __init__(self, job_name, job_doc, t3_task_instances):
		"""
		job_name: string
		job_doc: dict instance
		t3_task_instances: list of instances of ampel.pipeline.t3.T3Task
		"""

		self.job_name = job_name
		self.job_doc = job_doc
		self.t3_task_instances = t3_task_instances


	def get_tasks(self):
		""" 
		Returns the loaded tasks associated with this job
		"""
		return self.t3_task_instances


	def get_chunk(self):
		""" """
		return self.get_config('input.chunk')


	def get_config(self, param_name):
		"""
		"""
		return reduce(dict.get, param_name.split("."), self.job_doc)


	def launch_t3_job(self, bla):
		#run_job(self.al_config, central_db, t3_job, logger)
		pass


	def schedule(self, scheduler):

		t3_job = None
		if self.get_config('schedule.mode') == "fixed_rate":

			scheduler.every(
				self.get_config('schedule.interval')
			).minutes.do(
				self.launch_t3_job, 
				t3_job
			)

		elif self.get_config('schedule.mode') == "fixed_time":

			scheduler.every().day.at(
				self.get_config('schedule.time')
			).do(
				self.launch_t3_job, 
				t3_job
			)
