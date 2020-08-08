# -*- coding: utf-8 -*-
#
# Copyright (c) 2020~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from typing import *
from collections.abc import MutableMapping
from sqlite3 import Connection, connect, Cursor
from contextlib import closing
import json

from tinydb.storages import Storage

from .utils import TrackedMapping


class SQLiteTableProxy(MutableMapping):
    SQL_CREATE_TABLE = 'CREATE TABLE IF NOT EXISTS "%s" (key TEXT PRIMARY KEY, type TEXT, value BLOB);'
    SQL_DROP_TABLE = 'DROP TABLE IF NOT EXISTS "%s";'
    SQL_UPSERT_ITEM = 'INSERT OR REPLACE INTO %s VALUES (?, ?, ?);'
    SQL_DELETE_ITEM = 'DELETE FROM %s WHERE key=?;'
    SQL_ITER_KEYS = 'SELECT key FROM %s;'
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

    def overwrite(self, cursor: Cursor, data: Dict[str, Any]):
        # remove
        cursor.executemany(self.SQL_DELETE_ITEM % self._tablename, set(self) - set(data))

        # update
        params = []
        for k, v in data.items():
            params.append((k, *self._encode_value(v)))
        cursor.executemany(self.SQL_UPSERT_ITEM % self._tablename, params)

    def _decode_value(self, type_: str, value):
        if type_ == 'null':
            return None
        if type_ == 'bool':
            return bool(value)
        if type_ == 'int':
            return int(value)
        if type_ == 'float':
            return float(value)
        if type_ == 'str':
            return str(value)
        if type_ == 'bytes':
            return bytes(value)
        if type_ == 'json':
            return json.loads(value)
        raise NotImplementedError

    def _encode_value(self, value) -> Tuple[str, Any]:
        if value is None:
            return 'null', None
        type_ = type(value)
        if type_ in (bool, int, float, str, bytes):
            return type_.__name__, value
        return 'json', json.dumps(value, ensure_ascii=False)

    def __getitem__(self, key):
        with closing(self._conn.execute(self.SQL_GET_VALUE % self._tablename, (key, ))) as cursor:
            t, v = cursor.fetchone()
            return self._decode_value(t, v)

    def __setitem__(self, key, value):
        param = (key, *self._encode_value(value))
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
                data: TrackedMapping
                updated = set()
                deleted = set()

                for action, args in data.history:
                    if action == 'setitem':
                        # update entire table
                        k, v = args
                        updated.add(k)

                    elif action == 'getitem':
                        # update entire table
                        k, = args
                        updated.add(k)

                    elif action == 'delitem':
                        # drop table
                        k, = args
                        deleted.add(k)
                        updated.discard(k)

                    else:
                        raise NotImplementedError

                for k in updated:
                    table = SQLiteTableProxy(self._conn, k)
                    table.create_table(cursor)
                    table.overwrite(cursor, data[k])


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
