#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : Ampel-core/ampel/query/QueryEventsCol.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 11.07.2018
# Last Modified Date: 06.01.2020
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from typing import Dict, Union, Optional, List, Literal, Any
from time import time, strftime, gmtime

class QueryEventsCol:
	"""
	"""

	@staticmethod
	def get_last_run(process_name: str, days_back: Optional[int] = 10) -> List[Dict]:
		"""
		"""

		ret = QueryEventsCol.get(
			tier=3, process_name=process_name, 
			days_back=days_back
		)

		ret.append(
			{'$limit': 1} # take only the first entry
		)

		return ret


	@staticmethod
	def get_t0_stats(timestamp: Union[float, int]) -> List[Dict]:
		"""
		:param timestamp: unix timestamp
		"""

		ret = QueryEventsCol.get(
			tier=0, 
			timestamp=timestamp,
			days_back=int((time() - timestamp) / 86400) + 1
		)

		ret.append(
			{
                "$group": {
                    "_id": 1,
                    "alerts": {
                        "$sum": "$events.metrics.count.alerts"
                    }
                }
            }
		)

		return ret


	@staticmethod
	def get(
		tier: Literal[0, 1, 2, 3] = 0,
		process_name: Optional[str] = None,
		days_back: Optional[int] = 10,
		timestamp: Optional[Union[int, float]] = None
	) -> List[Dict]:
		"""
		:param tier: positive integer between 0 and 3
		:param days_back: positive integer or None
		:param timestamp: unix time
		:returns: list of dict to be used as aggregation pipeline query parameters
		"""

		# Array returned by this method
		ret: List[Dict] = []

		# restrict match criteria 
		if days_back is not None:

			# Matching db doc ids. Example: [20180711, 20180710]
			match = []

			# add today. Example: 20180711
			match.append(
				int(strftime('%Y%m%d'))
			)

			# add docs from previous days. Example: 20180710, 20180709
			for i in range(1, days_back+1):
				match.append(
					int(
						strftime('%Y%m%d', gmtime(time() - 86400 * i))
					)
				)

			ret.append(
				{
					'$match': {
						'_id': {
							'$in': match
						}
					}
				}
			)

		second_match_stage: Dict[str, Any] = {'events.tier': tier}

		if process_name:
			second_match_stage['events.process'] = process_name

		if timestamp is not None:
			second_match_stage['events.ts'] = {'$gt': timestamp}

		ret.extend(
			[
				{'$unwind': '$events'},
				{'$match': second_match_stage},
				# sort events by descending date-time
				{'$sort': {'events.ts': -1}},
			]
		)

		return ret
