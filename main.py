#! /usr/bin/env python

import socket
import threading
import signal
import urllib
import os.path
import string

interrupted = False	#Let it handle a ctrl-c
basedir = "/Users/finity/Documents/Code/DistSysProj2/"	#Temporarily store the basedir here
errorfile = "/Users/finity/Documents/Code/DistSysProj2/404.html"

def main():
	"""Handles the version that's not executed as a module"""
	host, port = '', 8080
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)	#Setup an ipv4 TCP socket
	s.bind((host, port))
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

class HandleConn(threading.Thread):
	HEAD_404 = "404"
	HEAD_FILE = "file"

	def __init__(self, conn, addr):
		threading.Thread.__init__(self)
		self._conn = conn
		self._addr = addr

	def run(self):
		"""Right now HandleConn.run() is built specifically for Chrome.  It may work for other browsers, but I need to check the standards at some point"""
		data = self._conn.recv(1024)
		url = None
		for line in data.splitlines():	#Split the data up into lines and check each
			words = line.split()	#Split a line into words
			for i, word in enumerate(words):	#Iterate over the words, store index in i
				if word == "GET":
					url = URL( words[i+1] )
					break
			if url is not None: #If we found the URL in this line, then quit
			 break
		if url is not None:
			self.respond(url)
		self._conn.close()
		print "Connection closed: ", self._addr

	def respond(self, url):
		filename, c = url.resolve()
		if c == url.URL_FILE:
			print self._addr, " requested file ", url
			self.send_file(filename)
		elif c == url.URL_DIR:
			print self._addr, " requested directory ", url
			self.send_dir(filename)
		else:	#Some error in classification
			print self._addr, " had an error with url request ", url
			self.send_error()
	
	def send_file(self, filename):
		header = self.build_header(self.HEAD_FILE, filename)
		self.send_file_contents(header, filename)

	def send_dir(self, filename):
		pass

	def send_error(self):
		global errorfile
		header = self.build_header(self.HEAD_404)
		self.send_file_contents(header, errorfile)

	def build_header(self, headertype, filename=""):
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
		header = "HTTP/1.1 " + responsecode + "\r\n" \
						 + "Content-Type: " + contenttype + "\r\n" + additional	#TODO:more headers
		return header

	def send_file_contents(self, header, filename, append=""):
		size = os.path.getsize(filename)
		header += "Content-Length: {0:d}\r\n\r\n".format(size+len(append))
		self._conn.send(header)
		with open(filename, 'rb') as f:
			data = f.read(1024)
			while data != "":
				self._conn.send(data)
				data = f.read(1024)
		if append != "":
			self._conn.send(append)

class URL():
	valid_chars = string.ascii_letters + string.digits + "/. "
	URL_ERR = "err"
	URL_FILE = "file"
	URL_DIR = "dir"
	URL_SYS = "sys"	#TODO: implement system files - these are html or js or css or whatever that are in a certain folder

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

def sigint_handler(signum, frame):
	global interrupted
	interrupted = True

if __name__ == "__main__":
	import sys
	main()
