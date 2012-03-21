//This defines a custom websocket object
//Goes through several states - 
function UploaderWS(fi, dir, onopen, onmessage, onclose, onerror, onstatusupdate, onfinish) {
	var stvalinc = 0
	var ST_OPENING = stvalinc++			//Connection is attempting to open
	var ST_OPENED = stvalinc++			//Connection is open
	var ST_FILESIZE = stvalinc++		//Filesize has been sent
	var ST_FILESENDING = stvalinc++	//In process of sending segments
	var ST_FILEFIN = stvalinc++			//All file segments sent, waiting for server OK
	var	ST_ERROR = stvalinc++				//Some kind of error received
	var ST_CLOSING = stvalinc++ 		//Trying to close connection
	var ST_CLOSED = stvalinc++ 			//Connection has been closed

	var OPEN="", CLOSED=""
	if( typeof WebSocket !== "undefined" ) { //We're on a more modern browser
		OPEN = WebSocket.OPEN
		CLOSED = WebSocket.CLOSED
	} else if( typeof MozWebSocket !== "undefined" ) { //We're on Firefox
		OPEN = MozWebSocket.OPEN
		CLOSED = MozWebSocket.CLOSED
	}

	//Initialization stuff
	var state =	ST_OPENING
	var uploader = this
	var interval = 0	//Stores the timer number from setInterval - used for onclose
	var file = fi
	var fr = null
	if(typeof FileReader !== "undefined" ) {
		fr = new FileReader()
	} else {	//We really can't do anything more on this browser
		state = ST_CLOSED
	}
	var readpos = 0	//Stores the current position in the file
	var oldPercent = 0	//Stores the old percentage, so we can let the user know how far we are
	if( dir[0] != "/" ) {
		dir = "/" + dir
	}
	if( dir[dir.length-1] != "/" ) {
		dir = dir + "/"
	}
	var wsURL = "ws://" + document.location.host + dir + file.name
	var socket = ""
	if(state == ST_OPENING) {	//If something hasn't already occured to make us abort
		if( typeof WebSocket !== "undefined" ) { //We're on a more modern browser
			socket = new WebSocket(wsURL)	//Attempt to open the websocket
		} else if( typeof MozWebSocket !== "undefined" ) { //We're on Firefox
			socket = new MozWebSocket(wsURL)	//Attempt to open the websocket
		}	else {
			state = ST_CLOSED
			onerror("Your Browser Is Not Supported.  Sorry.")
		}
	} else {
		onerror("Your Browser Is Not Supported.  Sorry.")
	}
	socket.onopen = function() {	//After the websocket opens do this
		state = ST_OPENED
		outputStatus = uploader.startUpload()	//Start the upload
		onopen("Opened") //Run the requested onopen event
	}
	socket.onmessage = function(message) {	//Whenever websocket receives a message...
		outputStatus = uploader.handleMessage(message)	//Call the message handler func
		onmessage(outputStatus)	//Run the requested onmessage event
	}
	socket.onclose = function() {	//Whenever the websocket closes...
		outputStatus = uploader.stopCloseTimer()	//Stop the close timer
		state = ST_CLOSED
		onclose("Closed")	//Run the requested onclose event
	}
	socket.onerror = function() {	//Whenever the websocket gets an error...
		state = ST_ERROR
		outputStatus = uploader.handleError()	//Handle the error - this will run the user supplied function
	}
	//End Initialization

	//Object Functions
	//This calls a user specified function with an updated upload percentage
	this.updateStatus = function() {	
		newPercent = Math.floor((readpos / file.size)*100)
		if( newPercent != oldPercent ) {
			oldPercent = newPercent
			onstatusupdate(newPercent)
		}
	}

	this.abort = function() {
		if(state != ST_CLOSING && state != ST_CLOSED) {
			state = ST_CLOSING
			this.close()
		}
	}

	//Stop the close timer - this is used to make sure the websocket closes
	this.stopCloseTimer = function() {
		clearInterval(interval)
		interval = 0
	}

	//Begin to upload a file
	this.startUpload = function() {
		outputStatus = ""
		if(this.socketIsValid() && state == ST_OPENED) {
			socket.send("Filesize: " + file.size)	//Send the file size
			state = ST_FILESIZE	//Next, wait for a server response
			outputStatus = "Filesize sent"
		} else {	//Generally occurs when we're in the wrong state
			state = ST_ERROR
			this.handleError("While Starting Upload. Transfer failed.")
			outputStatus = "Error sending filesize"
		}
		return outputStatus
	}

	//This thing will handle the different messages the server can send
	this.handleMessage = function(message) {
		outputStatus = ""
		if(state == ST_OPENING || state == ST_OPENED) {
			if(message.data == "Invalid: -1") {
				state = ST_ERROR
				this.handleError("Invalid Characters in Filename")
			} else {
				state = ST_ERROR
				this.handleError("Message Received Before Filesize Sent")
			}
		} else if(state==ST_FILESIZE) {
			if(message.data == "Permitted") {	//Good to go!
				outputStatus = "Sending"
				state = ST_FILESENDING
				this.sendFile()
			} else if(message.data == "Invalid: -1") {
				state = ST_ERROR
				this.handleError("Invalid Characters in Filename")
			} else if(message.data == "Not Permitted: -1") {
				state = ST_ERROR
				this.handleError("File already exists on server.")
			} else {	//Some odd error
				state = ST_ERROR
				this.handleError("Before Filesize Response Received: " + message.data)
			}
		} else if(state == ST_FILESENDING ) {	//Messages while sending the file are errors
			if(message.data == "Invalid: -1") {
				state = ST_ERROR
				this.handleError("Error during file transfer.  Transfer failed.")
			} else {	//Some kind of error
				state = ST_ERROR
				this.handleError("Error during file transfer.  Transfer failed.")
			}
		} else if(state == ST_FILEFIN ) {
			if(message.data == "Finished") {	//Good to go!
				outputStatus = "File Sent"
				state = ST_CLOSING
				this.close()
				onfinish()
			} else if(message.data == "Finish Error: -1") {
				state = ST_ERROR
				this.handleError("File storage error on server.")
			} else if(message.data == "Finish Error: -2") {
				state = ST_ERROR
				this.handleError("Error during file transfer.  Transfer failed.")
			} else if(message.data == "Invalid: -1") {
				state = ST_ERROR
				this.handleError("Error during file transfer.  Transfer failed.")
			} else {	//Some kind of error
				state = ST_ERROR
				this.handleError("After File Finished: " + message.data)
			}
		}
		return outputStatus
	}

	//The error handler
	this.handleError = function(message) {
		outputStatus = "Error Occurred: " + message
		onerror(outputStatus)
		state = ST_CLOSING
		this.close()
		return outputStatus
	}

	this.socketIsValid = function() {
		return (typeof socket !== "undefined" && socket.readyState == OPEN)
	}

	this.sendFile = function() {
		if(this.socketIsValid() && state == ST_FILESENDING) {
			readpos = 0
			var slice
			var stepsize = 0
			if(file.webkitSlice) {	//If this is supported, we can use WebSocket send on blobs
				stepsize = 1024*128	//128 kb
			} else if(file.mozSlice) {	//If this is supported, we must use send on strings only
				stepsize = (1024*128)+1	//About 128 kb, but divisible by 3 - good for the base64 encoding
			} else {	//Right now, if those aren't supported, we can't use WebSockets either
				stepsize = 0
			}
			function serve(e) {
				if(uploader.socketIsValid() && state == ST_FILESENDING) {
					if( socket.bufferedAmount > stepsize/2 ) { //If half of the last data hasn't been sent...
						setTimeout(function(){serve(e)}, 5) //Schedule this to try again in a short bit
						return
					}
					var contents = ""
					if(file.webkitSlice) {	//If this is supported, leave the data in binary format
						contents = e.target.result
					} else if(file.mozSlice) {	//If this is supported, base64 encode it to text
						if( typeof e.target.result === "string" ) {	//Occurs if we had to use readAsBinaryString
							contents = base64String(e.target.result)
						} else {
							contents = base64ArrayBuffer(e.target.result)
						}
					} else {	//We shouldn't get this far
						contents = ""
					}
					uploader.updateStatus()
					//Send metadata
					socket.send("Segment Start: ", readpos, " Segment Finish: ", end)
					//Send data
					socket.send(contents)
					readpos += stepsize
					if( readpos < file.size ) {
						slice()
					}	else {
						socket.send("File Finish")
						state = ST_FILEFIN
					}
				}
			}
			slice = function () {
				end = Math.min(readpos+stepsize, file.size)
				if(file.webkitSlice) {
					sliced = file.webkitSlice(readpos, end)
				} else if(file.mozSlice) {
					sliced = file.mozSlice(readpos, end)
				}	else {
					sliced = null //Just don't do anything if a modern slice function isn't implemented
				}
				fr.onload = serve
				if(sliced != null) {
					if( fr.readAsArrayBuffer ) {
						fr.readAsArrayBuffer(sliced)
					} else {	//Old Firefox versions needed this
						fr.readAsBinaryString(sliced)
					}
				}
			}
			slice()
		} else {
			state = ST_ERROR
			this.handle_error("While Sending: within sendFile")
		}
	}

	this.close = function() {
		if( state != ST_CLOSING ) {
			this.handle_error("While Closing")
		} else if( socket.readyState != CLOSED && interval == 0 ) {
			interval = setInterval( function() {	//Build a function which tries to close the socket every 100ms
					if(typeof socket !== "undefined" && socket.readyState != CLOSED) {
						socket.close()
					}
				}, 100 ) //end setInterval
		}
	}
}
