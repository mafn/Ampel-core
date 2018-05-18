#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/pipeline/dbquery/QueryLatestCompound.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 13.01.2018
# Last Modified Date: 11.03.2018

from ampel.flags.AlDocTypes import AlDocTypes
from ampel.flags.FlagUtils import FlagUtils

from ampel.pipeline.db.query.QueryMatchFlags import QueryMatchFlags
from ampel.pipeline.db.query.QueryMatchCriteria import QueryMatchCriteria

class QueryLatestCompound:
	"""
	"""

	@staticmethod
	def fast_query(tran_ids, channels=None):
		"""
		Note:
		-----
		! Must be used on transients whose compounds were solely created by T0 !
		(i.e with no T3 compounds)

		Returns:
		--------
		A dict instance to be used with the mongoDB *aggregation* framework.

		Example:
		--------
		In []: cursor = col.aggregate(
			QueryLatestCompound.fast_query(
				['ZTF18aaayyuq', 'ZTF17aaagvng', 'ZTF18aaabikt']
			)
		)

		In []: list(cursor)
		Out[]: 
		[
			{'_id': '5de2480f28bfca0bd3baae890cb2d2ae', 'tranId': 'ZTF18aaayyuq'},
 			{'_id': '5fcdeda5e116989a69f6cbbde7234654', 'tranId': 'ZTF18aaabikt'},
 			{'_id': '854b467971b7683a7317ab1a032d4978', 'tranId': 'ZTF17aaagvng'}
		]

		Parameters	
		----------
		tran_id: transient id(s) (string, list of string, set of strings). 
		Query can be performed on multiple ids at once.

		channels: can be a flag, a list of flags, a string, a list of strings, a 2d list of strings:
		  flags:
			-> either an instance of ChannelFlags (dynamically generated by FlagGenerator)
			    * the flags contained in each instance are 'AND' connected
			-> or list of instances of ChannelFlags 
				* whereby the list elements are OR connected 

		  strings:
			-> a list of strings (whereby string = channel id)
			-> a 2d list of strings 
				* outer list: flag ids connected by OR
				* innerlist: flag ids connected by AND

		Should perform faster than general_query.
		"""

		if not type(tran_ids) in (list, str, set):
			raise ValueError("Type of tran_ids must be either a string or a list of strings")

		match_dict = {
			'alDocType': AlDocTypes.COMPOUND
		}

		match_dict['tranId'] = ( 
			tran_ids if type(tran_ids) is str
			else {'$in': tran_ids if type(tran_ids) is list else list(tran_ids)}
		)

		if channels is not None:
			QueryMatchCriteria.add_from_list(
				match_dict, 'channels',
				(channels if not FlagUtils.contains_enum_flag(channels) 
				else FlagUtils.enum_flags_to_lists(channels)), 
			)

		return [
			{
				'$match': match_dict
			},
			{
				'$project': {
					'tranId': 1,
					'len': 1
				}
			},
			{
				'$sort': {
					'tranId': 1, 
					'len': -1
				} 
			},
			{
				'$group': {
					'_id': '$tranId',
					'data': {
						'$first': '$$ROOT'
					}
				}
			},
			{
				'$replaceRoot': {
					'newRoot': '$data'
				}
			},
			{ 
				'$project': { 
					'len': 0
				}
			}
		]


	@staticmethod
	def general_query(tran_id, project=None, channels=None):
		"""
		Can be used on any ampel transients.
		There is a very detailed explanation of each step of the aggragetion 
		documented in the python notebook "T3 get_lastest_compound"

		Returns:
		--------
		A dict instance to be used with the mongoDB *aggregation* framework.

		Parameters	
		----------
		tran_id: transient id (string). Query can *not* be done on multiple ids at once.
		project: optional projection stage at the end of the aggregation (dict instance)
		channels: see 'fast_query' docstring

		Examples:
		---------
		IMPORTANT NOTE: the following two examples show the output of the aggregation framework 
		from mongodb (i.e the output after having performed a DB query *using the output 
		of this fuunction as parameter*), they do not show the output of this function.

		*MONGODB* Output example 1:
		---------------------------
		In []: list(
			col.aggregate(
				QueryLatestCompound.general_query('ZTF18aaayyuq')
			)
		)
		Out[]: 
		[
		  {
			'_id': '5de2480f28bfca0bd3baae890cb2d2ae',
			  'added': 1520796310.496276,
			  'alDocType': 2,
			  'channels': ['HU_SN1'],
			  'lastppdt': 2458158.7708565,
			  'len': 12,
			  'pps': [{'pp': 375300016315010040},
			   {'pp': 375320176315010034},
			   {'pp': 375337116315010046},
			   {'pp': 375356366315010056},
			   {'pp': 377293446315010009},
			   {'pp': 377313156315010027},
			   {'pp': 377334096315010020},
			   {'pp': 377376126315010004},
			   {'pp': 377416496315010000},
			   {'pp': 378293006315010001},
			   {'pp': 378334946315010000},
			   {'pp': 404270856315015007}],
			  'tier': 0,
			  'tranId': 'ZTF18aaayyuq'
			}
		]

		*MONGODB* Output example 2:
		---------------------------
		In []: list(
			col.aggregate(
				QueryLatestCompound.general_query(
					'ZTF18aaayyuq', project={'$project': {'tranId':1}}
				)
			)
		)
		Out[]: 
			[{'_id': '5de2480f28bfca0bd3baae890cb2d2ae', 'tranId': 'ZTF18aaayyuq'}]
		"""
		if type(tran_id) is list:
			raise ValueError("Type of tran_id must be string (multi tranId queries not supported)")

		match_dict = {
			'tranId': tran_id, 
			'alDocType': AlDocTypes.COMPOUND
		}

		if channels is not None:
			QueryMatchCriteria.add_from_list(
				match_dict, 'channels',
				(channels if not FlagUtils.contains_enum_flag(channels) 
				else FlagUtils.enum_flags_to_lists(channels)), 
			)

		ret = [
			{
				'$match': match_dict
			},
			{
				'$group': {
					'_id': '$tier', 
					'latestAdded': {
						'$max': '$added'
					}, 
					'comp': {
						'$push': '$$ROOT'
					}
				}
			},
			{
				'$sort': {
					'latestAdded': -1
				}
			},
			{
				'$limit': 1
			},
			{
				'$unwind': '$comp'
			},
			{
				'$project': {
					'_id': 0,
					'comp': 1, 
					'sortValueUsed': {
						'$cond': {
							'if': {
								'$eq': ['$comp.tier', 0]
							},
							'then': '$comp.len',
							'else': '$comp.added'
						}
					}
				}
			},
			{
				'$sort': {
					'sortValueUsed': -1
				}
			},
			{
				'$limit': 1
			},
			{
				'$replaceRoot': {
					'newRoot': '$comp' 
				}
			}
		]

		if project is not None:
			ret.append(project)

		return ret
