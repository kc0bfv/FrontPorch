var titletext = "Front Porch"
var dirname = ""
var ws = null //This will store the UploaderWS object
var error_occurred = false

//setNameDiv displays the directory name in the correct place
function setNameDiv(data, dirnamearea) {
	dirnamearea.innerHTML = data.dirname
}

//genFilesTable populates the directory listing table with the json data
function genFilesTable(data, filetable) {
	for(var i=0, len=data.contents.length; i<len; i++) {
		var item = data.contents[i]
		var row = filetable.insertRow(filetable.rows.length)
		var cellCount = 0
		var filenameCell = row.insertCell(cellCount++)
		var sizeCell = row.insertCell(cellCount++)
		var modifiedCell = row.insertCell(cellCount++)
		var accessedCell = row.insertCell(cellCount++)
		filenameCell.innerHTML = "<a href=\"" + item.fileurl + "\">" + item.filename + "</a>"
		accessedCell.innerHTML = item.dateaccessed
		modifiedCell.innerHTML = item.datemodified
		if( item.type == "file" ) {
			sizeCell.innerHTML = humanizeSize(item.size)
		}
		filenameCell.className = "ftname"
		sizeCell.className = "ftsize"
		modifiedCell.className = "ftdatem"
		accessedCell.className = "ftdatea"
	}
}

//setTitle sets the titlebar text appropriately
function setTitle(data) {
	document.title = titletext + " - " + data.dirname
}

//humanizeSize turns a size in bytes into something more human friendly
function humanizeSize(size) {
	var human = ""
	var kb = 1024
	var mb = kb*1024
	var gb = mb*1024
	if(size<1000) {
		human = Math.floor(size) + "B"
	} else if(size<mb) {
		human = Math.floor(size/kb) + "KB"
	} else if(size<gb) {
		human = Math.floor(size/mb) + "MB"
	} else {
		human = Math.floor(size/gb) + "GB"
	}
	return human
}

//processData gets called with window.onload, and kicks off all the processing
function processData(data) {
	dirname = data.dirname
	setTitle(data)

	var dirnamearea = document.getElementById("dirnamespan")
	setNameDiv(data,dirnamearea)

	var filestable = document.getElementById("filetable")
	genFilesTable(data, filestable)
}

//intermedSend gets called with the send button's onclick.  It's just a middle man
function intermedSend() {
	send(document.getElementById("status"), document.getElementById("progressPercent"), document.getElementById("fileselector"))
}

//abort - The abort button calls this
function abort() {
	if(typeof ws !== "undefined" && ws !== null) {
		ws.abort()	//If the ws object is valid, tell it to abort
	}
}

//send is called by intermedSend
function send(statusbox, percentbar, fileselector) {
	if(fileselector.files.length != 1 || ws != null) {
		return	//If we don't have exactly one file selected, or ws already exists, quit
	}

	file = fileselector.files[0]	//Grab the selected file info

	statusbox.innerHTML = "Connecting"

	error_occurred = false
	//Build the UploaderWS object.  It will send the file when it's built.
	ws = new UploaderWS( file, dirname,
			function(msg) {	//on open
				statusbox.innerHTML = msg	//Set the statusbox appropriately
			},
			function(msg) { //on message
				statusbox.innerHTML = msg
			},
			function(msg) { //on close
				if(!error_occurred) {
					statusbox.innerHTML = msg
				}
				ws = null	//Invalidate the ws object
			},
			function(msg) { //on error
				statusbox.innerHTML = msg
				error_occurred = true
			},
			function(percent) { //on status update
				percentbar.style.width = percent + "%"
			},
			function() { //on finish
				setTimeout(function(){window.location.reload()}, 500)	//Reload the dir, see the new file
				//TODO: It would be better if we could just make an Ajax call and get the JSON update
			}
			)	//end new UploaderWS call
}
