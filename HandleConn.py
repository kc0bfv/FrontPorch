from __future__ import print_function #Make print work correctly prior to python 3

import threading, json, os.path, socket
from datetime import datetime

from URL import URL

class HandleConn(threading.Thread):
	"""Handle a user connection.  This is threaded.  It does its thing and cleans up when done."""
	HEAD_404 = "404"	#These things tell what type of header to build
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
		"""Handle everything about the connection, clean up when done."""
		data = ""
		try:
			data = self._conn.recv(1024)
		except socket.error:
			print("Socket timeout: ", self._addr)
		url = None
		for line in data.splitlines():	#Split the data up into lines and check each
			words = line.split()	#Split a line into words
			for i, word in enumerate(words):	#Iterate over the words, store index in i
				if word == b"GET" and url is None:	#Set URL, and only allow url to be set once
					url = URL(self._settings, words[i+1].decode("ascii"))	#TODO: is it ok to assume the URL is ascii?
					break	#Finish processing this line
				elif word == b"Sec-WebSocket-Key:" and url is not None:	#Test for websockets
					url.set_ws_key(words[i+1].decode("ascii")) #This assumes the key is ascii...
					break	#Finish processing the line
		if url is not None:
			self.respond(url)
		self._conn.close()
		print("Connection closed: ", self._addr)

	def respond(self, url):
		"""Respond to a GET request for a url."""
		filename, c = url.resolve()
		if c == url.URL_FILE:	#URL was for a file download
			print(self._addr, " requested file ", url)
			self.send_file(filename)
		elif c == url.URL_DIR:	#URL was for a directory listing
			print(self._addr, " requested directory ", url)
			self.send_dir(filename)
		elif c == url.URL_WS:	#Request is a websocket request
			print(self._addr, " requested upload ", url)	#All websocket requests are uploads
			ws = HandleWebsocket(self._conn, self._addr, url, filename)
			ws.handle_websocket()
		elif c == url.URL_SYS:	#Request is a system file
			print(self._addr, " requested system file ", url)	#All websocket requests are uploads
			self.send_sys(filename)
		else:	#Some error in classification
			print(self._addr, " had an error with url request ", url)
			self.send_error()

	def send_sys(self, filename):
		headertype = self.HEAD_HTML
		if filename.endswith(".js"):	#Use a naive filetype detection
			headertype = self.HEAD_JS
		elif filename.endswith(".css"):
			headertype = self.HEAD_CSS
		header = self.build_header(headertype, filename)
		self.send_file_contents(header, filename)
	
	def send_file(self, filename):
		"""Send the user a file download."""
		header = self.build_header(self.HEAD_FILE, filename)	#Build the header
		self.send_file_contents(header, filename)	#Send the file and header

	def send_dir(self, filename):
		"""Send the user a directory listing."""
		dirhtmlfile = self._settings["dirhtmlfile"]
		header = self.build_header(self.HEAD_HTML)	#Build the header
		jsondata = self.build_dir_json(filename)	#Build the directory listing
		toappend = "<script type=\"text/javascript\">\nwindow.onload = processData(" \
			+ jsondata + ")\n</script>\n</body>\n</html>"	#The listing HTML file needs the listing appended
		self.send_file_contents(header, dirhtmlfile, toappend)	#Send the header, HTML file, and listing

	def send_error(self):
		"""Send the error file.  The only one handled right now is a 404."""
		errorfile = self._settings["errorfile"]
		header = self.build_header(self.HEAD_404)
		self.send_file_contents(header, errorfile)

	def build_header(self, headertype, filename=""):
		"""Build a specific type of header.
		
		headertype specificaiton:
		HEAD_404 is for 404 errors
		HEAD_FILE is the header for a file download, and uses filename (others do not)
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
			additional = "Content-Disposition: attachment; filename=\"" + fixedfn + "\""
		elif headertype == self.HEAD_HTML:
			contenttype = "text/html; charset=UTF-8"
			#Don't cache this one.  It typically represents directory contents
		elif headertype == self.HEAD_JS:
			contenttype = "text/javascript"
			additional = self.get_expiry_date()
		elif headertype == self.HEAD_CSS:
			contenttype = "text/css"
			additional = self.get_expiry_date()
		header = "HTTP/1.1 " + responsecode + "\r\n" + "Content-Type: " + contenttype + "\r\n"
		if additional is not None:
			header += additional + "\r\n"
		return header

	def get_expiry_date(self):
		"""Return an Expires header for approximately 1 year from now"""
		curdatetime = datetime.now()
		curdatetime = curdatetime.replace(curdatetime.year+1)
		return "Expires: " + curdatetime.strftime("%a, %d %b %Y %H:%M:%S GMT")

	def build_dir_json(self, dirname):
		"""Build the JSON representation of a directory's contents
			
			JSON Format: { "dirname": "directory name here", "contents":[{"filename":"file name here",
				 "fileurl":"file url here", "type":"dir, file or other", "dateaccessed":"date created here",
				 "datemodified":"date modified here", "size":sizebyteshere}] } """
		dirlisting = []
		basedir = self._settings["basedir"]
		cleandirname = "/" + dirname.replace(basedir, "", 1).strip("/ ")	#Ready dir name for output, remove basedir
		if cleandirname != "/":	#Do some things if we're not in the root dir
			cleandirname += "/"	#Append a / to the name for filename construction
			dirlisting.append("..")	#Build a way to go up a dir level
		dirlisting.extend(os.listdir(dirname))	#Add dir contents to dirlisting - may already contain ".."
		contents = []
		for filename in dirlisting:
			fullpath = os.path.normpath(os.path.join(dirname, filename))	#Build the server's path - norm out ".."
			fileurl = os.path.normpath(cleandirname + filename)	#Build url for client - norm out ".."
			filestat = os.stat(fullpath)	#Get the file info
			filetype = ""	#Determine the file's type
			if os.path.isfile(fullpath):
				filetype = "file"
			elif os.path.isdir(fullpath):
				filetype = "dir"
			else:
				filetype = "other"
			#Format Times
			accesstime = datetime.fromtimestamp(filestat.st_atime).strftime("%d %b %Y %H:%M:%S")
			modifytime = datetime.fromtimestamp(filestat.st_mtime).strftime("%d %b %Y %H:%M:%S")
			#Build a dictionary representing the file
			fileinfo = {"filename": filename, "fileurl": fileurl, "type": filetype,
				"dateaccessed": accesstime, "datemodified": modifytime, "size": filestat.st_size}
			contents.append(fileinfo)	#Append it to the list of all files
		finaldict = {"dirname": cleandirname, "contents": contents}	#Build the full dictionary
		return json.dumps(finaldict)

	def send_file_contents(self, header, filename, append=""):
		"""Complete an HTTP transaction - send a header, file's contents, and perhaps something at the end"""
		size = os.path.getsize(filename)
		header += "Content-Length: {0:d}\r\n\r\n".format(size+len(append))	#The header needs the content size
		self._conn.send(header.encode())	#Send the header
		with open(filename, 'rb') as f:	#Send the file in 1KB chunks
			data = f.read(1024)
			while data != b"":
				self._conn.send(data)
				data = f.read(1024)
		if append != "":
			self._conn.send(append.encode())	#Send the trailer, generally the directory listing right now
