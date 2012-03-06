from __future__ import print_function #Make print work correctly prior to python 3

from string import ascii_letters, digits
import base64, sys, hashlib, os.path

if sys.version_info[0] >= 3:
	import urllib.parse	#The library got renamed in python3
else:
	import urllib

class URL():
	"""Processes URLs"""
	valid_chars = ascii_letters + digits + "/. -_"
	URL_ERR = "err"
	URL_WS = "websocket"
	URL_FILE = "file"
	URL_DIR = "dir"
	URL_SYS = "sys"	#TODO: implement system files - these are html or js or css or whatever that are in a certain folder

	_websocket = None	#This var stores whether this was a websocket url or not
	_key = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"	#This is the protocol's magic value

	def __init__(self, settings, urlString=""):
		self._urlString = urlString
		self._settings = settings

	def is_empty(self):
		return self._urlString == ""
	
	def set(self, urlString):
		self._urlString = urlString

	def __str__(self):
		return self._urlString

	def __repr__(self):
		return self._urlString
	
	#TODO: Test for bugs in the classification
	def resolve(self):
		filename, isserverfile = self.build_filename()
		response = self.URL_ERR
		if filename is None:
			pass	#This happens when the URL was invalid
		elif self.get_ws_key() is not None:
			response = self.URL_WS	#Being a websocket overrides others for now.  Don't check for file presence
		elif not os.path.exists(filename):	#See if the file/directory referenced exists
			filename = None
			response = self.URL_ERR
		elif os.path.isfile(filename):
			if isserverfile:
				response = self.URL_SYS
			else:
				response = self.URL_FILE
		elif os.path.isdir(filename):
			response = self.URL_DIR
		else:
			response = self.URL_ERR
		return filename, response

	def validate_contents(self, parsedurl):
		retval = True
		for char in parsedurl:	#Make sure all the chars in the url are permitted
			if char not in self.valid_chars:
				retval = False
		if (".." in parsedurl) or ("//" in parsedurl):	#Do not permit multiple . or / in a row
			retval = False
		return retval

	def build_filename(self):
		isserverfile = False
		sysdirprefix = self._settings["sysdirmagicprefix"]
		basedir = self._settings["basedir"]
		global sys
		if sys.version_info[0] >= 3:
			parsed = urllib.parse.unquote_plus(self._urlString).lstrip("/ ")
		else:
			parsed = urllib.unquote_plus(self._urlString).lstrip("/ ")
		if parsed.startswith(sysdirprefix):	#If this is a request for a system file...
			parsed = parsed.replace(sysdirprefix, "", 1)	#Remove that part of the filename
			isserverfile = True
			basedir = self._settings["systemfiledir"]
		filename = None
		if self.validate_contents(parsed):
			filename = os.path.join(basedir, parsed)
		return filename, isserverfile

	def set_ws_key(self, key=None):
		"""Set the websocket key if this is a websocket url.  Call with no parameter to unset the key."""
		self._websocket = key

	def get_ws_key(self):
		return self._websocket

	def gen_ws_accept_key(self):
		sha = hashlib.sha1()
		sha.update(self._websocket + self._key)
		encoded = base64.b64encode(sha.digest())
		return encoded
