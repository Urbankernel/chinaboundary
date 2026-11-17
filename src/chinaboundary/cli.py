"""命令行入口：chinaboundary run。"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

from . import __version__
from . import config, export, fetch, log
from .client import GeoAtlasClient
from .resolver import Resolver, default_dict_path
from .store import Store


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="chinaboundary", description="中国行政区边界数据获取工具（DataV.GeoAtlas）")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="按配置运行抓取（默认读取 configs/config.yaml）")
    r.add_argument("-c", "--config", default=None, help="配置文件路径（默认 configs/config.yaml）")
    r.add_argument("--level", choices=["country", "province", "city", "district"], help="目标层级（可从名称/adcode 推断），覆盖配置文件")
    g = r.add_mutually_exclusive_group()
    g.add_argument("--name", help="行政区名称，可逗号分隔多个（如 广东省,河北省），覆盖配置文件")
    g.add_argument("--adcode", help="6 位行政区编码，可逗号分隔多个（如 440000,440100），覆盖配置文件")
    r.add_argument("--depth", type=int, default=None, help="下钻层级数：0=本级，1=直接子级，2=孙级（默认 0）")
    r.add_argument("--children-only", action="store_true", default=None, help="仅获取下钻出的子级，不含目标自身边界")
    r.add_argument("--format", help="输出格式，逗号分隔：geojson,gpkg,shp（默认 geojson）")
    r.add_argument("--out", help="输出目录（覆盖配置文件的 outputs.dir）")
    r.add_argument("-v", "--verbose", action="store_true", help="详细日志")
    return p


def _parse_formats(raw: str | None):
    if not raw:
        return None
    return [x.strip() for x in raw.split(",") if x.strip()]


def _build_client(cfg: dict) -> tuple[GeoAtlasClient, Store | None]:
    req = cfg["request"]
    cache_cfg = cfg["cache"]
    store: Store | None = None
    if cache_cfg.get("enabled"):
        cache_dir = cache_cfg.get("dir") or os.path.join(os.path.expanduser("~"), ".cache", "chinaboundary")
        store = Store(cache_dir, enabled=True, ttl_hours=float(cache_cfg.get("ttl_hours", 168)))
    client = GeoAtlasClient(
        timeout=float(req["timeout"]),
        max_retries=int(req["max_retries"]),
        retry_base=float(req["retry_base"]),
        store=store,
    )
    return client, store


def _dict_path(cfg: dict) -> str:
    p = cfg["dictionary"].get("path")
    if p:
        return p
    return default_dict_path()  # 优先 cwd/docs/dict.json，回退项目根


def _base_name(cfg: dict, targets: list[dict]) -> str:
    """输出文件名：单目标用其名称/编码，多目标拼接（过多时省略）。"""
    labels = cfg.get("names") or cfg.get("adcodes") or []
    if not labels:
        return "china"
    if len(labels) == 1:
        return labels[0]
    if len(labels) <= 4:
        return "_".join(labels)
    return f"{labels[0]}_等{len(labels)}个"


def _run_core(cfg: dict) -> int:
    client, _ = _build_client(cfg)
    resolver = Resolver(client, _dict_path(cfg))

    features, targets = fetch.fetch_features(cfg, client, resolver)

    # 源数据（DataV.GeoAtlas）即为 WGS-84，直接原样输出
    crs_label = "WGS-84"

    base_name = _base_name(cfg, targets)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(cfg["outputs"]["dir"], f"{ts}_{base_name}")
    os.makedirs(run_dir, exist_ok=True)

    paths = export.export(features, run_dir, cfg["format"], base_name)

    meta = {
        "targets": targets,
        "crs": crs_label,
        "feature_count": len(features),
        "formats": list(paths.keys()),
        "outputs": paths,
    }
    # 单目标时保留兼容字段，便于旧脚本 / 文档直接读取
    if len(targets) == 1:
        meta["target_adcode"] = targets[0]["public_adcode"]
        meta["backend_adcode"] = targets[0]["backend_adcode"]
        meta["target_level"] = targets[0]["level"]
    with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"完成：{len(features)} 个要素（{len(targets)} 个目标），坐标系 {crs_label}")
    for t in targets:
        print(f"  目标：{t['input']} -> {t['public_adcode']}（后端 {t['backend_adcode']}，{t['level']}，depth={t['depth']}）")
    for fmt, p in paths.items():
        print(f"  {fmt}: {p}")
    print(f"  meta: {os.path.join(run_dir, 'meta.json')}")
    return 0


def _has_cli_target(args) -> bool:
    """是否通过命令行显式指定了任一抓取目标参数。"""
    return any(
        getattr(args, k, None) is not None
        for k in ("level", "name", "adcode", "depth", "children_only", "format", "out")
    )


def _run_run(args) -> int:
    explicit_config = args.config is not None
    has_cli = _has_cli_target(args)

    if explicit_config:
        # 显式 -c：必须存在，读它；CLI 参数仍覆盖其中字段
        cfg_path = args.config
        if not os.path.isfile(cfg_path):
            print(f"错误：未找到配置文件 {cfg_path}", file=sys.stderr)
            return 1
        print(f"使用配置：{cfg_path}")
    elif has_cli:
        # 有 CLI 参数：不读配置文件，用默认配置 + CLI 参数
        args.config = None
        print("使用命令行参数（默认配置）")
    else:
        # 纯 run：读默认 configs/config.yaml
        cfg_path = "configs/config.yaml"
        if not os.path.isfile(cfg_path):
            print(
                f"错误：未找到配置文件 {cfg_path}。请先复制 configs/example.yaml 为 configs/config.yaml 并设置参数：\n"
                f"  cp configs/example.yaml configs/config.yaml\n"
                f"  或通过命令行参数显式指定：chinaboundary run --name 广东省 --depth 1",
                file=sys.stderr,
            )
            return 1
        args.config = cfg_path
        print(f"使用配置：{cfg_path}")

    args.format = _parse_formats(args.format)
    cfg = config.load_config(args)
    if args.out:
        cfg["outputs"]["dir"] = args.out
    return _run_core(cfg)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    log.setup_logging(verbose=getattr(args, "verbose", False))
    try:
        return _run_run(args)
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
