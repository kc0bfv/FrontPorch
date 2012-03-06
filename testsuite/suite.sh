#!/bin/bash

../main.py &
serverPID=$!

wget http://localhost:8080/ -O diroutput
wget http://localhost:8080/asdf.rand -O asdfoutput

kill $serverPID
