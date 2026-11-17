"""resolver 模块测试。"""
from __future__ import annotations

import os

import pytest

from chinaboundary.resolver import (
    AmbiguousName,
    ResolveError,
    Resolver,
    default_dict_path,
    infer_level_from_adcode,
    infer_level_from_name,
    strip_suffix,
)

from .conftest import FakeClient


def test_default_dict_path_prefers_cwd(tmp_path, monkeypatch):
    # cwd 下存在 docs/dict.json 时优先命中 cwd（模拟从仓库根运行）
    (tmp_path / "docs").mkdir()
    fake = tmp_path / "docs" / "dict.json"
    fake.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert default_dict_path() == str(fake)


def test_default_dict_path_fallback_to_project(tmp_path, monkeypatch):
    # cwd 下无 docs/dict.json 时回退到 __file__ 反推的项目根
    monkeypatch.chdir(tmp_path)
    p = default_dict_path()
    assert p.endswith(os.path.join("docs", "dict.json"))


def _resolver_with_dict(data: dict):
    r = Resolver(FakeClient(), None)
    r.dictionary = data
    return r


def _records(*items):
    """把 (code, name, level, parent) 元组转成 records 映射。"""
    return {
        code: {"name": name, "level": level, "parent": parent, "backend_adcode": code}
        for code, name, level, parent in items
    }


def test_strip_suffix():
    assert strip_suffix("广东省") == "广东"
    assert strip_suffix("广州市") == "广州"
    assert strip_suffix("内蒙古自治区") == "内蒙古"
    assert strip_suffix("天河区") == "天河"
    assert strip_suffix("北京") == "北京"


def test_infer_level_from_adcode():
    assert infer_level_from_adcode("100000") == "country"
    assert infer_level_from_adcode("440000") == "province"
    assert infer_level_from_adcode("440100") == "city"
    assert infer_level_from_adcode("440106") == "district"
    assert infer_level_from_adcode("123") is None


def test_infer_level_from_name():
    assert infer_level_from_name("广东省") == "province"
    assert infer_level_from_name("广州市") == "city"
    assert infer_level_from_name("天河区") == "district"
    assert infer_level_from_name("北京") is None


def test_resolve():
    data = {
        "version": 2,
        "records": _records(
            ("440106", "天河区", "district", "440100"),
            ("440100", "广州市", "city", "440000"),
            ("440000", "广东省", "province", "100000"),
            ("110105", "朝阳区", "district", "110000"),
        ),
        "orphans": {},
        "backend_index": {},
    }
    resolver = _resolver_with_dict(data)
    # 精确全名
    assert resolver.resolve("天河区") == ("440106", "440106", "district")
    # 去后缀 / 前缀
    assert resolver.resolve("广州") == ("440100", "440100", "city")
    assert resolver.resolve("广东") == ("440000", "440000", "province")
    # 层级过滤
    assert resolver.resolve("朝阳", level="district") == ("110105", "110105", "district")


def test_ambiguous_name():
    # 「朝阳」同时命中 北京市朝阳区（district）与 辽宁省朝阳市（city）
    data = {
        "version": 2,
        "records": _records(
            ("110105", "朝阳区", "district", "110000"),
            ("110000", "北京市", "province", "100000"),
            ("211300", "朝阳市", "city", "210000"),
            ("210000", "辽宁省", "province", "100000"),
        ),
        "orphans": {},
        "backend_index": {},
    }
    resolver = _resolver_with_dict(data)
    with pytest.raises(AmbiguousName):
        resolver.resolve("朝阳")
    # 指定层级可消除歧义
    assert resolver.resolve("朝阳", level="city") == ("211300", "211300", "city")


def test_not_found():
    resolver = _resolver_with_dict({"version": 2, "records": {}, "orphans": {}, "backend_index": {}})
    with pytest.raises(ResolveError):
        resolver.resolve("不存在的名字")


def test_describe():
    data = {
        "version": 2,
        "records": _records(
            ("440106", "天河区", "district", "440100"),
            ("440100", "广州市", "city", "440000"),
            ("440000", "广东省", "province", "100000"),
            ("100000", "中华人民共和国", "country", None),
        ),
        "orphans": {},
        "backend_index": {},
    }
    resolver = _resolver_with_dict(data)
    assert resolver.describe("440106") == "广东省 / 广州市 / 天河区"


# ---------- Resolver 的 adcode 归一化与 orphan 提示 ----------

def test_resolve_adcode_renumber():
    data = {
        "version": 2,
        "records": {
            "320613": {"name": "崇川区", "level": "district", "parent": "320600", "backend_adcode": "320602"},
        },
        "orphans": {},
        "backend_index": {"320602": "320613"},
    }
    r = _resolver_with_dict(data)
    # 输入最新官方码
    assert r.resolve_adcode("320613") == ("320613", "320602", "district")
    # 输入 GeoAtlas 旧码，向后兼容归一化
    assert r.resolve_adcode("320602") == ("320613", "320602", "district")


def test_resolve_adcode_orphan():
    data = {
        "version": 2,
        "records": {},
        "orphans": {"659011": {"name": "新星市", "level": "city", "parent": "650000"}},
        "backend_index": {},
    }
    r = _resolver_with_dict(data)
    with pytest.raises(ResolveError, match="暂无边界数据"):
        r.resolve_adcode("659011")


def test_resolve_adcode_unknown():
    data = {"version": 2, "records": {}, "orphans": {}, "backend_index": {}}
    r = _resolver_with_dict(data)
    with pytest.raises(ResolveError, match="未知行政区编码"):
        r.resolve_adcode("999999")


def test_resolve_orphan_name():
    data = {
        "version": 2,
        "records": {},
        "orphans": {"659011": {"name": "新星市", "level": "city", "parent": "650000"}},
        "backend_index": {},
    }
    r = _resolver_with_dict(data)
    with pytest.raises(ResolveError, match="暂无边界数据"):
        r.resolve("新星市")


def test_remap_feature():
    data = {
        "version": 2,
        "records": {
            "320613": {"name": "崇川区", "level": "district", "parent": "320600", "backend_adcode": "320602"},
            "320600": {"name": "南通市", "level": "city", "parent": "320000", "backend_adcode": "320600"},
        },
        "orphans": {},
        "backend_index": {"320602": "320613"},
    }
    r = _resolver_with_dict(data)
    f = {"adcode": "320602", "name": "崇川区", "parent": "320600"}
    r.remap_feature(f)
    assert f["adcode"] == "320613"
    assert f["name"] == "崇川区"
    assert f["parent"] == "320600"  # 同码，不变化


def test_ensure_dictionary_missing():
    # 字典缺失时应报错（不再在线构建）
    r = Resolver(FakeClient(), None)
    with pytest.raises(ResolveError, match="未找到行政区划字典"):
        r.ensure_dictionary()


if __name__ == "__main__":
    pytest.main([__file__])
