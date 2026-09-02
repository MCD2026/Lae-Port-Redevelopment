from __future__ import annotations

import argparse
import json
import math
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

from PIL import Image, ImageOps


SITE_PREFIX = "var json_Lae_Port_Photos = "
IMAGE_SUFFIXES = {".jpg", ".jpeg"}
TERRAIN_SOURCE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

LAYER_NAMES = {
    "hbscampaccommodation": "HBS Camp Accommodation",
    "hbsservicessitevisit": "HBS Services",
    "laeportexistingwharfsitevisit": "Lae Port Existing Wharf",
    "laeportlandsidesitevisit": "Lae Port Landside",
    "pacificmarinegroupkimbeportsitevisit": "Pacific Marine Group – Kimbe Port",
    "readymixedconcretepngsitevisit": "Ready Mixed Concrete PNG",
    "transpacificpilingpotentialsubcontractor": "Trans Pacific Piling",
}


@dataclass(frozen=True)
class PhotoRecord:
    filename: str
    timestamp: str
    longitude: float
    latitude: float
    direction: float | None
    altitude: float | None
    image: Path
    site: str
    author: str


def parse_js_collection(path: Path, prefix: str | None = None) -> dict:
    text = path.read_text(encoding="utf-8")
    if prefix and not text.startswith(prefix):
        raise ValueError(f"Unexpected JavaScript data format: {path}")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"No JSON collection was found in {path}")
    return json.loads(text[start : end + 1])


def normalise_layer_name(value: object) -> str:
    raw = re.sub(r"_\d+(?:_\d+)?$", "", str(value)).strip(" _-")
    key = re.sub(r"[^a-z0-9]+", "", raw.lower())
    if key in LAYER_NAMES:
        return LAYER_NAMES[key]
    return re.sub(r"(?<!^)(?=[A-Z])", " ", raw).replace("_", " ").strip() or "Site photos"


def author_from_path(value: object) -> str:
    match = re.search(r"Images by ([^\\/]+)", str(value), re.IGNORECASE)
    return match.group(1).strip() if match else ""


def find_qgis_image(images: list[Path], properties: dict) -> Path:
    filename = str(properties.get("filename", "")).strip()
    photo = str(properties.get("photo", "")).strip()
    flattened_name = re.sub(r"[:\\\\/]", "_", photo).lower()
    exact = [path for path in images if path.name.lower() == flattened_name] if flattened_name else []
    if exact:
        return exact[0]
    original_name = PureWindowsPath(photo).name.lower()
    matches = [path for path in images if path.name.lower().endswith(original_name)] if original_name else []
    if not matches:
        matches = [path for path in images if path.stem.lower().endswith(filename.lower())]
    if not matches:
        raise FileNotFoundError(f"No exported image was found for {filename}")
    preferred_suffix = PureWindowsPath(photo).suffix.lower()
    return next((path for path in matches if path.suffix.lower() == preferred_suffix), matches[0])


def find_qgis_export(source: Path) -> Path | None:
    candidates: list[Path] = []
    for data_dir in list(source.rglob("data")) + list(source.rglob("layers")):
        root = data_dir.parent
        if not (root / "images").is_dir() or not any(data_dir.glob("*.js")):
            continue
        if root not in candidates:
            candidates.append(root)
    if len(candidates) > 1:
        joined = "\n  ".join(str(path) for path in candidates)
        raise ValueError(f"More than one QGIS export was found. Keep one export in the input folder:\n  {joined}")
    return candidates[0] if candidates else None


def records_from_qgis(root: Path) -> list[PhotoRecord]:
    data_dir = root / "data" if (root / "data").is_dir() else root / "layers"
    images = sorted(path for path in (root / "images").iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    unique: dict[tuple[str, str], tuple[dict, str]] = {}
    for data_file in sorted(data_dir.glob("*.js")):
        try:
            collection = parse_js_collection(data_file)
        except (ValueError, json.JSONDecodeError):
            continue
        layer = normalise_layer_name(collection.get("name", data_file.stem))
        for feature in collection.get("features", []):
            properties = feature.get("properties", {})
            filename = str(properties.get("filename", "")).strip()
            photo = str(properties.get("photo", ""))
            if not filename or feature.get("geometry", {}).get("type") != "Point":
                continue
            key = (layer.lower(), filename.lower())
            existing = unique.get(key)
            if existing is None or (photo.lower().endswith(".jpeg") and not str(existing[0]["properties"].get("photo", "")).lower().endswith(".jpeg")):
                unique[key] = (feature, layer)

    records = []
    for feature, layer in unique.values():
        properties = feature["properties"]
        filename = str(properties["filename"])
        image = find_qgis_image(images, properties)
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        records.append(
            PhotoRecord(
                filename=f"{layer} - {filename}",
                timestamp=str(properties.get("timestamp", "")),
                longitude=float(longitude),
                latitude=float(latitude),
                direction=number_or_none(properties.get("direction")),
                altitude=number_or_none(properties.get("altitude")),
                image=image,
                site=layer,
                author=author_from_path(properties.get("photo", "")),
            )
        )
    return sorted(records, key=lambda item: (item.timestamp, item.filename.lower()))


def number_or_none(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def gps_coordinate(values: object, reference: object) -> float:
    degrees, minutes, seconds = (float(value) for value in values)  # type: ignore[arg-type]
    result = degrees + minutes / 60 + seconds / 3600
    if str(reference).upper() in {"S", "W"}:
        result *= -1
    return result


def exif_timestamp(exif: Image.Exif, gps: dict) -> str:
    gps_date = gps.get(29)
    gps_time = gps.get(7)
    if gps_date and gps_time:
        year, month, day = (int(value) for value in str(gps_date).split(":"))
        hour, minute, second = (float(value) for value in gps_time)
        moment = datetime(year, month, day, int(hour), int(minute), int(second), tzinfo=timezone.utc)
        return moment.isoformat().replace("+00:00", "Z")

    exif_ifd = exif.get_ifd(0x8769)
    original = exif_ifd.get(36867)
    if original:
        moment = datetime.strptime(str(original), "%Y:%m:%d %H:%M:%S")
        return moment.isoformat()
    return ""


def clean_filename(path: Path) -> str:
    name = path.stem.strip()
    match = re.search(r"((?:IMG|DSC|DJI)[_-]\d+)$", name, re.IGNORECASE)
    if match:
        name = match.group(1)
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-.")
    return name or "site-photo"


def inferred_site(path: Path, source: Path) -> str:
    relative = path.relative_to(source)
    if len(relative.parts) > 1:
        return normalise_layer_name(relative.parts[0])
    key = re.sub(r"[^a-z0-9]+", "", path.stem.lower())
    for candidate, label in LAYER_NAMES.items():
        if candidate in key:
            return label
    if "simonson" in key:
        return "Simonsen Wharf"
    return "New Photos"


def record_from_original(path: Path, source: Path) -> PhotoRecord:
    with Image.open(path) as image:
        exif = image.getexif()
        gps = dict(exif.get_ifd(0x8825))
    required = {1, 2, 3, 4}
    if not required.issubset(gps):
        raise ValueError(f"GPS metadata is missing: {path.name}")
    altitude = number_or_none(gps.get(6))
    if altitude is not None and gps.get(5) not in (None, b"\x00", 0):
        altitude *= -1
    return PhotoRecord(
        filename=clean_filename(path),
        timestamp=exif_timestamp(exif, gps),
        longitude=gps_coordinate(gps[4], gps[3]),
        latitude=gps_coordinate(gps[2], gps[1]),
        direction=number_or_none(gps.get(17) or gps.get(24)),
        altitude=altitude,
        image=path,
        site=inferred_site(path, source),
        author="",
    )


def records_from_originals(source: Path) -> list[PhotoRecord]:
    image_paths = sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    if not image_paths:
        raise FileNotFoundError(f"No JPG or JPEG photos were found under {source}")
    records = []
    errors = []
    for path in image_paths:
        try:
            records.append(record_from_original(path, source))
        except ValueError as error:
            errors.append(str(error))
    if errors:
        preview = "\n  ".join(errors[:12])
        extra = f"\n  ...and {len(errors) - 12} more" if len(errors) > 12 else ""
        raise ValueError(f"Use original photos with location metadata enabled:\n  {preview}{extra}")
    names: dict[str, Path] = {}
    for record in records:
        key = record.filename.lower()
        if key in names:
            raise ValueError(f"Duplicate photo name {record.filename}: {names[key]} and {record.image}")
        names[key] = record.image
    return sorted(records, key=lambda item: (item.timestamp, item.filename.lower()))


def load_existing(site: Path) -> list[dict]:
    data_path = site / "data" / "Lae_Port_Photos.js"
    if not data_path.exists():
        return []
    return parse_js_collection(data_path, SITE_PREFIX).get("features", [])


def feature_for(record: PhotoRecord, photo_path: str) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "photo": photo_path,
            "filename": record.filename,
            "timestamp": record.timestamp,
            "direction": record.direction,
            "altitude": record.altitude,
            "site": record.site,
            "author": record.author,
        },
        "geometry": {"type": "Point", "coordinates": [record.longitude, record.latitude]},
    }


def optimise(source: Path, destination: Path, max_size: int, quality: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        image.save(destination, "JPEG", quality=quality, optimize=True, progressive=True)


def update_count(path: Path, count: int) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\d+ location-tagged photos", f"{count} location-tagged photos", text)
    text = re.sub(r"\d+ photos · Location-guided tour", f"{count} photos · Location-guided tour", text)
    path.write_text(text, encoding="utf-8")


def write_dataset(site: Path, features: list[dict]) -> None:
    collection = {"type": "FeatureCollection", "name": "Lae Port Redevelopment Photos", "features": features}
    text = SITE_PREFIX + json.dumps(collection, separators=(",", ":")) + ";\n"
    for path in (site / "data" / "Lae_Port_Photos.js", site / "map" / "data" / "Lae_Port_Photos.js"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def tile_xy(longitude: float, latitude: float, zoom: int) -> tuple[int, int]:
    size = 2**zoom
    x = int((longitude + 180) / 360 * size)
    latitude_radians = math.radians(max(-85.05112878, min(85.05112878, latitude)))
    y = int((1 - math.asinh(math.tan(latitude_radians)) / math.pi) / 2 * size)
    return max(0, min(size - 1, x)), max(0, min(size - 1, y))


def download_terrain(task: tuple[int, int, int, Path]) -> int:
    zoom, x, y, path = task
    if path.exists() and path.stat().st_size > 0:
        return path.stat().st_size
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        TERRAIN_SOURCE.format(z=zoom, x=x, y=y),
        headers={"User-Agent": "MCD-Lae-Port-rebuild/1.0"},
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
            path.write_bytes(data)
            return len(data)
        except Exception as error:  # pragma: no cover - depends on network
            last_error = error
            time.sleep(1 + attempt)
    raise RuntimeError(f"Could not download terrain tile {zoom}/{x}/{y}: {last_error}")


def cache_terrain(features: list[dict], destination: Path, max_zoom: int = 15, buffer: int = 1) -> None:
    coordinates = [feature["geometry"]["coordinates"] for feature in features]
    west = min(point[0] for point in coordinates)
    east = max(point[0] for point in coordinates)
    south = min(point[1] for point in coordinates)
    north = max(point[1] for point in coordinates)
    tasks = []
    tiles: dict[str, list[list[int]]] = {}
    for zoom in range(max_zoom + 1):
        limit = 2**zoom - 1
        level_tiles: set[tuple[int, int]] = set()
        for longitude, latitude in coordinates:
            center_x, center_y = tile_xy(longitude, latitude, zoom)
            for x in range(max(0, center_x - buffer), min(limit, center_x + buffer) + 1):
                for y in range(max(0, center_y - buffer), min(limit, center_y + buffer) + 1):
                    level_tiles.add((x, y))
        tiles[str(zoom)] = [[x, y] for x, y in sorted(level_tiles)]
        for x, y in sorted(level_tiles):
            tasks.append((zoom, x, y, destination / str(zoom) / str(x) / f"{y}.png"))
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(download_terrain, task) for task in tasks]
        for future in as_completed(futures):
            future.result()
    manifest = {
        "source": "Mapzen Terrain Tiles / AWS Open Data",
        "format": "terrarium",
        "bounds": [west, south, east, north],
        "maxZoom": max_zoom,
        "buffer": buffer,
        "tileCount": len(tasks),
        "tiles": tiles,
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Terrain coverage ready: {len(tasks)} tiles")


def referenced_number(feature: dict) -> int:
    match = re.search(r"photo-(\d+)\.jpg$", str(feature.get("properties", {}).get("photo", "")))
    return int(match.group(1)) if match else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild or append to the Lae Port Redevelopment PhotoMap.")
    parser.add_argument("source", type=Path, help="Folder containing original geotagged photos or a QGIS web export")
    parser.add_argument("site", type=Path, help="github-pages directory")
    parser.add_argument("--replace", action="store_true", help="Replace all existing photos instead of appending new ones")
    parser.add_argument("--skip-terrain", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-size", type=int, default=2000)
    parser.add_argument("--quality", type=int, default=78)
    args = parser.parse_args()

    source = args.source.resolve()
    site = args.site.resolve()
    qgis_root = find_qgis_export(source)
    incoming = records_from_qgis(qgis_root) if qgis_root else records_from_originals(source)
    existing = [] if args.replace else load_existing(site)
    existing_keys = {
        (
            str(feature.get("properties", {}).get("site", "")).lower(),
            str(feature.get("properties", {}).get("filename", "")).lower(),
        )
        for feature in existing
    }
    additions = [
        record for record in incoming
        if (record.site.lower(), record.filename.lower()) not in existing_keys
    ]
    print(f"Input photos: {len(incoming)}")
    print(f"Already present: {len(incoming) - len(additions)}")
    print(f"New photos: {len(additions)}")
    if args.dry_run:
        print("Dry run complete; no files were changed.")
        return

    output_images = site / "map" / "images"
    output_images.mkdir(parents=True, exist_ok=True)
    if args.replace:
        features = []
        next_number = 1
    else:
        features = list(existing)
        next_number = max((referenced_number(feature) for feature in existing), default=0) + 1

    for record in additions:
        target_name = f"photo-{next_number:03d}.jpg"
        optimise(record.image, output_images / target_name, args.max_size, args.quality)
        features.append(feature_for(record, f"images/{target_name}"))
        next_number += 1

    if args.replace:
        expected = {str(feature["properties"]["photo"]).split("/")[-1] for feature in features}
        for path in output_images.glob("photo-*.jpg"):
            if path.name not in expected:
                path.unlink()

    if not features:
        raise ValueError("The rebuilt site would contain no photos.")
    write_dataset(site, features)
    update_count(site / "index.html", len(features))
    update_count(site / "3d" / "index.html", len(features))
    missing = [feature["properties"]["photo"] for feature in features if not (site / "map" / feature["properties"]["photo"]).is_file()]
    if missing:
        raise FileNotFoundError(f"Generated dataset references {len(missing)} missing image(s): {missing[:5]}")
    if not args.skip_terrain:
        cache_terrain(features, site / "terrain")
    print(f"Site ready: {len(features)} photos")


if __name__ == "__main__":
    main()
