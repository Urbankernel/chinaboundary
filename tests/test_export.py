"""export 模块测试。"""
from __future__ import annotations

import json

import pytest

from chinaboundary import export, normalize

from .conftest import make_feature


def _features():
    fc = {
        "type": "FeatureCollection",
        "features": [
            make_feature(440100, "广州市", "city", 440000, 11),
            make_feature(440300, "深圳市", "city", 440000, 9),
        ],
    }
    return normalize.parse_response(fc)


def test_export_geojson(tmp_path):
    features = _features()
    p = tmp_path / "gd.geojson"
    export.export_geojson(features, str(p))
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2
    assert data["features"][0]["properties"]["name"] == "广州市"


def test_export_vector_skips_without_geopandas(tmp_path):
    features = _features()
    paths = export.export(features, str(tmp_path), ["geojson", "gpkg", "shp"], "gd")
    # geojson 一定产出
    assert "geojson" in paths
    # gpkg/shp 依赖 geopandas，未安装时应被跳过
    try:
        import geopandas  # noqa: F401

        has_gp = True
    except ImportError:
        has_gp = False
    assert ("gpkg" in paths) == has_gp
    assert ("shp" in paths) == has_gp


def test_export_dispatcher(tmp_path):
    features = _features()
    paths = export.export(features, str(tmp_path), ["geojson"], "gd")
    assert set(paths.keys()) == {"geojson"}


if __name__ == "__main__":
    pytest.main([__file__])
