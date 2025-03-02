#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File:                Ampel-core/ampel/abstract/AbsChannelTemplate.py
# License:             BSD-3-Clause
# Author:              valery brinnel <firstname.lastname@gmail.com>
# Date:                27.10.2019
# Last Modified Date:  07.04.2020
# Last Modified By:    valery brinnel <firstname.lastname@gmail.com>

from typing import Any
from ampel.base.decorator import abstractmethod
from ampel.log.AmpelLogger import AmpelLogger
from ampel.model.ChannelModel import ChannelModel
from ampel.config.builder.FirstPassConfig import FirstPassConfig
from ampel.config.builder.AbsConfigTemplate import AbsConfigTemplate


class AbsChannelTemplate(AbsConfigTemplate, ChannelModel, abstract=True):


	@abstractmethod
	def get_channel(self, logger: AmpelLogger) -> dict[str, Any]:
		...

	@abstractmethod
	def get_processes(self, logger: AmpelLogger, first_pass_config: FirstPassConfig) -> list[dict[str, Any]]:
		...

	def transfer_channel_parameters(self, process: dict[str, Any]) -> dict[str, Any]:
		"""
		Adds channel defined information to the provided process:
		'active, 'distrib', 'source' and 'channel'
		Note: a shallow copy of the input dict is made
		"""
		p = process.copy()

		# Inactivated channels cannot have active processes
		if not self.active:
			p['active'] = False

		# Processes inherit channel distribution/file/name infos
		p['distrib'] = self.distrib
		p['source'] = self.source
		p['channel'] = self.channel

		return p
