import requests
import bs4
import sqlite3
import logging
import io
import re


class Server:

    def __init__(self):
        self.session = requests.Session()
        self.resp = None
        self.RequestException = requests.RequestException

    def connect(self, method, url, **kwargs):
        kwargs['timeout'] = kwargs.get('timeout', 10)
        output = kwargs.pop('output', None)
        status_raise = kwargs.pop('raise_for_status', True)

        self.resp = self.session.request(method, url, **kwargs)
        if status_raise:
            self.resp.raise_for_status()

        if output == 'text':
            return self.resp.text
        elif output == 'content':
            return self.resp.content
        elif output == 'json':
            return self.resp.json()
        elif output == 'soup':
            return bs4.BeautifulSoup(self.resp.text, 'html.parser')
        else:
            return self.resp


class Database:

    def __init__(self, file, foreign_keys=True, row_factory=False):
        self.conn = sqlite3.connect(file)
        self.conn.create_function('REGEXP', 2, lambda x, y: True if re.search(x, y) else False)
        self.Error = sqlite3.Error
        if row_factory:
            self.conn.row_factory = sqlite3.Row
        if foreign_keys:
            self.conn.execute('PRAGMA foreign_keys = ON')
        self.c = self.conn.cursor()

    def create_table(self, table, columns):
        sql = f'CREATE TABLE IF NOT EXISTS {table} ({",".join(columns)})'
        self.c.execute(sql)

    def create_view(self, view, sql):
        sql = f'CREATE VIEW IF NOT EXISTS {view} AS {sql}'
        self.c.execute(sql)

    def insert_into(self, table, columns, values, commit=True, executemany=True):
        placeholder = ("?," * len(columns))[:-1]
        sql = f'INSERT INTO {table} ({",".join(columns)}) VALUES ({placeholder})'
        if executemany:
            self.c.executemany(sql, values)
        else:
            self.c.execute(sql, values)
        if commit:
            self.commit()

    def update(self, table, columns, where_clause, values, commit=True):
        set_clause = ('=?,'.join(columns)) + '=?'
        sql = f'UPDATE {table} SET {set_clause} WHERE {where_clause}'
        self.c.execute(sql, values)
        if commit:
            self.commit()

    def delete_rows(self, table, where_clause, values, commit=True):
        sql = f'DELETE FROM {table} WHERE {where_clause}'
        self.c.execute(sql, values)
        if commit:
            self.commit()

    def commit(self):
        self.conn.commit()

    def get_column_names(self, table):
        return tuple(map(lambda x: x[1], self.c.execute(f'PRAGMA TABLE_INFO({table})').fetchall()))

    @staticmethod
    def get_placeholders(number):
        ph = '?,' * number
        return ph[:-1]

    @staticmethod
    def dict_to_column(dict_to_map):
        columns = []
        for item in dict_to_map.items():
            if type(item[1]) in [int, bool]:
                columns.append(f'{item[0]} INTEGER')
            elif type(item[1]) is float:
                columns.append(f'{item[0]} REAL')
            elif type(item[1]) is str:
                columns.append(f'{item[0]} TEXT')
            elif type(item[1]) is dict:
                columns.extend(Database.dict_to_column(item[1]))
        return columns


class Vonage:

    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = Server()

    def send_otp(self, mobile, brand):
        params = {'api_key': self.api_key,
                  'api_secret': self.api_secret,
                  'number': mobile,
                  'brand': brand}
        resp = self.client.connect('GET', 'https://api.nexmo.com/verify/json', params=params, output='json')
        return resp.get('request_id')

    def check_otp(self, request_id, code):
        params = {'api_key': self.api_key,
                  'api_secret': self.api_secret,
                  'request_id': request_id,
                  'code': code}
        resp = self.client.connect('GET', 'https://api.nexmo.com/verify/check/json', params=params, output='json')
        return True if resp.get('status') == '0' else False

    def cancel_otp(self, request_id):
        params = {'api_key': self.api_key,
                  'api_secret': self.api_secret,
                  'request_id': request_id,
                  'cmd': 'cancel'}
        resp = self.client.connect('GET', 'https://api.nexmo.com/verify/control/json', params=params, output='json')
        return resp

    def send_sms(self, from_, to, text):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {'from': from_,
                'text': text,
                'to': to,
                'api_key': self.api_key,
                'api_secret': self.api_secret}

        resp = self.client.connect('POST', 'https://rest.nexmo.com/sms/json', headers=headers, data=data, output='json')
        status = [x['status'] for x in resp['messages']]
        if status.count('0') != len(status):
            raise self.client.RequestException(f'Failed to send SMS:\n{resp}')
        return resp


class Telegram:

    def __init__(self, token):
        self._url = f'https://api.telegram.org/bot{token}/'
        self.client = Server()
        self.keyboard = {"keyboard": None,
                         "is_persistent": False,
                         "resize_keyboard": True,
                         "one_time_keyboard": True,
                         "input_field_placeholder": "Choose an option..."}
        self.inline_keyboard = {"inline_keyboard": None}

    def add_kwargs(self, data, kwargs):
        for k, v in kwargs.items():
            data[k] = v
        return data

    def send_message(self, chat_id, text, **kwargs):
        data = {'chat_id': chat_id,
                'text': text}
        data = self.add_kwargs(data, kwargs)
        return self.execute('sendMessage', data)

    def send_chat_action(self, chat_id, action, **kwargs):
        """action = typing (to show bot typing)"""

        data = {'chat_id': chat_id,
                'action': action}
        data = self.add_kwargs(data, kwargs)
        return self.execute('sendChatAction', data)

    def answer_callback_query(self, cb_id, **kwargs):
        data = {'callback_query_id': cb_id}
        data = self.add_kwargs(data, kwargs)
        return self.execute('answerCallbackQuery', data)

    def set_webhook(self, url, **kwargs):
        data = {'url': url}
        data = self.add_kwargs(data, kwargs)
        return self.execute('setWebhook', data)

    def execute(self, method, data):
        resp = self.client.connect('POST', f'{self._url}{method}', json=data, output='json')
        if not resp.get('ok'):
            raise self.client.RequestException
        return resp


def create_log_file(file, **kwargs):
    fmt = kwargs.pop('format', '%(asctime)s %(levelname)s: %(message)s')
    datefmt = kwargs.pop('datefmt', '%H:%M:%S')
    level = kwargs.pop('level', logging.INFO)

    filemode = kwargs.pop('filemode', 'w')
    logging.basicConfig(filename=file, filemode=filemode, format=fmt, datefmt=datefmt, level=level, **kwargs)


def create_logger(name, **kwargs):
    fmt = kwargs.pop('format', '%(asctime)s %(levelname)s: %(message)s')
    datefmt = kwargs.pop('datefmt', '%H:%M:%S')
    level = kwargs.pop('level', logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    log_str = io.StringIO()

    sh = logging.StreamHandler(log_str)
    sh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    logger.addHandler(sh)
    return logger, log_str
