#! /usr/bin/env python -t -3
# Not compatible with 2.5 - no json module

# Remaining to do: make this easily distributed add in some authenticated
# upload feature?, add in upload destination restrictions?, exception classes?

# Standard library imports
from __future__ import print_function  # For python earlier than 3
import signal
import socket
import sys
import os.path
import logging
if sys.version_info[0] >= 3:
	from configparser import ConfigParser
else:
	from ConfigParser import ConfigParser

# Local imports
import UserConnection
from Error import DataError

# Global variables
DEFAULTCONFIGFILES = ["/usr/local/etc/frontPorch/fpDefaults.ini",
									 		"fpDefaults.ini", "frontPorch.ini"]
interrupted = False


def main():
	"""Main program, kicks off other execution."""
	# Setup the handler for ctrl-c
	signal.signal(signal.SIGINT, _sigint_handler)

	# Setup configuration and logging
	global DEFAULTCONFIGFILES
	settings = None
	try:
		settings = _read_config(DEFAULTCONFIGFILES)
	except DataError:
		_print_usage()
		return
	except IOError:
		logging.critical("Main: Failed to read configuration.")
		return
	logging.basicConfig(level=logging.INFO)

	# Build the IPV4 TCP socket and start listening
	try:
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	except socket.error:
		logging.critical("Main: Could not setup a socket.")
		return
	try:
		s.bind((settings["listenhost"], int(settings["listenport"])))
	except socket.error:  # Happens when the interface is already bound
		logging.critical("Main: Listening socket setup failed.  "
										 "Interface may already be bound.")
		return
	s.listen(100)

	# Accept connections and farm them out to threads
	global interrupted
	while not interrupted:
		try:
			conn, addr = s.accept()	# Block while waiting for a connection
			handler = UserConnection.UserConnection(settings, conn, addr)
			handler.start()
		except socket.error:
			# accept will throw this when someone hits ctrl-c - ignore it
			pass
	# When we're "interrupted"
	s.close()

# Determine the desired configuration.  Throw Exception for invalid args,
# throw IOError for configfile problems
def _read_config(configfiles):
	# If there are any cmd line args, recursively parse cmd line args
	settings = dict()
	if len(sys.argv) > 1:
		settings, recur_config_files = _parse_args(sys.argv[1:])
		configfiles.extend(recur_config_files)

	# Read the configuration files
	config = ConfigParser()
	try:
		config.read(configfiles)
	except IOError:
		_print_usage()
		raise
	else:
		# Get the settings from the config file.  Let cmd line args override
		filesettings = _retrieve_settings(config)
		filesettings.update(settings)
		settings = filesettings

	return settings

# Recursively parse the arguments.  Throw Exception for invalid args
def _parse_args(args):
	# Base case for recursion
	if len(args) < 1:
		return dict(), list()

	settings = dict()
	configfiles = list()
	nextarg = 1  # The next argument the recursive func will parse (rel to cur)
	cur = args[0]  # The arg we're parsing now
	hasnext = len(args) > 1  # Is there an argument available after cur?

	# Consider the current argument and parse out what it means
	if cur == "-c" and hasnext and os.path.isfile(args[1]):
		configfiles.append(args[1])
		nextarg = 2
	elif cur == "-p" and hasnext:
		try:
			tempport = int(args[1])
		except ValueError:
			raise DataError("Invalid command line argument")
		else:
			if tempport > 0 and tempport < 65536:
				settings["listenport"] = tempport
			else:
				raise DataError("Invalid port specified")
			nextarg = 2
	elif cur == "-r" and hasnext and os.path.isdir(args[1]):
		settings["basedir"] = args[1]
		nextarg = 2
	elif cur == "-h":
		raise DataError("Help argument present")
	else:
		raise DataError("Invalid command line argument")
	
	# Call the recursion, store the results, return
	recur_settings, recur_config_files = _parse_args(args[nextarg:])
	settings.update(recur_settings)
	configfiles.extend(recur_config_files)
	return settings, configfiles

# Parse the settings from the config file
def _retrieve_settings(config, section="Settings"):
	retval = dict()
	for option in config.options(section):
		retval[option] = config.get(section, option)
	return retval

# Print out the usage statement
def _print_usage():
	print("frontPorch.py [-h] [-r dir] [-c file] [-p port]")
	print("\t-h     \tUsage")
	print("\t-r dir \tRoot Directory")
	print("\t-c file\tConfiguration File")
	print("\t-p port\tListen Port")

# Handle the ctrl-c signal
def _sigint_handler(signum, frame):
	global interrupted
	interrupted = True

# This sets up main to execute if we've not been included as a module
if __name__ == "__main__":
	main()
