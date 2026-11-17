"""配置加载与校验：YAML + CLI 覆盖。"""
from __future__ import annotations

import copy
import logging

import yaml

logger = logging.getLogger("chinaboundary.config")

LEVELS = {"country", "province", "city", "district"}
FORMATS = {"geojson", "gpkg", "shp"}
MAX_DEPTH = 3  # 中国区划最多 4 层：country -> province -> city -> district

DEFAULTS = {
    "level": None,
    "name": None,
    "adcode": None,
    "children_only": False,
    "depth": None,
    "format": ["geojson"],
    "outputs": {"dir": "runs"},
    "request": {"timeout": 15.0, "max_retries": 5, "retry_base": 1.0},
    "cache": {"enabled": True, "dir": None, "ttl_hours": 168},
    "dictionary": {"path": None},
}


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def _split_csv(value) -> list[str]:
    """把单个值拆成去空格、去空的列表；支持逗号分隔的字符串或已是列表的输入。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value).split(",") if x.strip()]


def load_config(args) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    if getattr(args, "config", None):
        with open(args.config, encoding="utf-8") as f:
            yaml_cfg = yaml.safe_load(f) or {}
        _deep_merge(cfg, yaml_cfg)

    # CLI 覆盖
    for key in ("level", "name", "adcode"):
        val = getattr(args, key, None)
        if val is not None:
            cfg[key] = val
    # name 与 adcode 互斥：CLI 显式指定其一，需清空配置文件中残留的另一个
    if getattr(args, "name", None):
        cfg["adcode"] = None
    if getattr(args, "adcode", None):
        cfg["name"] = None
    if getattr(args, "children_only", False):
        cfg["children_only"] = True
    if getattr(args, "depth", None) is not None:
        cfg["depth"] = args.depth
    if getattr(args, "format", None):
        cfg["format"] = args.format

    validate(cfg)
    return cfg


def validate(cfg: dict) -> None:
    if cfg["level"] is not None and cfg["level"] not in LEVELS:
        raise ValueError(f"非法 level：{cfg['level']}，可选 {sorted(LEVELS)}")

    fmt = cfg["format"]
    if isinstance(fmt, str):
        # 配置文件与 CLI 均支持逗号分隔：format: geojson,gpkg
        fmt_list = [x.strip() for x in fmt.split(",") if x.strip()]
    else:
        fmt_list = [str(x).strip() for x in fmt]
    bad = [f for f in fmt_list if f not in FORMATS]
    if bad:
        raise ValueError(f"非法 format：{bad}，可选 {sorted(FORMATS)}")
    cfg["format"] = fmt_list

    # name / adcode 支持逗号分隔的多值（如 name: 山东省,河北省 或 adcode: 370000,130000）
    cfg["names"] = _split_csv(cfg.get("name"))
    cfg["adcodes"] = _split_csv(cfg.get("adcode"))
    if cfg["names"] and cfg["adcodes"]:
        raise ValueError("name 与 adcode 不能同时指定")

    # level=country 时无需 name/adcode：固定抓国家，name/adcode 被忽略
    if cfg["level"] == "country" and (cfg["names"] or cfg["adcodes"]):
        logger.warning("level=country 时无需 name/adcode，已忽略 %s，直接抓取中国国界", cfg["names"] or cfg["adcodes"])

    # depth 归一化：显式 depth 优先，未指定则默认 0（仅本级）
    depth = cfg.get("depth")
    if depth is None:
        depth = 0
    else:
        depth = int(depth)
    if depth < 0 or depth > MAX_DEPTH:
        raise ValueError(f"非法 depth：{depth}，范围 0~{MAX_DEPTH}")
    if cfg["children_only"] and depth == 0:
        logger.warning("children_only 需配合下钻，已自动将 depth 设为 1")
        depth = 1
    cfg["depth"] = depth
