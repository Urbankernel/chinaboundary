"""测试夹具：伪造客户端与样例 Feature。"""
from __future__ import annotations

import pytest


def make_feature(adcode, name, level, parent_adcode=None, children=0, geometry=None):
    return {
        "type": "Feature",
        "properties": {
            "adcode": adcode,
            "name": name,
            "center": [113.28, 23.12],
            "centroid": [113.42, 23.33],
            "childrenNum": children,
            "level": level,
            "parent": {"adcode": parent_adcode},
            "acroutes": [100000],
            "subFeatureIndex": 0,
        },
        "geometry": geometry
        or {
            "type": "Polygon",
            "coordinates": [[[113, 23], [114, 23], [114, 24], [113, 24], [113, 23]]],
        },
    }


class FakeClient:
    """按 (kind, adcode) 返回预设数据，记录调用。"""

    def __init__(self, data=None):
        self.data = data or {}
        self.calls = []

    def self_boundary(self, adcode):
        self.calls.append(("self", adcode))
        return self.data.get(("self", adcode), {"type": "FeatureCollection", "features": []})

    def children(self, adcode):
        self.calls.append(("children", adcode))
        return self.data.get(("children", adcode), {"type": "FeatureCollection", "features": []})


@pytest.fixture
def fake_client():
    return FakeClient()
