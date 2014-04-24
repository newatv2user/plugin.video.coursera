import sys, os
import urllib, urllib2, cookielib, re
import xbmcaddon, xbmcgui, xbmcplugin, xbmc
from xbmcgui import ListItem
import StorageServer, CommonFunctions
import json
import random

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
cache = StorageServer.StorageServer(Addonid, 12)

#CSRF_URL = 'https://www.coursera.org/maestro/api/user/csrf_token'
CSRF_URL = 'https://class.coursera.org/ml-2012-002/class/index'
REDIRECT_URL = 'https://class.coursera.org/%s/auth/auth_redirector?type=login&subtype=normal&email=&visiting=/%s/lecture/index&minimal=true'
#LOGIN_URL = 'https://www.coursera.org/maestro/api/user/login'
LOGIN_URL = 'https://accounts.coursera.org/api/v1/login'
#LOGIN_REFERER = 'https://www.coursera.org/account/signin'
LOGIN_REFERER = 'https://accounts.coursera.org/signin'
#LOGIN_HOST = "www.coursera.org"
LOGIN_HOST = 'https://accounts.coursera.org'
#USER_LIST = 'https://www.coursera.org/maestro/api/topic/list_my?user_id=%s'
USER_LIST = 'https://www.coursera.org/maestro/api/topic/list_my'
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
    try:
        response = opener.open(url)        
    except:
        print 'Need to log in'
        if Login():
            print 'Logged in'
            cj.load(cookiepath, ignore_discard=True)
        else:
            raise 'Could not log in'
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
    elif pluginQuery.startswith('?othercourses'):
        courses(True)
    else:
        courses()
        
def play():
    print 'play'
    Url = pluginQuery[6:].strip()
    Url = urllib.unquote_plus(Url)
    temp = cache.cacheFunction(getURL, Url)
    #temp = getURL(Url)
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
    item_list = common.parseDOM(data, "div", {"class": "course-item-list"})
    if not item_list:
        print 'not found'
        return
    item_list = item_list[0]
    Headers = common.parseDOM(item_list, "div", {"class": "course-item-list-header [a-z]*"})
    Items = common.parseDOM(item_list, "ul", {"class": "course-item-list-section-list"})
    MediaItems = []
    for i in range(len(Headers)):
        # First the header
        Lecture = common.parseDOM(Headers[i], "h3")[0]
        Mediaitem = MediaItem()
        Mediaitem.Url = pluginUrl + "?header"
        Lecture = common.stripTags(Lecture)
        Lecture = common.replaceHTMLCodes(Lecture)
        Lecture = Lecture.strip()
        Mediaitem.ListItem.setLabel(Lecture)
        MediaItems.append(Mediaitem)
        # Now the lecture segments
        Segments = common.parseDOM(Items[i], "li")
        for Segment in Segments:
            print Segment
            Title = common.parseDOM(Segment, "a", {"class": "lecture-link"})[0]
            Title = '* ' + common.stripTags(Title)
            Link = common.parseDOM(Segment, "a", {"class": "lecture-link"}, ret="data-modal-iframe")[0]
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
        
    

def courses(Active=False):
    print 'courses'
    
    #UID = cache.cacheFunction(Login)['ID']
    ##UID = Login()['ID']
    ##if not UID:
    ##    xbmcgui.Dialog().ok("Coursera", "Unable to login.")
    ##    return
    ##Url = USER_LIST % UID
    Url = USER_LIST
    try:
        data = cache.cacheFunction(getURL, Url)['html']
    except:
        print 'Login problem'
        return
    #data = getURL(Url)['html']
    dJson = json.loads(data)
    # set content type so library shows more views and info
    xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    MediaItems = []
    for item in dJson:        
        Courses = item['courses']
        Course = Courses[0]
        if Course['active'] == Active:
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
        Plot = 'Start Date: ' + (StartDate if StartDate else '') + '\n'
        Plot += 'Duration: ' + (Duration  if Duration else '') + '\n'
        Plot += 'Instructor: ' + (Instructor if Instructor else '') + '\n'
        Plot += (Description if Description else '')
        Plot = Plot.replace('<br>', '\n')
        
        YoutubeID = item['video']
        Trailer = None
        if YoutubeID != '':
            Trailer = 'plugin://plugin.video.youtube/?action=play_video&videoid=%s' % YoutubeID
        
        Mediaitem = MediaItem()
        Mediaitem.Image = Image
        Mediaitem.Url = pluginUrl + "?browse=" + urllib.quote_plus(Url)
        if not Trailer:
            Mediaitem.ListItem.setInfo('video', { 'Title': Title, 'Plot': Plot})
        else:
            Mediaitem.ListItem.setInfo('video', { 'Title': Title, 'Plot': Plot, 'Trailer': Trailer})
        Mediaitem.ListItem.setThumbnailImage(Mediaitem.Image)
        Mediaitem.ListItem.setLabel(Title)
        Mediaitem.Isfolder = True
        MediaItems.append(Mediaitem)
    # Browse Inactive courses
    if not Active:
        Mediaitem = MediaItem()
        Mediaitem.Url = pluginUrl + "?othercourses"
        Mediaitem.ListItem.setInfo('video', { 'Title': 'Other Courses', 'Plot': 'Subscribed but inactive.'})
        Mediaitem.ListItem.setLabel('Other Courses')
        Mediaitem.Isfolder = True
        MediaItems.append(Mediaitem)
    addDir(MediaItems)

    # End of Directory
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    ## Set Default View Mode. This might break with different skins. But who cares?
    SetViewMode()
    
def csrfMake():
    n = ''
    t = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    e = 24
    for r in range(e):
        n += t[random.randrange(len(t))]
        
    return n

def getCsrf():
    try:
        cj = cookielib.LWPCookieJar()
        try:
            cj.load(cookiepath, ignore_discard=True)
        except:
            pass
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        resp = opener.open(CSRF_URL)
        html = resp.read()
        cj.save(cookiepath, ignore_discard=True)
        resp.close()

        csrftoken = None
        for _, cookie in enumerate(cj):
            if cookie.name == 'csrf_token':
                csrftoken = cookie.value
            
        if not csrftoken:
            raise 'Could not get csrf_token'

        return csrftoken
    except:
        print 'Error occurred in getCsrf'

class MyHTTPRedirectHandler(urllib2.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        print "Cookie Manip Right Here"
        return urllib2.HTTPRedirectHandler.http_error_302(self, req, fp, code, msg, headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_302

def Login():
    try:
        username = Addon.getSetting("username")
        password = Addon.getSetting("password")
        cj = cookielib.LWPCookieJar()
        try:
            cj.load(cookiepath, ignore_discard=True)
        except:
            pass
        opener = urllib2.build_opener(MyHTTPRedirectHandler, urllib2.HTTPCookieProcessor(cj))
        # change email_address to email
        formParams = {
            'email': username,
            'password': password,
            }
    
        csrftoken = None
        for _, cookie in enumerate(cj):
            if cookie.name == 'csrf_token':
                csrftoken = cookie.value
            
        if not csrftoken:
            #csrftoken = csrfMake()
            csrftoken = getCsrf()
        
        print 'csrf_token: ' + csrftoken
        #opener.addheaders = [
        #                     ('X-Requested-With', 'XMLHttpRequest'),
        #                     ('X-CSRFToken', csrftoken),
        #                     ('Referer', LOGIN_REFERER),
        #                     ('Host', LOGIN_HOST),
        #                     ('Cookie', 'csrftoken=%s' % csrftoken)
        #                    ]
        opener.addheaders = [
                                ('Referer', LOGIN_REFERER),
                                ('Origin', LOGIN_HOST),
                                ('X-CSRFToken', csrftoken),
                                ('Cookie', 'csrftoken=%s' % csrftoken),
                                ('X-Requested-With', 'XMLHttpRequest'),
                                ('Content-type', 'application/x-www-form-urlencoded')]#,
                                #('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:21.0) Gecko/20100101 Firefox/21.0'),
                                #('Accept', '*/*'),
                                #('Accept-Encoding', 'gzip,deflate,sdch')
                            #]
        
        formParams = urllib.urlencode(formParams)
        try:
            resp = opener.open(LOGIN_URL, formParams)
        except URLError as e:
            if hasattr(e, 'reason'):
                print 'Server could not be reached.'
                print 'Reason: ', e.reason
            elif hasattr(e, 'code'):
                print 'Server error'
                print 'Error code: ', e.code
        else:
            pass
            
        html = resp.read()
        cj.save(cookiepath, ignore_discard=True)
        resp.close()

        print cj
        cjnew = cookielib.LWPCookieJar()
        try:
            cjnew.load(cookiepath, ignore_discard=True)
        except:
            pass
        loggedIn = 0
        for _, cookie in enumerate(cjnew):
            if cookie.name == 'maestro_login_flag':
                loggedIn = int(cookie.value)                

        if loggedIn == 1:
            return True
        return False
                
    except:
        e = sys.exc_info()[0]
        print e
        return False    

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
