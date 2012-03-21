# Standard library imports
from __future__ import print_function #Make print work correctly prior to python 3
import base64
import struct
import os.path
import socket
import logging

# Local imports
from FileWriter import FileWriter
from Error import StateError, ProtocolError

class Websocket():
	"""Handle a websocket connection"""

	# TODO: Make opcode its own object?
	# These are the possible opcodes
	OP_CONT = 0x0	# Continuation
	OP_TEXT = 0x1	# Text frame
	OP_BIN = 0x2	# Binary frame
	OP_CLOS = 0x8	# Close request
	OP_PING = 0x9	# Ping frame
	OP_PONG = 0xA	# Pong frame
	OP_OTH = 0xF	# Other - reserved

	# These are the receiver states
	ST_FILESIZE = "wait for filesize"
	ST_FILESEGM = "waiting for file segment metadata"
	ST_FILESEGD = "waiting for file segment data"
	ST_CLOSE = "close the connection"
	ST_FINISH = "file finish command received"

	def __init__(self, conn, addr, url, settings):
		self._conn = conn
		self._addr = addr
		self._url = url
		self._permitted_upload_dir = None
		if "uploaddir" in settings.keys():
			# Make sure there's one / at the end of the directory
			self._permitted_upload_dir = settings["uploaddir"].rstrip("/ ") + "/"
		self._filewriter = None
		self._curbuf=bytearray()	# Store the buffer of received bytes

	def handle_websocket(self):
		"""Handle a websocket connection"""
		self._send_header()
		state = self.ST_FILESIZE  # First, wait for the file size
		# Handle file upload.  Close connection nicely in any case
		try:
			while state != self.ST_FINISH:
				opcode, data = self._get_frame()
				if opcode == self.OP_PING:
					# Handle a ping in any state.  Don't do anything else with the data
					self._send_msg(data, self.OP_PONG)
				elif state == self.ST_FILESIZE:
					state = self._state_filesize(opcode, data)
				elif state == self.ST_FILESEGM:
					state = self._state_filesegm(opcode, data)
				elif state == self.ST_FILESEGD:
					state = self._state_filesegd(opcode, data)
				else:	
					raise StateError("Invalid state")
			# ST_FINISH state
			self._filewriter.finish()
		except (ProtocolError, StateError) as e:
			logging.error("%s: %s", self._addr, e.msg)
			if e.response is not None:
				self._send_msg(e.response.encode())
		else:
			self._send_msg(b"Finished")
		finally:
			self._send_msg(None, self.OP_CLOS)

	def handle_invalid_url(self):
		"""Handle a websocket request for an invalid URL."""
		self._send_header()
		self._send_msg("Invalid: -1")
		self._send_msg(None, self.OP_CLOS)
		
	# Send the header responding to the websocket connection request
	def _send_header(self):
		header = ("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
							"Connection: Upgrade\r\nSec-WebSocket-Accept: " +
							self._url.accept_key + "\r\n\r\n")
		self._conn.sendall(header.encode())

	# Handle the ST_FILESIZE state
	def _state_filesize(self, opcode, data):
		# Sanity check the frame
		if opcode != self.OP_TEXT:
			raise ProtocolError("Received non-text frame while waiting for filesize",
													"Invalid: -1")
		elif not data.startswith(b"Filesize: "):
			raise ProtocolError("Received invalid text while waiting for filesize",
													"Invalid: -1")

		# Retrieve the file size
		filesize = data.decode("ascii").replace("Filesize: ", "", 1).strip()
		if not filesize.isdigit():
			raise ProtocolError("Invalid filesize received", "Invalid: -1")
		# Make sure the upload is to a permitted destination
		elif (self._permitted_upload_dir is not None and 
				not self._url.filename.startswith(self._permitted_upload_dir)):
			raise ProtocolError("Invalid upload directory, upload denied",
													"Not Permitted: -2")
		# Now check if the file exists
		elif not os.path.isfile(self._url.filename):
			# We're go for file upload!
			self._send_msg(b"Permitted")
			self._filewriter = FileWriter(self._url.filename, int(filesize))
		else:
			# File already exists - let the client know it messed up
			raise ProtocolError("File already exists, upload denied",
													"Not Permitted: -1")
		return self.ST_FILESEGM

	# Handle the ST_FILESEGM state
	def _state_filesegm(self, opcode, data):
		if opcode != self.OP_TEXT:
			raise ProtocolError("Received non-text frame while waiting "
													"for segment metadata", "Invalid: -1")
		state = self.ST_FILESEGM
		if data.startswith(b"File Finish"):
			# The sender indicated that the file is done
			state = self.ST_FINISH
		elif data.startswith(b"Segment Start:"):
			#TODO: Parse out, verify, the segment start and finish data here
			# A file data segment will follow
			state = self.ST_FILESEGD
		else:
			raise ProtocolError("Received invalid segment metadata",
													"Invalid: -1")
		return state

	# Handle the ST_FILESEGD state
	def _state_filesegd(self, opcode, data):
		if opcode != self.OP_BIN and opcode != self.OP_TEXT:
			raise ProtocolError("Invalid opcode while waiting for file data",
													"Invalid: -1")
		if opcode == self.OP_TEXT:
			# In this case, the data is base64 encoded.  Decode it
			data = base64.b64decode(bytes(data))
		self._filewriter.append(data)
		if self._filewriter.test_size() > 0:
			raise ProtocolError("Received data after file met specified size",
													"Segment Error: -1")
		return self.ST_FILESEGM

	# Send a message over the websocket connection
	def _send_msg(self, data, opcode=None):
		if opcode == None:
			opcode = self.OP_TEXT
		# Start with a final message, blank opcode, no masking, 0 data length
		frame = bytearray(b"\x80\x00")
		# Place the opcode
		frame[0] = frame[0] | opcode
		# Place the size of the data segment
		if data is None:
			pass
		elif len(data) < 126:
			frame[1] = frame[1] | len(data)
		elif len(data) < 65535:
			frame[1] = frame[1] | 126
			packed = struct.pack(">I", len(data))
			frame.extend(packed)
		else:
			frame[1] = frame[1] | 127
			packed = struct.pack(">Q", len(data))
			frame.extend(packed)
		# Append the data
		if data is not None:
			frame.extend(data)
		# Send the frame
		self._conn.sendall(frame)

	# Receive a chunk of data into the buffer.  Get at least "amount" of data
	def _recv_data(self, amount, maxtimeouts=2, maxtries=1000):
		tocount = 0
		tries = 0
		while (len(self._curbuf) < amount and tocount < maxtimeouts and
					 tries < maxtries):
			tries += 1
			try:
				self._curbuf.extend(bytearray(self._conn.recv(1024*256)))
			except socket.error:
				tocount += 1
		if len(self._curbuf) < amount:
			raise ProtocolError("Socket timeout waiting for frame header",
													"Timeout: -1")

	# Return a byte array representing one single websocket frame
	def _get_frame(self):
		# TODO: handle fin set case - namely, if it's not set
		# Receive the header
		self._recv_data(2)
		headerlen = self._get_headerlen(self._curbuf)
		self._recv_data(headerlen)
		datalen = self._get_datalen(self._curbuf)
		framesize = headerlen + datalen

		# Receive the entire frame
		self._recv_data(framesize)
		frame = self._curbuf[0:framesize]
		del self._curbuf[0:framesize]
		opcode = self._get_opcode(frame)
		data = frame[headerlen:]
		# If there's a mask bit, unmask the frame
		if self._test_mask(frame):
			maskpos = headerlen - 4
			mask = frame[maskpos:(maskpos+4)]
			for i, byte in enumerate(data):
				data[i] = byte ^ mask[i%4]
		else:
			raise ProtocolError("Mask bit was not set", "Invalid: -1")
		return opcode, data

	# Return true if the mask bit is set
	def _test_mask(self, data):
		if len(data) >= 2 and data[1] & 0x80:
			return True
		return False

	# Return true if the fin bit is set
	def _test_fin(self, data):
		if len(data) >= 1 and data[0] & 0x80:
			return True
		return False

	# Return true if the specified rsv bit is set
	def _test_rsv(self, data, index=1):
		if (len(data) >= 1 and index > 1 and index < 3 and
				data[0] & (0x80 >> index)):
			return True
		return False

	# Return the value in the length field
	def _get_length_field(self, data):
		if len(data) < 2:
			raise ProtocolError("Invalid header", "Invalid: -1")
		# Remove the mask bit...
		return int(data[1] & 0x7f)

	# Determine the frame's opcode
	def _get_opcode(self, data):
		if len(data) < 1:
			raise StateError("Not enough data to get opcode")
		val = data[0] & 0x0f  # Remove the fin and rsv bits
		opcode = self.OP_OTH
		if val == self.OP_CONT: opcode = self.OP_CONT
		elif val == self.OP_TEXT: opcode = self.OP_TEXT
		elif val == self.OP_BIN: opcode = self.OP_BIN
		elif val == self.OP_CLOS: opcode = self.OP_CLOS
		elif val == self.OP_PING: opcode = self.OP_PING
		elif val == self.OP_PONG: opcode = self.OP_PONG
		else: opcode = self.OP_OTH
		return opcode

	# Determine the frame's length based on the header
	def _get_datalen(self, data):
		length = self._get_length_field(data)
		# The length field has magic values 126 and 127.  Handle them
		if length == 126:
			if len(data) < 4:
				raise ProtocolError("Invalid header", "Invalid: -1")
			# Unpack bytes 2 and 3 into an integer.  Unpack returns a tuple
			length, = struct.unpack(">H", bytes(data[2:4]))
		elif length == 127:
			if len(data) < 10:
				raise ProtocolError("Invalid header", "Invalid: -1")
			# Unpack bytes 2 thru 9 into an integer.  Unpack returns a tuple
			length, = struct.unpack(">Q", bytes(data[2:10]))
		return length

	# Determine the header's length based on the header
	def _get_headerlen(self, data):
		length = self._get_length_field(data)
		headerlen = 2
		# The length field has magic values 126 and 127.  Handle them
		if length == 126:
			headerlen = 4  # Length field is 3 bytes
		elif length == 127:
			headerlen = 10  # Length field is 9 bytes
		if self._test_mask(data):
			headerlen += 4  # Compensate for mask size
		return headerlen

