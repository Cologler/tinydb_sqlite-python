# -*- coding: utf-8 -*-
# 
# Copyright (c) 2023~2999 - Cologler <skyoflw@gmail.com>
# ----------
# 
# ----------

from tinydb_sqlite.storages import encode_value, decode_value

def test_encode_decode_value():
    def test_compare(val):
        type_, value = encode_value(val)
        assert decode_value(type_, value) == val

    test_compare(None)
    test_compare(True)
    test_compare(False)
    test_compare(1)
    test_compare(1)
    test_compare(1.5)
    test_compare('sss')
    test_compare(b'fff')
    test_compare({
        'a': 2,
        'b': {
            'c': 3,
            'd': [
                4, 5
            ]
        }
    })
