#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/model/db/AmpelColData.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 19.10.2019
# Last Modified Date: 19.10.2019
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from pydantic import BaseModel
from typing import List, Optional, Dict
from ampel.model.db.IndexData import IndexData
from ampel.model.BetterConfigDefaults import BetterConfigDefaults

class AmpelColData(BaseModel):
	""" """
	Config = BetterConfigDefaults

	name: str
	indexes: Optional[List[IndexData]]
	args: Dict = None
