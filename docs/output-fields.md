# 输出字段说明

所有输出格式（GeoJSON / GeoPackage / Shapefile）使用同一套属性字段，字段名均 ≤ 10 字符，保证 Shapefile 字段名安全。

| 字段 | 类型 | 说明 |
|---|---|---|
| `adcode` | string | 6 位行政区编码（如 `440100`；国家为 `100000`） |
| `name` | string | 行政区全名（如「广州市」「内蒙古自治区」） |
| `level` | string | 层级：`country` / `province` / `city` / `district` |
| `parent` | string | 上级 adcode（国家层级为 null） |
| `children` | int | 直接子级数量（`childrenNum`） |
| `cen_lng` | float | 标注中心点经度（`center[0]`，WGS-84） |
| `cen_lat` | float | 标注中心点纬度（`center[1]`，WGS-84） |

几何（`geometry`）：Polygon 或 MultiPolygon（含岛屿、飞地时），已做无效几何修复（`buffer(0)`）。

## 与原始 GeoAtlas 字段的对应关系

| 原始字段 | 输出字段 | 说明 |
|---|---|---|
| `properties.adcode` | `adcode` | 转字符串，避免前导 0 丢失 |
| `properties.name` | `name` | — |
| `properties.level` | `level` | — |
| `properties.parent.adcode` | `parent` | 拍平 |
| `properties.childrenNum` | `children` | — |
| `properties.center[0/1]` | `cen_lng` / `cen_lat` | 拆分为两列 |
| `properties.centroid` | （未导出） | 几何质心，如需可从 `acroutes` 同源字段补充 |
| `properties.acroutes` | （未导出） | 祖先链路，层次关系用 `parent` 字段表达 |

## 坐标系说明

源数据即 WGS-84，`geometry`、`cen_lng`、`cen_lat` 均原样输出，不做坐标转换；shp/gpkg 文件内投影元数据统一写 `EPSG:4326`。

## meta.json

每次运行在输出目录生成，字段：

```json
{
  "targets": [
    {"input": "320613", "public_adcode": "320613", "backend_adcode": "320602", "level": "district", "depth": 1}
  ],
  "target_adcode": "320613",
  "backend_adcode": "320602",
  "target_level": "district",
  "crs": "WGS-84",
  "feature_count": 1,
  "formats": ["geojson"],
  "outputs": {"geojson": "runs/.../320613.geojson"}
}
```

- `targets`：本次抓取的目标列表，每个元素含：
  - `input`：用户输入的原始值（名称或 adcode）；
  - `public_adcode`：公开主码（高德官方最新编码，即输入/名称解析出的编码）；
  - `backend_adcode`：后端抓取码（DataV.GeoAtlas 后台实际使用的旧码）。两者不同说明发生了行政区划重编号；相同时无重编号；
  - `level`：该目标的层级；
  - `depth`：该目标的下钻层数（0=仅本级，1=含直接子级，2=含孙级……）。
- 单目标时额外保留 `target_adcode` / `backend_adcode` / `target_level` 三个兼容字段（等于 `targets[0]` 对应值）；多目标时仅存在于 `targets`。
- 输出的 `adcode` / `parent` / `name` 字段均已回填为公开主码，与各目标的 `public_adcode` 语义一致；下钻得到的子级/孙级通过 `parent` 字段追溯归属关系。
