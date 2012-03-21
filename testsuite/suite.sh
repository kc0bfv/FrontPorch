#!/bin/bash

programname="../frontPorch.py"
tempdir="tempoutput"
corrdir="correctoutput"
uconvodir="uploadConversations"
DEBUG="NO"

which md5 &> /dev/null
md5found=$?
which md5sum &> /dev/null
md5sumfound=$?
if [ $md5found == 0 ]; then
	md5prog="md5"
	cutfield="2"
	cutdelim="="
elif [ $md5sumfound == 0 ]; then
	md5prog="md5sum"
	cutfield="1"
	cutdelim=" "
else
	echo "No MD5 program found."
	exit 1
fi

corroutput="INFO:root:('127.0.0.1', removed): Connection Received
INFO:root:('127.0.0.1', removed): Requested Directory /
INFO:root:('127.0.0.1', removed): Connection Closed
INFO:root:('127.0.0.1', removed): Connection Received
INFO:root:('127.0.0.1', removed): Requested File /asdf.rand
INFO:root:('127.0.0.1', removed): Connection Closed
INFO:root:('127.0.0.1', removed): Connection Received
INFO:root:('127.0.0.1', removed): Requested Upload /rand.sdf
INFO:root:('127.0.0.1', removed): Connection Closed
INFO:root:('127.0.0.1', removed): Connection Received
INFO:root:('127.0.0.1', removed): Requested Upload /rand2.sdf
INFO:root:('127.0.0.1', removed): Connection Closed"

testserver() {
	echo "Testing with: $1"

	progoutfn="progoutput"
	diroutfn="diroutput"
	asdfoutfn="asdfoutput"
	rootdir="testroot"

	rm -f "${tempdir}/${progoutfn}"
	rm -f "${tempdir}/${diroutfn}"
	rm -f "${tempdir}/${asdfoutfn}"
	rm -f "${rootdir}/rand.sdf"
	rm -f "${rootdir}/rand2.sdf"

	if [ "$DEBUG" == "YES" ]; then echo "starting"; fi
	$1 $programname &> "${tempdir}/${progoutfn}" &
	serverPID=$!
	if [ "$DEBUG" == "YES" ]; then echo "Server PID: $serverPID"; fi

	sleep 2	#Wait for the server to start

	#Download tests
	if [ "$DEBUG" == "YES" ]; then echo "downloading"; fi
	wget http://localhost:8080/ -O "${tempdir}/${diroutfn}" &> /dev/null
	wget http://localhost:8080/asdf.rand -O "${tempdir}/${asdfoutfn}" &> /dev/null

	if [ "$DEBUG" == "YES" ]; then echo "uploading"; fi
	#Upload test
	(cat "${uconvodir}/uploadConversation1"; sleep 1; cat "${uconvodir}/uploadConversation2") | nc localhost 8080 &> /dev/null
	sleep 1
	(cat "${uconvodir}/base64uploadConversation1"; sleep 1; cat "${uconvodir}/base64uploadConversation2") | nc localhost 8080 &> /dev/null

	if [ "$DEBUG" == "YES" ]; then echo "tests"; fi
	dirtempmd5=`grep --invert "window.onload = processData" "${tempdir}/${diroutfn}" | $md5prog | cut -f $cutfield -d "$cutdelim"`
	dircorrmd5=`grep --invert "window.onload = processData" "${corrdir}/${diroutfn}" | $md5prog | cut -f $cutfield -d "$cutdelim"`
	asdftempmd5=`$md5prog "${tempdir}/${asdfoutfn}" | cut -f $cutfield -d "$cutdelim"`
	asdfcorrmd5=`$md5prog "${corrdir}/${asdfoutfn}" | cut -f $cutfield -d "$cutdelim"`
	randtempmd5=`$md5prog "${rootdir}/rand.sdf" | cut -f $cutfield -d "$cutdelim"`
	randtempb64md5=`$md5prog "${rootdir}/rand2.sdf" | cut -f $cutfield -d "$cutdelim"`
	randcorrmd5=`$md5prog "${corrdir}/rand.sdf" | cut -f $cutfield -d "$cutdelim"`

	if [ "$dirtempmd5" == "$dircorrmd5" ]; then
		echo "Pass Dir Test"
	else
		echo "Fail Dir Test"
	fi

	if [ "$asdftempmd5" == "$asdfcorrmd5" ]; then
		echo "Pass Rand File Test"
	else
		echo "Fail Rand File Test"
	fi

	if [ "$randtempmd5" == "$randcorrmd5" ]; then
		echo "Pass Binary Upload Test"
	else
		echo "Fail Binary Upload Test"
	fi

	if [ "$randtempb64md5" == "$randcorrmd5" ]; then
		echo "Pass Text Upload Test"
	else
		echo "Fail Text Upload Test"
	fi

	if [ "$DEBUG" == "YES" ]; then echo "killing"; fi
	kill -s SIGINT $serverPID
	if [ $? != 0 ]; then
		echo "Failed to kill server ${serverPID}"
	fi
	sleep 2 #Wait for a little cleanup

	if [ "$DEBUG" == "YES" ]; then echo "outputtesting"; fi
	output=`cat "${tempdir}/${progoutfn}" | sed "s/\(('[0-9\.]*', \)[0-9]*\()\)/\1removed\2/"`
	if [ "$output" == "$corroutput" ]; then
		echo "Pass Output Test"
	else
		echo "Fail Output Test"
		if [ "$DEBUG" == "YES" ]; then
			echo "Output: $output"
			echo "Corr Output: $corroutput"
		fi
	fi
}

testserver "python2.6"
testserver "python2.7"
testserver "python3.2"
