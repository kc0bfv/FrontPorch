# Standard library imports
from __future__ import print_function #Make print work correctly prior to python 3
import tempfile
import shutil
import os.path

#Local imports
from Error import StateError, ProtocolError

class FileWriter():
	def __init__(self, filepath, filesize):
		self._filepath = filepath
		self._filesize = int(filesize)
		self._writtendat = 0
		self._tempfile = None
		try:
			self._tempfile = tempfile.TemporaryFile()
		except IOError:
			self._tempfile = None

	def test_size(self):
		"""Compare the amount of written data to the amount we're supposed to have

			Return 1 if too much has been received, 0 if the right amount has been
			received, and -1 if not enough data has been received

		"""
		retval = -1
		if self._writtendat > self._filesize:
			retval = 1
		elif self._writtendat == self._filesize:
			retval = 0
		return retval

	def append(self, data):
		"""Append data to the temporary file.
			
			Throws: StateError
			
		"""
		if self._tempfile is None:
			raise StateError("Temp file not created")
		else:
			self._tempfile.write(data)
			self._writtendat += len(data)

	def finish(self):
		"""Write the temporary file out to the real file.
			
			Throws: StateError

		"""
		# TODO: improve the usefulness of the error responses
		if self._tempfile is None:
			raise StateError("Temp file not created", "Finish Error: -1")
		# This will make sure that the temp file is closed when finish is done
		try:
			if self.test_size() == 0:
				self._tempfile.seek(0)
				# TODO: Resolve this race condition - perhaps os.open, os.fdopen
				if not os.path.exists(self._filepath):
					with open(self._filepath, 'wb') as f:
						shutil.copyfileobj(self._tempfile, f)
				else:
					raise StateError("File already exists", "Finish Error: -1")
			elif self.test_size() != 0:
				raise ProtocolError("File wasn't completely received",
														"Finish Error: -2")
		except:
			# Handle any exceptions at the next level up
			raise
		finally:
			self._tempfile.close()
			self._tempfile = None
