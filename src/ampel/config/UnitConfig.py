#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/config/UnitConfig.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 26.09.2019
# Last Modified Date: 04.10.2019
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from pydantic import BaseModel
from typing import Dict, Union, List
from ampel.common.docstringutils import gendocstring
from ampel.config.AmpelModelExtension import AmpelModelExtension

@gendocstring
class UnitConfig(AmpelModelExtension):
	"""
	run_config types:
	* None -> no run config
	* str -> a corresponding alias key must match the provided string
	* int -> a corresponding runConfig key must match the provided integer
	* Dict -> run config parameters are provided directly
	"""
	unit_id: str
	run_config: Union[None, int, str, Dict] = None
	override: Union[None, Dict] = None
	resources: Union[None, List[str]] = None
