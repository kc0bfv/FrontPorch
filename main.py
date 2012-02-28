#! /usr/bin/env python

import socket
import threading
import signal
import urllib
import os.path
from string import ascii_letters, digits
import json
import hashlib
import base64
import struct
from datetime import datetime

listenport = 8080
listenhost = ""
interrupted = False	#Let it handle a ctrl-c
basedir = "/Users/finity/Documents/Code/DistSysProj2/testroot/"	#Temporarily store the basedir here
errorfile = "/Users/finity/Documents/Code/DistSysProj2/404.html"
dirhtmlfile = "/Users/finity/Documents/Code/DistSysProj2/dir.html"

def main():
	"""Main program, kicks off other execution.  Setup for execution at end of file."""
	global listenport, listenhost
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)	#Setup an ipv4 TCP socket
	s.bind((listenhost, listenport))
	s.listen(1)	#Start listening for a connection

	signal.signal(signal.SIGINT, sigint_handler)	#Setup the handler for ctrl-c
	global interrupted
	while not interrupted:
		try:
			conn, addr = s.accept()	#Block while waiting for a connection
			print "Connection received from: ", addr
			handler = HandleConn(conn, addr)
			handler.start()
		except socket.error:	#accept will throw this when someone hits ctrl-c - ignore it
			pass
	s.close()

class HandleWebsocket():
	"""Handle a websocket connection"""
	OP_CONT = 0x0	#Continuation
	OP_TEXT = 0x1	#Text frame
	OP_BIN = 0x2	#Binary frame
	OP_CLOS = 0x8	#Close request
	OP_PING = 0x9	#Ping frame
	OP_PONG = 0xA	#Pong frame
	OP_OTH = 0xF	#Other - reserved

	def __init__(self, conn, addr, url, filename):
		self._conn = conn
		self._addr = addr
		self._url = url
		self._filename = filename

	def handle_websocket(self):
		header = "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n" + \
			"Connection: Upgrade\r\nSec-WebSocket-Accept: " + self._url.gen_ws_accept_key() + "\r\n\r\n"
		self._conn.send(header)
		opcode = self.OP_OTH
		opcode, data = self.get_frame()
		while opcode != self.OP_CLOS and opcode is not None:	#opcode is None when the connection is closed
			if opcode == self.OP_TEXT:
				print data
				self.send_msg(data)
			if opcode == self.OP_PING:
				print "Ping received!"
				self.send_msg(data, self.OP_PONG)
			opcode, data = self.get_frame()
		if opcode == self.OP_CLOS:	#We got a close request, so close the socket nicely
			self.send_msg(None, self.OP_CLOS)

	def send_msg(self, data, opcode=None):
		if opcode == None:
			opcode = self.OP_TEXT
		frame = bytearray("\x80\x00")	#Start with a final message, blank opcode, with no masking
		frame[0] = frame[0] | opcode	#Bitwise 'or' in the opcode
		if data is None:	#No data required, so data size is 0
			pass
		elif len(data) < 126:	#Build the length up
			frame[1] = frame[1] | len(data)
		elif len(data) < 65535:
			frame[1] = frame[1] | 126
			packed = struct.pack(">I", len(data))
			frame.extend(packed)
		else:
			frame[1] = frame[1] | 127
			packed = struct.pack(">Q", len(data))
			frame.extend(packed)
		if data is not None:
			frame.extend(data)
		self._conn.send(frame)

	def get_frame(self):
		"""Get a byte array representing the frame"""
		bytearr = bytearray(self._conn.recv(2000))	#Wait for a frame TODO: max frame size?
		opcode = None
		data = None
		#TODO: handle fin set case - namely, if it's not set
		if len(bytearr) > 2 and self.test_mask(bytearr):	#Test some reasonable requirements
			opcode = self.get_opcode(bytearr)
			data = self.get_data(bytearr)
		return opcode, data

	def get_data(self, bytearr):
		datalen = self.get_datalen(bytearr)
		datastart = self.get_headerlen(bytearr)
		if len(bytearr) != (datalen+datastart):	#TODO: What causes errors here?
#			print "Size error in get_data bytearr len=", len(bytearr), " sum=", (datalen+datastart), " datalen=", datalen, " datastart=", datastart
			pass
		data = bytearr[datastart:(datalen+datastart)]
		if self.test_mask(bytearr):	#If a mask is set, do the following to unmask
			maskpos = datastart - 4
			mask = bytearr[maskpos:(maskpos+4)]
			for i, byte in enumerate(data):
				data[i] = byte ^ mask[i%4]	#Actually do the unmask
		return data
		
	def test_fin(self, data):
		val = False
		if data[0] & 0x80:
			val = True
		return val

	def test_rsv(self, data, ind=1):
		val = False
		if ind > 1 and ind < 3 and data[0] & (0x80 >> ind):	#bit-and the byte with 0x40, 0x20, or 0x10
			val = True
		return val

	def get_opcode(self, data):
		val = data[0] & 0x0f	#Remove the fin and rsv bits
		opcode = self.OP_OTH
		if val == self.OP_CONT: opcode = self.OP_CONT
		elif val == self.OP_TEXT: opcode = self.OP_TEXT
		elif val == self.OP_BIN: opcode = self.OP_BIN
		elif val == self.OP_CLOS: opcode = self.OP_CLOS
		elif val == self.OP_PING: opcode = self.OP_PING
		elif val == self.OP_PONG: opcode = self.OP_PONG
		else: opcode = self.OP_OTH
		return opcode

	def test_mask(self, data):
		val = False
		if data[1] & 0x80:
			val = True
		return val

	def get_datalen(self, data):
		length = int(data[1] & 0x7f)	#Remove the mask bit
		if length == 126:	#Bytes 2 and 3 store the length
			length = struct.unpack(">I", buffer(data[2:4]))
		elif length == 127:
			length = struct.unpack(">Q", buffer(data[2:10]))	#Bytes 2 thru 9 store length
		return length

	def get_headerlen(self, data):
		maskadd = 0
		if self.test_mask(data):	#Compensate for mask data
			maskadd = 4
		headerlen = 2	#Header size with 1 byte length field
		length = int(data[1] & 0x7f)
		if length == 126:
			headerlen = 4	#Header size with 3 bytes of length
		elif length == 127:
			headerlen = 10	#Header size with 9 bytes of length
		return headerlen+maskadd

class HandleConn(threading.Thread):
	"""Handle a user connection.  This is threaded.  It does its thing and cleans up when done."""
	HEAD_404 = "404"	#These things tell what type of header to build
	HEAD_FILE = "file"
	HEAD_HTML = "html"

	def __init__(self, conn, addr):
		"""Setup the handler with a connection and address to handle."""
		threading.Thread.__init__(self)
		self._conn = conn
		self._addr = addr

	def run(self):
		"""Handle everything about the connection, clean up when done."""
		data = self._conn.recv(1024)
		url = None
		for line in data.splitlines():	#Split the data up into lines and check each
			words = line.split()	#Split a line into words
			for i, word in enumerate(words):	#Iterate over the words, store index in i
				if word == "GET" and url is None:	#Set URL, and only allow url to be set once
					url = URL(words[i+1])
					break	#Finish processing this line
				elif word == "Sec-WebSocket-Key:" and url is not None:	#Test for websockets
					url.set_ws_key(words[i+1])
					break	#Finish processing the line
		if url is not None:
			self.respond(url)
		self._conn.close()
		print "Connection closed: ", self._addr

	def respond(self, url):
		"""Respond to a GET request for a url."""
		filename, c = url.resolve()
		if c == url.URL_FILE:	#URL was for a file download
			print self._addr, " requested file ", url
			self.send_file(filename)
		elif c == url.URL_DIR:	#URL was for a directory listing
			print self._addr, " requested directory ", url
			self.send_dir(filename)
		elif c == url.URL_WS:	#Request is a websocket request
			ws = HandleWebsocket(self._conn, self._addr, url, filename)
			ws.handle_websocket()
		else:	#Some error in classification
			print self._addr, " had an error with url request ", url
			self.send_error()
	
	def send_file(self, filename):
		"""Send the user a file download."""
		header = self.build_header(self.HEAD_FILE, filename)	#Build the header
		self.send_file_contents(header, filename)	#Send the file and header

	def send_dir(self, filename):
		"""Send the user a directory listing."""
		global dirhtmlfile
		header = self.build_header(self.HEAD_HTML)	#Build the header
		jsondata = self.build_dir_json(filename)	#Build the directory listing
		toappend = "<script type=\"text/javascript\">\nwindow.onload = processData(" \
			+ jsondata + ")\n</script>\n</body>\n</html>"	#The listing HTML file needs the listing appended
		self.send_file_contents(header, dirhtmlfile, toappend)	#Send the header, HTML file, and listing

	def send_error(self):
		"""Send the error file.  The only one handled right now is a 404."""
		global errorfile
		header = self.build_header(self.HEAD_404)
		self.send_file_contents(header, errorfile)

	def build_header(self, headertype, filename=""):
		"""Build a specific type of header.
		
		headertype specificaiton:
		HEAD_404 is for 404 errors
		HEAD_FILE is the header for a file download, and uses filename (others do not)
		HEAD_HTML is the header for html file download
		"""
		responsecode = ""
		contenttype = ""
		additional = ""
		if headertype == self.HEAD_404:
			responsecode = "404 Not Found"
			contenttype = "text/html; charset=UTF-8"
		elif headertype == self.HEAD_FILE:
			responsecode = "200 OK"
			contenttype = "application/octet-stream"
			fixedfn = os.path.basename(filename)
			additional = "Content-Disposition: attachment; filename=\"" + fixedfn + "\""
		elif headertype == self.HEAD_HTML:
			responsecode = "200 OK"
			contenttype = "text/html; charset=UTF-8"
		header = "HTTP/1.1 " + responsecode + "\r\n" \
						 + "Content-Type: " + contenttype + "\r\n" + additional	#TODO: handle more headers
		return header

	def build_dir_json(self, dirname):
		"""Build the JSON representation of a directory's contents
			
			JSON Format: { "dirname": "directory name here", "contents":[{"filename":"file name here",
				 "fileurl":"file url here", "type":"dir, file or other", "dateaccessed":"date created here",
				 "datemodified":"date modified here", "size":sizebyteshere}] } """
		global basedir
		dirlisting = []
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
		self._conn.send(header)	#Send the header
		with open(filename, 'rb') as f:	#Send the file in 1KB chunks
			data = f.read(1024)
			while data != "":
				self._conn.send(data)
				data = f.read(1024)
		if append != "":
			self._conn.send(append)	#Send the trailer, generally the directory listing right now

class URL():
	"""Processes URLs"""
	valid_chars = ascii_letters + digits + "/. "
	URL_ERR = "err"
	URL_WS = "websocket"
	URL_FILE = "file"
	URL_DIR = "dir"
	URL_SYS = "sys"	#TODO: implement system files - these are html or js or css or whatever that are in a certain folder

	_websocket = None	#This var stores whether this was a websocket url or not
	_key = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"	#This is the protocol's magic value

	def __init__(self, urlString=""):
		self._urlString = urlString

	def is_empty(self):
		return self._urlString == ""
	
	def set(self, urlString):
		self._urlString = urlString

	def __str__(self):
		return self._urlString
	
	#TODO: Test for bugs in the classification
	def resolve(self):
		parsed = urllib.unquote_plus(self._urlString)
		filename = None
		response = self.URL_ERR
		if self.validate_contents(parsed):	#Make sure the url contains only permitted chars
			filename = self.build_filename(parsed)
			if self.get_ws_key() is not None:
				response = self.URL_WS	#Being a websocket overrides others for now.  Don't check for file presence
			if not os.path.exists(filename):	#See if the file/directory referenced exists
				filename = None
			elif os.path.isfile(filename):
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

	def build_filename(self, parsedurl):
		global basedir
		return os.path.join(basedir, parsedurl.lstrip("/ "))

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

def sigint_handler(signum, frame):
	"""Handle the ctrl-c signal"""
	global interrupted
	interrupted = True

#This sets up main to execute if we've not been included as a module
if __name__ == "__main__":
	import sys
	main()
