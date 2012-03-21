"""Specifies the URL class."""

# Standard library imports
from __future__ import print_function
import string
import base64
import sys
import hashlib
import os.path
if sys.version_info[0] >= 3:
	from urllib.parse	import unquote_plus
else:
	from urllib import unquote_plus

# URL Classifications
URL_ERR = "err"
URL_WS = "websocket"
URL_FILE = "file"
URL_DIR = "dir"
URL_SYS = "sys"

_WS_MAGIC_KEY = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_VALID_URL_CHARS = string.ascii_letters + string.digits + "/. -_"

class URL():
	"""Store a URL, convert it to a filename, and classify it.
		
	Classifications:
		URL_ERR - This is an invalid URL
		URL_WS - This URL represents a websocket
		URL_FILE - This URL requests a file download
		URL_DIR - This URL requests a directory listing
		URL_SYS - This URL requests a system file

	Data items:
		websocket_key - set/get - The websocket_key specified in a websocket header
		accept_key - get - The calculated accept key corresponding to websocket_key
		filename - A server filename corresponding to the requested URL
		classification - The classification for the URL, values as described above

	"""

	def __init__(self, settings, urlString=""):
		"""Initialize a URL object.

			settings - a dictionary which requires keys sysdirmagicprefix, basedir,
								 and systemfiledir.

		"""
		self._urlString = urlString
		self._sysdirprefix = settings["sysdirmagicprefix"]
		self._basedir = settings["basedir"]
		self._sysfiledir = settings["systemfiledir"]
		self._filename = None
		self._classification = None
		self.websocket_key = None

	def __str__(self):
		"""Return the text version of the URL."""
		return self._urlString

	__repr__ = __str__

	#TODO: Test for bugs in the classification
	# Resolve the URL into a filename, and classify it.  Cache the result
	def _resolve(self):
		filename, issystemfile = self._build_filename()
		response = URL_ERR
		if filename is None:
			pass
		elif self.websocket_key is not None:
			response = URL_WS
		elif os.path.isfile(filename) and issystemfile:
			response = URL_SYS
		elif os.path.isfile(filename) and not issystemfile:
			response = URL_FILE
		elif os.path.isdir(filename):
			response = URL_DIR
		else:
			filename = None
			response = URL_ERR
		self._filename = filename
		self._classification = response

	# Return the corresponding file name, and if it's a system file
	def _build_filename(self):
		parsed = unquote_plus(self._urlString).lstrip("/ ")
		basedir = self._basedir
		# Handle the case where the URL refers to a system file
		issystemfile = parsed.startswith(self._sysdirprefix)
		if issystemfile:
			parsed = parsed.replace(self._sysdirprefix, "", 1)
			basedir = self._sysfiledir
		filename = None
		if self._validate_contents(parsed):
			filename = os.path.join(basedir, parsed)
		return filename, issystemfile

	# Ensure that the url contains only valid characters
	def _validate_contents(self, parsedurl):
		if (parsedurl.strip(_VALID_URL_CHARS) != "" or 
				(".." in parsedurl) or ("//" in parsedurl)):
			return False
		return True

	# Generate the accept key for the specified websocket key
	def _gen_accept_key(self):
		if self.websocket_key is None:
			return None
		sha = hashlib.sha1()
		sha.update((self.websocket_key + _WS_MAGIC_KEY).encode("ascii"))
		encoded = base64.b64encode(sha.digest()).decode("ascii")
		return encoded

	# Return the filename for the specified URL
	def _get_filename(self):
		if self._filename is None:
			self._resolve()
		return self._filename

	# Return the classification for the specified URL
	def _get_classification(self):
		if self._classification is None:
			self._resolve()
		return self._classification

	accept_key = property(_gen_accept_key)
	filename = property(_get_filename)
	classification = property(_get_classification)
