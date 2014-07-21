#!/usr/bin/env python3

"""fdscrape, an F-droid source code scraper

Usage:
  fdscrape.py DOWNLOAD_PATH
  fdscrape.py (-h | --help | help)
  fdscrape.py --version

Options:
  -h --help        Show this screen.
  --version        Display version.

fdscrape is written by Quint Guvernator and licensed by the GPLv3.
"""

VERSION = "0.1.0"
FDROID_BROWSE_URL = "https://f-droid.org/repository/browse/"

import os, sys
import urllib.request
from bs4 import BeautifulSoup as bs
from docopt import docopt
import shutil
import pathlib
import json
from subprocess import check_call


def getPackage(url, filename):
    print("\tDownloading {} to {}".format(filename.name, filename.parent))
    try:
        with urllib.request.urlopen(url, timeout=10) as response, filename.open('xb') as outFile:
            shutil.copyfileobj(response, outFile)
        print("\tDone.")
    except FileExistsError:
        print("\tPath {} already exists, skipping...".format(filename))
        return
    except KeyboardInterrupt:
        print("\tUser killed program, removing partially downloaded file...")
        os.remove(filename.as_posix())
        print("\tDone. Exiting...")
        sys.exit(1)

    print("\tExtracting {}".format(filename))
    check_call(["tar", "xf", str(filename), "-C", str(filename.parent)])

    theDir = [ str(x) for x in filename.parent.glob("*/") if x.is_dir() ]
    if len(theDir) != 1:
        raise OSError("Too many directories in file!")
    else:
        theDir = theDir[0]

    check_call(["mv", theDir, str(filename.parent / "src")])
    check_call(["rm", str(filename)])

    print("\tDone.")

def prefixFromLink(s):
    repoPrefix = "https://f-droid.org/repository/browse/?fdid="
    repoSuffix = "&fdpage="

    s = s.replace(repoPrefix, '', 1)
    # get rid of page numbers
    if repoSuffix in s:
        s = s.rsplit(repoSuffix, maxsplit=1)[0]
    return s

def getAppLinks(url):
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
    print("Next page: {}".format(nextLink))

    return (appLinks, appNames, appPrefixes, nextLink)

def getDownloadLink(url):
    with urllib.request.urlopen(url) as r:
        soup = bs(r)
    link = soup.find('a', text="source tarball")
    if link is None:
        return
    return link.get("href")

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
    ratingCount = sum(ratings)

    if ratingCount == 0:
        return

    # dict maps weighting (how many stars) to count (how many people rated at
    # this weight)
    ratingWeights = { i + 1: num for i, num in enumerate(ratings) }

    theSum = sum(( weight * count for weight, count in ratingWeights.items() ))
    theMean = theSum / ratingCount

    # make a str:int statistics dictionary
    stats = { "star_{}".format(k): v for k, v in ratingWeights.items() }
    stats["star_mean"] = theMean
    stats["star_count"] = ratingCount

    return stats

def getAllApps(downloadPath, url=FDROID_BROWSE_URL):
    page = 0
    nextUrl = url
    while nextUrl is not None:
        page += 1
        print("Scraping app index, page {}...".format(page))
        appLinks, names, packages, nextUrl = getAppLinks(nextUrl)
        print("Got page {}.".format(page))
        print('')
        print("Downloading source of all available apps on page {}...".format(page))
        for appLink, name, package in zip(appLinks, names, packages):

            print('')
            print('"{}"'.format(name))

            # test for a directory with the same package name
            downloadFilename = pathlib.Path(downloadPath) / package
            if downloadFilename.exists():
                print("\tPath {} already exists, skipping download...".format(downloadFilename))
                continue

            # save google play rating to a file (rating.json) in the same path
            print("\tLooking for Google Play rating (as {})...".format(package))
            rating = getPlayRating(package)
            if rating is None:
                print("\tCouldn't find rating data on the Google Play store.")
                print("\tSkipping download...")
                continue

            print("\tMaking a directory for the application: {}...".format(downloadFilename))
            downloadFilename.mkdir()
            ratingFilename = downloadFilename / "rating.json"
            print("\tSaving rating to file ({})...".format(ratingFilename))
            with ratingFilename.open('x') as f:
                json.dump(rating, f)
            print("\tDone.")
            print('')

            # get link to source
            print("\tGetting remote link to source...")
            downloadLink = getDownloadLink(appLink)
            if downloadLink is None:
                print("\tNo source code available for \"{}\" from f-droid.org.".format(name))
                print("\tConsider visiting the f-droid detail page manually at:")
                print("\t\t{}".format(appLink))
                print("\tand looking for the link to the source code.")
                print("\tSkipping download...")
                print('')
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
            getPackage(downloadLink, downloadFilename)

        print("Page {} complete.".format(page))
        print('')
    print("Downloaded {} pages of apps to {}".format(page, downloadPath))

if __name__ == "__main__":
    args = docopt(__doc__, version=VERSION)

    downloadPath=pathlib.Path(args["DOWNLOAD_PATH"])

    try:
        downloadPath.mkdir()
    except FileExistsError:
        pass
    getAllApps(downloadPath)

    print("\nExiting...")
