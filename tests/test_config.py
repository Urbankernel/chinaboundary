"""config 模块与 run 子命令相关测试。"""
from __future__ import annotations

import argparse

from chinaboundary import config


def _args(**kw):
    ns = argparse.Namespace(
        config=None,
        level=None,
        name=None,
        adcode=None,
        children_only=False,
        depth=None,
        format=None,
    )
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def test_defaults():
    cfg = config.load_config(_args())
    assert cfg["level"] is None
    assert cfg["format"] == ["geojson"]
    assert cfg["outputs"]["dir"] == "runs"
    assert cfg["depth"] == 0


def test_load_yaml_merges_target_params(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "level: province\n"
        "name: 广东省\n"
        "depth: 1\n"
        "format: geojson,gpkg\n"
        "outputs:\n"
        "  dir: out_dir\n",
        encoding="utf-8",
    )
    cfg = config.load_config(_args(config=str(p)))
    assert cfg["level"] == "province"
    assert cfg["name"] == "广东省"
    assert cfg["depth"] == 1
    assert cfg["format"] == ["geojson", "gpkg"]
    assert cfg["outputs"]["dir"] == "out_dir"


def test_format_string_normalized():
    cfg = config.load_config(_args())
    cfg["format"] = "gpkg"
    config.validate(cfg)
    assert cfg["format"] == ["gpkg"]


def test_format_comma_separated():
    cfg = config.load_config(_args())
    # 逗号分隔 + 容忍多余空格
    cfg["format"] = "geojson, gpkg ,shp"
    config.validate(cfg)
    assert cfg["format"] == ["geojson", "gpkg", "shp"]


def test_format_list_still_supported():
    cfg = config.load_config(_args())
    cfg["format"] = ["geojson", "shp"]
    config.validate(cfg)
    assert cfg["format"] == ["geojson", "shp"]


def test_names_comma_separated():
    cfg = config.load_config(_args())
    cfg["name"] = "山东省, 河北省 ,河南省"
    config.validate(cfg)
    assert cfg["names"] == ["山东省", "河北省", "河南省"]
    assert cfg["adcodes"] == []


def test_adcodes_comma_separated():
    cfg = config.load_config(_args())
    cfg["adcode"] = "370000,130000,410000"
    config.validate(cfg)
    assert cfg["adcodes"] == ["370000", "130000", "410000"]
    assert cfg["names"] == []


def test_single_value_still_one_element():
    cfg = config.load_config(_args())
    cfg["name"] = "广东省"
    config.validate(cfg)
    assert cfg["names"] == ["广东省"]


def test_name_adcode_mutually_exclusive_multi():
    cfg = config.load_config(_args())
    cfg["name"] = "山东省"
    cfg["adcode"] = "370000"
    import pytest

    with pytest.raises(ValueError, match="不能同时指定"):
        config.validate(cfg)


def test_depth_explicit():
    cfg = config.load_config(_args(depth=2))
    assert cfg["depth"] == 2


def test_depth_out_of_range():
    import pytest

    cfg = config.load_config(_args())
    cfg["depth"] = 9
    with pytest.raises(ValueError, match="非法 depth"):
        config.validate(cfg)


def test_children_only_auto_depth():
    cfg = config.load_config(_args(children_only=True))
    assert cfg["depth"] == 1  # children_only 且 depth=0 -> 自动 depth=1


def test_cli_adcode_overrides_config_name(tmp_path):
    # 配置文件里是 name，命令行显式传 --adcode 时应覆盖并清空 name
    p = tmp_path / "config.yaml"
    p.write_text("name: 山东省\n", encoding="utf-8")
    cfg = config.load_config(_args(config=str(p), adcode="440000"))
    assert cfg["adcodes"] == ["440000"]
    assert cfg["names"] == []


def test_cli_name_overrides_config_adcode(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("adcode: 440000\n", encoding="utf-8")
    cfg = config.load_config(_args(config=str(p), name="广东省"))
    assert cfg["names"] == ["广东省"]
    assert cfg["adcodes"] == []


def test_run_missing_config(tmp_path, monkeypatch, capsys):
    from chinaboundary import cli

    monkeypatch.chdir(tmp_path)
    rc = cli.main(["run"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "configs/config.yaml" in err


def test_cli_params_skip_config_file(tmp_path, monkeypatch, capsys):
    """有 CLI 参数时不读配置文件，用 DEFAULTS 打底。"""
    from chinaboundary import cli

    # 造一个默认 configs/config.yaml，里面设置 adcode + children_only
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "config.yaml").write_text(
        "adcode: 370000,130000\nchildren_only: true\ndepth: 2\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    captured = {}

    def fake_core(cfg):
        captured.update(cfg)
        return 0

    monkeypatch.setattr(cli, "_run_core", fake_core)
    rc = cli.main(["run", "--level", "country"])
    assert rc == 0
    # 不读配置文件：adcode 应为空（被 DEFAULTS 覆盖），children_only 为 False
    assert captured["adcodes"] == []
    assert captured["names"] == []
    assert captured["children_only"] is False
    assert captured["level"] == "country"


def test_cli_country_target_is_national(tmp_path, monkeypatch, capsys):
    """run --level country 目标应为国家本体 100000。"""
    from chinaboundary import cli

    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "config.yaml").write_text(
        "adcode: 370000,130000\nchildren_only: true\ndepth: 2\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    captured = {}

    def fake_core(cfg):
        captured.update(cfg)
        return 0

    monkeypatch.setattr(cli, "_run_core", fake_core)
    rc = cli.main(["run", "--level", "country", "--adcode", "440000"])
    assert rc == 0
    # adcode 被 CLI 覆盖，level=country 下 fetch 目标仍应为 100000（在 fetch 层短路）
    assert captured["level"] == "country"


def test_explicit_config_still_reads_file(tmp_path, monkeypatch, capsys):
    """显式 -c 时仍读该配置文件，CLI 参数覆盖其中字段。"""
    from chinaboundary import cli

    p = tmp_path / "other.yaml"
    p.write_text("name: 广东省\nchildren_only: true\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    captured = {}

    def fake_core(cfg):
        captured.update(cfg)
        return 0

    monkeypatch.setattr(cli, "_run_core", fake_core)
    rc = cli.main(["run", "-c", str(p), "--depth", "1"])
    assert rc == 0
    assert captured["names"] == ["广东省"]
    assert captured["depth"] == 1
    assert captured["children_only"] is True  # 来自配置文件


def test_explicit_config_missing(tmp_path, monkeypatch, capsys):
    from chinaboundary import cli

    monkeypatch.chdir(tmp_path)
    rc = cli.main(["run", "-c", "nope.yaml"])
    assert rc == 1
    assert "nope.yaml" in capsys.readouterr().err
