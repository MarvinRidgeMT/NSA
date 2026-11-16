"""Seekable HTTP range-read file object, so stdlib zipfile can list a remote zip (and read single
members) without downloading the archive. Used for the Zenodo GSFC SfS archive (L6)."""
import io
import urllib.request


class HTTPRangeFile(io.RawIOBase):
    def __init__(self, url, block=1 << 16):
        self.url, self.pos, self.block = url, 0, block
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'polaris-science-limits'})
        with urllib.request.urlopen(req, timeout=60) as r:
            self.url = r.geturl()
            self.size = int(r.headers['Content-Length'])
        self.cache = {}
        self.bytes_fetched = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        if n == 0:
            return b''
        req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{self.pos + n - 1}',
                                                         'User-Agent': 'polaris-science-limits'})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        self.bytes_fetched += len(data)
        self.pos += len(data)
        return data

    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d
        return len(d)
