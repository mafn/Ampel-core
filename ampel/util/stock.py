#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File:                Ampel-core/ampel/utils/stock.py
# License:             BSD-3-Clause
# Author:              valery brinnel <firstname.lastname@gmail.com>
# Date:                29.04.2020
# Last Modified Date:  29.04.2020
# Last Modified By:    valery brinnel <firstname.lastname@gmail.com>

from pymongo import MongoClient
from pymongo.collection import Collection
from multiprocessing import Pool
from collections.abc import Sequence
from ampel.types import ChannelId, StockId


def get_ids_using_find(
	col: Collection,
	channel: ChannelId | Sequence[ChannelId],
	batch_size=1000000
) -> dict[ChannelId, set[StockId]]:

	if isinstance(channel, (int, str)):
		return {
			channel: {
				el['_id'] for el in col \
					.find({'channel': channel}, {'_id': 1}) \
					.batch_size(batch_size)
			}
		}

	return {k: get_ids_using_find(col, k, batch_size)[k] for k in channel}


def get_ids_using_parallel_find(
	channel: ChannelId | Sequence[ChannelId],
	mongo_uri: None | str = None,
	db_name='Ampel_data', col_name='stock', *,
	pool_size=None, batch_size=1000000
) -> dict[ChannelId, set[StockId]]:

	if isinstance(channel, (int, str)):
		return get_ids_using_find(
			MongoClient(mongo_uri) \
				.get_database(db_name) \
				.get_collection(col_name),
			channel, batch_size
		)

	pool = Pool(processes=pool_size)

	ret: dict[ChannelId, set[StockId]] = {k: set() for k in channel}

	results = [
		pool.apply_async(
			find_ids_worker,
			(k, mongo_uri, db_name, col_name, batch_size),
			callback = ret[k].update
		)
		for k in channel
	]

	for r in results:
		r.wait()

	pool.close()
	return ret


def find_ids_worker(
	channel: ChannelId | Sequence[ChannelId],
	mongo_uri: None | str = None, db_name='Ampel_data',
	col_name='stock', batch_size=1000000
) -> set[StockId]:

	mc = MongoClient(mongo_uri)
	db = mc.get_database(db_name)

	return {
		el['_id'] for el in db.get_collection(col_name) \
			.find({'channel': channel}, {'_id': 1}) \
			.batch_size(batch_size)
	}
