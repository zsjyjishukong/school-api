# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import inspect
import requests
from bs4 import BeautifulSoup

from school_api.client.api.base import BaseSchoolApi
from school_api.session.memorystorage import MemoryStorage
from school_api.utils import to_text, ObjectDict
from school_api.config import URL_ENDPOINT, CLASS_TIME_LIST


def _is_api_endpoint(obj):
    return isinstance(obj, BaseSchoolApi)


class BaseSchoolClient(object):

    def __init__(self, url, **kwargs):

        self.school = {
            'url': url,
            'debug': kwargs.get('debug'),
            'name': to_text(kwargs.get('name')),
            'code': kwargs.get('code'),
            'use_ex_handle': kwargs.get('use_ex_handle', True),
            'exist_verify': kwargs.get('exist_verify', True),
            'lan_url': kwargs.get('lan_url'),
            'proxies': kwargs.get('proxies'),
            'priority_porxy': kwargs.get('priority_porxy'),
            'timeout': kwargs.get('timeout', 10),
            'login_url': kwargs.get('login_url_path', '/default2.aspx'),
            'url_endpoint': kwargs.get('url_endpoint') or URL_ENDPOINT,
            'time_list': kwargs.get('class_time_list') or CLASS_TIME_LIST
        }
        storage = kwargs.get('session', MemoryStorage)
        self.session = storage(self.school['code'])
        self.init_login_view_state(kwargs.get('login_view_state', {}))
        self.school = ObjectDict(self.school)

    def init_login_view_state(self, login_view_state):
        for url_key, view_state in login_view_state.items():
            self.session.set('login_view:' + url_key, view_state)


class BaseUserClient(object):
    """docstring for BaseUserClient"""

    _proxy = None

    def __new__(cls, *args):
        self = super(BaseUserClient, cls).__new__(cls)
        api_endpoints = inspect.getmembers(self, _is_api_endpoint)
        for name, api in api_endpoints:
            api_cls = type(api)
            api = api_cls(self)
            setattr(self, name, api)
        return self

    def __init__(self, school, account, password, user_type):
        self._http = requests.Session()
        self._http.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/62.0.3202.89 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
        })
        self.account = to_text(account)
        self.password = password
        self.user_type = user_type
        self.school = school.school
        self.base_url = self.school.url
        self.session = school.session

        if self.school.priority_porxy:
            self.set_proxy()

    def _request(self, method, url_or_endpoint, **kwargs):
        if not url_or_endpoint.startswith(('http://', 'https://')):
            url = '{base}{endpoint}'.format(
                base=self.base_url,
                endpoint=url_or_endpoint
            )
        else:
            url = url_or_endpoint

        kwargs['timeout'] = kwargs.get('timeout', self.school.timeout)
        res = self._http.request(
            method=method,
            url=url,
            proxies=self._proxy,
            **kwargs
        )
        return res

    def get(self, url, **kwargs):
        return self._request(
            method='GET',
            url_or_endpoint=url,
            **kwargs
        )

    def post(self, url, **kwargs):
        return self._request(
            method='POST',
            url_or_endpoint=url,
            **kwargs
        )

    def head(self, url, **kwargs):
        return self._request(
            method='HEAD',
            url_or_endpoint=url,
            **kwargs
        )

    def set_proxy(self):
        self.school.priority_porxy = True
        self.base_url = self.school.lan_url or self.base_url
        self._proxy = self.school.proxies

    def update_headers(self, headers_dict):
        self._http.headers.update(headers_dict)

    def get_view_state(self, url_suffix, **kwargs):
        res = self.get(url_suffix, allow_redirects=False, **kwargs)
        if res.status_code != 200:
            return None
        return self.get_view_state_from_html(res.text)

    @staticmethod
    def get_view_state_from_html(html):
        pre_soup = BeautifulSoup(html, "html.parser")
        view_state = pre_soup.find(
            attrs={"name": "__VIEWSTATE"})['value']
        return view_state

    def get_login_session(self):
        ''' 获取登录会话 '''
        url = self.base_url + self.school.login_url
        key = '{}:{}:{}'.format('login_session', url, self.account)
        cookie = self.session.get(key)
        if not cookie:
            return None
        url = self.base_url + self.school.login_url
        self.update_headers({'Referer': url})
        self._http.cookies.update(cookie)
        return True

    def del_login_session(self):
        ''' 删除会话 '''
        url = self.base_url + self.school.login_url
        key = '{}:{}:{}'.format('login_session', url, self.account)
        self.session.delete(key)
        self._http.cookies.clear()

    def save_login_session(self):
        ''' 保存登录会话 '''
        url = self.base_url + self.school.login_url
        key = '{}:{}:{}'.format('login_session', url, self.account)
        cookie = self._http.cookies.get_dict()
        self.session.set(key, cookie, 3600)

    def get_login_view_state(self, **kwargs):
        ''' 获取登录的view_state '''
        base_key = 'login_view:' + self.base_url + self.school.login_url
        if not self.session.get(base_key):
            view_state = self.get_view_state(self.school.login_url, **kwargs)
            self.session.set(base_key, view_state)
        return self.session.get(base_key)
