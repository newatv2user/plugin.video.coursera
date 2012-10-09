'''
Created on Oct 4, 2012

@author: newatv2user
based on one or more of following:
https://github.com/itelichko/coursera-download
https://github.com/jplehmann/coursera
https://github.com/dmotitsk/coursera
'''
import sys, os
import urllib, urllib2, cookielib, re
import xbmcaddon, xbmcgui, xbmcplugin, xbmc
from xbmcgui import ListItem
import StorageServer, CommonFunctions
import json

Addon = xbmcaddon.Addon()
Addonid = Addon.getAddonInfo('id') 
pluginUrl = sys.argv[0]
pluginHandle = int(sys.argv[1])
pluginQuery = sys.argv[2]
settingsDir = Addon.getAddonInfo('profile')
settingsDir = xbmc.translatePath(settingsDir)
cacheDir = os.path.join(settingsDir, 'cache')

# For parsedom
common = CommonFunctions
common.dbg = False
common.dbglevel = 3

# initialise cache object to speed up plugin operation
cache = StorageServer.StorageServer(Addonid)

CSRF_URL = 'https://www.coursera.org/maestro/api/user/csrf_token'
REDIRECT_URL = 'https://class.coursera.org/%s/auth/auth_redirector?type=login&subtype=normal&email=&visiting=/%s/lecture/index&minimal=true'
LOGIN_URL = 'https://www.coursera.org/maestro/api/user/login'
LOGIN_REFERER = 'https://www.coursera.org/account/signin'
LOGIN_HOST = "www.coursera.org"
USER_LIST = 'https://www.coursera.org/maestro/api/topic/list_my?user_id=%s'
CLASSES_HOST = 'https://class.coursera.org'
VID_REDIRECT_URL = 'https://class.coursera.org/%s/auth/auth_redirector?type=login&subtype=normal&email=&visiting=/%s/lecture/view?lecture_id=%s'

cookiepath = os.path.join(cacheDir, 'cookie')

##################
## Class for items
##################
class MediaItem:
    def __init__(self):
        self.ListItem = ListItem()
        self.Image = ''
        self.Url = ''
        self.Isfolder = False
        self.Mode = ''

## Get URL
def getURL(url):
    print 'getURL :: url = ' + url    
    cj = cookielib.LWPCookieJar()
    try:
        cj.load(cookiepath, ignore_discard=True)
    except:
        pass
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    response = opener.open(url)
    if 'redirect' in url:
        pat = re.compile('visiting=([^&]+)').findall(url)
        #splits = url.split("/auth", 1)
        #newUrl = splits[0] + '/lecture/index'
        newUrl = CLASSES_HOST + pat[0]
        #print newUrl
        response = opener.open(newUrl)
    html = response.read()
    
    response.close()
    
    ret = {}
    ret['html'] = html
    return ret

def main():
    if pluginQuery.startswith('?play='):
        play()
    elif pluginQuery.startswith('?browse='):
        browse()
    elif pluginQuery.startswith('?header'):
        return
    else:
        courses()
        
def play():
    print 'play'
    Url = pluginQuery[6:].strip()
    Url = urllib.unquote_plus(Url)
    temp = cache.cacheFunction(getURL, Url)
    data = temp['html']
    #print data
    PLContainer = common.parseDOM(data, "div", {"id": "QL_player_container_first"})
    if not PLContainer:
        #print 'oops returned here'
        return
    PLContainer = PLContainer[0]
    Link = common.parseDOM(PLContainer, "source", {"type": "video/mp4"}, ret="src")
    if not Link:
        xbmcplugin.setResolvedUrl(pluginHandle, False, xbmcgui.ListItem())
        print 'Video not found.'        
    else:
        xbmcplugin.setResolvedUrl(pluginHandle, True, xbmcgui.ListItem(path=Link[0]))
    
def browse():
    print 'browse'
    Url = pluginQuery[8:].strip()
    Url = urllib.unquote_plus(Url)
    temp = cache.cacheFunction(getURL, Url)
    #temp = getURL(Url)
    data = temp['html']
    item_list = common.parseDOM(data, "div", {"class": "item_list"})
    if not item_list:
        print 'not found'
        return
    item_list = item_list[0]
    Headers = common.parseDOM(item_list, "a", {"class": "list_header_link [a-z]*"})
    Items = common.parseDOM(item_list, "ul", {"class": "item_section_list"})
    MediaItems = []
    for i in range(len(Headers)):
        # First the header
        Lecture = common.parseDOM(Headers[i], "h3", {"class": "list_header"})[0]
        Mediaitem = MediaItem()
        Mediaitem.Url = pluginUrl + "?header"        
        Mediaitem.ListItem.setLabel(Lecture)
        MediaItems.append(Mediaitem)
        # Now the lecture segments
        Segments = common.parseDOM(Items[i], "li", {"class": "item_row [a-z]*"})
        for Segment in Segments:
            Title = common.parseDOM(Segment, "a", {"class": "lecture-link"})[0]
            Title = '* ' + common.stripTags(Title)
            Link = common.parseDOM(Segment, "a", {"class": "lecture-link"}, ret="data-lecture-view-link")[0]
            pat = re.compile('.+?org/(.+?)/.+?=(.+)').findall(Link)
            classname, vidID = pat[0]
            Mediaitem = MediaItem()
            Mediaitem.Url = pluginUrl + "?play=" + urllib.quote_plus(VID_REDIRECT_URL % (classname, classname, vidID))      
            Mediaitem.ListItem.setLabel(Title)
            Mediaitem.ListItem.setProperty('IsPlayable', 'true')
            MediaItems.append(Mediaitem)
            
    addDir(MediaItems)

    # End of Directory
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
        
    

def courses():
    print 'courses'
    
    UID = cache.cacheFunction(Login)['ID']
    if not UID:
        xbmcgui.Dialog().ok("Coursera", "Unable to login.")
        return
    Url = USER_LIST % UID
    data = cache.cacheFunction(getURL, Url)['html']
    dJson = json.loads(data)
    # set content type so library shows more views and info
    xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    MediaItems = []
    for item in dJson:        
        Courses = item['courses']
        Course = Courses[0]
        if not Course['active']:
            continue
        Title = item['name']
        Image = item['photo']
        StartDate = Course['start_date_string']
        Duration = Course['duration_string']
        Instructor = item['instructor']
        Description = item['short_description']
        HomeLink = Course['home_link']
        SplitUrl = HomeLink.rsplit("/", 2)
        Url = REDIRECT_URL % (SplitUrl[1], SplitUrl[1])
        Plot = 'Start Date: ' + StartDate + '\n'
        Plot += 'Duration: ' + Duration + '\n'
        Plot += 'Instructor: ' + Instructor + '\n'
        Plot += Description
        
        Mediaitem = MediaItem()
        Mediaitem.Image = Image
        Mediaitem.Url = pluginUrl + "?browse=" + urllib.quote_plus(Url)
        Mediaitem.ListItem.setInfo('video', { 'Title': Title, 'Plot': Plot})
        Mediaitem.ListItem.setThumbnailImage(Mediaitem.Image)
        Mediaitem.ListItem.setLabel(Title)
        Mediaitem.Isfolder = True
        MediaItems.append(Mediaitem)
    addDir(MediaItems)

    # End of Directory
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    ## Set Default View Mode. This might break with different skins. But who cares?
    SetViewMode()

def Login():
    username = Addon.getSetting("username")
    password = Addon.getSetting("password")
    cj = cookielib.LWPCookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    opener.open(CSRF_URL)
    formParams = {
            'email_address': username,
            'password': password,
        }
    
    csrftoken = ""
    for _, cookie in enumerate(cj):
        if cookie.name == 'csrftoken':
            csrftoken = cookie.value
     
    opener.addheaders = [
            ('X-Requested-With', 'XMLHttpRequest'),
            ('X-CSRFToken', csrftoken),
            ('Referer', LOGIN_REFERER),
            ('Host', LOGIN_HOST)
        ]
    
    formParams = urllib.urlencode(formParams)
    resp = opener.open(LOGIN_URL, formParams)
    html = resp.read()
    cj.save(cookiepath, ignore_discard=True)
    resp.close()
    
    rjson = json.loads(html)
    UserID = rjson['id']      
    
    ret = {}
    ret['ID'] = UserID
    return ret

# Set View Mode selected in the setting
def SetViewMode():
    try:
        # if (xbmc.getSkinDir() == "skin.confluence"):
        if Addon.getSetting('viewmode') == "1": # List
            xbmc.executebuiltin('Container.SetViewMode(502)')
        if Addon.getSetting('viewmode') == "2": # Big List
            xbmc.executebuiltin('Container.SetViewMode(51)')
        if Addon.getSetting('viewmode') == "3": # Thumbnails
            xbmc.executebuiltin('Container.SetViewMode(500)')
        if Addon.getSetting('viewmode') == "4": # Poster Wrap
            xbmc.executebuiltin('Container.SetViewMode(501)')
        if Addon.getSetting('viewmode') == "5": # Fanart
            xbmc.executebuiltin('Container.SetViewMode(508)')
        if Addon.getSetting('viewmode') == "6":  # Media info
            xbmc.executebuiltin('Container.SetViewMode(504)')
        if Addon.getSetting('viewmode') == "7": # Media info 2
            xbmc.executebuiltin('Container.SetViewMode(503)')
            
        if Addon.getSetting('viewmode') == "0": # Media info for Quartz?
            xbmc.executebuiltin('Container.SetViewMode(52)')
    except:
        print "SetViewMode Failed: " + Addon.getSetting('viewmode')
        print "Skin: " + xbmc.getSkinDir()
        
def addDir(Listitems):
    if Listitems is None:
        return
    Items = []
    for Listitem in Listitems:
        Item = Listitem.Url, Listitem.ListItem, Listitem.Isfolder
        Items.append(Item)
    handle = pluginHandle
    xbmcplugin.addDirectoryItems(handle, Items)
    
if __name__ == '__main__':
    if Addon.getSetting("username") == "" or Addon.getSetting("password") == "":
        Addon.openSettings()
        if Addon.getSetting("username") == "" or Addon.getSetting("password") == "":
            xbmcgui.Dialog().ok("Coursera", "Username and/or password not specified.")            
    if Addon.getSetting("username") <> "" and Addon.getSetting("password") <> "":
        if not os.path.exists(settingsDir):
            os.mkdir(settingsDir)
        if not os.path.exists(cacheDir):
            os.mkdir(cacheDir)
        main()
