#!/usr/bin/env python3
import sys

from bs4 import BeautifulSoup
from bs4.element import ResultSet, Tag


class Result(ResultSet):
    def __init__(self, source, result):
        super().__init__(source, result=result)

    def _select(self, selector):
        if selector == '@':
            return self.load()
        if isinstance(selector, int) or isinstance(selector, slice):
            return super().__getitem__(selector)
        raise NotImplementedError

    def __truediv__(self, selector):
        return self._select(selector)

    def __getitem__(self, selector):
        return self._select(selector)

    def __floordiv__(self, v):
        if isinstance(v, tuple) or isinstance(v, list):
            return [tuple(self.getprop(vv, r) for vv in v) for r in self]
        return [self.getprop(v, r) for r in self]

    def load(self):
        return Result(self, (self.source.load(r) for r in self))
        # return Pages((self.source.load(r) for r in self))

    @staticmethod
    def getprop(prop, item):
        if prop == 'tag':
            return item.name
        if prop == 'text':
            return item.text
        return item.get(prop)


class Parser(BeautifulSoup):
    headers = {'User-Agent': 'Mozilla/5.0'}

    def __init__(self, uri='', markup='', session=None, initiator=None, debug=False):
        from urllib.parse import ParseResult, urlparse
        from requests import Session
        from requests.adapters import HTTPAdapter
        from requests.exceptions import RequestException

        self.start_uri = uri
        self.debug = debug

        pu: ParseResult = urlparse(uri)

        self.scheme = pu.scheme
        self.host = pu.hostname
        self.start_path = '?'.join((pu.path, pu.query))
        self.base = '%s://%s' % (pu.scheme, pu.netloc)
        self.initiator = initiator

        if session:
            self._session = session
        else:
            self._session = Session()
            self._session.mount(self.base, HTTPAdapter(max_retries=3))

        if uri:
            try:
                if self.debug:
                    print('GET', uri)
                r = self._session.get(uri, timeout=10, headers=self.headers)
                if r.status_code >= 400:
                    sys.stderr.write('err: %s %s\n' % (r.status_code, uri))
                super().__init__(r.text, 'lxml')
            except RequestException as e:
                sys.stderr.write('err: %s %s\n' % (e, uri))
                super().__init__('', 'lxml')
        elif markup:
            super().__init__(markup, 'lxml')

    def load(self, uri):
        initiator = self
        if isinstance(uri, Tag) and uri.name == 'a':
            initiator = uri
            uri = uri.get('href')
        if uri.startswith('//'):
            uri = '%s:%s' % (self.scheme, uri)
        elif uri.startswith('/'):
            uri = '%s%s' % (self.base, uri)
        elif not uri.startswith(('http://', 'https://')):
            # maybe wrong solution for paths: level1/level2.html
            uri = '%s/%s' % (self.base, uri)
        return Parser(uri, session=self._session, initiator=initiator, debug=self.debug)

    def _select(self, selector: str or int):
        if self.debug:
            print('Select Start:', selector)
        if isinstance(selector, int):
            return super().__getitem__(selector)

        rest = None
        output_format = None

        # @ -> load every link
        # % -> output format (not implemented)

        need_load = '@' in selector
        if '%' in selector:
            selector, _, output_format = selector.rpartition('%')

        if need_load:
            selector, _, rest = selector.partition('@')

        if self.debug:
            print('Select:', selector)
        results = self.select(selector)

        if need_load:
            if self.debug:
                print('Load:', selector)
            results = Result(self, results).load()

            # @ in selector, need to process rest selectors on result
            if rest:
                if self.debug:
                    print('Select:', rest, 'for each page')
                res = []
                for page in results:
                    for r in page._select(rest):
                        res.append(r)
                results = res

        return self.output(Result(self, results), output_format)

    def output(self, result: Result, fmt):
        if self.debug:
            print('Output:', fmt, result)
        if not fmt:
            return result
        import re
        print(type(result[0]))
        fmt = re.sub(r'(\W|^)\.', '\\1item.', fmt)
        return (eval(fmt, {'item': r}) for r in result)

    def __repr__(self):
        return str(self.result)

    def __truediv__(self, selector):
        return self._select(selector)

    def __getitem__(self, selector):
        return self._select(selector)


def _main(start_uri, selector, d=False):
    for t in Parser(start_uri, debug=d) / selector:
        print(t)


if __name__ == '__main__':
    from fire import Fire
    Fire(_main)
