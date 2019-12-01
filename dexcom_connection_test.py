#!/usr/bin/env python

import datetime
import logging
import os
import re
import requests
import time
import urllib
import facebook
import tweepy

log = logging.getLogger(__file__)
log.setLevel(logging.ERROR)

formatter = logging.Formatter(
    '{"timestamp": "%(asctime)s", "progname":' +
    ' "%(name)s", "loglevel": "%(levelname)s", "message":, "%(message)s"}')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
ch.setLevel(logging.DEBUG)
log.addHandler(ch)

# Get sensitive credentials from the environment to avoid accidentally open sourcing them
# (https://github.com/jaylagorio/Craal)

# The username and password for the Dexcom servers to check against.
DEXCOM_ACCOUNT_NAME = os.getenv("DEXCOM_ACCOUNT_NAME")
DEXCOM_PASSWORD = os.getenv("DEXCOM_PASSWORD")

# The ID of the Facebook Page to post on and the Access Token to use
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")

# The consumer and access tokens and secrets to post on Twitter
TWITTER_CONSUMER_TOKEN = os.getenv("TWITTER_CONSUMER_TOKEN")
TWITTER_CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# Messages to post when the system goes up or down
MESSAGE_SERVICE_DOWN = "The Dexcom Share service appears to be down."
MESSAGE_SERVICE_UP = "The Dexcom Share service appears to have been restored."

CHECK_INTERVAL = 60 * 2.5
AUTH_RETRY_DELAY = 5
FAIL_RETRY_DELAY_BASE = 2
MAX_AUTHFAILS = 3
MAX_FETCHFAILS = 10
RETRY_DELAY = 60 # Seconds
LAST_READING_MAX_LAG = 60 * 15

last_date = 0

# This data is needed to communicate with the Dexcom services. It makes us look more like their client.
class DexcomServerData:
    applicationId = "d89443d2-327c-4a6f-89e5-496bbb0317db"
    agent = "Dexcom Share/3.0.2.11 CFNetwork/711.2.23 Darwin/14.0.0"
    login_url = "https://share1.dexcom.com/ShareWebServices/Services/General/LoginPublisherAccountByName"
    accept = 'application/json'
    content_type = 'application/json'
    LatestGlucose_url = "https://share1.dexcom.com/ShareWebServices/Services/Publisher/ReadPublisherLatestGlucoseValues"
    accountName = DEXCOM_ACCOUNT_NAME 
    password = DEXCOM_PASSWORD 
    interval = 60


# Base exception class
class Error(Exception):
    """Base class for exceptions in this module."""
    pass


# Exceptions when authentication fails (or the service is down)
class AuthError(Error):
    """Exception raised for errors when trying to Auth to Dexcome share
    """

    def __init__(self, status_code, message):
        self.expression = status_code
        self.message = message
        log.error(message.__dict__)


# Exceptions when attempting to get a BG value fails
class FetchError(Error):
    """Exception raised for errors in the data fetch.
    """

    def __init__(self, status_code, message):
        self.expression = status_code
        self.message = message
        log.error(message.__dict__)


# Posts the system status to Twitter
def post_twitter_page(service_down=True):
    # Get an OAuth handler and set the access token
    auth = tweepy.OAuthHandler(TWITTER_CONSUMER_TOKEN, TWITTER_CONSUMER_SECRET)
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
    api = tweepy.API(auth)

    # Send the tweet
    if (service_down):
        status = api.update_status(status=MESSAGE_SERVICE_DOWN) 
    else:
        status = api.update_status(status=MESSAGE_SERVICE_UP)


# Posts the system status to Facebook
def post_facebook_page(service_down=True):
    graph = facebook.GraphAPI(FACEBOOK_ACCESS_TOKEN)
    # Get page token to post as the page. You can skip 
    # the following if you want to post as yourself. 
    resp = graph.get_object('me/accounts')
    page_access_token = None
    for page in resp['data']:
        if page['id'] == FACEBOOK_PAGE_ID:
            page_access_token = page['access_token']
    graph = facebook.GraphAPI(page_access_token)

    # Post the update
    if (sevice_down):
        status = graph.put_object(parent_object="me", connection_name="feed", message=MESSAGE_SERVICE_DOWN)
    else:
        status = graph.put_object(parent_object="me", connection_name="feed", message=MESSAGE_SERVICE_UP)
                

# Attempt to read the status file that shows whether prior tests showed the service to be available
def get_previous_server_working():
    # Try to read the file, if it doesn't exist assume the service was working
    try:
        with open('prevstate.bin', 'r') as content_file:
            content = content_file.read()
    except:
        content = "up"

    # If the service was down, return False, True otherwise
    if content == "down":
        return False
    else:
        return True


# Write the new previous state of the server based on the check just performed
def set_previous_server_working(service_down):
    content_file = open("prevstate.bin","w+")
    if (service_down):
        content_file.write("down")
    else:
        content_file.write("up")

    content_file.close()


# Attempt to fetch a reading from the Dexcom site. Requires a valid Session ID.
def fetch(sessionID):
    """ Fetch latest reading from dexcom share
    """
    # Build the api query URL for the data fetch
    q = {
        "sessionID": sessionID,
        "minutes":  1440,
        "maxCount": 1
        }
    url = DexcomServerData.LatestGlucose_url + '?' + urllib.parse.urlencode(q)

    # Build the body and headers for the request
    body = {
            'applicationId': DexcomServerData.applicationId
            }

    headers = {
            'User-Agent': DexcomServerData.agent,
            'Content-Type': DexcomServerData.content_type,
            'Content-Length': "0",
            'Accept': DexcomServerData.accept
            }

    # Post the request
    return requests.post(url, json=body, headers=headers)


def parse_dexcom_response(res):
    epochtime = int((
                datetime.datetime.utcnow() -
                datetime.datetime(1970, 1, 1)).total_seconds())
    try:
        last_reading_time = int(
            re.search('\d+', res.json()[0]['ST']).group())/1000
        reading_lag = epochtime - last_reading_time
        mgdl = res.json()[0]['Value']
        log.info(
                "Last bg: {}  last reading at: {} seconds ago".format(mgdl, reading_lag))
        if reading_lag > LAST_READING_MAX_LAG:
            log.warning(
                "***WARN It has been {} minutes since DEXCOM got a" +
                "new measurement".format(int(reading_lag/60)))
        return {
                "bg": mgdl,
                "reading_lag": reading_lag,
                "last_reading_time": last_reading_time
                }
    except IndexError:
        log.error(
                "Caught IndexError: return code:{} ... response output" +
                " below".format(res.status_code))
        log.error(res.__dict__)
        return None


# Attempt to authenticate against the Dexcom servers
def authorize():
    """ Login to dexcom share and get a session token """

    # Build the login URL, body, and headers to look like the app
    url = DexcomServerData.login_url
    body = {
        "password": DexcomServerData.password,
        "applicationId": DexcomServerData.applicationId,
        "accountName": DexcomServerData.accountName
        }
    headers = {
        'User-Agent': DexcomServerData.agent,
        'Content-Type': DexcomServerData.content_type,
        'Accept': DexcomServerData.accept
        }

    # Post the requrst to authenticate
    return requests.post(url, json=body, headers=headers)


# Get the session ID we'll need to try and get BGs
def get_sessionID():
    sessionID = ""
    authfails = 0

    # Try MAX_AUTHFAILS number of times to authenticate. If we don't actually get a Session ID
    # the system is probably down.
    while not sessionID:
        # Authenticate to the servers
        res = authorize()

        # If we get a 200 code we successfully authenticated and they might not be down.
        if res.status_code == 200:
            sessionID = res.text.strip('"')
            log.debug("Got auth token {}".format(sessionID))

        # If we get a 500 error code the servers are probably down
        elif res.status_code == 502 or res.status_code == 503:
            log.warning("Auth failed: Service Unavailable ({})".format(res.status_code))
            if authfails > MAX_AUTHFAILS:
                # We've tried enough times to consider the error repeatable. The
                # servers are probably down.
                raise AuthError(res.status_code, res)
            else:
                # We haven't tried the maximum number of times, hold off and try again.
                time.sleep(AUTH_RETRY_DELAY)
                authfails += 1

        # If we get some different error code we should log it but we don't expect others.
        else:
            if authfails > MAX_AUTHFAILS:
                raise AuthError(res.status_code, res)
            else:
                log.warning("Auth failed with: {}".format(res.status_code))
                time.sleep(AUTH_RETRY_DELAY)
                authfails += 1

    # Return a session ID if authentication was successful
    return sessionID


# Runs the meat of the tests and tells you if the service is up
def dexcom_check_connect():
    log.info("Running test as Dexcom user {}...".format(DEXCOM_ACCOUNT_NAME))

    # Attempt to authenticate, get a session ID, and pass that session ID to
    # the function to download BGs from Dexcom
    try:
        res = fetch(get_sessionID())
        if res and res.status_code < 400:
            reading = parse_dexcom_response(res)
            if reading:
                log.info("Successfully returned a reading.")
                return True
            else:
                log.error("parse_dexcom_response returned None. investigate above logs")
                return False
        else:
            log.warning("Saw an error from the dexcom api, code: {}.  details to follow".format(res.status_code))
            raise FetchError(res.status_code, res)
    except AuthError:
        return False
    except FetchError:
        return False

# Create logger and set it up
log = logging.getLogger(__file__)
log.setLevel(logging.DEBUG)
fh = logging.FileHandler('dexcom_tools.log')
fh.setLevel(logging.INFO)
formatter = logging.Formatter(
    '{"timestamp": "%(asctime)s", "progname":' +
    '"%(name)s", "loglevel": "%(levelname)s", "message":, "%(message)s"}')
fh.setFormatter(formatter)
log.addHandler(fh)

# Check to see what the last known state of the service was
previous_server_working = get_previous_server_working()

# Check to see what the current state of the service is
if dexcom_check_connect():
    current_server_working = True
else:
    current_server_working = False

# And now check to see if based on those two states that things have changed and notify as appropriate
if current_server_working != previous_server_working:
    log.info("Service availability state has changed.")
    if current_server_working == True:
        # Server must have come back up from being down
        log.info("Service is up.")
        set_previous_server_working(False)
        #post_facebook_page(False)
        #post_twitter_page(False)
    else:
        # Server must have been up and is now down
        log.info("Service is down.")
        set_previous_server_working(True)
        #post_facebook_page(True)
        #post_twitter_page(True)
else:
    if current_server_working:
        log.info("Service availability hasn't changed, the service is available")
    else:
        log.info("Service availability hasn't changed, the service is down")
