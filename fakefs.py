import io
import os
import tempfile
from io import BytesIO, StringIO
from pathlib import Path
import typing


class FakeFilesystem:

    def __init__(self):
        self.root = Directory(Path('/'))

    def listdir(self, path) -> typing.List[str]:
        current_dir = self.root
        tokens = Path(path).parts[1:]
        for token in tokens:
            try:
                current_dir = current_dir[token]
            except KeyError:
                raise FileNotFoundError(str(current_dir.path / token))
            if not isinstance(current_dir, Directory):
                # For now, ignoring the possibility of this being a symlink
                # and am assuming we referred to something which is not equivalent to
                # a directory.
                # Also not sure how we want to handle listdir on a single file - do we
                # raise an error, or return a single entry?
                raise NotImplementedError()

        return [str(child.path) for child in current_dir]

    def makedir(self, path: str, make_parents: bool = False) -> 'Directory':
        if not path.startswith('/'):
            raise ValueError('Path must start with slash')
        current_dir = self.root
        tokens = Path(path).parts[1:]
        for token in tokens[:-1]:
            if token in current_dir:
                current_dir = current_dir[token]
            else:
                if make_parents:
                    current_dir = current_dir.create_dir(token)
                else:
                    raise FileNotFoundError(str(current_dir.path / token))

        # Current backend will always raise an error if the final directory component
        # already exists.
        token = tokens[-1]
        if token not in current_dir:
            current_dir = current_dir.create_dir(token)
        else:
            raise FileExistsError(str(current_dir.path / token))
        return current_dir

    def create_file(self, path: typing.Union[str, Path], data: typing.Union[bytes, str, typing.BinaryIO, typing.TextIO]) -> 'File':
        path = Path(path)
        dir_ = self[path.parent]
        return dir_.create_file(path.name, data)

    def open(self, path: typing.Union[str, Path], encoding: typing.Union[str, None] = 'utf-8') -> typing.Union[typing.BinaryIO, typing.TextIO]:
        path = Path(path)
        file: File = self[path]  # warning: no check re: directories
        return file.open(encoding=encoding)

    def __getitem__(self, path: typing.Union[str, Path]) -> typing.Union['Directory', 'File']:
        path = Path(path)
        tokens = path.parts[1:]
        current_object = self.root
        for token in tokens:
            # ASSUMPTION / TESTME: object might be file
            if token in current_object:
                current_object = current_object[token]
            else:
                raise FileNotFoundError(str(current_object.path / token))
        return current_object

    def __delitem__(self, path: typing.Union[str, Path]) -> None:
        parent_dir: Directory = self[path.parent]
        del parent_dir[path.name]



class Directory:
    def __init__(self, path: Path):
        self.path = path
        self._children: typing.Dict[str, typing.Union[Directory, File]] = {}

    @property
    def name(self) -> str:
        return self.path.name

    def __contains__(self, child: str) -> bool:
        return child in self._children

    def __iter__(self) -> typing.Iterator[typing.Union['File', 'Directory']]:
        return (value for value in self._children.values())

    def __getitem__(self, key: str) -> typing.Union['File', 'Directory']:
        return self._children[key]

    def __delitem__(self, key: str) -> None:
        try:
            del self._children[key]
        except KeyError:
            raise FileNotFoundError(str(self.path / key))

    def create_dir(self, name: str) -> 'Directory':
        self._children[name] = Directory(self.path / name)
        return self._children[name]

    def create_file(self, name: str, data: typing.Union[bytes, str, StringIO, BytesIO]) -> 'File':
        if isinstance(data, (StringIO, BytesIO)):
            pass
        if isinstance(data, str):
            data = data.encode()  # Implicit encode to utf-8 bytes
        self._children[name] = File(self.path / name, data)
        return self._children[name]


class File:
    MAX_MEM_LENGTH = 102400
    READ_BLOCK_SIZE = 102400

    def __init__(self, path: Path, data: typing.Union[str, bytes, StringIO, BytesIO]):
        self.path = path
        if isinstance(data, (StringIO, BytesIO)):
            data = self._get_data_from_filelike(data)
        else:
            # Farm out to file if too large
            if len(data) > File.MAX_MEM_LENGTH:
                tf = tempfile.NamedTemporaryFile(delete=False)
                with tf:
                    tf.write(data)
                data = tf
        self.data = data

    def _get_data_from_filelike(self, data):
        blocks = []
        total_read = 0
        tf = None
        while True:
            block = data.read(self.READ_BLOCK_SIZE)
            if len(block) == 0:
                break
            if isinstance(block, str):
                block = block.encode()

            if tf is not None:
                tf.write(block)
            else:
                blocks.append(block)
                total_read += len(block)
                if total_read > self.MAX_MEM_LENGTH:
                    tf = tempfile.NamedTemporaryFile(delete=False)
                    for queued_block in blocks:
                        tf.write(queued_block)
        if tf:
            tf.close()
            data = tf
        else:
            data = b''.join(blocks)
        return data

    def open(self, encoding: typing.Union[str, None] = 'utf-8') -> typing.Union[typing.TextIO, typing.BinaryIO]:
        if hasattr(self.data, 'name'):  # tempfile case
            return open(self.data.name, encoding=encoding)
        if encoding is None:
            # binary mode; coerce string to utf-8 bytes if needed
            return BytesIO(self.data if isinstance(self.data, bytes) else self.data.encode())
        else:
            # string mode; coerce bytes to string if needed.  encoding ignored if already a string.
            return StringIO(self.data if isinstance(self.data, str) else self.data.decode(encoding))

    def __del__(self, unlink=os.unlink) -> None:
        if hasattr(self.data, 'name'):
            # This is a file-like object returned from tempfile.NamedTemporaryFile; remove the tempfile.
            unlink(self.data.name)