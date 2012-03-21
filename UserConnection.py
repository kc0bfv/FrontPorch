# Standard library imports
from __future__ import print_function # For python earlier than 3
import threading
import json
import os.path
import socket
import logging
from datetime import datetime

# Local imports
import URL
import HandleWebsocket
from Error import StateError, ProtocolError

class UserConnection(threading.Thread):
	"""Handle a user connection.  It does its thing and cleans up when done."""
	# These consts tell what type of header to build
	# TODO: Would it make sense to make "header" a class?
	HEAD_404 = "404"
	HEAD_FILE = "file"
	HEAD_HTML = "html"
	HEAD_JS = "js"
	HEAD_CSS = "css"

	def __init__(self, settings, conn, addr):
		"""Setup the handler with a connection and address to handle."""
		threading.Thread.__init__(self)
		self._conn = conn
		self._addr = addr
		self._settings = settings

	def run(self):
		"""Executed when the thread is started"""
		logging.info("%s: Connection Received", self._addr)
		# Close the connection regardless of exceptions
		try:
			self._handle_connection()
		except socket.error:
			logging.error("%s: Connection closed unexpectedly", self._addr)
		except:
			logging.error("%s: Unknown error occurred", self._addr)
			raise
		finally:
			self._conn.close()
			logging.info("%s: Connection Closed", self._addr)

	# Actually handle the connection
	def _handle_connection(self):
		self._conn.settimeout(5)
		try:
			data = self._conn.recv(1024)
			url = self._process_headers(data)
		except socket.error:
			logging.error("%s: Fatal socket timeout", self._addr)
		except ProtocolError:
			logging.error("%s: Invalid headers specified", self._addr)
		else:
			self._respond(url)

	# Figure out what the headers say
	def _process_headers(self, data):
		words = data.split()
		url = None
		# Handle the GET header
		try:
			getlocation = words.index(b"GET")
			# TODO: Unicode URLs?
			urlstring = words[getlocation + 1]
		except (ValueError, IndexError):
			raise ProtocolError("No GET URL specified", "Invalid Headers")
		else:
			url = URL.URL(self._settings, urlstring.decode("ascii"))

		# Handle a websocket key header
		try:
			wskeylocation = words.index(b"Sec-WebSocket-Key:")
			# TODO: Is there a problem with assuming the key is ascii?
			url.websocket_key = words[wskeylocation+1].decode("ascii")
		except ValueError:
			pass  # This was not a websocket connection - no worries!
		except NameError:
			raise StateError("NameError storing websocket info.")
		except IndexError:
			raise ProtocolError("Invalid websocket key specified", "Invalid Headers")

		# Finish up, and raise an error if something strange happened
		if url is None:
			raise StateError("No URL object created.")
		return url

	# Respond to a user's GET request
	def _respond(self, url):
		if url.classification == URL.URL_FILE:
			logging.info("%s: Requested File %s", self._addr, url)
			self._send_file(url.filename)
		elif url.classification == URL.URL_DIR:
			logging.info("%s: Requested Directory %s", self._addr, url)
			self._send_dir(url.filename)
		elif url.classification == URL.URL_WS:
			# Handle an upload - all websockets are uploads, all uploads are websocks
			logging.info("%s: Requested Upload %s", self._addr, url)
			ws = HandleWebsocket.HandleWebsocket(self._conn, self._addr, url)
			ws.handle_websocket()
		elif url.classification == URL.URL_SYS:
			logging.info("%s: Requested System File %s", self._addr, url)
			self._send_sys(url.filename)
		else:
			logging.error("%s: Error with Url Request %s", self._addr, url)
			if url.websocket_key is not None:
				ws = HandleWebsocket(self._conn, self._addr, url)
				ws.handle_invalid_url()
			else:
				self._send_error()

	# Send the user a system file - build the header, send the file
	def _send_sys(self, filename):
		headertype = self.HEAD_HTML
		# TODO: Use better, or more, filetype determination
		if filename.endswith(".js"):
			headertype = self.HEAD_JS
		elif filename.endswith(".css"):
			headertype = self.HEAD_CSS
		header = self._build_header(headertype, filename)
		self._send_file_contents(header, filename)
	
	# Send the user a file download - build header, send the file
	def _send_file(self, filename):
		header = self._build_header(self.HEAD_FILE, filename)
		self._send_file_contents(header, filename)

	# Send the user a directory listing - build header, send dir list html file
	def _send_dir(self, filename):
		dirhtmlfile = self._settings["dirhtmlfile"]
		header = self._build_header(self.HEAD_HTML)
		jsondata = self._build_dir_json(filename)
		# The directory listing HTML file needs some of this to wrap it up
		toappend = ("<script type=\"text/javascript\">\n"
							  "window.onload = processData(" + jsondata + ")\n"
							  "</script>\n</body>\n</html>")
		self._send_file_contents(header, dirhtmlfile, toappend)

	# Send the user an error file - build header, send 404 HTML file
	def _send_error(self):
		errorfile = self._settings["errorfile"]
		header = self._build_header(self.HEAD_404)
		self._send_file_contents(header, errorfile)

	# Build a header to spec
	def _build_header(self, headertype, filename=""):
		"""Build a specific type of header.
		
		headertype specificaiton:
		HEAD_404 is for 404 errors
		HEAD_FILE is the header for file download, it uses filename (others don't)
		HEAD_HTML is the header for html file download

		"""
		responsecode = "200 OK"
		contenttype = ""
		additional = None
		if headertype == self.HEAD_404:
			responsecode = "404 Not Found"
			contenttype = "text/html; charset=UTF-8"
		elif headertype == self.HEAD_FILE:
			contenttype = "application/octet-stream"
			fixedfn = os.path.basename(filename)
			additional = ("Content-Disposition: attachment; "
									  "filename=\"" + fixedfn + "\"")
		elif headertype == self.HEAD_HTML:
			contenttype = "text/html; charset=UTF-8"
			# No caching settings set.  It's for directory contents right now
		elif headertype == self.HEAD_JS:
			contenttype = "text/javascript"
			additional = self._get_expiry_date()
		elif headertype == self.HEAD_CSS:
			contenttype = "text/css"
			additional = self._get_expiry_date()
		header = ("HTTP/1.1 " + responsecode + "\r\n" + "Content-Type: " +
							contenttype + "\r\n" + "Connection: close\r\n")
		if additional is not None:
			header += additional + "\r\n"
		return header

	# Return an expires header for 1 year from now.  This enables client caching
	def _get_expiry_date(self):
		curdatetime = datetime.now()
		curdatetime = curdatetime.replace(curdatetime.year+1)
		return "Expires: " + curdatetime.strftime("%a, %d %b %Y %H:%M:%S GMT")

	# Represent directory contents as a JSON string
	def _build_dir_json(self, dirname):
		"""Build the JSON representation of a directory's contents
			
		JSON Format: { "dirname": "directory name here", "contents":
									[{"filename":"file name here", "fileurl":"file url here",
										"type":"dir, file or other", "dateaccessed":
										"date created here", "datemodified":"date modified here",
										"size":sizebyteshere}] }
											
		"""
		# Setup a list of everything in the directory to parse through later
		dirlisting = list()
		basedir = self._settings["basedir"]
		# Remove local file system directory info from the dir name
		cleandirname = "/" + dirname.replace(basedir, "", 1).strip("/ ")
		# Get the /'s right at beginning and end of the clean directory name
		if cleandirname != "/":
			cleandirname += "/"
			# Allow user to go up a dir if we're not at the virtual root
			dirlisting.append("..") 
		# Add all the directory's files to the directory listing
		dirlisting.extend(os.listdir(dirname))

		# Peruse the directory contents, build the JSON data for each file
		contents = list()
		for filename in dirlisting:
			# Normpath will replace ".." with the parent directory
			fullpath = os.path.normpath(os.path.join(dirname, filename))
			# Normpath now replaces ".." with the parent virtual directory
			fileurl = os.path.normpath(cleandirname + filename)
			filestat = os.stat(fullpath)
			filetype = "other"
			if os.path.isfile(fullpath):
				filetype = "file"
			elif os.path.isdir(fullpath):
				filetype = "dir"
			accessdatetime = datetime.fromtimestamp(filestat.st_atime)
			modifydatetime = datetime.fromtimestamp(filestat.st_mtime)
			accesstime = accessdatetime.strftime("%d %b %Y %H:%M:%S")
			modifytime = modifydatetime.strftime("%d %b %Y %H:%M:%S")
			# Build a dictionary representing the file
			fileinfo = {"filename": filename, "fileurl": fileurl, "type": filetype,
									"dateaccessed": accesstime, "datemodified": modifytime,
									"size": filestat.st_size}
			contents.append(fileinfo)
		# Put the file JSON together in this nice package dictionary
		finaldict = {"dirname": cleandirname, "contents": contents}
		return json.dumps(finaldict)

	# Send a header, fill in the size, send a file's contents too
	# TODO: throw a custom type of exception so it can be handled at top level
	def _send_file_contents(self, header, filename, append=None):
		size = os.path.getsize(filename)
		if append is not None:
			size += len(append)
		# Append the content-length to the header
		header += "Content-Length: {0:d}\r\n\r\n".format(size)
		self._conn.sendall(header.encode())
		# Send the file in 4 kb chunks
		with open(filename, 'rb') as f:
			data = f.read(4096)
			while data != b"":
				self._conn.sendall(data)
				data = f.read(4096)
		# Append the trailer, if one was specified
		if append is not None:
			self._conn.sendall(append.encode())
