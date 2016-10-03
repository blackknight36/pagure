# -*- coding: utf-8 -*-

"""
 (c) 2016 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

__requires__ = ['SQLAlchemy >= 0.8']
import pkg_resources

import json
import unittest
import shutil
import sys
import os

import pygit2
from mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.abspath(__file__)), '..'))

import pagure.lib
import tests


class PagureFlaskPluginNoFFtests(tests.Modeltests):
    """ Tests for Block non fast-forward pushes plugin of pagure """

    def setUp(self):
        """ Set up the environnment, ran before every tests. """
        super(PagureFlaskPluginNoFFtests, self).setUp()

        pagure.APP.config['TESTING'] = True
        pagure.SESSION = self.session
        pagure.ui.SESSION = self.session
        pagure.ui.app.SESSION = self.session
        pagure.ui.plugins.SESSION = self.session
        pagure.ui.repo.SESSION = self.session
        pagure.ui.filters.SESSION = self.session

        pagure.APP.config['GIT_FOLDER'] = self.path
        pagure.APP.config['FORK_FOLDER'] = os.path.join(
            self.path, 'forks')
        pagure.APP.config['TICKETS_FOLDER'] = os.path.join(
            self.path, 'tickets')
        pagure.APP.config['DOCS_FOLDER'] = os.path.join(
            self.path, 'docs')
        self.app = pagure.APP.test_client()

    def test_plugin_noff(self):
        """ Test the noff plugin on/off endpoint. """

        tests.create_projects(self.session)
        tests.create_projects_git(self.path)

        user = tests.FakeUser(username='pingou')
        with tests.user_set(pagure.APP, user):
            output = self.app.get(
                '/test/settings/Block non fast-forward pushes')
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn(
                '<h3>Block non fast-forward pushes settings</h3>',
                output.data)
            self.assertIn(
                '<td><input id="branches" name="branches" type="text" '
                'value=""></td>', output.data)
            self.assertTrue(
                '<input id="active" name="active" type="checkbox" value="y">'
                in output.data)

            csrf_token = output.data.split(
                'name="csrf_token" type="hidden" value="')[1].split('">')[0]

            data = {}

            output = self.app.post(
                '/test/settings/Block non fast-forward pushes', data=data)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn(
                '<h3>Block non fast-forward pushes settings</h3>',
                output.data)
            self.assertIn(
                '<td><input id="branches" name="branches" type="text" '
                'value=""></td>', output.data)
            self.assertTrue(
                '<input id="active" name="active" type="checkbox" value="y">'
                in output.data)

            data['csrf_token'] = csrf_token

            # With the git repo
            output = self.app.post(
                '/test/settings/Block non fast-forward pushes',
                data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<section class="settings">\n  <h3>Settings for test</h3>',
                output.data)
            self.assertTrue(
                '</button>\n                      Hook Block non '
                'fast-forward pushes inactived' in output.data)

            output = self.app.get(
                '/test/settings/Block non fast-forward pushes')
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn(
                '<h3>Block non fast-forward pushes settings</h3>',
                output.data)
            self.assertIn(
                '<td><input id="branches" name="branches" type="text" '
                'value=""></td>', output.data)
            self.assertTrue(
                '<input id="active" name="active" type="checkbox" value="y">'
                in output.data)

            self.assertFalse(os.path.exists(os.path.join(
                self.path, 'test.git', 'hooks', 'post-receive.mail')))

            # Missing the required mail_to
            data = {'csrf_token': csrf_token, 'active': 'y'}

            output = self.app.post(
                '/test/settings/Block non fast-forward pushes',
                data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn(
                '<h3>Block non fast-forward pushes settings</h3>',
                output.data)
            self.assertNotIn(
                '</button>\n                      Hook activated',
                output.data)
            self.assertIn(
                '<td><input id="branches" name="branches" type="text" '
                'value=""></td>', output.data)
            self.assertTrue(
                '<input checked id="active" name="active" type="checkbox" '
                'value="y">' in output.data)

            self.assertFalse(os.path.exists(os.path.join(
                self.path, 'test.git', 'hooks',
                'pre-receive.pagureforcecommit')))

            # Activate hook
            data = {
                'csrf_token': csrf_token,
                'active': 'y',
                'branches': 'master',
            }

            output = self.app.post(
                '/test/settings/Block non fast-forward pushes',
                data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<h3>Settings for test</h3>',
                output.data)
            self.assertIn(
                '</button>\n                      Hook Block non '
                'fast-forward pushes activated', output.data)

            output = self.app.get(
                '/test/settings/Block non fast-forward pushes')
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn(
                '<h3>Block non fast-forward pushes settings</h3>',
                output.data)
            self.assertIn(
                '<td><input id="branches" name="branches" type="text" '
                'value="master"></td>', output.data)
            self.assertIn(
                '<input checked id="active" name="active" type="checkbox" '
                'value="y">', output.data)

            self.assertTrue(os.path.exists(os.path.join(
                self.path, 'test.git', 'hooks',
                'pre-receive.pagureforcecommit')))

            # De-Activate hook
            data = {'csrf_token': csrf_token}
            output = self.app.post(
                '/test/settings/Block non fast-forward pushes',
                data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<section class="settings">\n  <h3>Settings for test</h3>',
                output.data)
            self.assertIn(
                '</button>\n                      Hook Block non '
                'fast-forward pushes inactived', output.data)

            output = self.app.get(
                '/test/settings/Block non fast-forward pushes')
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn(
                '<h3>Block non fast-forward pushes settings</h3>',
                output.data)
            self.assertIn(
                '<td><input id="branches" name="branches" type="text" '
                'value=""></td>', output.data)
            self.assertIn(
                '<input id="active" name="active" type="checkbox" '
                'value="y">', output.data)

            self.assertFalse(os.path.exists(os.path.join(
                self.path, 'test.git', 'hooks',
                'pre-receive.pagureforcecommit')))


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(
        PagureFlaskPluginNoFFtests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
