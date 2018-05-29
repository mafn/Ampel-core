#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/base/Transient.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 13.01.2018
# Last Modified Date: 29.05.2018
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from ampel.pipeline.logging.LoggingUtils import LoggingUtils
from ampel.flags.AlDocTypes import AlDocTypes
from types import MappingProxyType
import logging


class Transient:
	"""
	Container class referencing:
	-> possibly various instances of objects:
		* ampel.base.PhotoPoint
		* ampel.base.UpperLimit
		* ampel.base.Compound
		* ampel.base.LightCurve
		* ampel.base.T2Record

	Instances of this class are typically generated 
	by TransientLoader and provided to T3 modules.
	"""

	def __init__(self, tran_id, logger=None):
		"""
		Parameters:
		* tran_id: transient id (string)
		* logger: logger instance from python module 'logging'
		"""
		self.logger = LoggingUtils.get_logger() if logger is None else logger
		self.tran_id = tran_id
		self.photopoints = {}
		self.upperlimits = {}
		self.compounds = {}
		self.lightcurves = {}
		self.science_records = {}
		self.latest_lightcurve = None
		self.latest_compound_id = None
		self.flags = None
		self.created = None
		self.last_modified = None


	def set_parameter(self, name, value):
		""" """
		setattr(self, name, value)


	def set_parameters(self, plist):
		""" """
		for el in plist:
			setattr(self, el[0], el[1])


	def get_flags(self):
		""" """
		return self.flags


	def add_lightcurve(self, lightcurve):
		"""
		argument 'lightcurve' must be an instance of ampel.base.LightCurve
		"""
		self.lightcurves[getattr(lightcurve, 'id')] = lightcurve


	def get_latest_lightcurve(self):
		""" 
		"""
		if self.latest_compound_id is None:
			self.logger.warn('Request for latest lightcurve cannot complete (latest compound id not set)')
			return None

		if len(self.lightcurves) == 0:
			self.logger.warn('Request for latest lightcurve cannot complete (No lightcurve was loaded)')
			return None

		if self.latest_compound_id not in self.lightcurves:
			self.logger.warn(
				'Request for latest lightcurve cannot complete (Lightcurve %s not found)' % 
				self.latest_compound_id		
			)
			return None

		return self.lightcurves[self.latest_compound_id]


	def get_latest_compound_id(self):
		""" """
		if self.latest_compound_id is None:
			self.logger.warn('Request for latest compound id cannot complete (not set)')
			return None

		return self.latest_compound_id


	def set_latest_compound_id(self, comp_id):
		""" """
		self.latest_compound_id = comp_id


	def get_lightcurves(self):
		""" """
		return self.lightcurves

	
	def get_lightcurve(self, lightcurve_id):
		""" """
		return self.lightcurves[lightcurve_id]


	def add_photopoint(self, photopoint):
		""" argument 'photopoint' must be an instance of ampel.base.PhotoPoint """
		self.photopoints[photopoint.get_id()] = photopoint


	def get_photopoint(self, photopoint_id):
		""" 
		argument 'photopoint_id' must be a python integer 
		"""
		if photopoint_id not in self.photopoints:
			return None

		return self.photopoints[photopoint_id]


	def get_photopoints(self, copy=False):
		"""
		Returns a dict instance
		-> key: photopoint id
		-> value: instance of ampel.base.PhotoPoint
		-> dict can be empty if PhotoPoints were not loaded 
		   (see load_options of class TransientLoader)
		"""
		return self.photopoints if copy is False else self.photopoints.copy()
	

	def add_upperlimit(self, upperlimit):
		""" argument 'upperlimit' must be an instance of ampel.base.UpperLimit """
		self.upperlimits[upperlimit.get_id()] = upperlimit


	def get_upperlimit(self, upperlimit_id):
		""" argument 'upperlimit_id' must be a python integer """
		if upperlimit_id not in self.upperlimits:
			return None

		return self.upperlimits[upperlimit_id]


	def get_upperlimits(self, copy=False):
		"""
		Returns a dict instance
		-> key: upperlimit id
		-> value: instance of ampel.base.UpperLimit
		-> dict can be empty if UpperLimits were not loaded 
		   (see load_options of class TransientLoader)
		"""
		return self.upperlimits if copy is False else self.upperlimits.copy()


	def add_compound(self, compound):
		""" argument 'compound' must be an instance of ampel.base.Compound"""
		self.compounds[compound.get_id()] = compound


	def get_compound(self, compound_id):
		""" 
		argument 'compound_id' must be a python integer 
		"""
		if compound_id not in self.compounds:
			return None

		return self.compounds[compound_id]


	def get_compounds(self, copy=False):
		"""
		Returns a dict instance
		-> key: compound id
		-> value: instance of ampel.base.Compound
		-> dict can be empty if Compounds were not loaded 
		   (see load_options of class TransientLoader)
		"""
		return self.compounds if copy is False else self.compounds.copy()


	def add_science_record(self, record):
		"""
		"""
		t2_unit_id = record.get_t2_unit_id()

		if not t2_unit_id in self.science_records:
			self.science_records[t2_unit_id] = []

		self.science_records[t2_unit_id].append(record)


	def get_science_records(self, t2_unit_id=None, flatten=False):
		""" 
		"""
		if t2_unit_id is None:
			if flatten is False:
				return self.science_records
			else:
				records = []
				for key in self.science_records.keys():
					records += self.science_records[key]
				return records
		else: 
			if not t2_unit_id in self.science_records:
				return None

			return self.science_records[t2_unit_id]


	def set_read_only(self):
		"""
		Convert internal Photopoint / Upperlimits / Lightcurves and Science Records 
		to immutable dicts and freeze this class (class members will not be chang anymore).
		Please note that only internal dicts *referencing* these object are cast to immutable dicts.
		The dicts containes by those objects ('content' of Photopoint for example) are not changed.
		It means that these objects (Photopoints...) must be instantiated with read_only=True 
		before they are added to this class (methods add_photopoints, add_upperlimits....)
		"""
		self.photopoints = MappingProxyType(self.photopoints)
		self.upperlimits = MappingProxyType(self.upperlimits)
		self.compounds = MappingProxyType(self.compounds)
		self.lightcurves = MappingProxyType(self.lightcurves)
		self.science_records = MappingProxyType(self.science_records)
		self.__isfrozen = True


	def new_channel_register(self):
		"""
		ChannelRegister is used when transient instances need to be forked and trim down
		"""
		from ampel.pipeline.t3.ChannelRegister import ChannelRegister
		self.channel_register = ChannelRegister(self.tran_id)
		return self.channel_register


	def __setattr__(self, key, value):
		"""
		Overrrides python's default __setattr__ method to enable frozen instances
		"""
		# '_Transient__isfrozen' and not simply '__isfrozen' due to 'Private name mangling'
		if getattr(self, "_Transient__isfrozen", None) is not None:
			raise TypeError("%r is a frozen instance " % self)

		object.__setattr__(self, key, value)
