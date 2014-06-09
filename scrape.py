#!/usr/bin/env python3

"""fdscrape, an F-droid source code scraper

Usage:
  fdscrape [-v] [-l FILE] --all
  fscrape (-h | --help | help)
  fscrape --version

Options:
  --all      Scrape all applications on F-droid.org
  -h --help  Show this screen.
  -v         Increase verbosity.
  -l         Log output to a file.
  --version  Display version.

fdscrape is written in Python 3 by Quint Guvernator and licensed by the GPLv3.
"""

VERSION = "0.1.0"
FDROID_BROWSE_URL = "https://f-droid.org/repository/browse/"

import urllib.request
import os
from bs4 import BeautifulSoup as bs
from docopt import docopt

def getAllAppLinks(url=FDROID_BROWSE_URL, log=lambda x: None):
    allLinks = []
    page = 1
    log("Getting all links...")
    while url is not None:
        log("    got page {}".format(page))
        links, url = getAppLinks(url=url, log=log)
        allLinks.append(links)
        page += 1
    return allLinks

def getAppLinks(url=FDROID_BROWSE_URL, log=lambda x: None):
    '''Gets all app links on a page and returns the links as an array and the
    next page as a string (or None if it's over) in a tuple.

    e.g.

    (["http://w3c.org/", "http://example.com/"],
     "http://next-page.example.com")

    or

    (["http://w3c.org/", "http://example.com/"],
     None)
    '''
    with urllib.request.urlopen(url) as f:
        listing = r.read()
    soup = bs(listing)
    appBlocks = soup.find_all(id="appheader")
    for app in appBlocks:
        log(app.string, app)
    nextLink = soup.find(text="next>")
    return nextLink.href

if __name__ == "__main__":
    args = docopt(__doc__, version=VERSION)
    if docopt["-v"] and docopt["-l"]:
        os.exit(print("select either logging or verbosity, not both"))

    if docopt["-v"]:
        logfn = print
    elif docopt["-l"] and not docopt["-v"]:
        logFile = open(docopt["-l"], 'a')
        logfn = logFile.write

    if docopt["--all"]:
        getAllApps()
