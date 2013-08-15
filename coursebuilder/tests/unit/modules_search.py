# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for the Search module."""

__author__ = 'Ellis Michael (emichael@google.com)'

import robotparser
import urlparse
from functional import actions
from modules.search import resources
from google.appengine.api import urlfetch

VALID_PAGE_URL = 'http://valid.null/'
VALID_PAGE = """<html>
                  <head>
                     <title>Test Page</title>
                     <script>
                         alert('test');
                     </script>
                     <style>
                         body {
                           font-size: 12px;
                         }
                     </style>
                     </head>
                 <body>
                     Lorem ipsum <strong> dolor </strong> sit.
                     <a href="index.php?query=bibi%20quid">Ago gratias tibi</a>.
                     <a>Cogito ergo sum.</a>
                     <a href="//partial.null/"> Partial link </a>
                     <a href="ftp://absolute.null/"> Absolute link </a>
                 </body>
             </html>"""
VALID_PAGE_ROBOTS = ('User-agent: *', 'Allow: /')

BANNED_PAGE_URL = 'http://banned.null/'
BANNED_PAGE = 'Should note be accessed'
BANNED_PAGE_ROBOTS = ('User-agent: *', 'Disallow: /')


class SearchTestBase(actions.TestBase):
    """Unit tests for all search functionality."""

    pages = {VALID_PAGE_URL: VALID_PAGE,

             urlparse.urljoin(VALID_PAGE_URL, '/robots.txt'):
             VALID_PAGE_ROBOTS,

             # The default Power Searching course has notes in this domain
             'http://www.google.com/robots.txt':
             VALID_PAGE_ROBOTS,

             BANNED_PAGE_URL: BANNED_PAGE,

             urlparse.urljoin(BANNED_PAGE_URL, '/robots.txt'):
             BANNED_PAGE_ROBOTS
            }

    def setUp(self):  # Name set by parent. pylint: disable-msg=g-bad-name
        """Do all of the necessary monkey patching to test search."""
        super(SearchTestBase, self).setUp()

        def return_doc(url):
            """Monkey patch for URL fetching."""

            class Response(object):
                def __init__(self, code, content_type, content):
                    self.status_code = code
                    self.headers = {}
                    self.headers['Content-type'] = content_type
                    self.content = content

            try:
                body = self.pages[url]
            except KeyError:
                body = self.pages[VALID_PAGE_URL]
            result = Response(200, 'text/html', body)
            return result

        self.swap(urlfetch, 'fetch', return_doc)

        class FakeRobotParser(robotparser.RobotFileParser):
            """Monkey patch for robot parser."""

            def read(self):
                response = urlfetch.fetch(self.url)
                self.parse(response.content)

        self.swap(robotparser, 'RobotFileParser', FakeRobotParser)


class HTMLParserTests(SearchTestBase):
    """Unit tests for the search HTML Parser."""

    def setUp(self):
        super(HTMLParserTests, self).setUp()

        valid_url = VALID_PAGE_URL
        self.parser = resources.ResourceHTMLParser(valid_url)
        self.parser.feed(self.pages[valid_url])

    def test_found_tokens(self):
        content = self.parser.get_content()
        for text in ['Lorem', 'ipsum', 'dolor']:
            self.assertIn(text, content)

    def test_no_false_matches(self):
        content = self.parser.get_content()
        for text in ['Loremipsum', 'ipsumdolor', 'tibiCogito', 'sit.Ago']:
            self.assertNotIn(text, content)

    def test_ignored_fields(self):
        content = self.parser.get_content()
        for text in ['alert', 'font-size', 'body', 'script', 'style']:
            self.assertNotIn(text, content)

    def test_links(self):
        links = self.parser.get_links()
        self.assertIn('http://valid.null/index.php?query=bibi%20quid', links)
        self.assertIn('http://partial.null/', links)
        self.assertIn('ftp://absolute.null/', links)
        self.assertEqual(len(links), 3)

    def test_unopened_tag(self):
        self.parser = resources.ResourceHTMLParser('')
        self.parser.feed('Lorem ipsum </script> dolor sit.')
        content = self.parser.get_content()
        for text in ['Lorem', 'ipsum', 'dolor', 'sit']:
            self.assertIn(text, content)

    def test_title(self):
        self.assertEqual('Test Page', self.parser.get_title())

    def test_get_parser_allowed(self):
        self.parser = resources.get_parser_for_html(VALID_PAGE_URL)
        content = self.parser.get_content()
        self.assertIn('Cogito ergo sum', content)

        with self.assertRaises(resources.URLNotParseableException):
            self.parser = resources.get_parser_for_html(BANNED_PAGE_URL)
            content = self.parser.get_content()
            self.assertNotIn('accessed', content)
