var base64Lookup = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

//Currently for Chrome and newer Firefoxes - this is the preferred function
function base64ArrayBuffer(buff) {
	var encodedStr = ""
	var result = new Uint8Array(buff)
	for(var i = 0, size = result.length; i < size; i += 3) {
		char1 = char2 = char3 = char4 = "*" //Use * as a test for invalid output
		lookup1 = (result[i] & 252)>>2
		char1 = base64Lookup[lookup1]
		if(i+1 < size){
			lookup2 = ((result[i] & 3) << 4) | ((result[i+1] & 240) >> 4)
			if(i+2 < size) {
				lookup3 = ((result[i+1] & 15) << 2) | ((result[i+2] & 192) >> 6)
				lookup4 = result[i+2] & 63
				char4 = base64Lookup[lookup4]
			} else {
				lookup3 = (result[i+1] & 15) << 2
				char4 = "="
			}
			char3 = base64Lookup[lookup3]
		} else {
			lookup2 = (result[i] & 3) << 4
			char3 = "="
			char4 = "="
		}
		char2 = base64Lookup[lookup2]

		encodedStr += char1 + char2 + char3 + char4
	}
	return encodedStr
}

//This is needed for older Firefoxes, which didn't handle ArrayBuffers
function base64String(buff) {
	var encodedStr = ""
	var result = buff
	for(var i = 0, size = result.length; i < size; i += 3) {
		char1 = char2 = char3 = char4 = "*" //Use * as a test for invalid output
		lookup1 = (result.charCodeAt(i) & 252)>>2
		char1 = base64Lookup[lookup1]
		if(i+1 < size){
			lookup2 = ((result.charCodeAt(i) & 3) << 4) | ((result.charCodeAt(i+1) & 240) >> 4)
			if(i+2 < size) {
				lookup3 = ((result.charCodeAt(i+1) & 15) << 2) | ((result.charCodeAt(i+2) & 192) >> 6)
				lookup4 = result.charCodeAt(i+2) & 63
				char4 = base64Lookup[lookup4]
			} else {
				lookup3 = (result.charCodeAt(i+1) & 15) << 2
				char4 = "="
			}
			char3 = base64Lookup[lookup3]
		} else {
			lookup2 = (result.charCodeAt(i) & 3) << 4
			char3 = "="
			char4 = "="
		}
		char2 = base64Lookup[lookup2]

		encodedStr += char1 + char2 + char3 + char4
	}
	return encodedStr
}
