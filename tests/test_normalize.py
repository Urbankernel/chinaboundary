"""normalize 模块测试。"""
from __future__ import annotations

import pytest

from chinaboundary import normalize

from .conftest import make_feature


def test_parse_normal_feature():
    f = make_feature(440100, "广州市", "city", parent_adcode=440000, children=11)
    parsed = normalize.parse_feature(f)
    assert parsed["adcode"] == "440100"
    assert parsed["name"] == "广州市"
    assert parsed["level"] == "city"
    assert parsed["parent"] == "440000"
    assert parsed["children"] == 11
    assert parsed["cen_lng"] == 113.28
    assert parsed["cen_lat"] == 23.12
    assert parsed["geometry"]["type"] == "Polygon"


def test_skip_special_feature():
    f = {
        "type": "Feature",
        "properties": {"name": "", "adcode": "100000_JD"},
        "geometry": {"type": "MultiPolygon", "coordinates": []},
    }
    assert normalize.parse_feature(f) is None
    # 显式保留时可解析（但几何为空会被过滤）
    assert normalize.parse_feature(f, include_special=True) is None


def test_skip_missing_geometry():
    f = {"type": "Feature", "properties": {"adcode": 440000, "name": "广东省", "level": "province"}}
    assert normalize.parse_feature(f) is None


def test_fix_invalid_polygon():
    # 自相交（蝴蝶结）多边形
    bowtie = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]]],
    }
    f = make_feature(999999, "测试", "district", geometry=bowtie)
    parsed = normalize.parse_feature(f)
    assert parsed is not None  # buffer(0) 修复后仍有效


def test_parse_response_empty():
    assert normalize.parse_response(None) == []
    assert normalize.parse_response({"type": "FeatureCollection", "features": []}) == []


if __name__ == "__main__":
    pytest.main([__file__])
