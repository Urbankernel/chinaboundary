"""fetch 模块测试：多目标抓取编排。"""
from __future__ import annotations

from chinaboundary import fetch
from chinaboundary.resolver import Resolver

from .conftest import FakeClient, make_feature


def _resolver(records=None, orphans=None):
    r = Resolver(FakeClient(), None)
    r.dictionary = {
        "version": 2,
        "records": records or {},
        "orphans": orphans or {},
        "backend_index": {},
    }
    return r


def _cfg(**kw):
    base = {
        "level": None,
        "names": [],
        "adcodes": [],
        "depth": 0,
        "children_only": False,
    }
    base.update(kw)
    return base


def test_fetch_multiple_adcodes():
    client = FakeClient({
        ("self", "370000"): {"type": "FeatureCollection", "features": [make_feature(370000, "山东省", "province", 100000)]},
        ("self", "130000"): {"type": "FeatureCollection", "features": [make_feature(130000, "河北省", "province", 100000)]},
    })
    resolver = _resolver({
        "370000": {"name": "山东省", "level": "province", "parent": "100000", "backend_adcode": "370000"},
        "130000": {"name": "河北省", "level": "province", "parent": "100000", "backend_adcode": "130000"},
    })
    features, targets = fetch.fetch_features(_cfg(adcodes=["370000", "130000"]), client, resolver)
    assert len(features) == 2
    assert len(targets) == 2
    assert [t["public_adcode"] for t in targets] == ["370000", "130000"]
    assert client.calls == [("self", "370000"), ("self", "130000")]


def test_fetch_multiple_names():
    client = FakeClient({
        ("self", "370000"): {"type": "FeatureCollection", "features": [make_feature(370000, "山东省", "province", 100000)]},
        ("self", "130000"): {"type": "FeatureCollection", "features": [make_feature(130000, "河北省", "province", 100000)]},
    })
    resolver = _resolver({
        "370000": {"name": "山东省", "level": "province", "parent": "100000", "backend_adcode": "370000"},
        "130000": {"name": "河北省", "level": "province", "parent": "100000", "backend_adcode": "130000"},
    })
    features, targets = fetch.fetch_features(_cfg(names=["山东省", "河北省"]), client, resolver)
    assert len(features) == 2
    assert [t["input"] for t in targets] == ["山东省", "河北省"]


def test_fetch_depth_one_multi():
    client = FakeClient({
        ("self", "370000"): {"type": "FeatureCollection", "features": [make_feature(370000, "山东省", "province", 100000)]},
        ("children", "370000"): {"type": "FeatureCollection", "features": [make_feature(370100, "济南市", "city", 370000)]},
        ("self", "130000"): {"type": "FeatureCollection", "features": [make_feature(130000, "河北省", "province", 100000)]},
        ("children", "130000"): {"type": "FeatureCollection", "features": [make_feature(130100, "石家庄市", "city", 130000)]},
    })
    resolver = _resolver({
        "370000": {"name": "山东省", "level": "province", "parent": "100000", "backend_adcode": "370000"},
        "370100": {"name": "济南市", "level": "city", "parent": "370000", "backend_adcode": "370100"},
        "130000": {"name": "河北省", "level": "province", "parent": "100000", "backend_adcode": "130000"},
        "130100": {"name": "石家庄市", "level": "city", "parent": "130000", "backend_adcode": "130100"},
    })
    features, targets = fetch.fetch_features(_cfg(adcodes=["370000", "130000"], depth=1), client, resolver)
    assert len(features) == 4  # 2 省 + 2 市


def test_fetch_children_only_multi():
    client = FakeClient({
        ("children", "370000"): {"type": "FeatureCollection", "features": [make_feature(370100, "济南市", "city", 370000)]},
        ("children", "130000"): {"type": "FeatureCollection", "features": [make_feature(130100, "石家庄市", "city", 130000)]},
    })
    resolver = _resolver({
        "370000": {"name": "山东省", "level": "province", "parent": "100000", "backend_adcode": "370000"},
        "370100": {"name": "济南市", "level": "city", "parent": "370000", "backend_adcode": "370100"},
        "130000": {"name": "河北省", "level": "province", "parent": "100000", "backend_adcode": "130000"},
        "130100": {"name": "石家庄市", "level": "city", "parent": "130000", "backend_adcode": "130100"},
    })
    features, targets = fetch.fetch_features(
        _cfg(adcodes=["370000", "130000"], depth=1, children_only=True),
        client, resolver,
    )
    assert len(features) == 2  # 仅子级
    # 未调用 self_boundary
    assert ("self", "370000") not in client.calls


def test_fetch_default_country_when_empty():
    client = FakeClient({
        ("self", "100000"): {"type": "FeatureCollection", "features": [make_feature(100000, "中华人民共和国", "country", None)]},
    })
    resolver = _resolver({
        "100000": {"name": "中华人民共和国", "level": "country", "parent": None, "backend_adcode": "100000"},
    })
    features, targets = fetch.fetch_features(_cfg(), client, resolver)
    assert len(features) == 1
    assert targets[0]["public_adcode"] == "100000"


def test_fetch_depth_two():
    # 省 -> 市 -> 区县 三层下钻
    client = FakeClient({
        ("self", "370000"): {"type": "FeatureCollection", "features": [make_feature(370000, "山东省", "province", 100000, children=1)]},
        ("children", "370000"): {"type": "FeatureCollection", "features": [make_feature(370100, "济南市", "city", 370000, children=1)]},
        ("children", "370100"): {"type": "FeatureCollection", "features": [make_feature(370102, "历下区", "district", 370100, children=0)]},
    })
    resolver = _resolver({
        "370000": {"name": "山东省", "level": "province", "parent": "100000", "backend_adcode": "370000"},
        "370100": {"name": "济南市", "level": "city", "parent": "370000", "backend_adcode": "370100"},
        "370102": {"name": "历下区", "level": "district", "parent": "370100", "backend_adcode": "370102"},
    })
    features, targets = fetch.fetch_features(_cfg(adcodes=["370000"], depth=2), client, resolver)
    assert len(features) == 3  # 省 + 市 + 区县
    assert {f["name"] for f in features} == {"山东省", "济南市", "历下区"}
    assert targets[0]["depth"] == 2


def test_fetch_depth_two_children_only():
    # children_only：跳过根，仍递归下钻子级/孙级
    client = FakeClient({
        ("children", "370000"): {"type": "FeatureCollection", "features": [make_feature(370100, "济南市", "city", 370000, children=1)]},
        ("children", "370100"): {"type": "FeatureCollection", "features": [make_feature(370102, "历下区", "district", 370100, children=0)]},
    })
    resolver = _resolver({
        "370000": {"name": "山东省", "level": "province", "parent": "100000", "backend_adcode": "370000"},
        "370100": {"name": "济南市", "level": "city", "parent": "370000", "backend_adcode": "370100"},
        "370102": {"name": "历下区", "level": "district", "parent": "370100", "backend_adcode": "370102"},
    })
    features, targets = fetch.fetch_features(
        _cfg(adcodes=["370000"], depth=2, children_only=True),
        client, resolver,
    )
    assert len(features) == 2  # 济南市 + 历下区，不含山东省
    assert ("self", "370000") not in client.calls


def test_fetch_dedup_overlapping_targets():
    # 370000 + 370100 两个目标 depth=1，济南市(370100) 会被两条路径抓到，需去重
    client = FakeClient({
        ("self", "370000"): {"type": "FeatureCollection", "features": [make_feature(370000, "山东省", "province", 100000, children=1)]},
        ("children", "370000"): {"type": "FeatureCollection", "features": [make_feature(370100, "济南市", "city", 370000, children=1)]},
        ("self", "370100"): {"type": "FeatureCollection", "features": [make_feature(370100, "济南市", "city", 370000, children=1)]},
        ("children", "370100"): {"type": "FeatureCollection", "features": [make_feature(370102, "历下区", "district", 370100, children=0)]},
    })
    resolver = _resolver({
        "370000": {"name": "山东省", "level": "province", "parent": "100000", "backend_adcode": "370000"},
        "370100": {"name": "济南市", "level": "city", "parent": "370000", "backend_adcode": "370100"},
        "370102": {"name": "历下区", "level": "district", "parent": "370100", "backend_adcode": "370102"},
    })
    features, targets = fetch.fetch_features(_cfg(adcodes=["370000", "370100"], depth=1), client, resolver)
    # 去重前 4 个（济南市重复），去重后 3 个
    assert len(features) == 3
    assert sorted(f["adcode"] for f in features) == ["370000", "370100", "370102"]


def test_target_inputs_country_ignores_name_adcode():
    # level=country 时固定抓国家，忽略 name/adcode
    assert fetch._target_inputs(_cfg(level="country", names=["山东省"])) == [("adcode", "100000")]
    assert fetch._target_inputs(_cfg(level="country", adcodes=["370000"])) == [("adcode", "100000")]
    assert fetch._target_inputs(_cfg(level="country")) == [("adcode", "100000")]


def test_fetch_level_country_ignores_config_adcodes():
    # 配置里残留 adcode，但 level=country 时应只抓国家本体，不碰 370000
    client = FakeClient({
        ("self", "100000"): {"type": "FeatureCollection", "features": [make_feature(100000, "中华人民共和国", "country", None)]},
    })
    resolver = _resolver({
        "100000": {"name": "中华人民共和国", "level": "country", "parent": None, "backend_adcode": "100000"},
    })
    features, targets = fetch.fetch_features(
        _cfg(level="country", adcodes=["370000", "130000"]),
        client, resolver,
    )
    assert len(features) == 1
    assert targets[0]["public_adcode"] == "100000"
    # 不应请求 370000 / 130000
    assert ("self", "370000") not in client.calls
    assert ("self", "130000") not in client.calls
