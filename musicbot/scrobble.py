import urllib
import json
import hashlib
import time
import sys

sk = ''
api_key = ''
api_secret = ''

class Scrobble(object):
	def __init__(self, user, passwd, key, secret):
		global sk
		global api_key
		global api_secret
		api_key = key
		api_secret = secret
		api_sig = hashlib.md5(("api_key" + api_key + "methodauth.getMobileSessionpassword" + passwd + "username" + user + api_secret).encode('utf-8')).hexdigest()
		params = {
			'method': 'auth.getMobileSession',
			'format': 'json',
			'username': user,
			'password': passwd,
			'api_key': api_key,
			'api_sig': api_sig
		}
		try:
			sk = self.request(params)['session']['key']
		except:
			print('There was an error getting a session key with the LastFM credentials provided.')
			sys.exit()
			
	def send(self, entry):
		global sk
		global api_key
		global api_secret
		params = {
			'method': 'track.search',
			'format': 'json',
			'track': entry.title,
			'api_key': api_key,
			'limit': '1'
		}
		try:
			t = self.request(params)['results']['trackmatches']['track']
		except:
			print("There was an error searching LastFM for '" + entry.title + "'")
			return
			
		if len(t)==0:
			print(entry.title + ' was not found on LastFM')
			return
		artist = t[0]['artist']
		track = t[0]['name']
		ts = str(time.time()).split(".")[0]
		api_sig = hashlib.md5(("api_key" + api_key + "artist" + artist + "methodtrack.scrobblesk" + sk + "timestamp" + ts + "track" + track + api_secret).encode('utf-8')).hexdigest()
		params = {
			'method': 'track.scrobble',
			'format': 'json',
			'artist': artist,
			'track': track,
			'timestamp': ts,
			'api_key': api_key,
			'api_sig': api_sig,
			'sk': sk
		}
		try:
			self.request(params)
		except:
			print('There was an error scobbling the track ' + entry.title + "'")
			return
		
	def request(self, params):
		url = "https://ws.audioscrobbler.com/2.0/"
		params = urllib.parse.urlencode(params).encode()
		r = urllib.request.Request(url, data=params, headers={"Content-Type": "application/x-www-form-urlencoded"})
		u = urllib.request.urlopen(r)
		return json.loads(u.read().decode('utf-8'))
