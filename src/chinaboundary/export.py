"""导出 GeoJSON / GeoPackage / Shapefile。"""
from __future__ import annotations

import json
import logging
import os

from .normalize import OUTPUT_FIELDS

logger = logging.getLogger("chinaboundary.export")

DRIVERS = {"geojson": "GeoJSON", "gpkg": "GPKG", "shp": "ESRI Shapefile"}


def _feature_to_geojson(feature: dict) -> dict:
    props = {k: feature[k] for k in OUTPUT_FIELDS if feature.get(k) is not None}
    return {"type": "Feature", "properties": props, "geometry": feature["geometry"]}


def export_geojson(features: list[dict], path: str) -> None:
    fc = {"type": "FeatureCollection", "features": [_feature_to_geojson(f) for f in features]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
    logger.info("已导出 GeoJSON: %s（%d 要素）", path, len(features))


def export_vector(features: list[dict], path: str, fmt: str) -> None:
    """gpkg / shp 导出（需 geopandas）。"""
    try:
        import geopandas as gpd
        from shapely.geometry import shape
    except ImportError as e:  # pragma: no cover - 依赖缺失路径
        raise ImportError(f"{fmt} 导出需要 geopandas，请先 `pip install geopandas`") from e

    rows = []
    geoms = []
    for f in features:
        rows.append({k: f[k] for k in OUTPUT_FIELDS if f.get(k) is not None})
        geoms.append(shape(f["geometry"]))

    # 输出统一为 WGS-84，EPSG:4326
    gdf = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326")
    gdf.to_file(path, driver=DRIVERS[fmt], encoding="utf-8")
    logger.info("已导出 %s: %s（%d 要素）", fmt.upper(), path, len(features))


def export(features: list[dict], run_dir: str, formats: list[str], base_name: str) -> dict[str, str]:
    """按 formats 导出，返回 {格式: 路径}。"""
    paths: dict[str, str] = {}
    for fmt in formats:
        if fmt == "geojson":
            p = os.path.join(run_dir, f"{base_name}.geojson")
            export_geojson(features, p)
        elif fmt in ("gpkg", "shp"):
            p = os.path.join(run_dir, f"{base_name}.{fmt}")
            try:
                export_vector(features, p, fmt)
            except ImportError as e:
                logger.warning("跳过 %s：%s", fmt, e)
                continue
        else:
            raise ValueError(f"未知格式: {fmt}")
        paths[fmt] = p
    return paths
