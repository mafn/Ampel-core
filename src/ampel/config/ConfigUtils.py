#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/config/ConfigUtils.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 06.10.2018
# Last Modified Date: 10.12.2019
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from typing import Dict, List, Callable, Union, Optional
from ampel.db.DBUtils import DBUtils
from ampel.typing import StrictIterable
from ampel.model.operator.AnyOf import AnyOf
from ampel.model.operator.AllOf import AllOf
from ampel.model.operator.OneOf import OneOf
from ampel.common.AmpelUtils import AmpelUtils


class ConfigUtils:
	""" """

	@classmethod
	def has_nested_type(cls, obj, target_type, strict=True):
		"""
		:param obj: object instance (dict/list/set/tuple)
		:param type target_type: example: ReadOnlyDict/list
		"""

		if strict: 
			# pylint: disable=unidiomatic-typecheck
			if type(obj) is target_type:
				return True
		else:
			if isinstance(obj, target_type):
				return True

		if isinstance(obj, dict):
			for el in obj.values():
				if cls.has_nested_type(el, target_type):
					return True

		elif isinstance(obj, StrictIterable):
			for el in obj:
				if cls.has_nested_type(el, target_type):
					return True

		return False


	@classmethod
	def flatten_dict(cls, d, separator='.'):
		""" 
		Unlike the flatten_dict method from AmpelUtils, 
		this version converts list into dicts as well.

		Illustration:
		In []: flatten_dict({'a': [{'b':{'f':2}}, {'c':2}], 'd': {'e':1}})
		Out[]: {'a.0.b.f': 2, 'a.1.c': 2, 'd.e': 1}
		"""
		out = {}
		for k, v in d.items():
			if isinstance(v, dict):
				for kk, vv in cls.flatten_dict(v, separator=separator).items():
					out["%s%s%s" % (k, separator, kk)] = vv
			elif isinstance(v, list):
				for kk, vv in cls.flatten_dict(cls.list_to_dict(v), separator=separator).items():
					out["%s%s%s" % (k, separator, kk)] = vv
			else:
				out[k] = v

		return out


	@staticmethod
	def list_to_dict(l):
		""" """
		return {i: l[i] for i in range(len(l))}


	@classmethod
	def unflatten_dict(cls, d, separator='.'):		
		""" 
		Unlike the unflatten_dict method from AmpelUtils, 
		this version restores dict-encoded lists.

		Illustration:
		In []: unflatten_dict({'a.0.b.f': 2, 'a.1.c': 2, 'd.e': 1})
		Out[]: {'a': [{'b': {'f': 2}}, {'c': 2}], 'd': {'e': 1}}
		"""

		out = AmpelUtils.unflatten_dict(d)
		for k, v in out.items():
			try:
				# pylint: disable=expression-not-assigned
				[int(el) for el in v]
				out[k] = [cls.unflatten_dict(out[k][el], separator) for el in v]
			except Exception:
				pass
		return out


	@classmethod
	def walk_and_process_dict(
		cls, arg: Union[Dict, List], callback: Callable, match: List[str], path: str = None, **kwargs
	) -> None:
		"""
		callback is called with 4 arguments:
		1) the path of the possibly nested entry. Ex: "processor.initConfig.select" or "processor"
		2) the matching key (from list 'match'). Ex: 'initConfig'
		3) the matching (sub) dict
		4) the **kwargs provided to this method

		Simplest callback function:
		def my_callback(path, k, d):
			print(f"{path} -> {k}: {d}\n")
		"""

		if isinstance(arg, list):
			for i, el in enumerate(arg):
				cls.walk_and_process_dict(
					el, callback, match, f"{path}.{i}" if path else f"{i}", **kwargs
				)

		if isinstance(arg, dict):

			for k, v in arg.items():

				if k in match:
					callback(path, k, arg, **kwargs)

				if isinstance(v, dict):
					cls.walk_and_process_dict(
						v, callback, match, f"{path}.{k}" if path else f"{k}", **kwargs
					)

				if isinstance(v, list):
					for i, el in enumerate(v):
						cls.walk_and_process_dict(
							el, callback, match, f"{path}.{k}" if path else f"{k}", **kwargs
						)


	@staticmethod
	def set_by_path(mapping, path, val, delimiter='.', create=True) -> bool:
		"""
		:param create: whether to create directory sub-structures if they do not exits 
		(in this case, this method will alawys return False)
		:returns: False if the key was successfully set, True otherwise
		"""
		d = mapping
		keys = path.split(delimiter)
		l = len(keys) - 1
		for i, k in enumerate(keys):
			if k not in d:
				if not create:
					return True
				d[k] = {}
			if i == l:
				d[k] = val
				return False
			d = d[k]
		return True


	@staticmethod
	def del_by_path(mapping, path, delimiter='.') -> bool:
		"""
		:returns: False if the key was successfully deleted, True otherwise
		"""
		d = mapping
		keys = path.split(delimiter)
		l = len(keys) - 1
		for i, k in enumerate(keys):
			if k not in d:
				return True
			if i == l:
				del d[k]
				return False
			d = d[k]
		return True


	@staticmethod
	def hash_schema(
		arg: Optional[Union[str, Dict, AllOf, AnyOf, OneOf]]
	) -> Union[int, Dict]:
		"""
		Converts dict schema containing str representation of tags into 
		a dict schema containing hashed values (int64).

		:param arg: schema dict. \
		See :obj:`QueryMatchSchema <ampel.query.QueryMatchSchema>` \
		docstring for more details

		examples:
		FlagUtils.hash_schema("aa")
		FlagUtils.hash_schema({'allOf': ["aa", "bb"]})
		FlagUtils.hash_schema({'anyOf': ["aa", "bb"]})
		FlagUtils.hash_schema({'anyOf': [{'allOf': ["aa", 'bb']}, "cc"]})

		:returns: new schema dict where tag elements are integers
		"""

		out={}
		
		if isinstance(arg, str):
			return DBUtils.b2_hash(arg)

		if isinstance(arg, (AllOf, AnyOf, OneOf)):
			arg = arg.dict()

		if isinstance(arg, dict):

			if "anyOf" in arg:
				if AmpelUtils.check_seq_inner_type(arg['anyOf'], str):
					out['anyOf'] = [DBUtils.b2_hash(el) for el in arg['anyOf']]
				else:
					out['anyOf'] = []
					for el in arg['anyOf']:
						if isinstance(el, str):
							out['anyOf'].append(DBUtils.b2_hash(el))
						elif isinstance(el, dict):
							if 'allOf' not in el:
								raise ValueError("Unsupported format (1)")
							out['anyOf'].append(
								{'allOf': [DBUtils.b2_hash(ell) for ell in el['allOf']]}
							)
						else:
							raise ValueError("Unsupported format (type: %s)" % type(el))
	
			elif 'allOf' in arg:
				out['allOf'] = [DBUtils.b2_hash(el) for el in arg['allOf']]

			elif 'oneOf' in arg:
				out['oneOf'] = [DBUtils.b2_hash(el) for el in arg['oneOf']]
		else:
			raise ValueError("Unsupported format (%s)" % type(arg))
		
		return out
