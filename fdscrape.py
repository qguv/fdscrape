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
    log("Downloading {} to {}".format(filename.name, filename.parent))
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


def prefixFromLink(s):
    repoPrefix = "https://f-droid.org/repository/browse/?fdid="
    repoSuffix = "&fdpage="

    s = s.replace(repoPrefix, '', 1)
    # get rid of page numbers
    if repoSuffix in s:
        s = s.rsplit(repoSuffix, maxsplit=1)[0]
    return s


def getAppLinks(url, log=lambda x: None):
    '''Gets all app links on a page and returns the links as a list, their
    names as a list, the package names as a list, and the next page as a string (or None if it's over)
    all bundled together in a tuple.

    e.g.

    (["http://app1.example.org/", "http://app2.example.com/"],
     ["app1", "app2"],
     ["org.mozilla.app1", "com.ableton.app2"],
     "http://next-page.example.com")

    or

    (["http://app1.example.org/", "http://app2.example.com/"],
     ["app1", "app2"],
     ["org.mozilla.app1", "com.ableton.app2"],
     None)
    '''
    with urllib.request.urlopen(url) as r:
        soup = bs(r)

    appBlocks = soup(id="appheader")
    appNames = [ b.find('p', recursive=False).find("span").string for b in appBlocks ]
    appLinks = [ b.parent.get('href') for b in appBlocks ]
    appPrefixes = [ prefixFromLink(l) for l in appLinks ]

    nextLink = soup.find('a', text="next>")
    if nextLink is not None:
        nextLink = nextLink.get('href')
    log("Next page: {}".format(nextLink))
    log('')

    return (appLinks, appNames, appPrefixes, nextLink)


def getDownloadLink(url, log=lambda x: None):
    with urllib.request.urlopen(url) as r:
        soup = bs(r)
    link = soup.find('a', text="source tarball")
    if link is None:
        return
    return link.get("href")


class Rating:

    def __init__(self, ones, twos, threes, fours, fives):
        # how many of each rating the program got
        self.ones = ones
        self.twos = twos
        self.threes = threes
        self.fours = fours
        self.fives = fives

        # a helper array (of pointers)
        self.data = [self.ones, self.twos, self.threes, self.fours,
                self.fives]

    def count(self):
        return sum(self.data)

    def average(self):
        weighted = 0

        # one-indexing
        for i, x in enumerate(self.data):
            weighted += x * (i + 1)
        return weighted / self.count()

    def __str__(self):
        lines = [ x for x in self.data ]
        lines.append(self.count())
        lines.append(self.average())
        lines = [ str(x) for x in lines ]
        return '\n'.join(lines)

    def distribution(self):
        bits = [ "{}: {}".format((i + 1), x) for i, x in enumerate(self.data) ]
        return ", ".join(bits)


def getPlayRating(package):
    prefix = "https://play.google.com/store/apps/details?id="

    try:
        with urllib.request.urlopen(prefix + package) as r:
            soup = bs(r)
    except urllib.error.HTTPError:
        return

    hist = soup.find("div", class_="rating-histogram")
    if hist is None:
        return

    ratings = hist(class_="rating-bar-container")
    ratings = [ r.find("span", class_="bar-number").text for r in ratings ]
    ratings = [ int(r.replace(',', '')) for r in ratings ]
    ratings.reverse() #  one-to-five in increasing order
    return Rating(*ratings)


def getAllApps(downloadPath, url=FDROID_BROWSE_URL, log=lambda x: None):
    page = 0
    nextUrl = url
    while nextUrl is not None:
        page += 1
        log("Scraping app index, page {}...".format(page))
        appLinks, names, packages, nextUrl = getAppLinks(nextUrl, log=addLogLevel(log))
        log("Got page {}.".format(page))
        log('')
        log("Downloading source of all available apps on page {}...".format(page))
        for appLink, name, package in zip(appLinks, names, packages):

            log('')
            log('"{}"'.format(name))

            # test for a directory with the same package name
            downloadFilename = pathlib.Path(downloadPath) / package
            if downloadFilename.exists():
                log("\tPath {} already exists, skipping download...".format(downloadFilename))
                continue
            downloadFilename.mkdir()

            # save google play rating to a file (rating.txt) in the same path
            log("\tLooking for Google Play rating (as {})...".format(package))
            rating = getPlayRating(package)
            if rating is None:
                log("\tCouldn't find rating on the Google Play store.")
                log("\tSkipping download...")
                continue
            log("\tApp is rated \"{:.2}\" stars ({})".format(rating.average(), rating.distribution()))
            log('')
            ratingFilename = downloadFilename / "rating.txt"
            log("\tSaving rating to file ({})...".format(ratingFilename))
            with ratingFilename.open('x') as f:
                f.write(str(rating))
            log("\tDone.")
            log('')

            # get link to source
            log("\tGetting remote link to source...")
            downloadLink = getDownloadLink(appLink, log=addLogLevel(log))
            if downloadLink is None:
                log("\tNo source code available for \"{}\" from f-droid.org.".format(name))
                log("\tConsider visiting the f-droid detail page manually at:")
                log("\t\t{}".format(appLink))
                log("\tand looking for the link to the source code.")
                log("\tSkipping download...")
                log('')
                continue

            # calculate tar-gz filename
            safename = ''
            for c in name:
                if c.isalnum():
                    safename += c.lower()
                elif c.isspace():
                    safename += '_'
            safename += ".tar.gz"
            downloadFilename = downloadFilename / safename

            # download the file
            downloadFile(downloadLink, downloadFilename, log=addLogLevel(log))

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
