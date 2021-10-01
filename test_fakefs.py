import io
import tempfile
from io import StringIO, BytesIO
from pathlib import Path
import unittest

import fakefs


class Test(unittest.TestCase):
    def setUp(self):
        self.fs = fakefs.FakeFilesystem()

    def test_listdir_root_on_empty_os(self):
        self.assertEqual(self.fs.listdir('/'), [])

    def test_listdir_on_nonexistant_dir(self):
        with self.assertRaises(FileNotFoundError) as cm:
            self.fs.listdir('/etc')
        self.assertEqual(cm.exception.args[0], '/etc')

    def test_makedir(self):
        d = self.fs.makedir('/etc')
        self.assertEqual(d.name, 'etc')
        self.assertEqual(d.path, Path('/etc'))

    def test_makedir_fails_if_already_exists(self):
        self.fs.makedir('/etc')
        with self.assertRaises(FileExistsError) as cm:
            self.fs.makedir('/etc')
        self.assertEqual(cm.exception.args[0], '/etc')

    def test_makedir_fails_if_parent_dir_doesnt_exist(self):
        with self.assertRaises(FileNotFoundError) as cm:
            self.fs.makedir('/etc/init.d')
        self.assertEqual(cm.exception.args[0], '/etc')

    def test_make_and_list_directory(self):
        self.fs.makedir('/etc')
        self.fs.makedir('/var')
        self.assertEqual(set(self.fs.listdir('/')), {'/etc', '/var'})

    def test_make_directory_recursively(self):
        self.fs.makedir('/etc/init.d', make_parents=True)
        self.assertEqual(self.fs.listdir('/'), ['/etc'])
        self.assertEqual(self.fs.listdir('/etc'), ['/etc/init.d'])

    def test_makedir_path_must_start_with_slash(self):
        with self.assertRaises(ValueError) as cm:
            self.fs.makedir("noslash")
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
        data = "#" * 1_000_000

        # Via blob
        self.fs.create_file('/test', data)

        file = self.fs['/test']
        self.assertTrue(hasattr(file.data, 'name'))  # not present on str/bytes
        with self.fs.open('/test') as infile:
            self.assertEqual(infile.read(), data)

        # Via file-like object
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

    def test_get_object(self):
        self.fs.makedir('/etc/init.d', make_parents=True)

        # By path
        o = self.fs[Path('/etc/init.d')]
        self.assertIsInstance(o, fakefs.Directory)
        self.assertEqual(o.path, Path('/etc/init.d'))

        # By str
        o = self.fs['/etc/init.d']
        self.assertIsInstance(o, fakefs.Directory)
        self.assertEqual(o.path, Path('/etc/init.d'))

    # def test_get_object_error_if_child_of_file(self):
    #     # Get child of file - should fail



    # Also do:
    # * From BinaryIO
    # * From TextIO

    # And:
    # * Large data to/from tempfile

    # push/pull/makedirs/listdirs/remove   ->  remove is all that's left