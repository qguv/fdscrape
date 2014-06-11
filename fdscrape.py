#!/usr/bin/env python3

"""fdscrape, an F-droid source code scraper

Usage:
  fdscrape.py [-v] [-l LOGFILE] DOWNLOAD_PATH
  fdscrape.py (-h | --help | help)
  fdscrape.py --version

Options:
  -l LOGFILE       Log output to a file.
  -v               Increase verbosity.
  -h --help        Show this screen.
  --version        Display version.

fdscrape is written in Python 3 by Quint Guvernator and licensed by the GPLv3.
"""

VERSION = "0.1.0"
FDROID_BROWSE_URL = "https://f-droid.org/repository/browse/"

import os, sys
import urllib.request
from bs4 import BeautifulSoup as bs
from docopt import docopt
import shutil
import pathlib


def addLogLevel(logfn):
    return lambda x: logfn('\t' + x)


def downloadFile(url, filename, log=lambda x: None):
    log("Downloading \"{}\"".format(filename.name))
    try:
        with urllib.request.urlopen(url, timeout=10) as response, filename.open('xb') as outFile:
            shutil.copyfileobj(response, outFile)
            log("Done.")
    except FileExistsError:
        log("Path {} already exists, skipping...".format(filename))
    except KeyboardInterrupt:
        log("User killed program, removing partially downloaded file...")
        os.remove(filename.as_posix())
        log("Done. Exiting...")
        sys.exit(1)


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
        log('')

    nextLink = soup.find('a', text="next>")
    if nextLink is not None:
        nextLink = nextLink.get('href')
    log("Next page: {}".format(nextLink))
    log('')

    return (appLinks, appNames, nextLink)


def getDownloadLink(url, log=lambda x: None):
    with urllib.request.urlopen(url) as r:
        soup = bs(r)
    link = soup.find('a', text="source tarball")
    if link is None:
        return
    return link.get("href")


def getAllApps(downloadPath, url=FDROID_BROWSE_URL, log=lambda x: None):
    page = 0
    nextUrl = url
    while nextUrl is not None:
        page += 1
        log("Scraping app index, page {}...".format(page))
        appLinks, names, nextUrl = getAppLinks(nextUrl, log=addLogLevel(log))
        log("Got page {}.".format(page))
        log('')
        log("Downloading source of all available apps on page {}...".format(page))
        for appLink, name in zip(appLinks, names):
            safename = ''
            for c in name:
                if c.isalnum():
                    safename += c.lower()
                elif c.isspace():
                    safename += '_'
            safename += ".tar.gz"
            downloadFilename = pathlib.Path(downloadPath) / safename
            if downloadFilename.exists():
                log("\tPath {} already exists in {}, skipping download...".format(downloadFilename, downloadPath))
                continue
            log('')
            log("\tGetting remote link to source of \"{}\"...".format(name))
            downloadLink = getDownloadLink(appLink, log=addLogLevel(log))
            if downloadLink is None:
                log("\tNo source code available for \"{}\" from f-droid.org.".format(name))
                log("\tConsider visiting the f-droid detail page manually at:")
                log("\t\t{}".format(appLink))
                log("\tand looking for the link to the source code.")
                log('')
                continue
            downloadFile(downloadLink, pathlib.Path(downloadPath) / safename, log=addLogLevel(log))
        log("Page {} complete.".format(page))
        log('')
    log("Downloaded {} pages of apps to {}".format(page, downloadPath))


if __name__ == "__main__":
    args = docopt(__doc__, version=VERSION)

    # command-line errors
    if args["-v"] and args["-l"]:
        print("select either logging or verbosity, not both")
        sys.exit(2)

    if args["-v"]:
        logfn = print
    elif args["-l"] and not args["-v"]:
        logFile = open(args["LOGFILE"], 'a')
        logfn = lambda x: print(x, file=logFile)
    else:
        logfn = lambda x: None

    downloadPath=pathlib.Path(args["DOWNLOAD_PATH"])
    try:
        downloadPath.mkdir()
    except FileExistsError:
        pass
    getAllApps(downloadPath, log=logfn)
    logfn('')
    logfn("Exiting...")

    if args["-l"] and not args["-v"]:
        logFile.close()
