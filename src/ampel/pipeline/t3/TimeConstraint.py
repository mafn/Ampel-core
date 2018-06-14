#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/pipeline/t3/TimeConstraint.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 06.06.2018
# Last Modified Date: 06.06.2018
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from datetime import datetime, timedelta
from voluptuous import Schema, Any, Required


class TimeConstraint:
	"""
	* 'from' and 'until': either:
		-> None
		-> datetime.datetime
		-> datetime.timedelta
		-> dict fulfilling TimeConstraint._json_sub_schema criteria

	TimeConstraint._json_sub_schema dict key/value criteria are either:
		* key: 'unixTime', value: float
		* keys 'dateTimeStr' and 'dateTimeFormat' with str values
		* key 'timeDelta', value: dict that will be passed to datetime.timedelta (ex: {'days': -10})
	"""

	_json_sub_schema = Schema(
		Any(
			{Required('timeDelta'): dict},
			{Required('unixTime'): float},
			{
				Required('dateTimeStr'): str, 
				Required('dateTimeFormat'): str
			}
		)
	)

	json_root_schema = Schema(
		Any(
			None,
			{
				"from": Any(None, datetime, timedelta, _json_sub_schema), 
				"until": Any(None, datetime, timedelta, _json_sub_schema)
			}
		)
	)


	@staticmethod
	def from_parameters(time_constraint_dict, time_constraint_obj=None, runs_col=None):
		"""	
		"""	
		if time_constraint_dict is None:
			return None

		TimeConstraint.json_root_schema(time_constraint_dict) # Robustness
		tc = TimeConstraint() if time_constraint_obj is None else time_constraint_obj
		tc.set_from(time_constraint_dict.get('from'), False)
		tc.set_until(time_constraint_dict.get('until'), False)
		return tc


	def __init__(self, parameters=None):
		"""
		parameters: dict instance with keys: 'from' and/or 'until'
		* 'from' and 'until' dict values, either: 
			-> datetime.datetime 
			-> datetime.timedelta 
		   	-> dict fulfilling TimeConstraint._json_sub_schema criteria (see class docstring)
		"""
		self.params = {}

		if parameters is not None:
			self.from_parameters(parameters, self)


	def set_from(self, value, schema_check=True):
		""" """
		if schema_check:
			TimeConstraint._json_sub_schema(value)
		self.params['from'] = value


	def set_until(self, value, schema_check=True):
		""" """
		if schema_check:
			TimeConstraint._json_sub_schema(value)
		self.params['until'] = value


	def has_constraint(self):
		""" """ 
		return len(self.params) > 0

	
	def get(self, param):
		""" 
		param: either 'from' or 'until'
		Schema validation ensures val can be only either None, dict, datetime or timedelta
		"""

		val = self.params.get(param)

		if val is None:
			return None

		if type(val) is datetime:
			return val

		elif type(val) is timedelta:
			return datetime.today() + val

		elif type(val) is dict:

			if 'timeDelta' in val:
				return datetime.today() + timedelta(**val['timeDelta'])

			if '$lastRun' in val:
				raise NotImplementedError("soon...")

			if 'unixTime' in val:
				return datetime.utcfromtimestamp(val['unixTime'])

			if 'dateTimeStr' in val:
				# Schema validation ensures 'dateTimeFormat' is set when 'dateTimeStr' is
				return datetime.strptime(val['dateTimeStr'], ['dateTimeFormat'])

		raise ValueError("Illegal argument")
