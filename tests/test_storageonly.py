# -*- coding: utf-8 -*-
#
# Copyright (c) 2020~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from tinydb import TinyDB
from tinydb_sqlite import SQLiteStorage

def open_memorydb():
    return TinyDB(storage=SQLiteStorage, connection=':memory:')

def test_do_notthing():
    with open_memorydb():
        pass

def test_empty():
    with open_memorydb() as db:
        assert db.tables() == set()

def test_insert():
    with open_memorydb() as db:
        a = db.table('a')
        assert db.tables() == set()
        assert a.all() == []
        a.insert({'b':1})
        assert db.tables() == {'a'}
        assert a.all() == [{'b':1}]

def test_count():
    with open_memorydb() as db:
        a = db.table('a')
        assert len(a) == 0
        a.insert({'b':1})
        assert len(a) == 1
