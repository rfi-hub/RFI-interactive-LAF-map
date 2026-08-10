# RFI map data

This directory is the map-data area inside the RFI map project repository. The
WordPress plugin is the presentation layer; these tracked files are the
versioned source of truth for the manifest, GeoJSON, and published raster
previews.

The checked-in `map-config.json` currently loads the repository copy of the LAF
user map over the satellite basemap. The RFI boundary, eight GeoPackage layers,
the `LAF_DEM_formap` elevation-band GeoJSON, and the howler-monkey study points
and transects are connected; the opening map view fits the boundary
automatically.

The Environmental health analysis section reads the repository's MODIS-derived
NDVI, EVI, MIR reflectance, NDMI, and combined plant/soil health overlays.
Each analysis includes annual views from 2019 through 2026. The analysis
selector shows one annual raster and one matching legend at a time;
switching top sections removes it while the locked basemap and boundary remain.

This directory is tracked directly by the root repository. It is not a
submodule or nested Git repository.

## Repository contract

- `map-config.json` is the public manifest and entry point.
- URLs inside the manifest may be relative. They resolve from the manifest's
  raw URL, so the repository can move between Git hosts without rewriting every
  layer.
- `qgis/` contains the active browser-ready river GeoJSON referenced by the
  manifest; superseded QGIS exports are kept in the external project backup.
- `laf-user-view-map/` contains the browser-ready GeoJSON exported from the
  current LAF user-view GeoPackages.
- `source/laf-user-view-map/` contains clean, checkpointed GeoPackage snapshots,
  the boundary source, and the original QGIS project used for provenance and
  future editing.
- `media/infrastructure/` contains the repository copies of the Cabanas and
  Stable photographs linked from their infrastructure polygons.
- `media/landuse/` contains browser-ready parcel photographs organized into
  conventional-agriculture, infrastructure, pasture, secondary-forest,
  syntropic, and timber folders. Multi-image parcels use popup carousels;
  Syntropic 2 currently uses four images. DNG sources are represented by
  repository JPEG previews so browsers and WordPress can display them.
- `satellite/timeline/` contains only the 40 published annual PNG overlays
  referenced by the active environmental-analysis configuration.
- `environmental_health` in `map-config.json` names the repository-relative
  overview and annual overlay paths, bounds, years, opacity, and original
  analysis color ramps. The validator expands every `{year}` path and confirms
  all 40 referenced PNG files are stored inside the repository.
- `schema/map-config.schema.json` documents the core manifest shape.
- A configured global basemap may use a hosted tile service. All
  project-specific layers, overlays, and downloadable assets must be copied
  into this directory and referenced with repository-relative URLs.
- Layers and overlays may set `section` to `land-use`, `contours`,
  `monkey-study`, or `environmental-health-analysis` to appear under the
  matching top map section. When omitted, the interface infers a section from
  the layer name, group, kind, and metric. The section bar is mutually
  exclusive: selecting one section hides all categorized layers belonging to
  the other three sections. The locked basemap and boundary remain visible.
- Land-use polygons use 75% fill opacity so their QGIS colors remain legible
  against the permanent satellite imagery.
- The Infrastructure layer contains 11 polygons from the refreshed LAF user
  map. The `cabanas` and singular `stable` features display their repository
  photographs in the parcel profile; the older plural `stables` feature remains
  a separate polygon.
- The Riparian area layer uses the one-feature `riparian 10m` GeoPackage table.
  Its browser style reproduces the current QGIS single-symbol renderer: blue
  (`#007cff`) single-direction hatching at 135 degrees, 2 mm spacing, 0.3 mm line
  width, and a 0.3 mm blue polygon outline. The hatch fill uses the same 75% opacity as
  the other land-use fills and is rendered above the solid polygons so the
  narrow 10 m corridor stays legible. That display copy is non-interactive and
  remains below the popup pane; the interactive geometry stays beneath the
  parcel layers. Its popup is titled `Riparian area`, uses
  a locally stored description adapted from USDA NRCS General Manual Part 411,
  and omits the composition and past-use sections that apply to managed parcels.
- The current QGIS polygon edits are checkpointed into the repository. All nine
  referenced GeoPackages were refreshed with SQLite online backups on
  2026-08-05, so edits present in the live QGIS WAL files are folded into
  self-contained `.gpkg` snapshots without committing `.gpkg-wal` or
  `.gpkg-shm` transaction sidecars. The browser exports for the 10 m riparian
  area and Secondary forest use the same live source state.
- The Syntropic layer uses the 12-feature `syntropic with census.gpkg` source.
  Each Syntropic popup parses its `Plant census` field and ignores blank, null,
  zero, or invalid counts. Its donut and four-row summary aggregate the parcel's
  trees into Emergent, High, Medium, and Low strata. The repository manifest's
  `census_strata_by_species` mapping preserves the source strata from
  `Syntropic Census.xlsx`; `Middle`/`mid` are normalized to Medium, `mid/high`
  to High, and `variable` to Low for the four-band display. “See full tree
  census” expands to the complete positive-count tree type, count, and
  percentage table. A parcel with no entered census displays an explicit
  no-data message. Current-use/composition panels are omitted from every
  non-Syntropic land-use popup.
- `source/laf-user-view-map/syntropic.gpkg` is also retained because the
  repository's `User map.qgz` QGIS project references it directly; the web map
  continues to use `syntropic with census.gpkg` for populated census fields.
- The Monkey study section presents the 3 study transects and 12 sighting
  points stored in `laf-user-view-map/`. The browser symbology matches the
  supplied study GeoJSON: transects use a high-contrast display palette
  (`T1 #00E5FF`, `T2 #FF4FD8`, and `T3 #FFE34D`) with the source feature colors
  and `#fab519` retained as fallbacks,
  displayed 20% thicker than its 0.26 mm reference width with a dark contrast
  casing, while sightings use its unweighted, automatically
  normalized 10 mm heatmap and transparent `#fff5f0`-to-`#67000d` Reds ramp. The
  authoritative point GeoJSON is unchanged. The bottom-right legend labels the
  transects and the QGIS minimum-to-maximum heat scale.
- `LAF_DEM_formap` uses the original QGIS categorized `ELEV_MAX` renderer:
  49–118 metre bands, the red–orange–yellow–green–blue color ramp, solid fill,
  and `#232323` bevel-joined outlines. The web map presents those outlines at
  25% of their initial width for a less dominant contour stroke. Its source
  GeoJSON and QGIS project are retained under `source/laf-user-view-map/`.
- The Elevation and watershed river network is a WGS 84 web export generated
  directly from the latest 50-record EPSG:32717 `rivers.geojson`. The refreshed
  source contains 25 non-empty MultiLineString geometries; its remaining
  records have null geometry and are retained for source fidelity. The current
  visible extent is `-80.04758321, -0.57626012, -80.04251554, -0.56937052`.
  The projected source and its QGIS metadata are retained under
  `source/laf-user-view-map/`.
- Parcel profile popups calculate area directly from each Polygon or
  MultiPolygon geometry on the WGS 84 ellipsoid and display the result in
  hectares. They read existing
  `Name`, description, date, and past-use fields when
  present. Empty fields display stable
  Latin/numeric preview text in the browser only; placeholder values are never
  written into the authoritative GeoJSON.
- Future parcel photos, video previews, or derived imagery must be copied into
  a repository directory such as `media/` and referenced with relative paths.
  Do not point parcel profiles at unversioned project-data files outside the
  repository.

The map fetches files directly in a visitor's browser. Publish the root
repository or its built data branch somewhere that permits cross-origin `GET`
requests.
Do not store passwords, access tokens, private field notes, or personal data in
this repository.

## Connect it to WordPress

1. Push the complete RFI map project repository to your Git host.
2. Copy the raw HTTPS URL of this directory's `map-config.json`. For GitHub it
   resembles: `https://raw.githubusercontent.com/ORG/REPO/main/rfi-interactive-map/data/map-config.json`.
3. In WordPress, open **Settings → RFI Map** and paste that URL into **Raw
   manifest URL**.
4. Add `[rfi_interactive_map]` to a page.

The plugin keeps a bundled manifest as a fallback. A shortcode can override the
site-wide setting for one map:

```text
[rfi_interactive_map data_url="https://example.org/map-data/map-config.json" height="720px"]
```

## Publishing an update

1. Export web layers as WGS 84 / EPSG:4326 GeoJSON.
2. Add or replace files inside this repository without changing established
   paths when possible. The builder now copies browser-ready inputs here by
   default and rejects external project-data URLs. The configured satellite
   basemap is the sole hosted-data exception.
3. Update `map-config.json` when a layer name, path, style, or default visibility
   changes.
4. Run `./rfi-interactive-map/data/validate-map-data.ps1` from the repository
   root in PowerShell.
5. Commit and push from the root repository. The WordPress map reads the new revision on its next page
   load; no plugin upload is required.

Use Git LFS for large raster files so the data remains versioned with the
repository without inflating ordinary Git history.
