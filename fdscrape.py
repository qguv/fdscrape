#!/usr/bin/env python3

"""fdscrape, an F-droid source code scraper

Usage:
  fdscrape.py [-v] [-l LOGFILE] --all DOWNLOAD_PATH
  fdscrape.py (-h | --help | help)
  fdscrape.py --version

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
DEFAULT_DOWNLOAD_PATH = path

import os
import urllib.request
from bs4 import BeautifulSoup as bs
from docopt import docopt
import shutil
import pathlib


def addLogLevel(logfn):
    return lambda x: logfn('\t' + x)


def downloadFile(url, filename):
    print(url)
    with urllib.request.urlopen(url, timeout=10) as response, open(filename, 'wb') as outFile:
        shutil.copyfileobj(response, outFile)


def getAppLinks(url, log=lambda x: None):
    '''Gets all app links on a page and returns the links as an array, their
    names as an array, and the next page as a string (or None if it's over) all
    bundled together in a tuple.

    e.g.

    (["http://app1.example.org/", "http://app2.example.com/"],
     ["app1", "app2"])
     "http://next-page.example.com")

    or

    (["http://app1.example.org/", "http://app2.example.com/"],
     ["app1", "app2"])
     None)
    '''
    with urllib.request.urlopen(url) as r:
        soup = bs(r)

    appBlocks = soup(id="appheader")
    appLinks = [ b.parent.get('href') for b in appBlocks ]
    appNames = [ b.find('p', recursive=False).find("span").string for b in appBlocks ]

    for n, l in zip(appNames, appLinks):
        log("Name: {}".format(n))
        log("Link: {}".format(l))

    nextLink = soup.find('a', text="next>")
    if nextLink is not None:
        nextLink = nextLink.get('href')
    log("")
    log("Next page: {}".format(nextLink))

    return (appLinks, appNames, nextLink)


def getDownloadLink(url, log=lambda x: None):
    with urllib.request.urlopen(url) as r:
        soup = bs(r)
    link = soup.find('a', text="source tarball")
    return link.get("href")  # TODO


def getAllApps(downloadPath, url=FDROID_BROWSE_URL, log=lambda x: None):
    page = 0
    nextUrl = url
    log("Getting page {}".format(page))
    while nextUrl is not None:
        page += 1
        appLinks, names, nextUrl = getAppLinks(nextUrl, log=addLogLevel(log))
        log("Got page {}".format(page))
        for appLink, name in zip(appLinks, names):
            downloadLink = getDownloadLink(appLink, log=addLogLevel(log))
            log("Downloading \"{}\"".format(name))
            downloadFile(downloadLink, downloadPath / name)
        log("Downloaded {} pages of apps".format(page))


if __name__ == "__main__":
    args = docopt(__doc__, version=VERSION)

    # command-line errors
    if args["-v"] and args["-l"]:
        print("select either logging or verbosity, not both")
        os.exit(2)

    if args["-v"]:
        logfn = print
    elif args["-l"] and not args["-v"]:
        logFile = open(args["LOGFILE"], 'a')
        logfn = lambda x: print(x, file=logFile)
    else:
        logfn = lambda x: None

    if args["--all"]:
        downloadPath=pathlib.Path(args["DOWNLOAD_PATH"])
        getAllApps(downloadPath=args["DOWNLOAD_PATH"], log=logfn)

    if args["-l"] and not args["-v"]:
        logFile.close()
