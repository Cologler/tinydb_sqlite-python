# -*- coding: utf-8 -*-
#
# Copyright (c) 2020~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from collections.abc import MutableMapping

class TrackedMapping(MutableMapping):
    def __init__(self, mapping: dict):
        super().__init__()
        self._mapping = mapping
        self.history = []

    def __getitem__(self, key):
        rv = self._mapping[key]
        self.history.append(('getitem', (key,)))
        return rv

    def __setitem__(self, key, value):
        self._mapping[key] = value
        self.history.append(('setitem', (key, value)))

    def __delitem__(self, key):
        del self._mapping[key]
        self.history.append(('delitem', (key,)))

    def __iter__(self):
        for key in self._mapping:
            yield key

    def __len__(self):
        return len(self._mapping)
