# tinydb_sqlite

## Usage

``` py
from tinydb import TinyDb
from tinydb_sqlite import SQLiteStorage

with TinyDB(storage=SQLiteStorage, connection='db.sqlite') as db:
    ...
```
