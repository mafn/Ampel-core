
from ampel.flags.FlagUtils import FlagUtils
from ampel.flags.CompoundFlags import CompoundFlags
from types import MappingProxyType


class Compound:
	"""
	Wrapper class around a dict instance ususally originating from pymongo DB.
	An instance of this class can be frozen (by setting read_only to True) 
	which should prevent unwilling modifications from happening.
	More precisely, it means:
		-> the internal dict will be casted into an MappingProxyType
		-> a change of any existing internal variable of this instance will not be possible
		-> the creation of new instance variables won't be possible as well
	"""

	def __init__(self, db_doc, read_only=True):
		"""
		'db_doc': dict instance (usually resulting from a pymongo DB query)
		'read_only': if True, db_doc will be casted to MappingProxyType and this class will be frozen
		"""

		# Convert db flag to python enum flag
		#self.flags = FlagUtils.dbflag_to_enumflag(
		#	db_doc['alFlags'], CompoundFlags
		#)

		self.id = db_doc['_id']
		self.tier = db_doc['tier']
		self.ppCompId = db_doc['ppCompId']
		self.lastppdt = db_doc['lastppdt']

		# Check wether to freeze this instance.
		if read_only:
			self.content = tuple(MappingProxyType(el) for el in db_doc['comp'])
			self.__isfrozen = True
		else:
			self.content = db_doc['comp']


	def __setattr__(self, key, value):
		"""
		Overrride python's default __setattr__ method to enable frozen instances
		"""
		# '_PhotoPoint__isfrozen' and not simply '__isfrozen' because: 'Private name mangling'
		if getattr(self, "_Compound__isfrozen", None) is not None:
			raise TypeError( "%r is a frozen instance " % self )
		object.__setattr__(self, key, value)


	#def has_flags(self, arg_flags):
	#	return arg_flags in self.flags


	def get_id(self):
		"""
		"""
		return self.id
