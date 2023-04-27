# -*- coding: utf-8 -*-
#
# Copyright (c) 2020~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from typing import Any, Tuple, Dict, Optional
from collections.abc import MutableMapping, ItemsView, ValuesView
from sqlite3 import Connection, connect, Cursor
from contextlib import closing
import json

from tinydb.storages import Storage

from .utils import TrackedMapping

_TYPES_MAPPING = {
    (type(None),    ''),
    (bool,          '?'),
    (int,           'i'),
    (float,         'f'),
    (str,           's'),
    (bytes,         'b'),
}
_T2V = dict(_TYPES_MAPPING)
_V2T = dict(reversed(x) for x in _TYPES_MAPPING)
assert len(_T2V) == len(_V2T)

def decode_value(type_id: str, value):
    type_ = _V2T.get(type_id)
    if type_ is not None:
        if type_ is type(None):
            return None # type(None)() takes no arguments
        else:
            return type_(value)
    if type_id == 'j':
        return json.loads(value)
    raise NotImplementedError(type_id, value)

def encode_value(value) -> Tuple[str, Any]:
    type_ = type(value)
    type_id = _T2V.get(type_)
    if type_id is not None:
        return type_id, value
    return 'j', json.dumps(value, ensure_ascii=False)

class SQLiteTableProxy(MutableMapping):
    SQL_CREATE_TABLE = 'CREATE TABLE IF NOT EXISTS "%s" (key TEXT PRIMARY KEY, type TEXT, value BLOB);'
    SQL_DROP_TABLE = 'DROP TABLE IF NOT EXISTS "%s";'
    SQL_UPSERT_ITEM = 'INSERT OR REPLACE INTO %s VALUES (?, ?, ?);'
    SQL_DELETE_ITEM = 'DELETE FROM %s WHERE key=?;'
    SQL_ITER_KEYS = 'SELECT key FROM %s;'
    SQL_ITER_ROWS = 'SELECT key, type, value FROM %s;'
    SQL_GET_VALUE = 'SELECT type, value FROM %s WHERE key=?;'
    SQL_COUNT = 'SELECT COUNT(*) FROM %s'

    def __init__(self, connection: Connection, tablename: str):
        super().__init__()
        self._conn = connection
        self._tablename = tablename

    def create_table(self, cursor: Cursor):
        cursor.execute(self.SQL_CREATE_TABLE % self._tablename)

    def drop_table(self, cursor: Cursor):
        cursor.execute(self.SQL_DROP_TABLE % self._tablename)

    def iter_raw(self, cursor: Cursor) -> Tuple[str, str, Any]:
        cursor.execute(self.SQL_ITER_ROWS % self._tablename)
        yield from cursor

    def iter_items_decoded(self, cursor: Cursor, encode=True) -> Tuple[str, Any]:
        for k, t, v in self.iter_raw(cursor):
            yield k, decode_value(t, v)

    def overwrite(self, cursor: Cursor, data: Dict[str, Any]):
        # fetch
        data_indb = dict((i[0], i[1:]) for i in self.iter_raw(cursor))

        # remove
        params = [(k,) for k in (set(data_indb) - set(data))]
        cursor.executemany(self.SQL_DELETE_ITEM % self._tablename, params)

        # update
        params = []
        for k, v in data.items():
            encoded_value = encode_value(v)
            if encoded_value != data_indb.get(k):
                params.append((k, *encoded_value))
        cursor.executemany(self.SQL_UPSERT_ITEM % self._tablename, params)

    def __getitem__(self, key):
        with closing(self._conn.execute(self.SQL_GET_VALUE % self._tablename, (key, ))) as cursor:
            t, v = cursor.fetchone()
            return decode_value(t, v)

    def __setitem__(self, key, value):
        param = (key, *encode_value(value))
        with closing(self._conn.execute(self.SQL_UPSERT_ITEM % self._tablename, param)):
            pass

    def __delitem__(self, key):
        param = key,
        with closing(self._conn.execute(self.SQL_DELETE_ITEM % self._tablename, param)):
            pass

    def __iter__(self):
        with closing(self._conn.execute(self.SQL_ITER_KEYS % self._tablename)) as cursor:
            for k, in cursor:
                yield k

    def __len__(self):
        with closing(self._conn.execute(self.SQL_COUNT % self._tablename)) as cursor:
            v, = cursor.fetchone()
            return v

    def items(self):
        return SQLiteTableProxyItemsView(self)

    def values(self):
        return SQLiteTableProxyValuesView(self)


class SQLiteTableProxyItemsView(ItemsView):
    @property
    def _conn(self):
        return self._mapping._conn

    def __iter__(self):
        with closing(self._conn.cursor()) as cursor:
            yield from self._mapping.iter_items_decoded(cursor)


class SQLiteTableProxyValuesView(ValuesView):
    @property
    def _conn(self):
        return self._mapping._conn

    def __iter__(self):
        with closing(self._conn.cursor()) as cursor:
            for _, value in self._mapping.iter_items_decoded(cursor):
                yield value


class SQLiteStorage(Storage):
    SQL_LIST_TABLES = 'SELECT name FROM sqlite_master WHERE type="table";'

    def __init__(self, connection, **kwargs):
        super().__init__()
        if not isinstance(connection, Connection):
            connection = connect(connection)
        self._conn: Connection = connection

    def _list_tables(self, cursor: Cursor) -> Dict[str, SQLiteTableProxy]:
        cursor.execute(self.SQL_LIST_TABLES)
        tablenames = [n[0] for n in cursor.fetchall()]
        db = {}
        for name in tablenames:
            db[name] = SQLiteTableProxy(self._conn, name)
        return db

    def read(self) -> Optional[Dict[str, Dict[str, Any]]]:
        with closing(self._conn.cursor()) as cursor:
            return TrackedMapping(self._list_tables(cursor))

    def write(self, data: Dict[str, Dict[str, Any]]) -> None:
        with closing(self._conn.cursor()) as cursor:
            updated: set
            deleted: set

            if isinstance(data, TrackedMapping):
                updated = set()
                deleted = set()
                for action, args in data.history:
                    if action in ('setitem', 'getitem'):
                        updated.add(args[0])

                    elif action == 'delitem':
                        # drop table
                        k = args[0]
                        deleted.add(k)
                        updated.discard(k)

                    else:
                        raise NotImplementedError
            else:
                exists = set(self._list_tables(cursor))
                updated = set(data)
                deleted = exists - updated

            for k in updated:
                table = SQLiteTableProxy(self._conn, k)
                table.create_table(cursor)
                table.overwrite(cursor, data[k])

            for k in deleted:
                SQLiteTableProxy(self._conn, k).drop_table(cursor)

            self._conn.commit()

    def close(self) -> None:
        self._conn.close()
