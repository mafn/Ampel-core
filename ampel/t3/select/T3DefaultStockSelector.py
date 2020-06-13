#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : Ampel-core/ampel/t3/select/T3DefaultStockSelector.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 06.12.2019
# Last Modified Date: 13.06.2020
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from pydantic import validator
from pymongo.cursor import Cursor
from typing import Union, Optional

from ampel.type import ChannelId, Tag
from ampel.query.QueryMatchStock import QueryMatchStock
from ampel.log.AmpelLogger import AmpelLogger
from ampel.log.utils import safe_query_dict
from ampel.t3.select.AbsStockSelector import AbsStockSelector
from ampel.model.operator.AllOf import AllOf
from ampel.model.operator.AnyOf import AnyOf
from ampel.model.operator.OneOf import OneOf
from ampel.model.time.TimeConstraintModel import TimeConstraintModel
from ampel.config.LogicSchemaUtils import LogicSchemaUtils


class T3DefaultStockSelector(AbsStockSelector):
	"""
	Default stock/transient selector used by T3Processor
	Example:
	.. sourcecode:: python\n
	{
		"created": {"after": {"use": "$timeDelta", "arguments": {"days": -40}}},
		"modified": {"after": {"use": "$timeDelta", "arguments": {"days": -1}}},
		"channel": "HU_GP_CLEAN",
		"with_tags": "ZTF",
		"without_tags": "HAS_ERROR"
	}
	"""

	logger: AmpelLogger
	created: Optional[TimeConstraintModel]
	modified: Optional[TimeConstraintModel]
	channel: Optional[Union[ChannelId, AnyOf[ChannelId], AllOf[ChannelId], OneOf[ChannelId]]]
	with_tags: Optional[Union[Tag, AnyOf[Tag], AllOf[Tag], OneOf[Tag]]]
	without_tags: Optional[Union[Tag, AnyOf[Tag], AllOf[Tag], OneOf[Tag]]]


	@validator('channel', 'with_tags', 'without_tags', pre=True, whole=True)
	def cast(cls, v, values, **kwargs):
		""" """
		return LogicSchemaUtils.to_logical_struct(
			v, kwargs['field'].name.split("_")[0]
		)


	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		if self.logger is None:
			raise ValueError("Parameter logger cannot be None")


	# Override/Implement
	def fetch(self) -> Cursor:
		"""
		The returned Iterator is a pymongo Cursor
		"""

		# Build query for matching transients using criteria defined in config
		match_query = QueryMatchStock.build_query(
			channels = self.channel,
			time_created = self.created.get_query_model(db=self.context.db) \
				if self.created else None,
			time_modified = self.modified.get_query_model(db=self.context.db) \
				if self.modified else None,
			with_tags = self.with_tags,
			without_tags = self.without_tags
		)

		self.logger.info("Executing search query", extra=safe_query_dict(match_query))

		# Execute 'find transients' query
		cursor = self.context.db \
			.get_collection('stock') \
			.find(
				match_query,
				{'_id': 1}, # indexed query
				no_cursor_timeout = True, # allow query to live for > 10 minutes
			) \
			.hint('_id_1_channel_1')

		# Count results
		if cursor.count() == 0:
			self.logger.info("No transient matches the given criteria")
			return None

		self.logger.info(
			f"{cursor.count()} transients match search criteria"
		)

		return cursor
