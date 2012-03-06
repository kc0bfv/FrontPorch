#! /usr/bin/env python3
#Not compatible with 2.5 - no json module

#Remaining to do: build a test suite, test on linux, implement inetd or xinetd usage, break this file out, fix the settings setup, logging

#import os.path
#from string import ascii_letters, digits
#import json
#import hashlib
#import base64
#import struct
#from datetime import datetime

from __future__ import print_function #Make print work correctly prior to python 3

defaultSettings="""[DEFAULT]
rootDir = /Users/finity/Documents/Code/DistSysProj2
listenport = 8080
listenhost = 
basedir = %(rootDir)s/testroot/
systemfiledir = %(rootDir)s/systemfiles/
errorfile = %(rootDir)s/systemfiles/404.html
dirhtmlfile = %(rootDir)s/systemfiles/dir.html
sysdirmagicprefix = (system)/"""	#This is the default config

defaultConfigFile="frontPorch.ini"

interrupted = False	#Let it handle a ctrl-c

import signal, socket, sys, os.path

if sys.version_info[0] >= 3:
	from configparser import ConfigParser
else:
	from ConfigParser import ConfigParser

from HandleWebsocket import HandleWebsocket
from HandleConn import HandleConn

def main():
	"""Main program, kicks off other execution.  Setup for execution at end of file."""
	global defaultConfigFile
	settings, goOn = determine_config(defaultConfigFile)
	if goOn != True:
		return	#determine_config has instructed us to not go on
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)	#Setup an ipv4 TCP socket
	s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	try:
		s.bind((settings["listenhost"], int(settings["listenport"])))
	except socket.error:	#Happens when the interface is already bound
		print("Could not setup listening socket.  Interface is probably already bound.")	#TODO:better msg
		return
	s.listen(100)	#Start listening for a connection

	signal.signal(signal.SIGINT, sigint_handler)	#Setup the handler for ctrl-c
	global interrupted
	while not interrupted:
		try:
			conn, addr = s.accept()	#Block while waiting for a connection
			conn.settimeout( 5 )	#Set a blocking timeout of 5 seconds for the recvd conn
			print("Connection received from: ", addr)
			handler = HandleConn(settings, conn, addr)
			handler.start()
		except socket.error:	#accept will throw this when someone hits ctrl-c - ignore it
			pass
	s.close()


def determine_config(defaultConfFile):
	configFile = defaultConfFile
	listenPort = None
	baseDir = None
	goOn = True
	for i, item in enumerate(sys.argv):
		if i == 0:	#Give the first item in argv a pass, it's the command name
			pass
		elif item == "-c" and i+1 < len(sys.argv) and os.path.isfile(sys.argv[i+1]):	#config file
			configFile = sys.argv[i+1]
		elif item == "-h":	#Usage
			print_usage()
			goOn = False
		elif item == "-p" and i+1 < len(sys.argv):	#Listen port
			try:
				tempPort = int(sys.argv[i+1])
			except ValueError:
				tempPort = 0
			if tempPort > 0 and tempPort < 65536:
				listenPort = tempPort
		elif item == "-r" and i+1 < len(sys.argv) and os.path.isdir(sys.argv[i+1]):	#Root directory
			baseDir = sys.argv[i+1]
		else:
			print_usage()
			goOn = False
	try:
		config = ConfigParser()
		global defaultSettings
		config.read_string(defaultSettings)
		config.read(configFile)
		settings = retrieve_settings(config)
	except IOError:
		print_usage()
		raise
	if baseDir is not None:
		settings["basedir"] = baseDir
	if listenPort is not None:
		settings["listenport"] = listenPort
	return settings, goOn

def retrieve_settings(config, section="Settings"):
	retval = dict()
	for option in config.options(section):
		retval[option] = config.get(section, option)
	return retval

def print_usage():
	print("frontPorch.py [-h] [-r dir] [-c file] [-p port]")
	print("\t-h     \tUsage")
	print("\t-r dir \tRoot Directory")
	print("\t-c file\tConfiguration File")
	print("\t-p port\tListen Port")

def sigint_handler(signum, frame):
	"""Handle the ctrl-c signal"""
	global interrupted
	interrupted = True

#This sets up main to execute if we've not been included as a module
if __name__ == "__main__":
#	import sys
	main()
