!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/query/QueryMatchSchema.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 11.03.2018
# Last Modified Date: 10.12.2019
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from typing import Dict, Union, Tuple
from ampel.common.AmpelUtils import AmpelUtils
from ampel.model.operator.AnyOf import AnyOf
from ampel.model.operator.AllOf import AllOf
from ampel.model.operator.OneOf import OneOf

valid_types = (int, str)

class QueryMatchSchema:
	"""
	Schema syntax example:

	.. sourcecode:: python\n
		{'anyOf': ["a", "b", "c"]}
		{'allOf': ["a", "b", "c"]}
		{'oneOf': ["a", "b", "c"]}
		{'anyOf': [{'allOf': ["a","b"]}, "c"]}
		{'anyOf': [{'allOf': ["a","b"]}, {'allOf': ["a","c"]}, "d"]}
	"""

	@classmethod
	def apply_schema(cls, 
		query: Dict, field_name: str, 
		arg: Union[int, str, Dict, AllOf, AnyOf, OneOf]
	) -> Dict:
		"""
		Warning: The method changes keys and values in the input dict parameter "query"

		This function translates a dict schema containing conditional (AND/OR) matching criteria \
		into a dict syntax that mongodb understands. It is typically used for queries \
		whose selection criteria are loaded directly from config documents. 

		:param query: dict that will be later used as query criteria (can be empty). \
		This dict will be updated with the additional matching criteria computed by this method. \
		query value examples:\n
			- {}  (empty dict)
			- {'tranId': 'ZTFabc'}  (basic transient ID matching criteria)

		:param field_name: name of the DB field containing the tag values

		:param arg: for convenience, the parameter can be of type int/str if only one value is to be matched. \
		The dict can be nested up to one level. \
		Please see :obj:`QueryMatchSchema <ampel.query.QueryMatchSchema>` docstring for details.

		:raises ValueError: if 'query' already contains:\n
			- the value of 'field_name' as key
			- the key '$or' (only if the list 'arg' contains other lists)
	
		:returns: (modified/updated) dict instance referenced by query
		"""

		# Checks were already performed by validators
		if isinstance(arg, (AllOf, AnyOf, OneOf)):
			arg = arg.dict()
		else:
			# Be robust
			if cls.arg_check(arg, (int, str)):
				query[field_name] = arg
				return

		if 'allOf' in arg:

			# Raises error if invalid
			cls.check_allOf(arg, valid_types)

			if len(arg['allOf']) == 1:
				query[field_name] = arg['allOf'][0]
			else:
				query[field_name] = {'$all': arg['allOf']}

		elif 'anyOf' in arg:

			# Case 1: no nesting below anyOf
			if AmpelUtils.check_seq_inner_type(arg['anyOf'], valid_types):
				if len(arg['anyOf']) == 1: # dumb case
					query[field_name] = arg['anyOf'][0]
				else:
					query[field_name] = {'$in': arg['anyOf']}

			# Case 2: nesting below anyOf
			else:
	
				or_list = []
				optimize_potentially = []
	
				for el in arg['anyOf']:
	
					if isinstance(el, valid_types):
						or_list.append(
							{field_name: el}
						)
						optimize_potentially.append(or_list[-1])

					elif isinstance(el, dict):

						# Raises error if invalid
						cls.check_allOf(el, valid_types)

						if len(el['allOf']) == 1:
							or_list.append(
								{field_name: el['allOf'][0]}
							)
							optimize_potentially.append(or_list[-1])
						else:
							or_list.append(
								{field_name: {'$all': el['allOf']}}
							)

					else:
						raise ValueError(
							f"Unsupported format: depth 2 element is not a of type {valid_types} or dict)"
							f"\nOffending value: {el}"
						)


				# ex: add_from_dict(query, 'withTags', {'anyOf': [{'allOf': ["a","b"]}, "3", "1", "2"]})
				# optimize_potentially enables to replace:
				#   '$or': [
				#		{'withTags': {'$all': ['a', 'b']}},
  				#   	{'withTags': '3'}, {'withTags': '1'}, {'withTags': '2'}
				#	]
				# with:
				#   '$or': [
				#		{'withTags': {'$all': ['a', 'b']}},
  				#   	{'withTags': {'$in': ['3', '1', '2']}}
				#	]
				if len(optimize_potentially) > 1:
					or_list.append(
						{
							field_name: {
								'$in': [el[field_name] for el in optimize_potentially]
							}
						}
					)
					for el in optimize_potentially:
						or_list.remove(el)
	
				if len(or_list) == 1:
					query[field_name] = or_list[0][field_name]
				else:
					query['$or'] = or_list

		elif 'oneOf' in arg:
			query[field_name] = arg['oneOf']

		else:
			raise ValueError(
				"Invalid 'arg' keys (must contain either 'anyOf' or 'allOf'" +
				"\nOffending value: %s" % arg
			)

		return query


	@classmethod
	def apply_excl_schema(cls,
		query: Dict, field_name: str, 
		arg: Union[int, str, Dict, AllOf, AnyOf, OneOf]
	) -> Dict:
		"""
		###############################################################################
		Warning: The method changes keys and values in the input dict parameter "query"

		ATTENTION: call this method *last* if you want to combine 
		the match criteria generated by this method with the one 
		computed in method add_from_dict
		###############################################################################

		Parameters: see docstring of apply_schema
		:returns: dict instance referenced by parameter 'query' (which was updated)
		"""

		# Checks were already performed by validators
		if isinstance(arg, (AllOf, AnyOf, OneOf)):
			arg = arg.dict()
		else:
			cls.arg_check(arg, valid_types)

		# Check if field_name criteria were set previously
		if field_name in query:
			if isinstance(query[field_name], valid_types):
				# If a previous scalar tag matching criteria was set
				# then we need rename it since query[field_name] will become a dict 
				query[field_name] = {'$eq': query[field_name]}

		if isinstance(arg, valid_types):
			if field_name not in query:
				query[field_name] = {}
			query[field_name]['$ne'] = arg
			return

		if not isinstance(arg, Dict):
			raise ValueError('Illegal "arg" parameter')

		if 'allOf' in arg:

			# Raises error if invalid
			cls.check_allOf(arg, valid_types)

			if field_name not in query:
				query[field_name] = {}

			if len(arg['allOf']) == 1: # dumb case
				query[field_name]['$ne'] = arg['allOf'][0]
			else:
				query[field_name]['$not'] = {'$all': arg['allOf']}

		elif 'anyOf' in arg:

			# Case 1: no nesting below anyOf
			if AmpelUtils.check_seq_inner_type(arg['anyOf'], valid_types):

				if field_name not in query:
					query[field_name] = {}

				if len(arg['anyOf']) == 1: # dumb case
					query[field_name]['$ne'] = arg['anyOf'][0]
				else:
					query[field_name]['$not'] = {'$all': arg['anyOf']}

			else:

				and_list = []
				optimize_potentially = []

				for el in arg['anyOf']:

					if isinstance(el, valid_types):
						and_list.append(
							{field_name: {'$ne': el}}
						)
						optimize_potentially.append(and_list[-1])

					elif isinstance(el, dict):

						# Raises error if el is invalid
						cls.check_allOf(el, valid_types)

						if len(el['allOf']) == 1:
							and_list.append(
								{field_name: {'$ne': el['allOf'][0]}}
							)
							optimize_potentially.append(and_list[-1])
						else:
							and_list.append(
								{
									field_name: {
										'$not': {'$all': el['allOf']}
									}
								}
							)
					else:
						raise ValueError(
							f"Unsupported format: depth 2 element is not a {valid_types} or dict)"
							f"\nOffending value: {el}"
						)

				# ex: add_from_excl_dict(query, 'withTags', {'anyOf': [{'allOf': ["a","b"]}, "3", "1", "2"]})
				# optimize_potentially allows to replace:
				#   '$and': [
				#		{'withTags': {'$not': {'$all': ['a', 'b']}}},
  				#   	{'withTags': {'$ne': '3'}}, {'withTags': {'$ne': '1'}}, {'withTags': {'$ne': '2'}}
				#	]
				# with:
				#   '$and': [
				#		{'withTags': {'$not': {'$all': ['a', 'b']}}},
  				#   	{'withTags': {'$nin': ['3', '1', '2']}}
				#	]
				if len(optimize_potentially) > 1:
					and_list.append(
						{
							field_name: {
								'$nin': [el[field_name]['$ne'] for el in optimize_potentially]
							}
						}
					)
					for el in optimize_potentially:
						and_list.remove(el)

				if len(and_list) == 1:
					query[field_name] = and_list[0][field_name]
				else:
					query['$and'] = and_list

		elif 'oneOf' in arg:
			query[field_name] = arg['oneOf']

		else:
			raise ValueError(
				"Invalid 'arg' keys (must contain either 'anyOf' or 'allOf'" +
				"\nOffending value: %s" % arg
			)

		return query


	@staticmethod	
	def check_allOf(el, in_type: Union[int, str, Tuple]) -> None:
		"""
		:raises: ValueError
		"""
		if 'allOf' not in el:
			raise ValueError(
				"Expected dict with key 'allOf'" + 
				"\nOffending value: %s" % el
			)

		if not AmpelUtils.check_seq_inner_type(el['allOf'], in_type):
			raise ValueError(
				"No further nesting allowed beyond 'allOf'" + 
				"\nOffending value: %s" % el
			)

		if len(el) != 1:
			raise ValueError(
				"'allOf' dict should have only one key" + 
				"\nOffending value: %s" % el
			)


	@staticmethod
	def arg_check(arg, in_type: Union[int, str, Tuple]) -> bool:
		"""
		:raises: ValueError
		"""

		# Be robust
		if arg is None:
			raise ValueError('"arg" is None')

		# Be flexible
		if isinstance(arg, in_type):
			return True

		# Dict must be provided
		if not isinstance(arg, Dict):
			raise ValueError("Parameter 'arg' should be a dict (is %s)" % type(arg))

		# With only one key
		if len(arg) != 1:
			raise ValueError(
				"Invalid 'arg' parameter. Should have only one key ('anyOf' or 'allOf')" +
				"\nOffending value: %s" % arg
			)

		return False
