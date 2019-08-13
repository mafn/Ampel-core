#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/t3/T3JournalUpdater.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 15.10.2018
# Last Modified Date: 23.11.2018
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from time import time
from pymongo.operations import UpdateMany, UpdateOne
from pymongo.errors import BulkWriteError
from ampel.core.flags.AlDocType import AlDocType
from ampel.db.AmpelDB import AmpelDB
from ampel.common.AmpelUtils import AmpelUtils
from ampel.logging.LoggingUtils import LoggingUtils


class T3JournalUpdater:
	"""
	"""

	def __init__(self, run_id, event_name, logger, raise_exc=False):
		"""
		:param str event_name: job or task name
		:param int run_id: run id
		:param bool raise_exc: raise exception rather than populating 'troubles' collection
		"""

		self.run_id = run_id
		self.raise_exc = raise_exc
		self.event_name = event_name
		self.logger = logger
		self.reset()


	def reset(self):
		"""
		:returns: None
		"""
		self.journal_updates = {
			True: [],
			False: []
		}

		self.journal_updates_count = {
			True: 0,
			False: 0
		}


	def add_default_entries(self, tran_views, channels, event_name=None, run_id=None):
		"""
		:param tran_views: TransientView instances
		:type tran_views: list(:py:class:`TransientView <ampel.base.TransientView>`)
		:param list(str) channels: list of channel names
		:param str event_name: optional event name override (ex: subtask name of job)
		:param int run_id: optional run_id override (ex: job subtask run_id)
		:returns: None
		"""

		self.journal_updates_count[False] += len(tran_views)
		self.journal_updates[False].append(
			UpdateMany(
				{	
					'tranId': {'$in': [el.tran_id for el in tran_views]},
					'alDocType': AlDocType.TRANSIENT
				},
				{
					'$push': {
						"journal": {
							'tier': 3,
							'dt': int(time()),
							'event':  event_name if event_name else self.event_name,
							'runId':  run_id if run_id else self.run_id,
							'channels': channels
						}
					}
				}
			)
		)


	def add_custom_entries(self, journal_updates, channels, event_name=None, run_id=None):
		"""
		:param journal_updates: list of JournalUpdate dataclass instances
		:type journal_updates: list(:py:class:`JournalUpdate \
			<ampel.base.dataclass.JournalUpdate>`)
		:param list(str) channels: list of channel names
		:param str event_name: optional event name override (ex: subtask name of job)
		:param int run_id: optional run_id override (ex: job subtask run_id)
		:returns: None
		"""

		if journal_updates is None:
			return

		for jup in journal_updates:

			if AmpelUtils.is_sequence(jup.tran_id):
				self.journal_updates_count[jup.ext] += len(jup.tran_id)
				tran_match = {'$in': jup.tran_id}
				Op = UpdateMany
			else:
				self.journal_updates_count[jup.ext] += 1
				tran_match = jup.tran_id
				Op = UpdateOne

			if jup.ext:
				# No need for alDocType in Ampel_ext->journal
				match = {'_id': tran_match}
			else:
				match = {
					'tranId': tran_match,
					'alDocType': AlDocType.TRANSIENT
				}

			self.journal_updates[jup.ext].append(
				Op(
					match,
					{
						'$push': {
							"journal": {
								**jup.content,
								'tier': 3,
								'dt': int(time()),
								'event':  event_name if event_name else self.event_name,
								'runId':  run_id if run_id else self.run_id,
								'channels': channels
							}
						}
					},
					upsert=jup.ext
				)
			)


	def flush(self):

		if self.journal_updates[False]:
			self._flush(False)

		if self.journal_updates[True]:
			self._flush(True)

		self.reset()

	def _flush(self, permanent=False):
		"""
		:param bool permanent:

		self.reset() is not called.
		"""
		try:

			# Journal entries to be inserted
			ret = AmpelDB.get_collection(
				'journal' if permanent else 'tran'
			).bulk_write(
				self.journal_updates[permanent]
			)

			self.logger.info(
				"%i %s entries inserted" % (
					self.journal_updates_count[permanent],
					"permanent journal" if permanent else "journal"
				)
			)
	
		except BulkWriteError as bwe:

			if self.raise_exc:
				raise ValueError("Journal update error: %s" % str(bwe.details))
	
			# Populate troubles collection
			LoggingUtils.report_exception(
				self.logger, bwe, tier=3, run_id=self.run_id, info={
					'event': self.event_name,
					'msg': 'Exception in flush()',
					'journalUpdateCount': self.journal_updates_count[permanent],
					'permanentjournalEntries': permanent,
					'BulkWriteError': str(bwe.details)
				}
			)

		except Exception as e:

			# Populate troubles collection
			LoggingUtils.report_exception(
				self.logger, e, tier=3, run_id=self.run_id, info={
					'msg': 'Exception in flush()',
					'event': self.event_name
				}
			)
