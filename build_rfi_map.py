#!/usr/bin/env python3
"""Build a WordPress-ready draft map from QGIS and satellite/NDVI folders.

The generated plugin exposes [rfi_interactive_map] in WordPress. GeoJSON files
are browser-ready and can be copied into the plugin. GeoTIFFs are catalogued in
the map's data panel; publish them as XYZ tiles (recommended) or pair a PNG/JPG
preview with a .bounds.json file to display a raster overlay on the map.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VECTOR_EXTENSIONS = {".geojson", ".json"}
RASTER_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_BASEMAPS: tuple[dict[str, Any], ...] = (
    {
        "id": "satellite-imagery",
        "name": "Google satellite imagery",
        "type": "xyz",
        "url": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        "visible": True,
        "max_zoom": 19,
        "attribution": "Satellite imagery © Google",
    },
)

# These parcel layers are referenced by the QGIS project.  They are kept
# separate from the general QGIS imports so they can be presented together in
# the web map without obscuring the other reference layers.
LANDUSE_DISPLAY_NAMES = {
    "bamboo": "Bamboo",
    "besr-bamboo-enriched-secondary-forest": "BESR — bamboo-enriched secondary forest",
    "bsf-bamboo-enrichment-secondary-forest": "BSF — bamboo enrichment secondary forest",
    "syntropic3-export": "Syntropic 3 export",
    "syntropic3": "Syntropic 3 parcel",
    "cana-mansa-forest": "Cana Mansa forest",
    "balsa": "Balsa",
    "syntropic-2": "Syntropic 2",
    "group-6": "Group 6",
    "pasture-terrazas": "Pasture terrazas",
    "group-5": "Group 5",
    "secondary-regrowth": "Secondary regrowth",
    "semango-pasture": "Semango pasture",
    "group-c": "Semango pasture",
    "group-b": "Group B",
    "group-a": "Group A",
    "big-teak": "Big Teak",
    "syntropic-moral-fino-border": "Syntropic Moral Fino border",
    "syntropic-loma-nueva-border": "Syntropic Loma Nueva border",
    "syntropic-massbu": "Syntropic MassBu",
    "orange-cacao-south-border": "Orange cacao south border",
    "baby-teak": "Baby teak",
    "pasture": "Pasture",
    "group-4": "Pasture",
    "syntropic-near-biocorridor-border": "Syntropic near biocorridor border",
    "syntropic-road-moral-fino-border": "Syntropic Road Moral Fino border",
    "loma-aguacate-curcuma": "Loma aguacate + curcuma",
    "syntropic-1-border": "Syntropic 1 border",
    "syntropic1": "Syntropic 1",
    "syntropic-taller-border": "Syntropic Taller border",
    "cacao-incomplete-balsa-mc": "Cacao incomplete balsa-mc",
}

LANDUSE_POPUP_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Name", ("Name", "name")),
    ("Area", ("Area", "area")),
    ("Installation year", ("Installation year", "Install", "install")),
    ("System design & implementation", ("System design & implementation", "design", "Design")),
    ("Plant survival & failure", ("Plant survival & failure", "survival", "Survival")),
    ("Major learnings", ("Major learnings", "learnings", "Learnings")),
    ("Description", ("Description", "description")),
)


def landuse_metadata(source: Path) -> dict[str, Any]:
    """Return the presentation settings shared by the land-use parcel layers."""
    layer_id = safe_id(source.stem)
    if layer_id not in LANDUSE_DISPLAY_NAMES:
        return {}
    return {
        "name": LANDUSE_DISPLAY_NAMES[layer_id],
        "group": "Land use parcels",
        "visible": False,
        "style": {"kind": "landuse"},
    }


WATERSHED_DISPLAY_NAMES = {
    "rivers-reproj": "Rivers",
    "streams-adj": "Streams",
}


def watershed_metadata(source: Path) -> dict[str, Any]:
    """Place the map's reference watercourses in a dedicated layer group."""
    layer_id = safe_id(source.stem)
    if layer_id not in WATERSHED_DISPLAY_NAMES:
        return {}
    return {"name": WATERSHED_DISPLAY_NAMES[layer_id], "group": "DEM and watershed"}


def safe_id(value: str) -> str:
    """Make a stable JavaScript/HTML-safe identifier."""
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "layer"


def read_bounds(raster: Path) -> list[list[float]] | None:
    """Read [[south, west], [north, east]] from a sidecar bounds JSON file."""
    candidates = [
        raster.with_name(raster.name + ".bounds.json"),
        raster.with_suffix(".bounds.json"),
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if (isinstance(data, list) and len(data) == 2 and
                    all(isinstance(row, list) and len(row) == 2 for row in data)):
                return data
        except (OSError, ValueError):
            pass
    return None


def copy_into(source: Path, root: Path, destination: Path) -> str:
    relative = source.relative_to(root)
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return relative.as_posix()


def read_dbf(source: Path) -> list[dict[str, Any]]:
    """Read the attribute table paired with a shapefile (standard library only)."""
    dbf = source.with_suffix(".dbf")
    if not dbf.is_file():
        return []
    raw = dbf.read_bytes()
    if len(raw) < 32:
        return []
    records = struct.unpack_from("<I", raw, 4)[0]
    header_length, record_length = struct.unpack_from("<HH", raw, 8)
    fields: list[tuple[str, str, int]] = []
    offset = 32
    while offset + 32 <= len(raw) and raw[offset] != 0x0D:
        name = raw[offset:offset + 11].split(b"\0", 1)[0].decode("latin-1").strip()
        fields.append((name, chr(raw[offset + 11]), raw[offset + 16]))
        offset += 32
    encoding = "utf-8"
    cpg = source.with_suffix(".cpg")
    if cpg.is_file():
        try:
            encoding = cpg.read_text(encoding="ascii").strip() or encoding
        except OSError:
            pass
    output: list[dict[str, Any]] = []
    for index in range(records):
        row = header_length + index * record_length
        if row + record_length > len(raw) or raw[row:row + 1] == b"*":
            continue
        props: dict[str, Any] = {}
        cursor = row + 1
        for name, kind, width in fields:
            value = raw[cursor:cursor + width].decode(encoding, errors="replace").strip()
            cursor += width
            if kind in {"N", "F"} and value:
                try:
                    value = float(value) if "." in value else int(value)
                except ValueError:
                    pass
            elif kind == "L":
                value = value.lower() in {"y", "t", "1"}
            props[name] = value
        output.append(props)
    return output


def shapefile_to_geojson(source: Path) -> dict[str, Any]:
    """Convert WGS 84 point/line/polygon shapefiles to GeoJSON without GDAL."""
    raw = source.read_bytes()
    if len(raw) < 100:
        raise ValueError("shapefile is too small")
    attributes = read_dbf(source)
    features: list[dict[str, Any]] = []
    offset = 100
    feature_index = 0
    while offset + 8 <= len(raw):
        content_words = struct.unpack_from(">I", raw, offset + 4)[0]
        end = offset + 8 + content_words * 2
        content = raw[offset + 8:end]
        offset = end
        if len(content) < 4:
            continue
        shape_type = struct.unpack_from("<I", content, 0)[0]
        geometry: dict[str, Any] | None = None
        if shape_type in {1, 11, 21} and len(content) >= 20:  # Point (+ Z/M variants)
            geometry = {"type": "Point", "coordinates": list(struct.unpack_from("<2d", content, 4))}
        elif shape_type in {3, 5, 13, 15, 23, 25} and len(content) >= 44:  # Line/polygon (+ Z/M)
            parts_count, points_count = struct.unpack_from("<2I", content, 36)
            points_offset = 44 + parts_count * 4
            if len(content) < points_offset + points_count * 16:
                continue
            starts = list(struct.unpack_from(f"<{parts_count}I", content, 44))
            points = [list(struct.unpack_from("<2d", content, points_offset + i * 16)) for i in range(points_count)]
            paths = [points[start:(starts[n + 1] if n + 1 < len(starts) else points_count)] for n, start in enumerate(starts)]
            if shape_type in {3, 13, 23}:
                geometry = {"type": "LineString", "coordinates": paths[0]} if len(paths) == 1 else {"type": "MultiLineString", "coordinates": paths}
            else:
                geometry = {"type": "Polygon", "coordinates": paths}
        elif shape_type in {8, 18, 28} and len(content) >= 40:  # MultiPoint (+ Z/M)
            points_count = struct.unpack_from("<I", content, 36)[0]
            geometry = {"type": "MultiPoint", "coordinates": [list(struct.unpack_from("<2d", content, 40 + i * 16)) for i in range(points_count)]}
        if geometry:
            props = attributes[feature_index] if feature_index < len(attributes) else {}
            features.append({"type": "Feature", "properties": props, "geometry": geometry})
            feature_index += 1
    return {"type": "FeatureCollection", "features": features}


def gpx_to_geojson(source: Path) -> dict[str, Any]:
    """Convert waypoints, routes, and tracks from GPX into GeoJSON."""
    root = ET.parse(source).getroot()
    features: list[dict[str, Any]] = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "wpt":
            features.append({"type": "Feature", "properties": {"name": element.findtext("{*}name") or source.stem}, "geometry": {"type": "Point", "coordinates": [float(element.attrib["lon"]), float(element.attrib["lat"])]}})
        elif tag in {"rte", "trk"}:
            point_tag = "rtept" if tag == "rte" else "trkpt"
            points = [[float(point.attrib["lon"]), float(point.attrib["lat"])] for point in element.iter() if point.tag.rsplit("}", 1)[-1] == point_tag]
            if points:
                features.append({"type": "Feature", "properties": {"name": element.findtext("{*}name") or source.stem}, "geometry": {"type": "LineString", "coordinates": points}})
    return {"type": "FeatureCollection", "features": features}


def elevation_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Style the QSWAT elevation-band polygons like a coloured contour map."""
    values = [feature.get("properties", {}).get("ELEV_MIN") for feature in payload.get("features", [])]
    values = [float(value) for value in values if isinstance(value, (int, float))]
    maxima = [feature.get("properties", {}).get("ELEV_MAX") for feature in payload.get("features", [])]
    maxima = [float(value) for value in maxima if isinstance(value, (int, float))]
    if not values or not maxima:
        return {}
    low, high = min(values), max(maxima)
    colours = ["#c92727", "#ef7044", "#f3bf73", "#d7df9d", "#9ac59d", "#5ea8a5", "#218dbc"]
    stops = [{"value": f"{low + (high - low) * index / (len(colours) - 1):.0f} m", "color": colour} for index, colour in enumerate(colours)]
    return {
        "style": {"kind": "elevation-bands", "field": "ELEV_MIN", "min": low, "max": high, "colours": colours},
        "legend": {"title": "Elevation (m)", "stops": stops, "low_label": "Lower elevation", "high_label": "Higher elevation"},
    }


def qgis_layers(folder: Path | None, data_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    layers: list[dict[str, Any]] = []
    notices: list[str] = []
    if not folder:
        return layers, notices
    for source in sorted(p for p in folder.rglob("*") if p.is_file()):
        suffix = source.suffix.lower()
        if safe_id(source.stem) in {"laf-dem-formap", "laf-t1-4-v1"}:
            notices.append(f"{source.name} is retained as source data and excluded from the web map.")
            continue
        if suffix in VECTOR_EXTENSIONS:
            try:
                payload = json.loads(source.read_text(encoding="utf-8-sig"))
                if not isinstance(payload, dict) or payload.get("type") not in {"FeatureCollection", "Feature"}:
                    notices.append(f"Skipped {source.name}: not GeoJSON feature data.")
                    continue
            except (OSError, ValueError):
                notices.append(f"Skipped {source.name}: cannot read valid GeoJSON.")
                continue
            relative = source.relative_to(folder).as_posix()
            relative = copy_into(source, folder, data_dir / "qgis")
            url = "qgis/" + relative
            layer_id = safe_id(source.stem)
            display_names = {"qswat2": "DEM contours", "track": "Syntropic 3"}
            layer = {"id": layer_id, "name": display_names.get(layer_id, source.stem.replace("_", " ").title()),
                     "type": "geojson", "url": url, "source_reference": url, "visible": True,
                     "zoom_on_load": layer_id == "laf-border-web"}
            layer.update(landuse_metadata(source))
            if layer_id == "track":
                layer["group"] = "Land use parcels"
            layer.update(watershed_metadata(source))
            if layer_id == "laf-border-web":
                layer.update({"name": "LAF border", "primary_boundary": True, "style": {"kind": "boundary"}})
            if layer_id == "qswat2":
                layer["group"] = "DEM and watershed"
                layer.update(elevation_metadata(payload))
            layers.append(layer)
        elif suffix in {".shp", ".gpx"}:
            relative = source.relative_to(folder).as_posix()
            if safe_id(source.stem) == "laf-border":
                notices.append(f"{source.name} is retained as source data; LAF_border_web.geojson is the standalone web boundary.")
                continue
            if suffix == ".shp" and safe_id(source.stem) == "for-qswat":
                notices.append("FOR_QSWAT.shp is retained as source data; use DEM contours for the visible elevation layer.")
                continue
            try:
                payload = shapefile_to_geojson(source) if suffix == ".shp" else gpx_to_geojson(source)
            except (OSError, ValueError, ET.ParseError, struct.error) as error:
                notices.append(f"Skipped {source.name}: conversion failed ({error}).")
                continue
            target_relative = str(Path(relative).with_suffix(".geojson")).replace("\\", "/")
            target = data_dir / "qgis" / target_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload), encoding="utf-8")
            layer = {"id": safe_id(target_relative), "name": source.stem.replace("_", " ").title(),
                           "type": "geojson", "url": "qgis/" + target_relative,
                           "source_reference": "qgis/" + target_relative, "visible": True,
                           "zoom_on_load": safe_id(source.stem) == "laf-border-web"}
            layer.update(landuse_metadata(source))
            layer.update(watershed_metadata(source))
            layers.append(layer)
        elif suffix in {".gpkg", ".sqlite", ".gdb"}:
            notices.append(f"{source.name} is a database layer. Export the wanted layer to GeoJSON in QGIS to display it in the browser.")
        elif suffix in {".qgz", ".qgs"}:
            notices.append(f"Found QGIS project {source.name}; its project file is retained as a reference, not a web layer.")
    return layers, notices


def landuse_layers(folder: Path | None, data_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Convert the parcel shapefiles referenced by the QGIS project for the web map."""
    layers: list[dict[str, Any]] = []
    notices: list[str] = []
    if not folder:
        return layers, notices
    for source in sorted(folder.glob("*.shp")):
        metadata = landuse_metadata(source)
        if not metadata:
            continue
        try:
            payload = shapefile_to_geojson(source)
        except (OSError, ValueError, struct.error) as error:
            notices.append(f"Skipped land-use layer {source.name}: conversion failed ({error}).")
            continue
        target_relative = Path("landuse") / source.with_suffix(".geojson").name
        target = data_dir / "qgis" / target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")
        layers.append({
            "id": "landuse-" + safe_id(source.stem),
            "name": metadata["name"],
            "type": "geojson",
            "url": "qgis/" + target_relative.as_posix(),
            "source_reference": "qgis/" + target_relative.as_posix(),
            "visible": False,
            "zoom_on_load": False,
            "group": metadata["group"],
            "style": metadata["style"],
        })
    return layers, notices


def packaged_landuse_source_layers(data_dir: Path) -> list[dict[str, Any]]:
    """Rebuild parcel source references from the GeoJSON files already packaged for the map."""
    source_root = data_dir / "qgis"
    layers: list[dict[str, Any]] = []
    if not source_root.is_dir():
        return layers
    for source in sorted(source_root.rglob("*.geojson")):
        if source.name == "landuse_parcels.geojson":
            continue
        metadata = landuse_metadata(source)
        layer_id = safe_id(source.stem)
        if layer_id == "track":
            metadata = {"name": "Syntropic 3", "group": "Land use parcels", "style": {"kind": "landuse"}}
        if not metadata:
            continue
        relative = source.relative_to(data_dir).as_posix()
        layers.append({
            "id": "landuse-source-" + safe_id(relative),
            "name": metadata["name"],
            "type": "geojson",
            "url": relative,
            "source_reference": relative,
            "visible": False,
            "zoom_on_load": False,
            "group": "Land use parcels",
            "style": {"kind": "landuse"},
        })
    return layers


def standardized_landuse_properties(source_properties: dict[str, Any], parcel_name: str, source_id: str) -> dict[str, Any]:
    """Ensure the map exposes each land-use field, including empty values."""
    properties: dict[str, Any] = {"Land-use parcel": parcel_name}
    for field_name, alternatives in LANDUSE_POPUP_FIELDS:
        properties[field_name] = parcel_name if field_name == "Name" else next((source_properties[name] for name in alternatives if name in source_properties), None)
    seen = {key.casefold() for key in properties}
    for key, value in source_properties.items():
        if key.casefold() not in seen:
            properties[key] = value
            seen.add(key.casefold())
    properties["_rfi_source_id"] = source_id
    return properties


def refresh_consolidated_landuse_layer(layers: list[dict[str, Any]], combined_layer: dict[str, Any], data_dir: Path) -> list[dict[str, Any]]:
    """Refresh one already-consolidated layer without losing its source identities."""
    source = data_dir / str(combined_layer.get("url") or "")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return layers
    features = payload.get("features", []) if payload.get("type") == "FeatureCollection" else []
    source_layers: dict[str, dict[str, str]] = {}
    refreshed_features: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, dict) or not feature.get("geometry"):
            continue
        source_properties = dict(feature.get("properties") or {})
        source_id = str(source_properties.get("_rfi_source_id") or "landuse-source")
        parcel_name = str(source_properties.get("Land-use parcel") or "Land-use parcel")
        source_layers.setdefault(source_id, {
            "id": source_id,
            "name": parcel_name,
            "source_reference": "Retained as a separate browser-ready source GeoJSON",
        })
        refreshed_features.append({
            "type": "Feature",
            "properties": standardized_landuse_properties(source_properties, parcel_name, source_id),
            "geometry": feature["geometry"],
        })
    if not refreshed_features:
        return layers
    source.write_text(json.dumps({"type": "FeatureCollection", "features": refreshed_features}), encoding="utf-8")
    refreshed = dict(combined_layer)
    refreshed["source_reference"] = f"{len(source_layers)} separate parcel sources"
    refreshed["source_layers"] = list(source_layers.values())
    return [layer for layer in layers if layer.get("group") != "Land use parcels"] + [refreshed]


def consolidate_landuse_layers(layers: list[dict[str, Any]], data_dir: Path) -> list[dict[str, Any]]:
    """Package separately sourced land-use features as one interactive map layer."""
    parcel_layers = [layer for layer in layers if layer.get("group") == "Land use parcels"]
    if not parcel_layers:
        return layers
    if len(parcel_layers) == 1 and parcel_layers[0].get("id") == "landuse-parcels":
        return refresh_consolidated_landuse_layer(layers, parcel_layers[0], data_dir)

    combined_features: list[dict[str, Any]] = []
    source_layers: list[dict[str, str]] = []
    for layer in parcel_layers:
        url = str(layer.get("url") or "")
        if not url or "://" in url:
            return layers  # Keep individual controls when local source data is unavailable.
        source = (data_dir / url).resolve()
        try:
            source.relative_to(data_dir.resolve())
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return layers
        if payload.get("type") == "FeatureCollection":
            features = payload.get("features", [])
        elif payload.get("type") == "Feature":
            features = [payload]
        else:
            return layers
        for feature in features:
            if not isinstance(feature, dict) or not feature.get("geometry"):
                continue
            combined_features.append({
                "type": "Feature",
                "properties": standardized_landuse_properties(dict(feature.get("properties") or {}), str(layer["name"]), str(layer["id"])),
                "geometry": feature["geometry"],
            })
        source_layers.append({
            "id": str(layer["id"]),
            "name": str(layer["name"]),
            "source_reference": str(layer.get("source_reference") or ""),
        })

    if not combined_features:
        return layers
    target_relative = Path("qgis") / "landuse_parcels.geojson"
    target = data_dir / target_relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"type": "FeatureCollection", "features": combined_features}), encoding="utf-8")
    combined_layer = {
        "id": "landuse-parcels",
        "name": "Land use parcels",
        "type": "geojson",
        "url": target_relative.as_posix(),
        "source_reference": f"{len(source_layers)} separate parcel sources",
        "source_layers": source_layers,
        "visible": False,
        "zoom_on_load": False,
        "group": "Land use parcels",
        "style": {"kind": "landuse-parcels"},
    }
    return [layer for layer in layers if layer.get("group") != "Land use parcels"] + [combined_layer]


def satellite_layers(folder: Path | None, data_dir: Path) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    if not folder:
        return assets
    for source in sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in RASTER_EXTENSIONS):
        relative = source.relative_to(folder).as_posix()
        suffix = source.suffix.lower()
        bounds = read_bounds(source)
        displayable = suffix in {".png", ".jpg", ".jpeg", ".webp"} and bounds is not None
        if not displayable:
            continue
        relative = copy_into(source, folder, data_dir / "satellite")
        url = "satellite/" + relative
        for bounds_source in (source.with_name(source.name + ".bounds.json"), source.with_suffix(".bounds.json")):
            if bounds_source.is_file():
                copy_into(bounds_source, folder, data_dir / "satellite")
        assets.append({
            "id": safe_id(source.stem), "name": source.stem.replace("_", " ").title(),
            "kind": "ndvi" if "ndvi" in source.name.lower() else "satellite-raster",
            "format": suffix.lstrip("."), "url": url, "source_reference": url,
            "bounds": bounds, "displayable_overlay": True,
        })
    return assets


PLUGIN_PHP = r'''<?php
/**
 * Plugin Name: RFI Interactive Map
 * Description: Draft interactive map built from QGIS and satellite/NDVI data.
 * Version: 0.1.0
 */
if (!defined('ABSPATH')) { exit; }
function rfi_interactive_map_assets() {
  $base = plugin_dir_url(__FILE__);
  wp_enqueue_style('leaflet', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', array(), '1.9.4');
  wp_enqueue_style('rfi-map', $base . 'assets/rfi-map.css', array('leaflet'), '0.1.0');
  wp_enqueue_script('leaflet', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', array(), '1.9.4', true);
  wp_enqueue_script('leaflet-rotate', $base . 'assets/leaflet-rotate.js', array('leaflet'), '0.2.8', true);
  wp_enqueue_script('rfi-map', $base . 'assets/rfi-map.js', array('leaflet', 'leaflet-rotate'), '0.1.0', true);
  wp_localize_script('rfi-map', 'RFIMapData', array('configUrl' => $base . 'data/map-config.json'));
}
function rfi_interactive_map_shortcode($atts) {
  rfi_interactive_map_assets();
  $atts = shortcode_atts(array('height' => '650px'), $atts, 'rfi_interactive_map');
  return '<div class="rfi-map" style="height:' . esc_attr($atts['height']) . '"><div class="rfi-map__canvas"></div><aside class="rfi-map__panel"><h3>Map layers</h3><div class="rfi-map__layers"></div><details class="rfi-data-references"><summary>Data references</summary><div class="rfi-map__assets"></div></details></aside></div>';
}
add_shortcode('rfi_interactive_map', 'rfi_interactive_map_shortcode');
'''

MAP_JS = r'''(() => {
  const configUrl = window.RFIMapData && window.RFIMapData.configUrl;
  const resolveUrl = (url) => url && new URL(url, new URL(configUrl, window.location.href)).href;
  const colorFor = (id) => `hsl(${[...id].reduce((a, c) => a + c.charCodeAt(0), 0) % 360} 62% 39%)`;
  const hashFor = (value) => [...String(value)].reduce((total, character) => (total * 31 + character.charCodeAt(0)) >>> 0, 17);
  const landuseSymbol = (source) => {
    const properties = source?.properties || source || {};
    const name = String(properties['Land-use parcel'] || source?.name || 'Land-use parcel');
    const id = String(properties._rfi_source_id || source?.id || name);
    if (/^syntropic\b/i.test(name)) return {color: '#5d9e5b', pattern: 'diagonal', key: 'syntropic'};
    const colours = ['#cc6b5a', '#b79a45', '#4f9ba9', '#9a6ba4', '#718c52', '#c9834f', '#6d83b6', '#9a7060'];
    const patterns = ['solid', 'diagonal', 'crosshatch', 'dots'];
    const hash = hashFor(id);
    return {color: colours[hash % colours.length], pattern: patterns[Math.floor(hash / colours.length) % patterns.length], key: id};
  };
  const landusePreviewFill = (symbol) => {
    const hatch = 'rgba(20, 38, 26, .72)';
    if (symbol.pattern === 'diagonal') return `repeating-linear-gradient(135deg, transparent 0 6px, ${hatch} 6px 7px), ${symbol.color}`;
    if (symbol.pattern === 'crosshatch') return `repeating-linear-gradient(135deg, transparent 0 6px, ${hatch} 6px 7px), repeating-linear-gradient(45deg, transparent 0 6px, ${hatch} 6px 7px), ${symbol.color}`;
    if (symbol.pattern === 'dots') return `radial-gradient(${hatch} 1px, transparent 1.2px), ${symbol.color}`;
    return symbol.color;
  };
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const interpolateColour = (colours, position) => {
    const index = Math.min(colours.length - 2, Math.max(0, Math.floor(position * (colours.length - 1))));
    const fraction = position * (colours.length - 1) - index;
    const parse = colour => [1, 3, 5].map(offset => parseInt(colour.slice(offset, offset + 2), 16));
    const start = parse(colours[index]), end = parse(colours[index + 1]);
    return `#${start.map((value, channel) => Math.round(value + (end[channel] - value) * fraction).toString(16).padStart(2, '0')).join('')}`;
  };
  const vectorStyle = (layer, feature, patternFill) => {
    if (layer.style?.kind === 'flow-channels') return {color: feature.properties?.mapped_river_nearby ? '#1261a0' : '#e88936', weight: 2.2, opacity: .9};
    if (layer.style?.kind === 'river-network-portions') {
      const basis = feature.properties?.river_network_match || '';
      return {color: basis.startsWith('Both') ? '#164d80' : basis.startsWith('Mapped') ? '#1475a3' : '#55a3b9', weight: 5, opacity: .95, lineCap: 'round'};
    }
    if (layer.style?.kind === 'boundary') return {color: '#bd332b', weight: 2.4, opacity: 1, fill: false};
    if (layer.style?.kind === 'landuse') { const color = colorFor(layer.id); return {color, weight: 1.5, opacity: .95, fillColor: color, fillOpacity: .42}; }
    if (layer.style?.kind === 'landuse-parcels') { const symbol = landuseSymbol(feature); return {color: symbol.color, weight: 1.5, opacity: .95, fillColor: patternFill ? patternFill(symbol) : symbol.color, fillOpacity: .55}; }
    if (layer.style?.kind !== 'elevation-bands') return {color: colorFor(layer.id), weight: 2, fillOpacity: .18};
    const value = Number(feature.properties?.[layer.style.field]);
    const position = Math.min(1, Math.max(0, (value - layer.style.min) / (layer.style.max - layer.style.min)));
    return {color: '#151515', weight: .65, opacity: .95, fillColor: interpolateColour(layer.style.colours, position), fillOpacity: .92};
  };
  const boot = async (root) => {
    const canvas = root.querySelector('.rfi-map__canvas');
    const panel = root.querySelector('.rfi-map__layers');
    const assetsPanel = root.querySelector('.rfi-map__assets');
    const legendPanel = document.createElement('aside'); legendPanel.className = 'rfi-map__legend'; legendPanel.hidden = true;
    const landuseLegendPanel = document.createElement('aside'); landuseLegendPanel.className = 'rfi-map__landuse-legend'; landuseLegendPanel.hidden = true;
    root.append(legendPanel, landuseLegendPanel);
    const activeLegends = new Map();
    const legendKey = entry => entry.legend?.title || entry.name;
    const layerGroups = new Map();
    const positionLanduseLegend = () => {
      if (landuseLegendPanel.hidden) return;
      const top = 12 + (legendPanel.hidden ? 0 : legendPanel.offsetHeight + 10);
      landuseLegendPanel.style.top = `${top}px`;
      landuseLegendPanel.style.maxHeight = `calc(100% - ${top + 12}px)`;
    };
    const renderLanduseLegend = (layer, visible) => {
      landuseLegendPanel.replaceChildren();
      landuseLegendPanel.hidden = !visible;
      if (!visible) return;
      const heading = document.createElement('h3'); heading.textContent = 'Land use parcels'; landuseLegendPanel.append(heading);
      const sources = Array.isArray(layer.source_layers) ? layer.source_layers : [];
      sources.forEach(source => {
        const row = document.createElement('div'); row.className = 'rfi-landuse-legend__row';
        const swatch = document.createElement('span'); swatch.className = 'rfi-landuse-legend__swatch';
        const symbol = landuseSymbol(source); swatch.style.background = landusePreviewFill(symbol);
        if (symbol.pattern === 'dots') swatch.style.backgroundSize = '6px 6px';
        const label = document.createElement('span'); label.textContent = source.name;
        row.append(swatch, label); landuseLegendPanel.append(row);
      });
      positionLanduseLegend();
    };
    const placeLayerControl = (control, group, standalone = false) => {
      if (standalone) { control.classList.add('rfi-primary-boundary'); panel.prepend(control); return; }
      if (!group) { panel.append(control); return; }
      if (!layerGroups.has(group)) {
        const details = document.createElement('details'); details.className = 'rfi-layer-group'; details.open = true;
        const summary = document.createElement('summary'); summary.textContent = group; details.append(summary);
        const content = document.createElement('div'); content.className = 'rfi-layer-group__content'; details.append(content);
        details.addEventListener('toggle', () => {
          if (details.open) return;
          content.querySelectorAll('input[type="checkbox"]:checked').forEach(input => {
            input.checked = false;
            input.dispatchEvent(new Event('change'));
          });
        });
        if (group === 'Plant health indicators') {
          const boundary = panel.querySelector('.rfi-primary-boundary');
          if (boundary) panel.insertBefore(details, boundary.nextSibling);
          else panel.prepend(details);
        } else panel.append(details);
        layerGroups.set(group, content);
      }
      layerGroups.get(group).append(control);
    };
    const renderLegends = () => {
      legendPanel.replaceChildren();
      if (!activeLegends.size || !landuseLegendPanel.hidden) { legendPanel.hidden = true; positionLanduseLegend(); return; }
      legendPanel.hidden = false;
      const heading = document.createElement('h3'); heading.textContent = 'Legend'; legendPanel.append(heading);
      activeLegends.forEach((legend, name) => {
        const item = document.createElement('div'); item.className = 'rfi-legend';
        const title = document.createElement('b'); title.textContent = legend.title || name;
        if (legend.description) { title.title = legend.description; title.className = 'rfi-legend__title--help'; }
        item.append(title);
        const bar = document.createElement('div'); bar.className = 'rfi-legend__bar';
        bar.style.background = `linear-gradient(to right, ${legend.stops.map((stop, index) => `${stop.color} ${index / (legend.stops.length - 1) * 100}%`).join(', ')})`;
        item.append(bar);
        const values = document.createElement('div'); values.className = 'rfi-legend__values';
        legend.stops.forEach(stop => { const value = document.createElement('span'); value.textContent = stop.value; values.append(value); });
        item.append(values);
        const labels = document.createElement('div'); labels.className = 'rfi-legend__labels'; labels.textContent = `${legend.low_label}  •  ${legend.high_label}`; item.append(labels);
        legendPanel.append(item);
      });
      positionLanduseLegend();
    };
    const map = L.map(canvas, {scrollWheelZoom: true, rotate: true, bearing: 0, shiftKeyRotate: true, touchRotate: true, rotateControl: false}).setView([39.8283, -98.5795], 4);
    const landuseRenderer = L.svg({padding: .25}); landuseRenderer.addTo(map);
    const svgNamespace = 'http://www.w3.org/2000/svg';
    const landuseDefs = document.createElementNS(svgNamespace, 'defs'); landuseRenderer._container.insertBefore(landuseDefs, landuseRenderer._container.firstChild);
    const landusePatternFill = symbol => {
      if (symbol.pattern === 'solid') return symbol.color;
      const id = `rfi-landuse-${symbol.pattern}-${symbol.color.slice(1)}`;
      if (!landuseDefs.querySelector(`#${id}`)) {
        const pattern = document.createElementNS(svgNamespace, 'pattern');
        pattern.setAttribute('id', id); pattern.setAttribute('patternUnits', 'userSpaceOnUse'); pattern.setAttribute('width', '8'); pattern.setAttribute('height', '8');
        const background = document.createElementNS(svgNamespace, 'rect'); background.setAttribute('width', '8'); background.setAttribute('height', '8'); background.setAttribute('fill', symbol.color); pattern.append(background);
        const ink = 'rgba(20, 38, 26, .72)';
        if (symbol.pattern === 'dots') {
          const dot = document.createElementNS(svgNamespace, 'circle'); dot.setAttribute('cx', '2'); dot.setAttribute('cy', '2'); dot.setAttribute('r', '1'); dot.setAttribute('fill', ink); pattern.append(dot);
        } else {
          const hatch = document.createElementNS(svgNamespace, 'path');
          hatch.setAttribute('d', symbol.pattern === 'crosshatch' ? 'M-2,2 L2,-2 M0,8 L8,0 M6,10 L10,6 M6,-2 L10,2 M0,0 L8,8 M-2,6 L2,10' : 'M-2,2 L2,-2 M0,8 L8,0 M6,10 L10,6');
          hatch.setAttribute('stroke', ink); hatch.setAttribute('stroke-width', '1'); pattern.append(hatch);
        }
        landuseDefs.append(pattern);
      }
      return `url(#${id})`;
    };
    L.control.scale({position: 'bottomleft', imperial: true}).addTo(map);
    const compass = L.control({position: 'bottomleft'});
    compass.onAdd = () => {
      const control = L.DomUtil.create('div', 'rfi-rotate-control');
      control.setAttribute('role', 'group'); control.setAttribute('aria-label', 'Map rotation compass');
      control.innerHTML = '<button type="button" class="rfi-rotate-control__direction rfi-rotate-control__north" data-bearing="0" aria-label="Orient map north-up">N</button><button type="button" class="rfi-rotate-control__direction rfi-rotate-control__east" data-bearing="270" aria-label="Orient map east-up">E</button><button type="button" class="rfi-rotate-control__direction rfi-rotate-control__south" data-bearing="180" aria-label="Orient map south-up">S</button><button type="button" class="rfi-rotate-control__direction rfi-rotate-control__west" data-bearing="90" aria-label="Orient map west-up">W</button><button type="button" class="rfi-rotate-control__reset" aria-label="Drag to rotate the map; click to reset north"><span class="rfi-rotate-control__needle" aria-hidden="true">▲</span></button>';
      L.DomEvent.disableClickPropagation(control); L.DomEvent.disableScrollPropagation(control);
      const needle = control.querySelector('.rfi-rotate-control__needle');
      const reset = control.querySelector('.rfi-rotate-control__reset');
      const updateCompass = () => {
        const bearing = map.getBearing ? map.getBearing() : 0;
        needle.style.transform = `rotate(${bearing}deg)`;
        reset.setAttribute('aria-label', Math.abs(bearing) < .5 ? 'Map is north-up; drag compass to rotate' : `Drag compass to rotate; click to reset north (currently ${Math.round(bearing)} degrees)`);
      };
      control.querySelectorAll('[data-bearing]').forEach(button => button.addEventListener('click', () => map.setBearing(Number(button.dataset.bearing))));
      let dragStartAngle = 0, dragStartBearing = 0, dragged = false, suppressReset = false;
      const compassAngle = event => {
        const bounds = control.getBoundingClientRect();
        return Math.atan2(event.clientY - (bounds.top + bounds.height / 2), event.clientX - (bounds.left + bounds.width / 2)) * 180 / Math.PI;
      };
      const stopDrag = () => {
        document.removeEventListener('pointermove', dragCompass);
        document.removeEventListener('pointerup', stopDrag);
        document.removeEventListener('pointercancel', stopDrag);
        if (dragged) {
          suppressReset = true; control.classList.remove('is-rotating');
          setTimeout(() => { suppressReset = false; }, 0);
        } else map.setBearing(0);
      };
      const dragCompass = event => {
        const delta = compassAngle(event) - dragStartAngle;
        if (Math.abs(delta) > 1) { dragged = true; control.classList.add('is-rotating'); map.setBearing(dragStartBearing + delta); }
      };
      reset.addEventListener('pointerdown', event => {
        event.preventDefault(); dragStartAngle = compassAngle(event); dragStartBearing = map.getBearing(); dragged = false;
        document.addEventListener('pointermove', dragCompass); document.addEventListener('pointerup', stopDrag); document.addEventListener('pointercancel', stopDrag);
      });
      reset.addEventListener('click', () => { if (suppressReset) { suppressReset = false; return; } map.setBearing(0); });
      map.on('rotate', updateCompass); updateCompass();
      return control;
    };
    compass.addTo(map);
    const streetMap = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'});
    const satelliteMap = L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {maxZoom: 19, attribution: 'Tiles &copy; Esri'});
    satelliteMap.addTo(map);
    L.control.layers({'Satellite imagery': satelliteMap, 'Street map': streetMap}, {}, {position: 'topleft'}).addTo(map);
    let config;
    try { config = await fetch(configUrl).then(r => { if (!r.ok) throw Error(r.status); return r.json(); }); }
    catch (error) { panel.textContent = 'Map configuration could not be loaded.'; return; }
    [...(config.layers || []), ...(config.satellite_assets || [])].forEach(entry => {
      if (entry.legend) activeLegends.set(legendKey(entry), entry.legend);
    });
    renderLegends();
    const extent = L.featureGroup();
    let focusLayer;
    (config.layers || []).filter(layer => layer.type === 'xyz').forEach(layer => {
      const tile = L.tileLayer(layer.url, {opacity: layer.opacity || .7, attribution: layer.attribution || ''});
      if (layer.visible) { tile.addTo(map); }
      panel.insertAdjacentHTML('beforeend', `<label><input type="checkbox" ${layer.visible ? 'checked' : ''}> ${escapeHtml(layer.name)}</label>`);
      panel.lastElementChild.querySelector('input').addEventListener('change', e => e.target.checked ? tile.addTo(map) : map.removeLayer(tile));
    });
    for (const layer of (config.layers || []).filter(layer => layer.type === 'geojson')) {
      const label = document.createElement('label');
      const input = document.createElement('input'); input.type = 'checkbox'; input.checked = !!layer.visible;
      label.append(input, document.createTextNode(' ' + layer.name)); placeLayerControl(label, layer.group, !!layer.primary_boundary);
      if (!layer.url) { label.classList.add('rfi-muted'); label.title = 'No public URL configured for this data source.'; continue; }
      try {
        const data = await fetch(resolveUrl(layer.url)).then(r => r.json());
        const geojson = L.geoJSON(data, {renderer: layer.style?.kind === 'landuse-parcels' ? landuseRenderer : undefined, style: feature => vectorStyle(layer, feature, layer.style?.kind === 'landuse-parcels' ? landusePatternFill : undefined), onEachFeature: (f, l) => {
          const entries = Object.entries(f.properties || {}).filter(([key]) => key !== '_rfi_source_id');
          const popupEntries = layer.style?.kind === 'landuse-parcels' ? entries : entries.slice(0, 12);
          const props = popupEntries.map(([k,v]) => `<b>${escapeHtml(k)}</b>: ${escapeHtml(v == null || v === '' ? 'Not entered' : v)}`).join('<br>'); if (props) l.bindPopup(props);
          if (layer.style?.kind === 'landuse-parcels') {
            l.on({
              mouseover: event => { const target = event.target; target.setStyle({color: '#ffd54a', weight: 3.5, fillColor: '#ffd54a', fillOpacity: .72}); if (target.bringToFront) target.bringToFront(); },
              mouseout: event => geojson.resetStyle(event.target),
            });
          }
        }});
        extent.addLayer(geojson); if (input.checked) geojson.addTo(map);
        if (layer.style?.kind === 'landuse-parcels') renderLanduseLegend(layer, input.checked);
        if (layer.zoom_on_load || layer.id === 'laf-border-web') focusLayer = geojson;
        if (layer.legend && input.checked) { activeLegends.set(legendKey(layer), layer.legend); renderLegends(); }
        input.addEventListener('change', e => {
          if (e.target.checked) { geojson.addTo(map); if (layer.legend) activeLegends.set(legendKey(layer), layer.legend); }
          else { map.removeLayer(geojson); activeLegends.delete(legendKey(layer)); }
          if (layer.style?.kind === 'landuse-parcels') renderLanduseLegend(layer, e.target.checked);
          renderLegends();
        });
      } catch (error) { console.error(`Could not load layer: ${layer.name}`, error); label.classList.add('rfi-muted'); label.title = 'Layer could not be fetched; see the browser console for details.'; }
    }
    const healthIndicatorInputs = new Set();
    const timelineAssets = (config.satellite_assets || []).filter(asset => asset.kind === 'timeline-health-overlay' && asset.url && asset.bounds);
    for (const asset of (config.satellite_assets || [])) {
      if (asset.kind === 'timeline-health-overlay') continue;
      // Source GeoTIFFs without a public URL are retained in the manifest but
      // are not useful rows in the browser UI. Generated health PNGs remain.
      if (!asset.displayable_overlay && !asset.url) continue;
      const row = document.createElement('div'); row.className = 'rfi-asset';
      row.innerHTML = `<b>${escapeHtml(asset.name)}</b><small>${escapeHtml(asset.kind)} · ${escapeHtml(asset.format.toUpperCase())}</small>`;
      if (asset.url) { const a = document.createElement('a'); a.href = resolveUrl(asset.url); a.target = '_blank'; a.rel = 'noopener'; a.textContent = asset.displayable_overlay ? 'Open overlay' : 'Open data'; row.append(a); }
      assetsPanel.append(row);
      if (asset.displayable_overlay && asset.url && asset.bounds) {
        const overlay = L.imageOverlay(resolveUrl(asset.url), asset.bounds, {opacity: asset.opacity ?? .65});
        const control = document.createElement('label'); control.innerHTML = `<input type="checkbox"> ${escapeHtml(asset.name)} overlay`; placeLayerControl(control, asset.group);
        const input = control.querySelector('input');
        if (asset.kind === 'health-overview-overlay') healthIndicatorInputs.add(input);
        input.addEventListener('change', e => {
          if (e.target.checked && asset.kind === 'health-overview-overlay') {
            healthIndicatorInputs.forEach(other => {
              if (other !== input && other.checked) { other.checked = false; other.dispatchEvent(new Event('change')); }
            });
          }
          if (e.target.checked) { overlay.addTo(map); if (asset.legend) activeLegends.set(legendKey(asset), asset.legend); }
          else { map.removeLayer(overlay); activeLegends.delete(legendKey(asset)); }
          renderLegends();
          if (asset.kind === 'health-overview-overlay' && ['Health_score', 'NDVI', 'EVI', 'MIR_reflectance', 'NDMI', 'NDWI'].includes(asset.metric)) {
            root.dispatchEvent(new CustomEvent('rfi-timeline-metric', {detail: {metric: asset.metric, visible: e.target.checked}}));
          }
        });
      }
    }
    if (timelineAssets.length) {
      const labels = {Health_score: 'Plant + soil health score', NDVI: 'NDVI', EVI: 'EVI', MIR_reflectance: 'MIR reflectance', NDMI: 'NDMI', NDWI: 'NDWI'};
      const assetsByMetric = new Map();
      timelineAssets.forEach(asset => {
        const metric = asset.timeline_metric;
        const year = Number(asset.timeline_year);
        if (!assetsByMetric.has(metric)) assetsByMetric.set(metric, new Map());
        assetsByMetric.get(metric).set(year, asset);
      });
      const metrics = [...assetsByMetric.keys()].filter(metric => labels[metric]);
      const years = [...new Set(timelineAssets.map(asset => Number(asset.timeline_year)))].sort((a, b) => a - b);
      if (metrics.length && years.length) {
        const control = document.createElement('section');
        control.className = 'rfi-timeline'; control.hidden = true;
        control.setAttribute('aria-label', 'Plant-health imagery timeline');
        control.innerHTML = `<b>Imagery timeline</b><label>Index <select></select></label><label>Year <output>${years.at(-1)}</output><input type="range" min="0" max="${years.length - 1}" value="${years.length - 1}" step="1" aria-label="Timeline year"></label>`;
        root.append(control);
        L.DomEvent.disableClickPropagation(control); L.DomEvent.disableScrollPropagation(control);
        const metric = control.querySelector('select');
        const slider = control.querySelector('input[type="range"]');
        const yearOutput = control.querySelector('output');
        const visibleMetrics = new Set();
        let overlay, activeLegendKey;
        const update = () => {
          const year = years[Number(slider.value)];
          const asset = assetsByMetric.get(metric.value)?.get(year);
          yearOutput.value = year; yearOutput.textContent = year;
          if (overlay) map.removeLayer(overlay);
          if (activeLegendKey) activeLegends.delete(activeLegendKey);
          overlay = undefined; activeLegendKey = undefined;
          if (asset && visibleMetrics.has(metric.value)) {
            overlay = L.imageOverlay(resolveUrl(asset.url), asset.bounds, {opacity: asset.opacity ?? 1});
            activeLegendKey = legendKey(asset); overlay.addTo(map);
            if (asset.legend) activeLegends.set(activeLegendKey, asset.legend);
          }
          renderLegends();
        };
        const updateVisibleMetrics = preferredMetric => {
          const active = metrics.filter(metricName => visibleMetrics.has(metricName));
          control.hidden = !active.length;
          if (!active.length) { update(); return; }
          const selected = active.includes(preferredMetric) ? preferredMetric : active.includes(metric.value) ? metric.value : active.at(-1);
          metric.replaceChildren(...active.map(metricName => {
            const option = document.createElement('option'); option.value = metricName; option.textContent = labels[metricName]; return option;
          }));
          metric.value = selected; update();
        };
        root.addEventListener('rfi-timeline-metric', event => {
          const {metric: metricName, visible} = event.detail;
          if (visible) visibleMetrics.add(metricName); else visibleMetrics.delete(metricName);
          updateVisibleMetrics(metricName);
        });
        metric.addEventListener('change', update);
        slider.addEventListener('input', update);
      }
    }
    if (focusLayer && focusLayer.getBounds().isValid()) {
      map.fitBounds(focusLayer.getBounds().pad(.12));
      console.info('Map focused on LAF_border_web.');
    } else if (extent.getLayers().length) {
      map.fitBounds(extent.getBounds().pad(.08));
      console.warn('LAF_border_web was not loaded; map focused on all layers instead.');
    }
    if (!panel.children.length) panel.textContent = 'No web-ready QGIS layers were found.';
  };
  document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('.rfi-map').forEach(boot));
})();
'''

MAP_CSS = r'''.rfi-map{position:relative;border:1px solid #d7ddd9;border-radius:8px;overflow:hidden;background:#fff}.rfi-map__canvas{height:100%;width:100%}.rfi-map__panel,.rfi-map__legend{position:absolute;top:12px;width:min(280px,calc(100% - 24px));max-height:calc(100% - 24px);overflow:auto;background:#fffc;padding:13px 15px;border-radius:6px;box-shadow:0 1px 8px #0003;font:14px/1.4 system-ui,sans-serif;z-index:500}.rfi-map__panel{right:12px}.rfi-map__legend{left:52px;width:min(250px,calc(100% - 76px))}.rfi-map__panel h3,.rfi-map__legend h3{font-size:14px;margin:0 0 6px}.rfi-map__layers label{display:block;margin:5px 0;cursor:pointer}.rfi-layer-group{border-top:1px solid #d7ddd9;margin:8px 0;padding-top:6px}.rfi-layer-group summary{font-weight:650;cursor:pointer}.rfi-layer-group__content{padding-left:8px}.rfi-muted{color:#68716c}.rfi-asset{border-top:1px solid #d7ddd9;padding:7px 0}.rfi-asset b,.rfi-asset small{display:block}.rfi-asset small{color:#5b665f}.rfi-asset a{font-size:12px}.rfi-legend{border-top:1px solid #d7ddd9;padding:7px 0}.rfi-legend b{display:block;font-size:12px}.rfi-legend__title--help{cursor:help;text-decoration:underline dotted;text-underline-offset:2px}.rfi-legend__bar{height:12px;border:1px solid #777;border-radius:2px;margin:4px 0}.rfi-legend__values{display:flex;justify-content:space-between;font-size:10px}.rfi-legend__labels{font-size:10px;color:#5b665f;margin-top:2px}.rfi-rotate-control{position:relative;width:84px;height:84px;color:#fff;font:700 12px/1 system-ui,sans-serif;touch-action:none;user-select:none;background:transparent;border:0;border-radius:50%;box-shadow:none;text-shadow:0 1px 2px #000}.rfi-rotate-control:before{content:"";position:absolute;inset:10px;border:1.5px solid #fff;border-radius:50%;pointer-events:none}.rfi-rotate-control__direction,.rfi-rotate-control__reset{position:absolute;border:0;background:transparent;color:inherit;font:inherit;cursor:pointer}.rfi-rotate-control__direction{padding:3px;color:#bd332b;text-shadow:0 1px 2px #000}.rfi-rotate-control__north{top:0;left:50%;transform:translateX(-50%)}.rfi-rotate-control__east{right:0;top:50%;transform:translateY(-50%)}.rfi-rotate-control__south{bottom:0;left:50%;transform:translateX(-50%)}.rfi-rotate-control__west{left:0;top:50%;transform:translateY(-50%)}.rfi-rotate-control__reset{left:50%;top:50%;width:31px;height:31px;padding:0;transform:translate(-50%,-50%);border:1.5px solid #fff;border-radius:50%;cursor:grab}.rfi-rotate-control.is-rotating .rfi-rotate-control__reset{cursor:grabbing}.rfi-rotate-control__needle{display:block;color:#bd332b;font-size:22px;line-height:28px;transform-origin:50% 50%;transition:transform .15s ease}.rfi-rotate-control__direction:focus-visible,.rfi-rotate-control__reset:focus-visible{outline:2px solid #fff;outline-offset:1px}.rfi-map .leaflet-control-scale{color:#fff;text-shadow:0 1px 2px #000}.rfi-map .leaflet-control-scale-line{color:#fff;background:transparent;border-color:#fff;text-shadow:inherit}@media(max-width:600px){.rfi-map__panel{top:auto;bottom:10px;max-height:45%}.rfi-map__legend{top:10px;left:10px;max-height:35%}}
'''

MAP_CSS += r'''
.rfi-rotate-control__reset{display:grid;place-items:center}
.rfi-rotate-control__needle{line-height:1}
.rfi-timeline{position:absolute;left:50%;bottom:12px;z-index:500;min-width:215px;transform:translateX(-50%);background:#fffc;padding:10px 12px;border-radius:6px;box-shadow:0 1px 8px #0003;font:13px/1.35 system-ui,sans-serif}
.rfi-timeline b,.rfi-timeline label{display:block}
.rfi-timeline__show{margin:5px 0}
.rfi-timeline select,.rfi-timeline input[type="range"]{width:100%;box-sizing:border-box;margin:2px 0 5px}
.rfi-timeline output{float:right;font-weight:700}
'''

MAP_CSS += r'''
.rfi-map__landuse-legend{position:absolute;left:52px;width:min(280px,calc(100% - 76px));overflow:auto;background:#fffc;padding:13px 15px;border-radius:6px;box-shadow:0 1px 8px #0003;font:14px/1.4 system-ui,sans-serif;z-index:500}
.rfi-map__landuse-legend h3{font-size:14px;margin:0 0 6px}
.rfi-landuse-legend__row{display:flex;align-items:center;gap:7px;padding:3px 0;font-size:12px}
.rfi-landuse-legend__swatch{width:28px;height:15px;flex:0 0 28px;border:1px solid #38453b;border-radius:2px}
@media(max-width:600px){.rfi-map__landuse-legend{left:10px;width:min(250px,calc(100% - 20px))}}
'''

PUBLIC_HTML = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RFI Interactive Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <link rel="stylesheet" href="assets/rfi-map.css">
  <style>html,body{height:100%;margin:0;background:#eff3f0}.rfi-map{min-height:100%;height:100%;border:0;border-radius:0}</style>
</head>
<body>
  <main class="rfi-map"><div class="rfi-map__canvas"></div><aside class="rfi-map__panel"><h3>Map layers</h3><div class="rfi-map__layers"></div><details class="rfi-data-references"><summary>Data references</summary><div class="rfi-map__assets"></div></details></aside></main>
  <script>window.RFIMapData = {configUrl: 'data/map-config.json'};</script>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="assets/leaflet-rotate.js"></script>
  <script src="assets/rfi-map.js"></script>
</body>
</html>
'''


PREVIEW_HTML = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RFI Map — local preview</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <link rel="stylesheet" href="../assets/rfi-map.css">
  <style>body{margin:0;background:#eff3f0;font-family:system-ui,sans-serif}.rfi-preview-header{padding:12px 20px;background:#173d31;color:#fff}.rfi-preview-header p{margin:3px 0 0;font-size:14px}.rfi-map{height:calc(100vh - 75px);border:0;border-radius:0}</style>
</head>
<body>
  <header class="rfi-preview-header"><strong>RFI interactive map — local development preview</strong><p>Edit assets or data, refresh this page, and use browser Developer Tools (F12) for errors.</p></header>
  <main class="rfi-map"><div class="rfi-map__canvas"></div><aside class="rfi-map__panel"><h3>Map layers</h3><div class="rfi-map__layers"></div><details class="rfi-data-references"><summary>Data references</summary><div class="rfi-map__assets"></div></details></aside></main>
  <script>window.RFIMapData = {configUrl: '../data/map-config.json'};</script>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="../assets/leaflet-rotate.js"></script>
  <script src="../assets/rfi-map.js"></script>
</body>
</html>
'''


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def copy_app_shell(output: Path) -> None:
    """Copy the authoritative UI shell when building to a separate directory.

    The checked-in rfi-interactive-map directory contains the maintained public
    UI and WordPress settings. Data rebuilds in that directory must not replace
    those files with older embedded generator templates.
    """
    template_root = Path(__file__).resolve().parent / "rfi-interactive-map"
    shell_files = (
        Path("index.html"),
        Path("preview/index.html"),
        Path("README.md"),
        Path("rfi-interactive-map.php"),
        Path("assets/rfi-map.js"),
        Path("assets/rfi-map.css"),
        Path("assets/leaflet-rotate.js"),
    )
    for relative in shell_files:
        source = template_root / relative
        destination = output / relative
        if source.resolve() == destination.resolve():
            continue
        if not source.is_file():
            raise RuntimeError(f"Application shell file is missing: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a WordPress RFI map plugin draft.")
    parser.add_argument("--qgis-dir", type=Path, help="Folder containing QGIS exports/projects.")
    parser.add_argument("--landuse-dir", type=Path, help="Folder containing the parcel land-use shapefiles referenced by the QGIS project.")
    parser.add_argument("--satellite-dir", type=Path, help="Folder containing satellite or NDVI calculations.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "rfi-interactive-map", help="Generated plugin folder.")
    parser.add_argument("--copy-vector-data", action="store_true", help="Deprecated: browser-ready vectors are always copied into the repository.")
    parser.add_argument("--copy-raster-previews", action="store_true", help="Deprecated: bounded raster previews are always copied into the repository.")
    parser.add_argument("--public-base-url", default="", help="Deprecated: external project-data URLs are not allowed in repository manifests.")
    parser.add_argument("--ndvi-tile-url", default="", help="Deprecated: place displayable imagery inside the repository instead.")
    parser.add_argument("--consolidate-landuse-only", action="store_true", help="Create one interactive land-use overlay from the already packaged source GeoJSON files.")
    args = parser.parse_args()
    if args.public_base_url or args.ndvi_tile_url:
        parser.error("External project-data URLs are disabled. Copy browser-ready data into the repository instead.")
    output = args.output.resolve()
    if args.consolidate_landuse_only:
        data_dir = output / "data"
        config_path = data_dir / "map-config.json"
        if not config_path.is_file():
            parser.error(f"Map config not found: {config_path}")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        non_parcel_layers = [layer for layer in config.get("layers", []) if layer.get("group") != "Land use parcels"]
        config["layers"] = consolidate_landuse_layers(non_parcel_layers + packaged_landuse_source_layers(data_dir), data_dir)
        config["generated_at"] = datetime.now(timezone.utc).isoformat()
        write_text(config_path, json.dumps(config, indent=2))
        print("Consolidated Land use parcels into one hoverable map overlay.")
        return
    for label, folder in (("QGIS", args.qgis_dir), ("land-use", args.landuse_dir), ("satellite", args.satellite_dir)):
        if folder and not folder.is_dir(): parser.error(f"{label} folder does not exist: {folder}")
    rotate_plugin = Path(__file__).resolve().parent / "vendor" / "leaflet-rotate-0.2.8.js"
    if not rotate_plugin.is_file():
        parser.error(f"Bundled rotation extension is missing: {rotate_plugin}")
    data_dir = output / "data"
    layers, notices = qgis_layers(args.qgis_dir.resolve() if args.qgis_dir else None, data_dir)
    parcel_layers, parcel_notices = landuse_layers(args.landuse_dir.resolve() if args.landuse_dir else None, data_dir)
    layers.extend(parcel_layers)
    layers = consolidate_landuse_layers(layers, data_dir)
    notices.extend(parcel_notices)
    satellite = satellite_layers(args.satellite_dir.resolve() if args.satellite_dir else None, data_dir)
    config = {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": {"storage": "repository", "qgis_folder_provided": bool(args.qgis_dir), "landuse_folder_provided": bool(args.landuse_dir), "satellite_folder_provided": bool(args.satellite_dir), "data_references": []}, "basemaps": [dict(basemap) for basemap in DEFAULT_BASEMAPS], "layers": layers, "satellite_assets": satellite, "notices": notices}
    copy_app_shell(output)
    write_text(data_dir / "map-config.json", json.dumps(config, indent=2))
    print(f"Created WordPress plugin draft: {output}")
    print(f"GeoJSON layers: {len([x for x in layers if x['type'] == 'geojson'])}; satellite assets: {len(satellite)}")
    if notices:
        print("Notes:")
        print("\n".join(f"- {notice}" for notice in notices))


if __name__ == "__main__":
    main()
