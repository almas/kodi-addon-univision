"""XBMC video addon to watch univision tv."""

import sys
import urllib2
import cookielib
import urllib
import xml.etree.ElementTree as et
from HTMLParser import HTMLParser
import urlparse
import re
from datetime import timedelta, datetime, tzinfo
import time

import xbmcaddon
import xbmcplugin
import xbmcgui
import xbmc

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
    """show channels on the xbmc list."""
    for ch in fetch_channels():
        url = build_url(
            {'mode': 'channel', 'cid': ch.cid, 'sid': sid})
        iconurl = "http://tv.univision.mn/uploads/tv/%s.png" % ch.iconurl
        litem = xbmcgui.ListItem(
            '[%s]   %s' % (
                ch.title,
                'No information' if ch.current is None else ch.current[14:].strip(': ')),
            iconImage=iconurl,
            thumbnailImage=iconurl
            )
        xbmcplugin.addDirectoryItem(
            handle=HANDLE, url=url, listitem=litem, isFolder=True)
    xbmcplugin.endOfDirectory(
        handle=HANDLE, succeeded=True, cacheToDisc=False)


def list_programs(cid, sid):
    """show tv programs on the xbmc list."""
    selected = fetch_channels(cid)
    iconurl = "http://tv.univision.mn/uploads/tv/%s.png" % selected.iconurl
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
        selected.program[start + 5:end].strip(': ')) for start, end in zip(
            starts, starts[1:] + [len(selected.program)])]

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


def play_channel(cid, sid):
    """play channel."""
    item = xbmcgui.ListItem('Watch')
    current = fetch_channels(cid)
    bitrate_id = int(ADDON.getSetting('bitrate'))
    play_url = (
        'http://202.70.45.36/hls/_definst_/tv_mid/%s'
        '/playlist.m3u8?%s|BITRATES=%s|COMPONENT=HLS' %
        (current.url, sid, UNIVISION_BITRATES[bitrate_id]))
    xbmc.Player(xbmc.PLAYER_CORE_DVDPLAYER).play(play_url, item)


def login():
    """login using the credentials stored in the settings."""
    cookies = cookielib.LWPCookieJar()
    handlers = (
        urllib2.HTTPHandler(),
        urllib2.HTTPSHandler(),
        urllib2.HTTPCookieProcessor(cookies))

    opener = urllib2.build_opener(*handlers)

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

main()
