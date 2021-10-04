# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from io import BytesIO, StringIO
from pathlib import Path

import mock_fs


class Tests(unittest.TestCase):
    def setUp(self):
        self.fs = mock_fs.MockFilesystem()

    def test_listdir_root_on_empty_os(self):
        self.assertEqual(self.fs.list_dir('/'), [])

    def test_listdir_on_nonexistant_dir(self):
        with self.assertRaises(FileNotFoundError) as cm:
            self.fs.list_dir('/etc')
        self.assertEqual(cm.exception.args[0], '/etc')

    def test_listdir(self):
        self.fs.create_dir('/opt')
        self.fs.create_file('/opt/file1', 'data')
        self.fs.create_file('/opt/file2', 'data')
        self.assertEqual({'/opt/file1', '/opt/file2'}, set(self.fs.list_dir('/opt')))
        # Ensure that Paths also work for listdir
        self.assertEqual({'/opt/file1', '/opt/file2'}, set(self.fs.list_dir(Path('/opt'))))

    def test_listdir_on_file(self):
        self.fs.create_file('/file', 'data')
        with self.assertRaises(NotADirectoryError) as cm:
            self.fs.list_dir('/file')
        self.assertEqual(cm.exception.args[0], '/file')

    def test_makedir(self):
        d = self.fs.create_dir('/etc')
        self.assertEqual(d.name, 'etc')
        self.assertEqual(d.path, Path('/etc'))
        d2 = self.fs.create_dir('/etc/init.d')
        self.assertEqual(d2.name, 'init.d')
        self.assertEqual(d2.path, Path('/etc/init.d'))

    def test_makedir_fails_if_already_exists(self):
        self.fs.create_dir('/etc')
        with self.assertRaises(FileExistsError) as cm:
            self.fs.create_dir('/etc')
        self.assertEqual(cm.exception.args[0], '/etc')

    def test_makedir_fails_if_parent_dir_doesnt_exist(self):
        with self.assertRaises(FileNotFoundError) as cm:
            self.fs.create_dir('/etc/init.d')
        self.assertEqual(cm.exception.args[0], '/etc')

    def test_make_and_list_directory(self):
        self.fs.create_dir('/etc')
        self.fs.create_dir('/var')
        self.assertEqual(set(self.fs.list_dir('/')), {'/etc', '/var'})

    def test_make_directory_recursively(self):
        self.fs.create_dir('/etc/init.d', make_parents=True)
        self.assertEqual(self.fs.list_dir('/'), ['/etc'])
        self.assertEqual(self.fs.list_dir('/etc'), ['/etc/init.d'])

    def test_makedir_path_must_start_with_slash(self):
        with self.assertRaises(ValueError) as cm:
            self.fs.create_dir("noslash")
        self.assertEqual(cm.exception.args[0], "Path must start with slash")

    def test_create_file_from_str(self):
        self.fs.create_file('/test', "foo")
        with self.fs.open('/test') as infile:
            self.assertEqual(infile.read(), 'foo')

    def test_create_file_from_bytes(self):
        self.fs.create_file('/test', b"foo")
        with self.fs.open('/test', encoding=None) as infile:
            self.assertEqual(infile.read(), b'foo')

    def test_create_file_from_files(self):
        data = "foo"

        sio = StringIO(data)
        self.fs.create_file('/test', sio)
        with self.fs.open('/test') as infile:
            self.assertEqual(infile.read(), 'foo')

        bio = BytesIO(data.encode())
        self.fs.create_file('/test2', bio)
        with self.fs.open('/test2') as infile:
            self.assertEqual(infile.read(), 'foo')

    def test_create_and_read_large_file(self):
        # Create somewhat non-trivial data
        # (32 distinct printable ASCII characters, repeated 2**15 times,
        # 1 MiB of total data)
        data = "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" * (2**15)

        # Test via blob
        self.fs.create_file('/test', data)
        file = self.fs['/test']
        self.assertTrue(hasattr(file.data, 'name'))  # not present on str/bytes
        with self.fs.open('/test') as infile:
            self.assertEqual(infile.read(), data)

        # Test via file-like object
        self.fs.create_file('/test2', StringIO(data))
        file = self.fs['/test2']
        self.assertTrue(hasattr(file.data, 'name'))  # not present on str/bytes
        with self.fs.open('/test2') as infile:
            self.assertEqual(infile.read(), data)

    def test_create_and_read_with_different_encodings(self):
        # write str, read as utf-8 bytes
        self.fs.create_file('/test', "foo")
        with self.fs.open('/test', encoding=None) as infile:
            self.assertEqual(infile.read(), b'foo')

        # write bytes, read as utf-8-decoded str
        data = "日本語"  # Japanese for "Japanese"
        self.fs.create_file('/test2', data.encode('utf-8'))
        with self.fs.open('/test2') as infile:                    # Implicit utf-8 read
            self.assertEqual(infile.read(), data)
        with self.fs.open('/test2', encoding='utf-8') as infile:  # Explicit utf-8 read
            self.assertEqual(infile.read(), data)

    def test_open_directory_fails(self):
        self.fs.create_dir('/dir1')
        with self.assertRaises(IsADirectoryError) as cm:
            self.fs.open('/dir1')
        self.assertEqual(cm.exception.args[0], '/dir1')

    def test_delete_file(self):
        self.fs.create_file(Path('/test'), "foo")
        del self.fs[Path('/test')]
        with self.assertRaises(FileNotFoundError) as cm:
            self.fs[Path('/test')]

        # Deleting deleted files should fail as well
        with self.assertRaises(FileNotFoundError) as cm:
            del self.fs[Path('/test')]
        self.assertEqual(cm.exception.args[0], '/test')

    def test_create_dir_with_permissions(self):
        # Permissions are simply stored if provided.  No defaults are provided.
        d = self.fs.create_dir('/dir1')
        self.assertEqual(d.permissions, None)

        d = self.fs.create_dir('/dir2', permissions=0o700)
        self.assertEqual(d.permissions, 0o700)

    def test_create_file_with_permissions(self):
        # Permissions are simply stored if provided.  No defaults are provided.
        d = self.fs.create_file('/file1', 'data')
        self.assertEqual(d.permissions, None)

        d = self.fs.create_file('/file2', 'data', permissions=0o754)
        self.assertEqual(d.permissions, 0o754)

    def test_create_dir_with_ownership(self):
        d = self.fs.create_dir('/dir1')
        self.assertIs(d.user, None)
        self.assertIs(d.user_id, None)
        self.assertIs(d.group, None)
        self.assertIs(d.group_id, None)

        d = self.fs.create_dir('/dir2', user='ubuntu', user_id=1000, group='www-data', group_id=33)
        self.assertIs(d.user, 'ubuntu')
        self.assertIs(d.user_id, 1000)
        self.assertIs(d.group, 'www-data')
        self.assertIs(d.group_id, 33)

    def test_create_file_with_ownership(self):
        f = self.fs.create_file('/file1', 'data')
        self.assertIs(f.user, None)
        self.assertIs(f.user_id, None)
        self.assertIs(f.group, None)
        self.assertIs(f.group_id, None)

        f = self.fs.create_file('/file2', 'data',
                                user='ubuntu', user_id=1000,
                                group='www-data', group_id=33)
        self.assertIs(f.user, 'ubuntu')
        self.assertIs(f.user_id, 1000)
        self.assertIs(f.group, 'www-data')
        self.assertIs(f.group_id, 33)

    def test_getattr(self):
        self.fs.create_dir('/etc/init.d', make_parents=True)

        # By path
        o = self.fs[Path('/etc/init.d')]
        self.assertIsInstance(o, mock_fs.Directory)
        self.assertEqual(o.path, Path('/etc/init.d'))

        # By str
        o = self.fs['/etc/init.d']
        self.assertIsInstance(o, mock_fs.Directory)
        self.assertEqual(o.path, Path('/etc/init.d'))

    def test_getattr_file_not_found(self):
        # Arguably this could be a KeyError given the dictionary-style access.
        # However, FileNotFoundError seems more appropriate for a filesystem, and it
        # gives a closer semantic feeling, in my opinion.
        with self.assertRaises(FileNotFoundError) as cm:
            self.fs['/nonexistant_file']
        self.assertEqual(cm.exception.args[0], '/nonexistant_file')
