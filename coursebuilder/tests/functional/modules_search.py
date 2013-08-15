# coding: utf-8
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

"""Tests for modules/search/."""

__author__ = 'Ellis Michael (emichael@google.com)'

import re
from models import custom_modules
from modules.search import search
from unit.modules_search import SearchTestBase
import actions


class SearchTest(SearchTestBase):
    """Tests the search module."""

    # Don't require documentation for self-describing test methods.
    # pylint: disable-msg=g-missing-docstring

    # TODO(emichael): When external links are fully implemented, check that 2nd+
    # degree page link aren't crawled

    @classmethod
    def enable_module(cls):
        custom_modules.Registry.registered_modules[
            search.MODULE_NAME].enable()
        assert search.custom_module.enabled

    @classmethod
    def disable_module(cls):
        custom_modules.Registry.registered_modules[
            search.MODULE_NAME].disable()
        assert not search.custom_module.enabled

    @classmethod
    def get_xsrf_token(cls, body, form_name):
        match = re.search(form_name + r'.+[\n\r].+value="([^"]+)"',
                          body)
        assert match
        return match.group(1)

    def setUp(self):   # Name set by parent. pylint: disable-msg=g-bad-name
        super(SearchTest, self).setUp()
        self.enable_module()

    def test_module_disabled(self):
        email = 'admin@google.com'
        actions.login(email, is_admin=True)

        self.disable_module()

        response = self.get('/search?query=lorem', expect_errors=True)
        self.assertEqual(response.status_code, 404)

        response = self.get('dashboard?action=search')
        self.assertIn('Google &gt; Dashboard &gt; Search', response.body)
        self.assertNotIn('Index Course', response.body)
        self.assertNotIn('Clear Index', response.body)

    def test_module_enabled(self):
        email = 'admin@google.com'
        actions.login(email, is_admin=True)

        response = self.get('course')
        self.assertIn('gcb-search-box', response.body)

        response = self.get('/search?query=lorem')
        self.assertEqual(response.status_code, 200)

        response = self.get('dashboard?action=search')
        self.assertIn('Google &gt; Dashboard &gt; Search', response.body)
        self.assertIn('Index Course', response.body)
        self.assertIn('Clear Index', response.body)

    def test_indexing_and_clearing_buttons(self):
        email = 'admin@google.com'
        actions.login(email, is_admin=True)

        response = self.get('dashboard?action=search')

        index_token = self.get_xsrf_token(response.body, 'gcb-index-course')
        clear_token = self.get_xsrf_token(response.body, 'gcb-clear-index')

        response = self.post('dashboard?action=index_course',
                             {'xsrf_token': index_token})
        self.assertEqual(response.status_int, 200)

        response = self.post('dashboard?action=clear_index',
                             {'xsrf_token': clear_token})
        self.assertEqual(response.status_int, 200)

        response = self.post('dashboard?action=index_course', {},
                             expect_errors=True)
        assert response.status_int != 200

    def test_index_search_clear(self):
        email = 'admin@google.com'
        actions.login(email, is_admin=True)

        response = self.get('dashboard?action=search')
        index_token = self.get_xsrf_token(response.body, 'gcb-index-course')
        clear_token = self.get_xsrf_token(response.body, 'gcb-clear-index')
        response = self.post('dashboard?action=index_course',
                             {'xsrf_token': index_token})
        self.execute_all_deferred_tasks()

        # weather is a term found in the Power Searching Course and should not
        # be in the HTML returned by the patched urlfetch in SearchTestBase
        response = self.get('search?query=weather')
        self.assertNotIn('gcb-search-result', response.body)

        # This term should be present as it is in the dummy content.
        response = self.get('search?query=cogito%20ergo%20sum')
        self.assertIn('gcb-search-result', response.body)

        response = self.post('dashboard?action=clear_index',
                             {'xsrf_token': clear_token})
        self.execute_all_deferred_tasks()

        # After the index is cleared, it shouldn't match anything
        response = self.get('search?query=cogito%20ergo%20sum')
        self.assertNotIn('gcb-search-result', response.body)

    def test_bad_search(self):
        email = 'user@google.com'
        actions.login(email, is_admin=False)

        # %3A is a colon, and searching for only punctuation will cause App
        # Engine's search to throw an error that should be handled
        response = self.get('search?query=%3A')
        self.assertEqual(response.status_int, 200)
        self.assertIn('gcb-search-info', response.body)
