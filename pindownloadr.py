#!/usr/bin/python

# pinterest downloadr - Get the big images from pinterest
# Copyright (c) 2012 R.Wimmer (githubixx AT tauceti.net)
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


"""
pinterest gfx downloadr written in Python.

On pinterest.com users organize their images in boards (themes if you like).
If you like the images of such a board this scripts helps you to get all the
images onto your disk. This script downloads the closeup images (the big ones).

The only parameter needed is the url of the board e.g.:

    pindownloadr -b http://pinterest.com/<username>/<boardname>/
    pindownloadr -b http://pinterest.com/johnfernandez/outer-limits/

For more options run script with -h or --help.

This script uses some other python libs you need to install:

pip install progressbar
pip install requests
pip install pyquery

If you use Python < 2.7 you may need also argparse:
pip install argparse

TODO: Some options currently not implemented
TODO: Not much error handling implemented. Be prepared for strange errors! ;-)
TODO: Needs more documentation.
"""


import urllib
import requests
import os
import errno
import sys
import argparse

from pyquery import PyQuery

from progressbar import AnimatedMarker, Bar, BouncingBar, Counter, ETA,\
                        FileTransferSpeed, FormatLabel, Percentage,\
                        ProgressBar, ReverseBar, RotatingMarker,\
                        SimpleProgress, Timer


class CloseupImageFetcher(object):
    """
    The CloseupImageFetcher takes a list of image urls and download the
    images into the save_path.

    The only usefull and public method is fetch_images()
    """

    def __init__(self, closeup_image_info_list, min_size=25000, save_path='/tmp'):
        """
        Initialize the image fetcher.
        """
        self._closeup_image_info_list = closeup_image_info_list
        self._min_size = min_size
        self._save_path = save_path
        self._widgets = [Bar('>'), ' ', ETA(), ' ', ReverseBar('<')]

    def fetch_images(self):
        # If a image already exist count up
        images_exists_count = 0

        # Create directory where the images will be saved
        self._ensure_save_path()

        for closeup_image_info in self._closeup_image_info_list:
            # TODO: Sometimes None, don't know why currently.
            # Never had this problem with HTMLParser...
            if closeup_image_info.source is not None:
                file_name = self._filename_from_url(closeup_image_info.source)

                if not self._file_exists(file_name):
                    print("Downloading: %s") % file_name
                    u = urllib.urlopen(closeup_image_info.source)
                    data = u.read()
                    self._save_image(data, file_name)
                else:
                    images_exists_count += 1

        if images_exists_count > 0:
            print("")
            print("%i of %i images not downloaded because filename exists in savepath!") % (images_exists_count, len(self._closeup_image_info_list))

        return False

    def _file_exists(self, file_name):
        return os.path.exists(os.path.join(self._save_path, file_name))

    def _ensure_save_path(self):
        try:
            os.makedirs(self._save_path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST:
                pass
            else:
                raise

    def _save_image(self, data, file_name):
        file2save = os.path.join(self._save_path, file_name)
        f = open(file2save, 'wb')
        f.write(data)
        f.close()

    def _filename_from_url(self, url):
        split_path = url.split(os.sep)
        return split_path.pop()

    def _get_content_length(self, url):
        return int(requests.head(url).headers['Content-Length'])


class CloseupImageUpdater(CloseupImageFetcher):

    def __init__(self, closeup_image_info_list, save_path, min_size=25000):
        """
        Initialize the image updater.
        """
        self._closeup_image_info_list = closeup_image_info_list
        self._min_size = min_size
        self._save_path = save_path
        self._widgets = [Bar('>'), ' ', ETA(), ' ', ReverseBar('<')]

    def fetch_images(self):
        # If a image already exist count up and after we got 10 images that
        # alread exists we stop updating
        images_exists_count = 0
        images_exists_count_max = 10

        # Create directory where the images will be saved
        self._ensure_save_path()

        for closeup_image_info in self._closeup_image_info_list:
            # TODO: Sometimes None, don't know why currently. Never had this
            # problem with HTMLParser...
            if closeup_image_info.source is not None:
                file_name = self._filename_from_url(closeup_image_info.source)

                if not self._file_exists(file_name):
                    print("Downloading: %s") % file_name
                    u = urllib.urlopen(closeup_image_info.source)
                    data = u.read()
                    self._save_image(data, file_name)
                else:
                    images_exists_count += 1
                    if images_exists_count > images_exists_count_max:
                        print("Update finished!")
                        return True

        return False

    def exists_duplicate(self):
        return self._duplicate

    def _set_duplicate(self, duplicate):
        self._duplicate = duplicate


class PinterestBoardParser(object):

    def __init__(self):
        self.pin_uris = []

    # <a href="/pin/316589048774982797/" class="PinImage ImgLink">
    def parse_board(self, html):
        # PyQuery has a problem when the value of class="..." includes
        # a space. We need to replace it so that the parser get's it...
        h = html.replace("PinImage ImgLink", "PinImageImgLink")
        j = PyQuery(h)

        for anchor in j("a"):
            if j(anchor).hasClass('PinImageImgLink'):
                self.pin_uris.append(j(anchor).attr("href"))

    def get_pin_uris(self):
        return self.pin_uris


class CloseupImageParser(object):

    def __init__(self, url, save_description=False, headers=None):
        if not headers:
            headers = {}
        self.url = url
        self.images = []
        self.headers = headers
        self.save_description = save_description

    def parse_closeup_image(self, html):
        j = PyQuery(html)
        img_src = j("#pinCloseupImage").attr("src")
        img_description = j(".description").text()
        img = CloseupImageInfo(img_src, img_description)
        return img

    def parse_pin_list(self, images_uri_list):
        i = 1
        widgets = [Bar('>'), ' ', ETA(), ' ', ReverseBar('<')]
        pbar = ProgressBar(widgets=widgets, maxval=len(images_uri_list) + 1).start()
        for image_uri in images_uri_list:
            i += 1
            r = requests.get("http://pinterest.com" + image_uri, headers=self.headers, cookies=cookies)
            closeup_image_html = r.text

            img = self.parse_closeup_image(closeup_image_html)
            img.uri = image_uri
            self.images.append(img)
            pbar.update(i)
        pbar.finish()

    def get_image_list(self):
        return self.images


class CloseupImageInfo(object):

    def __init__(self, source, description):
        self.source = source
        self.description = description

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, value):
        self._source = value

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value):
        self._description = value

    @property
    def uri(self):
        return self._uri

    @uri.setter
    def uri(self, value):
        self._uri = value


###############
# Local methods
###############
def save_page_count(save_path, page_count):
    _file = os.path.join(save_path, "page_count")
    f = open(_file, 'w')
    f.write(str(page_count))
    f.close()


def check_page_count(save_path):
    _file = os.path.join(save_path, "page_count")
    if os.path.exists(_file):
        f = open(_file, 'r')
        c = f.read()
        f.close()
        return int(c)
    else:
        return 1


def fetch_pin_list(url, page_no, http_headers):

    """
    Fetch the html code of a board and extract all /pin/ uri's which contains
    the big images.
    """

    pbp = PinterestBoardParser()
    board_html = requests.get(url + "?page=" + str(page_no), headers=http_headers, cookies=cookies).text
    pbp.parse_board(board_html)
    return pbp.get_pin_uris()


def generate_big_images_list(save_description, http_request_headers, pin_list):
    cip = CloseupImageParser(save_description, headers=http_request_headers)
    cip.parse_pin_list(pin_list)
    return cip.get_image_list()


def generate_save_path(path, url):

    """
    Generates the os path where to save the pictures. It combines the path the
    user has supplied with the pinterest username and the board name.

    :param path:    the main path (e.g. /tmp)
    :param url:     the pinterest url (e.g. http://pinterest.com/user/board/)
    :return:        the path where the big pictures will be stored
    """

    split_path = url.split(os.sep)
    split_path.pop()
    board_name = split_path.pop()
    pinterest_user = split_path.pop()
    return os.path.join(path, pinterest_user, board_name)


def read_cookies(path):

    """
    Reads cookies.txt in specified path if exists.

    :param path:    the path where cookies.txt is stored
    :return:        a dict (maybe empty)
    """

    cookies = dict()
    cookies_file = os.path.join(path, "cookies.txt")
    if os.path.exists(cookies_file):
        with open(cookies_file, "r") as c:
            _cookies = c.read().split("\n")
            for _cookie in _cookies:
                if len(_cookie) > 1:
                    key, value = _cookie.split("=", 1)
                    cookies[key] = value

    return cookies


def download(board_url, save_path, http_request_headers, save_description, page_no=1):

    # Parse every page of a board as long as we get 50 images per page
    # otherwise stop
    while True:
        print("Parsing html from: %s?page=%i") % (board_url, page_no)
        print("")

        # Get all pins for a page
        pin_list = fetch_pin_list(board_url, page_no, http_request_headers)

        # Now fetch every page which contains a big image and generate a
        # list of the big images
        print("Parsing html of all closeup uri's' from page %i:") % page_no
        big_image_list = generate_big_images_list(save_description, http_request_headers, pin_list)
        print("")

        # Now we can fetch the big/closeup images
        print("Now fetching big images...")
        cif = CloseupImageFetcher(big_image_list, save_path=save_path)
        cif.fetch_images()
        print("")

        # If the last board page returned less than 50 uri's we finish here...
        if len(pin_list) != 50:
            print("Search done!\n")
            break

        if save_pagecount:
            save_page_count(os.path.join(save_path), str(page_no))

        page_no += 1


def update(board_url, save_path, http_request_headers, save_description):
    # We always start from page 1 in update mode
    page_no = 1

    # Parse every page of a board as long as we get a duplicate image...
    while True:
        print("Parsing html from: %s?page=%i") % (board_url, page_no)
        print("")

        # Get all pins for a page
        pin_list = fetch_pin_list(board_url, page_no, http_request_headers)

        # Now fetch every page which contains a big image and generate
        # a list of the big images
        print("Parsing html of all closeup uri's' from page %i:") % page_no
        big_image_list = generate_big_images_list(save_description, http_request_headers, pin_list)
        print("")

        # Now we can fetch the big/closeup images
        print("Now fetching big images...")
        cif = CloseupImageUpdater(big_image_list, save_path=save_path)
        finished = cif.fetch_images()
        print("")

        # If the last board page returned less than 50 uri's we finish here...
        if len(pin_list) != 50 or finished:
            print("Search done!\n")
            break

        page_no += 1


if __name__ == "__main__":

    # HTTP Header for our "browser"
    http_request_header={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:18.0) Gecko/20100101 Firefox/18.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate',
                    'Accept-Language': 'en-US,en;q=0.5'}

    # Parse commandline options
    ap = argparse.ArgumentParser(description="Fetch pinterest images. USE THIS SCRIPT CAREFULLY! YOU POTENTIALLY GENERATE A LOT OF LOAD ON THE pinterest.com SERVER and will be locked out!",
                               version="%(prog)s 0.0.6")
    ap.add_argument('--boardurl', '-b', dest='boardurl', nargs=1, help='The board url to download (e.g. http://pinterest.com/<username>/<boardname>/)')
    ap.add_argument('--savepath', '-p', dest='savepath', default=os.sep + 'tmp', help='where to save the images (default: ' + os.sep + 'tmp)')
    ap.add_argument('-c', dest='save_pagecount', default=False, action="store_true", help='Very big boards may take to long to get content in one shot. This saves last page and continue from there next time.')
    ap.add_argument('--fetchdelay', '-f', dest='fetchdelay', help='Delay time in millisec. before fetching next pin.')
    ap.add_argument('-l', dest='shuffle_ua', default=False, action="store_true", help='Choose random useragent.')
    ap.add_argument('-o', dest='override', default=False, action="store_true", help='If a image is already downloaded (exists in savepath) it will not be downloaded again. This option forces the download.')
    ap.add_argument('-s', dest='save_description', default=False, action="store_true", help='Saves the image description like original location as a JSON file parallel to the image.')
    ap.add_argument('--update', '-t', dest='update_path', default=None, nargs=1, help='Fetch latest pictures of that path e.g. /user/board/')
    ap.add_argument('--cookiefile', dest='cookie_file', default=os.getcwd(), nargs=1, help='If you want to fetch your secret boards you need your private cookie stored in this file.')

    args = ap.parse_args()

    # Read cookie file if it exists
    cookies = read_cookies(args.cookie_file)

    # Board url
    if args.boardurl is not None:
        board_url = args.boardurl[0]
        if not board_url.endswith("/"):
            board_url = board_url + "/"
    elif args.update_path is not None:
        update_path = args.update_path[0]
        if not update_path.endswith("/"):
            update_path = update_path + "/"
    else:
        print("No arguments for option --boardurl or --update specified!")
        sys.exit(1)

    # Save last page
    if args.save_pagecount:
        save_pagecount = True
    else:
        save_pagecount = False

    # Fetch delay
    if args.fetchdelay is not None:
        fetchdelay = args.fetchdelay

    # Shuffle the useragentd
    if args.shuffle_ua:
        shuffle_ua = True
    else:
        shuffle_ua = False

    # Override pics already saved
    if args.override:
        override = True
    else:
        override = False

    # Save description
    if args.save_description:
        save_description = True
    else:
        save_description = False

    # Construct board_url if in update mode
    if args.update_path is not None:
        _update_path_tmp = update_path.split("/")
        _user = _update_path_tmp[len(_update_path_tmp) - 3]
        _board = _update_path_tmp[len(_update_path_tmp) - 2]
        board_url = "http://pinterest.com/" + _user + "/" + _board + "/"
        savepath = update_path
    else:
        savepath = args.savepath

    print("")

    # Where to save our closeup images
    if args.update_path is not None:
        save_path = savepath
    else:
        save_path = generate_save_path(savepath, board_url)

    # Check if we saved page count during the last run (returns 1 if no state exists)
    page_no = check_page_count(save_path)

    # If update mode...
    if args.update_path is not None:
        update(board_url, save_path, http_request_header, save_description)
    else:
        download(board_url, save_path, http_request_header, save_description, page_no)
