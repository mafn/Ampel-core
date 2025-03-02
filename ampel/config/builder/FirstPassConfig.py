#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File:                Ampel-core/ampel/config/builder/FirstPassConfig.py
# License:             BSD-3-Clause
# Author:              valery brinnel <firstname.lastname@gmail.com>
# Date:                16.10.2019
# Last Modified Date:  18.06.2021
# Last Modified By:    valery brinnel <firstname.lastname@gmail.com>

import json
from typing import Any, Literal
from ampel.log.AmpelLogger import AmpelLogger

from ampel.config.collector.ConfigCollector import ConfigCollector
from ampel.config.collector.LoggingCollector import LoggingCollector
from ampel.config.collector.DBConfigCollector import DBConfigCollector
from ampel.config.collector.UnitConfigCollector import UnitConfigCollector
from ampel.config.collector.AliasConfigCollector import AliasConfigCollector
from ampel.config.collector.ProcessConfigCollector import ProcessConfigCollector
from ampel.config.collector.ChannelConfigCollector import ChannelConfigCollector
from ampel.config.collector.ResourceConfigCollector import ResourceConfigCollector
from ampel.config.collector.ForwardProcessConfigCollector import ForwardProcessConfigCollector

tiers: tuple[Literal[0, 1, 2, 3], ...] = (0, 1, 2, 3)

class FirstPassConfig(dict):
	"""
	Class used to aggregate config pieces into a central configuration dict for ampel.
	"""

	conf_keys: dict[str, None | type[ConfigCollector]] = {
		"mongo": DBConfigCollector,
		"logging": LoggingCollector,
		"channel": ChannelConfigCollector,
		"unit": None,
		"process": None,
		"alias": None,
		"resource": ResourceConfigCollector,
	}

	def __init__(self, logger: AmpelLogger = None, verbose: bool = False, get_env: bool = True) -> None:

		self.logger = AmpelLogger.get_logger() if logger is None else logger

		d: dict[str, Any] = {
			k: Klass(conf_section=k, logger=logger, verbose=verbose)
			for k, Klass in self.conf_keys.items() if Klass
		}

		d['pwd'] = []

		d['unit'] = UnitConfigCollector(conf_section="unit", logger=logger, verbose=verbose, get_env=get_env)

		# Allow process to be defined in root key
		d['process'] = ForwardProcessConfigCollector(
			root_config=self, conf_section="process", # type: ignore
			target_collector_type=ProcessConfigCollector,
			logger=logger, verbose=verbose
		)

		d['alias'] = {}
		for k in tiers:

			d['alias'][f"t{k}"] = AliasConfigCollector(
				conf_section='alias', logger=logger,
				verbose=verbose, tier=k
			)

			# Allow processes to be defined in sub-tier entries already (process.t0, process.t1, ...)
			d['process'][f"t{k}"] = ProcessConfigCollector(
				conf_section='process', logger=logger,
				verbose=verbose, tier=k
			)

		d['process']["ops"] = ProcessConfigCollector(
			conf_section='process', logger=logger,
			verbose=verbose, tier="ops"
		)

		super().__init__(d)


	def unset_errors(self, d: None | dict = None) -> None:
		""" """
		for v in d.values() if d is not None else self.values():
			if isinstance(v, dict):
				if getattr(v, 'has_error', False):
					v.has_error = False # type: ignore
				self.unset_errors(v)


	def has_nested_error(self, d=None, k=None) -> bool:

		ret = False

		for kk, dd in d.items() if d is not None else self.items():
			if isinstance(dd, dict):
				if getattr(dd, 'has_error', False):
					ret = True
					hint = f"(key: '{kk}')" if kk else ""
					self.logger.warn(f"{dd.__class__.__name__} {hint} has errors")
				if self.has_nested_error(dd, kk):
					ret = True

		return ret


	def print(self) -> None:

		if self.has_nested_error():
			self.logger.warn(
				"Warning: error were reported while collecting configurations"
			)

		self.logger.info(json.dumps(self, indent=4))
