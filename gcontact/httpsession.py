# -*- coding: utf-8 -*-

"""
gcontact.httpsession
~~~~~~~~~~~~~~~~~~~

This module contains a class for working with http sessions.

"""

from urllib.parse import urlencode

import requests
from exceptions import RequestError
from meza import process as pr
DEF_HEADERS = {'Content-Type': 'application/json'}


class HTTPSession(object):
    """Handles HTTP activity while keeping headers persisting across requests.

       :param headers: A dict with initial headers.
    """

    def __init__(self, headers=None):
        self.headers = pr.merge([DEF_HEADERS, headers or {}])
        self.requests_session = requests.Session()

    def request(self, method, url, **kwargs):
        if kwargs.get('data'):
            data = urlencode(kwargs['data'])
        else:
            data = None

        if kwargs.get('headers'):
            headers = kwargs['headers']

            if not headers.get('Content-Type'):
                headers['Content-Type'] = 'application/x-www-form-urlencoded'

            combined = pr.merge([self.headers, headers])
            request_headers = {
                k: v for k, v in combined.items() if v is not None}
        else:
            request_headers = self.headers

        try:
            func = getattr(self.requests_session, method.lower())
        except AttributeError:
            raise RequestError('HTTP method %s is not supported' % method)

        extra = {'data': data, 'headers': request_headers}
        rkwargs = pr.merge([kwargs, extra])
        r = func(url, **rkwargs)

        if not r.ok:
            raise RequestError("{0}: {1}".format(r.status_code, r.reason))

        return r

    def get(self, url, params=None, **kwargs):
        return self.request('GET', url, params=params, **kwargs)

    def delete(self, url, params=None, **kwargs):
        return self.request('DELETE', url, params=params, **kwargs)

    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)

    def put(self, url, data=None, params=None,  **kwargs):
        return self.request('PUT', url, params=params, data=data, **kwargs)

    def add_header(self, name, value):
        self.headers[name] = value
