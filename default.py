"""kodi video addon to watch univision tv."""


import sys
import urllib2
import cookielib
import urllib
import xml.etree.ElementTree as et
from HTMLParser import HTMLParser
import urlparse
import os
import re
from datetime import timedelta, datetime, tzinfo
import time
import json

import xbmcaddon
import xbmcplugin
import xbmcgui
import xbmc

#def internet_on():
    #try:
        #response=urllib2.urlopen('http://tv.univision.mn',timeout=5)
        #return True
    #except urllib2.URLError as err: pass
    #return False

#if not internet_on():
    #import socks
    #import socket
    #socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050)
    #socket.socket = socks.socksocket
    

UNIVISION_TITLE = 'Univision Anywhere'
UNIVISION_BITRATES = ['1200000', '750000', '500000']
UNIVISION_BASEURL = 'https://my.univision.mn'
UNIVISION_SESSION_URL = 'http://tv.univision.mn/24/watch'

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASEURL = sys.argv[0]
ARGS = urlparse.parse_qs(sys.argv[2][1:])
PLUGIN_ID = 'plugin.video.univision'

xbmcplugin.setContent(HANDLE, 'video')


try:
    from htmlentitydefs import entitydefs
except ImportError:  # Python 3
    from html.entities import entitydefs


def htmlspecialchars_decode_func(m, defs=entitydefs):
    try:
        return defs[m.group(1)]
    except KeyError:
        return m.group(0)  # use as is


def htmlspecialchars_decode(string):
    pattern = re.compile("&(\w+?);")
    return pattern.sub(htmlspecialchars_decode_func, string)


class GMT8(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=8)

    def dst(self, dt):
        return timedelta(0)

    def tzname(self, dt):
        return "Asia/Ulaanbaatar"


class LoginPageParser(HTMLParser, object):
    def __init__(self):
        super(LoginPageParser, self).__init__()
        self.csrf_token = None
        self.form_action = None

    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            attr = dict(attrs)
            if attr['id'] == 'signin__csrf_token':
                self.csrf_token = attr['value']
        elif tag == 'form':
            attr = dict(attrs)
            if attr['id'] == 'login-form':
                self.form_action = attr['action']


class Channel(object):

    """TV channel class."""

    def __init__(self, cid, title, current, program, iconurl, url):
        """initialize channel object."""
        self.cid = cid
        self.title = title
        self.current = current
        self.program = program
        self.iconurl = iconurl
        self.url = url

    def __str__(self):
        """return string representation."""
        return "(%s) %s" % (self.cid, self.title)

    @classmethod
    def fromxml(cls, elem):
        channel = cls(
            elem.find('id').text,
            elem.find('title').text,
            elem.find('schedule').text,
            elem.find('scheduletoday').text,
            elem.find('image').text,
            elem.find('url').text)
        return channel


def build_url(query):
    """build url."""
    return BASEURL + '?' + urllib.urlencode(query)


def todt(hour_minute, tz):
    """convert 'hour:minute' (e.g. '23:22') to datetime in timezone."""
    return (
        datetime.now(tz).replace(hour=int(hour_minute[:2])).
        replace(minute=int(hour_minute[3:5])).
        replace(second=0))


def tolocaltz(dt):
    """convert arbitrary datetime to local timezone."""
    return dt + timedelta(seconds=-time.timezone - dt.utcoffset().seconds)


def fetch_channels(cid=None):
    """fetch channel list."""
    fetch_url = (
        'http://tv.univision.mn/tv/xml?id=' +
        ADDON.getSetting('username'))
    stream = urllib2.urlopen(fetch_url)
    tree = et.fromstring(stream.read())
    stream.close()
    fetch_channels.channels = dict()
    channels = [Channel.fromxml(item) for item in tree.findall('item')]
    

    if cid is None:
        return channels
    else:
        return next(ch for ch in channels if ch.cid == cid)







def list_channels(sid):
    """show channels on the kodi list."""
    for ch in fetch_channels():
        url = build_url(
            {'mode': 'channel', 'cid': ch.cid, 'sid': sid})
        iconurl = "http://tv.univision.mn/uploads/tv/%s.png" % ch.iconurl
        current_show = 'No information'
        if ch.current is not None:
            current_show = ch.current[14:].strip(': ')
        litem = xbmcgui.ListItem(
            '[%s]   %s' % (ch.title, current_show),
            iconImage=iconurl,
            thumbnailImage=iconurl)
        xbmcplugin.addDirectoryItem(
            handle=HANDLE, url=url, listitem=litem, isFolder=True)
    xbmcplugin.endOfDirectory(
        handle=HANDLE, succeeded=True, cacheToDisc=False)


def list_programs(cid, sid, progdate=False):
    """show tv programs on the kodi list."""
    selected = fetch_channels(cid)
    iconurl = "http://tv.univision.mn/uploads/tv/%s.png" % selected.iconurl
    
    if progdate == False:        
        x = 9;
        while x > 0:
            x = x - 1
            progdate = datetime.now() - timedelta(days=x)
            progdate_str = progdate.strftime("%Y-%m-%d")
            url = build_url(
                {'mode': progdate_str, 'cid': cid, 'sid': sid})
            litem = xbmcgui.ListItem(
                'Date: ' + progdate_str,
                iconImage=iconurl,
                thumbnailImage=iconurl)
            xbmcplugin.addDirectoryItem(
                handle=HANDLE, url=url, listitem=litem, isFolder=True)
                
        progdate = time.strftime("%Y-%m-%d") #today
        url = build_url({'mode': 'play', 'cid': cid, 'sid': sid})

        
        if selected.program is None:
            play_channel(cid, sid)
            return
    
        starts = [m.start() for m in re.finditer(
            r'[0-9]{2}\:[0-9]{2}\:', selected.program)]
        programs = [(
            todt(selected.program[start:start + 5], GMT8()),
            todt(selected.program[end:end + 5]
                 if end < len(selected.program) else '23:59', GMT8()),
            selected.program[start + 5:end].strip(': '))
            for start, end in zip(starts, starts[1:] + [len(selected.program)])]
    
        for prg in programs:
            now = datetime.now(GMT8())
            if prg[0] < now and prg[1] > now:
                litem = xbmcgui.ListItem(
                    '[Watch]   %s %s' % (
                        datetime.strftime(tolocaltz(prg[0]), '%H:%M'), prg[2]),
                    iconImage=iconurl,
                    thumbnailImage=iconurl)
                xbmcplugin.addDirectoryItem(
                    url=url,
                    handle=HANDLE, listitem=litem, isFolder=False)
            elif prg[0] > now:
                litem = xbmcgui.ListItem(
                    '%s %s' % (datetime.strftime(
                        tolocaltz(prg[0]), '%H:%M'), prg[2]),
                    iconImage=iconurl,
                    thumbnailImage=iconurl)
                xbmcplugin.addDirectoryItem(
                    url=None,
                    handle=HANDLE, listitem=litem, isFolder=False)
    
        xbmcplugin.endOfDirectory(
            handle=HANDLE, succeeded=True, cacheToDisc=False)
    
    else:

        cookiepath = get_cookie_path()
    
        #check that the cookie exists
        if os.path.exists(cookiepath):
            cookies = cookielib.LWPCookieJar()
            cookies.load(cookiepath)
        
        handlers = (
            urllib2.HTTPHandler(),
            urllib2.HTTPSHandler(),
            urllib2.HTTPCookieProcessor(cookies))
    
        opener = urllib2.build_opener(*handlers)
        opener.addheaders = [('Host','tv.univision.mn'),('Referer','http://tv.univision.mn/24/watch'),('DNT','1'),('X-Requested-With','XMLHttpRequest'),('Content-Type','application/x-www-form-urlencoded; charset=UTF-8'),('Accept','application/json, text/javascript, */*; q=0.01'),('User-agent', 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36')]
                   
        values = {
            'id': cid,
            'cDate': progdate}
        data = urllib.urlencode(values)
        req = urllib2.Request('http://tv.univision.mn/', data)
        response = opener.open(req)
        
    
        if response.getcode() == 200:
            programs1 = json.loads(response.read())
        else:
            play_channel(cid, sid)
            return
        
        for prg in programs1['Programs']:
            now = datetime.now()

            
            
            try:
                prog_starttime = datetime.strptime(prg['start_time'], "%Y-%m-%d %H:%M:%S")
            except TypeError:
                prog_starttime = datetime(*(time.strptime(prg['start_time'], "%Y-%m-%d %H:%M:%S")[0:6]))

            if prog_starttime < now:
                stream_start = prog_starttime.strftime("%Y-%m-%d-%H-%M-%S")
                url = build_url({'mode': 'play_last', 'cid': cid, 'sid': sid, 'stream_start': stream_start})
                litem = xbmcgui.ListItem(
                    '[Watch]   %s %s' % (
                        datetime.strftime(prog_starttime, '%H:%M'), htmlspecialchars_decode(prg['title'])),
                    iconImage=iconurl,
                    thumbnailImage=iconurl)
                xbmcplugin.addDirectoryItem(
                    url=url,
                    handle=HANDLE, listitem=litem, isFolder=False) 
            else:
                litem = xbmcgui.ListItem(
                    '%s %s' % (datetime.strftime(
                        prog_starttime, '%H:%M'), htmlspecialchars_decode(prg['title'])),
                    iconImage=iconurl,
                    thumbnailImage=iconurl)
                xbmcplugin.addDirectoryItem(
                    url=None,
                    handle=HANDLE, listitem=litem, isFolder=False)
    
        xbmcplugin.endOfDirectory(
            handle=HANDLE, succeeded=True, cacheToDisc=False)


#def touch(fname, mode=0o666, dir_fd=None, **kwargs):
    #flags = os.O_CREAT | os.O_APPEND
    #with os.fdopen(os.open(fname, flags=flags, mode=mode, dir_fd=dir_fd)) as f:
        #os.utime(f.fileno() if os.utime in os.supports_fd else fname,
            #dir_fd=None if os.supports_fd else dir_fd, **kwargs)

def touch(fname, times=None):
    fhandle = open(fname, 'a')
    try:
        os.utime(fname, times)
    finally:
        fhandle.close()
        
def get_cookie_path():

    
    __addon__        = xbmcaddon.Addon()
    __addonname__    = __addon__.getAddonInfo('id')
    __addonversion__ = __addon__.getAddonInfo('version')
    __addonpath__    = __addon__.getAddonInfo('path').decode('utf-8')
    __addonicon__    = xbmc.translatePath('%s/icon.png' % __addonpath__ )
    __language__     = __addon__.getLocalizedString
    
    cookiedir = xbmc.translatePath('special://profile/addon_data/%s' % __addonname__ ).decode('utf-8')
    if not os.access(cookiedir, os.W_OK):
        cookiedir = os.getcwd()
        if not os.access(cookiedir, os.W_OK):
            cookiedir = '/tmp'
            if not os.access(cookiedir, os.W_OK):
                cookiedir = '~'
                if not os.access(cookiedir, os.W_OK):
                    cookiedir = './'
    
    cookiepath = os.path.join(cookiedir, 'cookies.lwp')
    
    return cookiepath








def play_channel(cid, sid, stream_start=None):
    """play channel."""
    item = xbmcgui.ListItem('Watch')
    current = fetch_channels(cid)
    bitrate_id = int(ADDON.getSetting('bitrate'))
    cid = int(cid)
    
    if cid == 24:
        tv_shortcode = 'mnb_2'
    elif cid == 42:
        tv_shortcode = 'parliament'
    elif cid == 1:
        tv_shortcode = 'mnb'
    elif cid == 22:
        tv_shortcode = 'mn25'
    elif cid == 3:
        tv_shortcode = 'ubs'
    elif cid == 25:
        tv_shortcode = 'eagle'
    elif cid == 4:
        tv_shortcode = 'ntv'
    elif cid == 5:
        tv_shortcode = 'etv'
    elif cid == 23:
        tv_shortcode = 'edu'
    elif cid == 26:
        tv_shortcode = 'tv5'
    elif cid == 27:
        tv_shortcode = 'sbn'
    elif cid == 31:
        tv_shortcode = 'tv9'
    elif cid == 9:
        tv_shortcode = 'ehoron'
    elif cid == 41:
        tv_shortcode = 'bloomberg'
    elif cid == 2:
        tv_shortcode = 'mongolhd'
    elif cid == 38:
        tv_shortcode = 'royal'
    elif cid == 39:
        tv_shortcode = 'mnc'
        
    if current.url == None:
        current.url = 'smil:' + tv_shortcode + '.smil'
    
    if stream_start == None:
        #live url
        play_url = (
            'http://202.70.45.36/hls/_definst_/tv_mid/%s'
            '/playlist.m3u8?%s|BITRATES=%s|COMPONENT=HLS' %
            (current.url, sid, UNIVISION_BITRATES[bitrate_id]))
    else:
        #http://202.70.45.36/vod/_definst_/mp4:tv/medium/mnb_2.stream-2015-07-30-10-00-00/playlist.m3u8?3655dbb1ece17472a19aa8cbc980aca6       
        #http://202.70.32.50/vod/_definst_/mp4:tv/medium/"+suvag+".stream-"+$(".dialog-date").html()+"-"+time.replace(':','-')+"-00";
        #http://202.70.45.36/vod/_definst_/mp4:tv/medium/ntv.stream-2015-08-05-17-50-00/playlist.m3u8
        #http://202.70.45.36/vod/_definst_/mp4:tv/medium/ntv.stream-2015-08-05-16-55-00/playlist.m3u8
        play_url = (
            'http://202.70.45.36/vod/_definst_/mp4:tv/medium/%s'
            '.stream-%s/playlist.m3u8?%s' %
            (tv_shortcode, stream_start, sid))
    
    xbmc.Player(xbmc.PLAYER_CORE_DVDPLAYER).play(play_url, item)


def login():
    """login using the credentials stored in the settings."""
    cookies = cookielib.LWPCookieJar()

    handlers = (
        urllib2.HTTPHandler(),
        urllib2.HTTPSHandler(),
        urllib2.HTTPCookieProcessor(cookies))

    opener = urllib2.build_opener(*handlers)
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36')]
    
    logurl = UNIVISION_BASEURL + '/index.php/login'
    loginget = urllib2.Request(logurl)
    response = opener.open(loginget)
    parser = LoginPageParser()
    parser.feed(response.read())
    values = {
        'signin[_csrf_token]': parser.csrf_token,
        'signin[username]': ADDON.getSetting('username'),
        'signin[password]': ADDON.getSetting('password'),
        'signin[remember]': 'true'}
    data = urllib.urlencode(values)
    req = urllib2.Request(UNIVISION_BASEURL + parser.form_action, data)
    response = opener.open(req)

    if response.getcode() == 200:
        response = opener.open(
            urllib2.Request(UNIVISION_SESSION_URL))
        list_page = response.read()
        found = re.match(
            r'.*playlist\.m3u8.([^\']+)\'',
            list_page, re.MULTILINE | re.S)
        if found is not None:
            
            
            cookiepath = get_cookie_path()
                
            #delete any old version of the cookie file
            try:
                os.remove(cookiepath)
            except:
                pass
            
            cookies.save(cookiepath)
            
            
            
            
            
            sid = found.group(1)
            return sid
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                UNIVISION_TITLE,
                'Login failed. Check username and password and try again.',
                xbmcgui.NOTIFICATION_ERROR, 5000)
            ADDON.openSettings()
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification(
            UNIVISION_TITLE,
            'Possible API change.',
            xbmcgui.NOTIFICATION_ERROR, 5000)


def main():
    """addon entry point."""
    mode = ARGS.get('mode', None)
    if mode is None:
        sid = login()
        if sid is not None:
            list_channels(sid)
    elif mode[0] == 'channel':
        list_programs(ARGS.get('cid')[0], ARGS.get('sid')[0])
    elif mode[0] == 'play':
        play_channel(ARGS.get('cid')[0], ARGS.get('sid')[0])
    elif mode[0] == 'play_last':
        play_channel(ARGS.get('cid')[0], ARGS.get('sid')[0], ARGS.get('stream_start')[0])
    elif mode[0]:
        list_programs(ARGS.get('cid')[0], ARGS.get('sid')[0], mode[0])

main()
