class Error(Exception):
	"""Base class for exceptions in this module."""

	def __init__(self, msg):
		self.msg = msg

class ProtocolError(Error):
	"""Exception raised for errors in the protocol."""

	def __init__(self, msg, response):
		self.msg = msg
		self.response = response

class StateError(Error):
	"""Exception raised when an object cannot perform an operation
		 because it is in an invalid state.
		 
	"""

	def __init__(self, msg, response=None):
		self.msg = msg
		self.response = response