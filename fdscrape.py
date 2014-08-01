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
import datetime


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

def combineDictionaries(*dictionaries) -> dict:
    '''Combine dictionaries by adding keys.'''

    keys = set()
    for d in dictionaries:
        keys = keys.union(d.keys())

    newDict = dict()
    for k in keys:
        values = [ d.get(k, 0) for d in dictionaries ]
        newDict[k] = sum(values)

    return newDict

def decodeSi(si: str) -> int:
    prefixes = ['k', 'm', 'g', 't']
    prefixes = { prefix: 10**(3 * (i + 1)) for i, prefix in enumerate(prefixes) }

    si = si.lower()

    for prefix, multiplier in prefixes.items():
        num, prefix, _ = si.partition(prefix)
        if not prefix:
            continue
        num = num.replace(',', '')
        num = float(num)
        return int(num * multiplier)

def getPlayInfobox(boxTitle: str, soup) -> str:
    stat = soup.find("div", class_="title", text=lambda x: boxTitle in x)
    stat = stat.parent.find(class_="content")

    # TODO: handle potential error here
    return stat.text.strip()

def reviewPhrases(text) -> dict:
    '''Returns a dict with the amount of matching phrases.'''

    keys = ["incompatible", "uninstall", "crash", "slow", "lag", "black screen",
            "white screen", "blank screen"]
    # s.count(sub) counts occurrances of sub in s
    return { k.replace(' ', '-'): text.lower().count(k) for k in keys }

def getPlayStats(package):
    prefix = "https://play.google.com/store/apps/details?id="

    try:
        with urllib.request.urlopen(prefix + package) as r:
            soup = bs(r)
    except urllib.error.HTTPError:
        return

    hist = soup.find("div", class_="rating-histogram")

    # if we don't have ratings, tell caller function to abort
    if hist is None:
        return

    # pull ratings from soup
    ratings = hist(class_="rating-bar-container")
    ratings = [ r.find("span", class_="bar-number").text for r in ratings ]
    ratings = [ int(r.replace(',', '')) for r in ratings ]
    ratings.reverse() #  one-to-five in increasing order
    ratingCount = sum(ratings)

    # if we don't have ratings, tell caller function to abort
    if ratingCount == 0:
        return

    # dict maps weighting (how many stars) to count (how many people rated at
    # this weight)
    ratingWeights = { i + 1: num for i, num in enumerate(ratings) }

    # calculate the mean from the weighting dictionary above
    theSum = sum(( weight * count for weight, count in ratingWeights.items() ))
    theMean = theSum / ratingCount

    # make a str:int statistics dictionary
    stats = { "star_{}".format(k): v for k, v in ratingWeights.items() }
    stats["play_star_mean"] = theMean
    stats["play_star_count"] = ratingCount

    # count number of characters in the description as a control variable
    description = soup.find("div", class_="id-app-orig-desc")
    description = description.text
    stats["play_description_length"] = len(description)

    # this doesn't work because it's injected into the source with jquery
    '''
    # how many users +1'd this app on Google Play?
    plusOnes = soup.find(text=lambda x: "Recommend this on Google" in x)
    plusOnes = plusOnes.partition(' ')[0] #FIXME
    plusOnes = plusOnes.partition('+')[2]
    stats["play_google_plus"] = plusOnes
    '''

    # what sort of contact information does the developer provide?
    contact = soup.find("div", class_="title", text=lambda x: "Contact Developer" in x)
    contact = contact.parent.find(class_=["content", "contains-text-link"])
    availability = lambda x: "unavailable" if x is None else "available"

    web = contact.find("a", text=lambda x: "Visit Developer's Website" in x)
    stats["play_developer_web"] = availability(web)

    email = contact.find("a", text=lambda x: "Email Developer" in x)
    stats["play_developer_email"] = availability(email)

    privacy = contact.find("a", text=lambda x: "Privacy Policy" in x)
    stats["play_developer_privacy"] = availability(privacy)

    # application binary size
    rawSize = getPlayInfobox("Size", soup)
    if "Varies with device" in rawSize:
        stats["play_size"] = None
    else:
        stats["play_size"] = decodeSi(getPlayInfobox("Size", soup))

    # content rating
    stats["play_content_rating"] = getPlayInfobox("Content Rating", soup)

    # last updated
    dateFormat = "%B %d, %Y"
    lastUpdated = getPlayInfobox("Updated", soup)
    lastUpdated = datetime.datetime.strptime(lastUpdated, dateFormat).date()
    stats["play_updated"] = (datetime.date.today() - lastUpdated).days

    # category
    # we're using the backend link because the frontend text on the Web display
    # isn't specific enough and may change
    catLink = soup.find("span", itemprop="genre").parent
    catLink = catLink.get("href")
    # it's the last part of the category link
    catLink = catLink.rpartition('/')[2]
    stats["play_category"] = catLink

    # text reviews
    reviews = soup.find("div", class_="reviews")
    reviews = reviews.find("div", class_="all-reviews")
    if reviews is not None:
        reviews = reviews("div", class_="review-body")
        reviews = [ " ".join(review.stripped_strings) for review in reviews ]
        phrases = [ reviewPhrases(review) for review in reviews ]
        phrases = combineDictionaries(*phrases)
        wordCount = sum([ len(review.split(" ")) for review in reviews ])
        stats["review_words"] = wordCount
        for phrase, count in phrases.items():
            stats["review_frequency_" + phrase] = count / wordCount
    else:
        print("No reviews!")

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
            rating = getPlayStats(package)
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
