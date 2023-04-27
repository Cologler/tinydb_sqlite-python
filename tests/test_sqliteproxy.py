# -*- coding: utf-8 -*-
# 
# Copyright (c) 2023~2999 - Cologler <skyoflw@gmail.com>
# ----------
# 
# ----------

from sqlite3 import connect
from contextlib import contextmanager

from tinydb_sqlite.storages import SQLiteTableProxy

@contextmanager
def get_dbproxy():
    with connect(':memory:') as conn:
        proxy = SQLiteTableProxy(conn, 'xxx')
        proxy.create_table(conn.cursor())
        yield proxy

def test_count():
    with get_dbproxy() as db:
        assert len(db) == 0
        db['aaa'] = 2
        assert len(db) == 1

def test_keys():
    with get_dbproxy() as db:
        assert list(db.keys()) == []
        db['aaa'] = 2
        assert list(db.keys()) == ['aaa']
        assert list(db) == ['aaa']

def test_values():
    with get_dbproxy() as db:
        assert list(db.values()) == []
        db['aaa'] = 2
        assert list(db.values()) == [2]

def test_items():
    with get_dbproxy() as db:
        assert list(db.items()) == []
        db['aaa'] = 2
        assert list(db.items()) == [('aaa', 2)]
