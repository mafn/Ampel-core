#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/model/AmpelBaseModel.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 30.09.2018
# Last Modified Date: 10.10.2019
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from ampel.common.AmpelUtils import AmpelUtils
from pydantic import BaseModel, BaseConfig, Extra

def to_camel_case(arg: str) -> str:
	"""
	Converts snake_case to camelCase
	:returns: str
	"""
	s = arg.split("_")

	if len(s) == 1:
		return arg
	
	return s[0] + ''.join(
		word.capitalize() for word in s[1:]
	)

class AmpelBaseModel(BaseModel):
	""" """

	class Config(BaseConfig):
		"""
		Raise validation errors if extra fields are present,
		allows camelCase members
		"""
		extra = Extra.forbid
		arbitrary_types_allowed = True
		allow_population_by_alias = True
		alias_generator = to_camel_case


	def get(self, path):
		return AmpelUtils.get_nested_attr(self, path)


	def immutable(self) -> None:
		self.recursive_lock(self)


	@classmethod
	def recursive_lock(cls, model: BaseModel) -> None:
		""" """
		model.Config.allow_mutation=False
		for key in model.fields.keys():
			value = getattr(model, key)
			if isinstance(value, BaseModel):
				cls.recursive_lock(value)
