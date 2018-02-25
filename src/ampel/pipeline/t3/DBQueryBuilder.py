#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/pipeline/t3/DBQueryBuilder.py
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 13.01.2018
# Last Modified Date: 25.02.2018
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from ampel.flags.AlDocTypes import AlDocTypes
from ampel.flags.TransientFlags import TransientFlags
from ampel.flags.FlagUtils import FlagUtils
from bson.objectid import ObjectId
import logging
from datetime import datetime, timedelta




class DBQueryBuilder:
	"""
	"""

	@staticmethod
	def load_transient_query(tran_id, content_types, t2_ids=None):
		"""
		Please note that if AlDocTypes.COMPOUND is included in content_types, 
		document with AlDocTypes.PHOTOPOINT will be queried as well since photopoints instances
		are required to instanciate LightCurve objects.

		Stateless query: all compounds and (possible t2_ids limited) t2docs to be retrieved	
		"""

		query = {'tranId': tran_id}

		# Everything should be retrieved (1+2+4+8=15)
		if t2_ids is None and content_types.value == 15:
			return query

		# Build array of AlDocTypes (AlDocTypes.T2RECORD will be set later since it depends in t2_ids)
		al_types = []
		for al_type in [AlDocTypes.PHOTOPOINT, AlDocTypes.COMPOUND, AlDocTypes.TRANSIENT]:
			if al_type in content_types:
				al_types.append(al_type)

		# Loading LightCurve instances requires photopoints information
		if AlDocTypes.COMPOUND in content_types and AlDocTypes.PHOTOPOINT not in content_types:
			al_types.append(AlDocTypes.PHOTOPOINT)

		if t2_ids is None:

			# Complete alDocType with type T2RECORD if so whished
			if AlDocTypes.T2RECORD in content_types:
				al_types.append(AlDocTypes.T2RECORD)

			# Add single additional search criterium to query
			query['alDocType'] = (
				al_types[0] if len(al_types) == 1 
				else {'$in': al_types}
			)

		else:

			# Convert provided T2RunnableIds into an array on flag values
			t2_ids_db = FlagUtils.enumflag_to_dbflag(t2_ids)

			# Combine first part of query (photopoints+transient+compounds) with 
			# runnableId targeted T2RECORD query
			query['$or'] = [
				# photopoints+transient+compounds 
				{
					'alDocType': (
						al_types[0] if len(al_types) == 1 
						else {'$in': al_types}
					)
				},
				{
					'alDocType': AlDocTypes.T2RECORD,
					't2Runnable': (
						t2_ids_db[0] if len(t2_ids_db) == 1 
						else {'$in': t2_ids_db}
					)
				}
			]

		return query


	@staticmethod
	def load_transient_state_query(
		tran_id, content_types, compound_id, t2_ids=None, comp_already_loaded=False
	):
		"""
		Please note that if AlDocTypes.COMPOUND is included in content_types, 
		document with AlDocTypes.PHOTOPOINT will be queried as well since photopoints instances
		are required to instanciate LightCurve objects.
		"""

		# Logic check
		if AlDocTypes.COMPOUND not in content_types and AlDocTypes.T2RECORD not in content_types :
			raise ValueError(
				"State scoped queries make no sense without either AlDocTypes.COMPOUND " +
				"or AlDocTypes.T2RECORD set in content_types"
			)

		query = {'tranId': tran_id}

		# build query with 'or' connected search criteria
		or_list = []

		if (
			AlDocTypes.TRANSIENT|AlDocTypes.PHOTOPOINT in content_types or
			AlDocTypes.TRANSIENT|AlDocTypes.COMPOUND in content_types
		):

			or_list.append(
				{
					'alDocType': {
						'$in': [
							AlDocTypes.TRANSIENT, 
							AlDocTypes.PHOTOPOINT
						]
					}
				}
			)

		else:

			if AlDocTypes.TRANSIENT in content_types:
				or_list.append(
					{'alDocType': AlDocTypes.TRANSIENT}
				)

			if (
				AlDocTypes.PHOTOPOINT in content_types or 
				AlDocTypes.COMPOUND in content_types
			):
				or_list.append(
					{'alDocType': AlDocTypes.PHOTOPOINT}
				)

		if AlDocTypes.COMPOUND in content_types and comp_already_loaded is False:

			or_list.append(
				{
					'alDocType': AlDocTypes.COMPOUND, 
					'_id': compound_id
				}
			)

		if AlDocTypes.T2RECORD in content_types:

			rec_dict = {
				'alDocType': AlDocTypes.T2RECORD, 
				'compoundId': compound_id
			}

			if t2_ids is not None:
				t2_ids_db = FlagUtils.enumflag_to_dbflag(t2_ids)
				rec_dict['t2Runnable'] = (
					t2_ids_db[0] if len(t2_ids_db) == 1 
					else {'$in': t2_ids_db}
				)

			or_list.append(rec_dict)

		# If only 1 $or criteria was generated, then 
		# just add this criteria to the root dict ('and' connected with tranId: ...)
		if len(or_list) == 1:
			el = or_list[0]
			for key in el.keys():
				query[key] = el[key]
		else:
			query['$or'] = or_list

		return query



	@staticmethod
	def get_transients_query(
		tran_flags=None, channel_flags=None, 
		time_created={"now_minus": None, "from": None, "until": None},
		time_modified={"now_minus": None, "from": None, "until": None}
	):
		"""
		'tran_flags': 
		-> instance of ampel.flags.TransientFlags or list of instances of TransientFlags
		See FlagUtils.enumflag_to_dbquery docstring for more info

		'channel_flags': 
		-> instance of ampel.flags.ChannelFlags or list of instances of ChannelFlags
		See FlagUtils.enumflag_to_dbquery docstring for more info

		'time_created': 
			-> provide either 'now_minus' or ('from' and/or 'until')
			-> 'now_minus': instance of datetime.timedelta
			-> 'from' and 'until' must be of type datetime.datetime

		'time_modified': 
			-> provide either 'now_minus' or ('from' and/or 'until')
			-> 'now_minus': instance of datetime.timedelta
			-> 'from' and 'until' must be of type datetime.datetime
		"""

		query = {
			'alDocType': AlDocTypes.TRANSIENT
		}

		# TODO: generalize it and put it into FlagUtils!
		# might be used for channelFlags as well!
		if tran_flags is not None:
			query['alFlags'] = FlagUtils.enumflag_to_dbquery(tran_flags, 'alFlags')

		if channel_flags is not None:
			query['channels'] = FlagUtils.enumflag_to_dbquery(channel_flags, 'channels')

		DBQueryBuilder._build_time_contraint(query, '_id', time_created, is_oid=True)
		DBQueryBuilder._build_time_contraint(query, 'modified', time_modified)

		return query


	@staticmethod
	def _build_time_contraint(query, db_field_name, time_constraint, is_oid=False):
		"""
		"""
		if time_constraint['now_minus'] is not None:
			gen_time = datetime.today() - time_constraint['now_minus'] 
			query[db_field_name] = {
				"$gte": ObjectId.from_datetime(gen_time) if is_oid else gen_time
			}

		if time_constraint['from'] is not None or time_constraint['until'] is not None:

			if db_field_name in query:
				raise ValueError(
					"Wrong time_constraint criteria: " +
					"please use either 'now_minus' or ('from' and/or 'until'))"
				)

			query[db_field_name] = {}

			if time_constraint['from'] is not None:
				query[db_field_name]["$gte"] = (
					ObjectId.from_datetime(time_constraint['from']) if is_oid
					else time_constraint['from']
				)

			if time_constraint['until'] is not None:
				query[db_field_name]["$lte"] = (
					ObjectId.from_datetime(time_constraint['until']) if is_oid
					else time_constraint['until']
				)


	@staticmethod
	def latest_compound_faster_query(tran_ids, channel_flags=None):
		"""
		channel_flags: can be 
			-> either an instance of ampel.flags.ChannelFlags 
			  (whereby the flags contained in on instance are 'AND' connected)
			-> or list of instances of ampel.flags.ChannelFlags whereby the instances 
			   are 'OR' connected between each other
			Please see the doctring of FlagUtils.enumflag_to_dbquery for more info.
		Should perform faster than latest_compound_general_query.
		Must be used on transients with compounds solely created by T0 
		(i.e no T3 compounds)
		"""

		if not type(tran_ids) is list:
			if not type(tran_ids) is str:
				raise ValueError("Type of tran_ids must be either a string or a list of strings")

		match_dict = {
			'alDocType': AlDocTypes.COMPOUND
		}

		match_dict['tranId'] = ( 
			tran_ids if type(tran_ids) is str or len(tran_ids) == 1
			else {'$in': tran_ids}
		)

		if channel_flags is not None:
			match_dict['channels'] = FlagUtils.enumflag_to_dbquery(channel_flags, 'channels')

		return [
			{
				'$match': match_dict
			},
			{
				'$project': {
					'tranId': 1,
					'len': 1,
					'compoundId': 1
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
	def latest_compound_general_query(tran_id, channel_flags=None):

		if type(tran_id) is list:
			raise ValueError("Type of tran_ids must be string (multi tranId queries not supported)")

		match_dict = {
			'tranId': tran_id, 
			'alDocType': AlDocTypes.COMPOUND
		}

		if channel_flags is not None:
			match_dict['channels'] = FlagUtils.enumflag_to_dbquery(channel_flags, 'channels')

		return [
			{
				'$match': match_dict
			},
			{
				'$group': {
					'_id': '$tier', 
					'latestAdded': {
						'$max': '$added'
					}, 
					'compound': {
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
				'$unwind': '$compound'
			},
			{
				'$project': {
					'_id': 0,
					'compound': 1, 
					'sortValueUsed': {
						'$cond': {
							'if': {
								'$eq': ['$compound.tier', 0]
							},
							'then': '$compound.len',
							'else': '$compound.added'
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
					'newRoot': '$compound' 
				}
			}
		]
