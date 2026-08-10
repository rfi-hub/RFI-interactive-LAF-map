# RFI Interactive Map

An end-user WordPress map for land use, rivers, infrastructure, elevation, and
plant-health imagery. Map data is versioned in this project's Git repository,
so a hosted raw manifest can update the WordPress view without a plugin release.

The top navigation is the map's layer selector. Land use is selected on load;
selecting Elevation and watershed, Monkey study, or Environmental health analysis hides the
previous category and displays only layers assigned to the new category. The
selected category stays highlighted. Use the manifest's optional `section`
field to place a layer or overlay in one of those categories.

## WordPress installation

The root repository [`README.md`](../README.md) contains the complete
GitHub-to-WordPress procedure, including plugin ZIP creation, raw manifest URL
configuration, updates, and troubleshooting.

1. Copy `rfi-interactive-map` into `wp-content/plugins/` and activate **RFI
   Interactive Map**.
2. Add `[rfi_interactive_map]` to a page.
3. Optionally open **Settings → RFI Map** and paste the raw `map-config.json`
   URL from the published root repository. If this is left empty, the plugin
   uses its bundled data.

Shortcode options:

```text
[rfi_interactive_map height="720px" title="Interactive map"]
[rfi_interactive_map data_url="https://raw.githubusercontent.com/ORG/REPO/main/rfi-interactive-map/data/map-config.json"]
```

The public map includes an exclusive top category selector, parcel profile
popups, legends, plant-health timeline controls, keyboard focus states, and a
bundled-data fallback. The satellite basemap and RFI boundary are permanent and
remain visible while category layers change.

On desktop-width maps, opening a land-use parcel places its profile in the
right half of the map while preserving the current map center and zoom level.
Narrow screens retain the compact anchored popup layout so parcel details
remain readable.
The refreshed Infrastructure layer contains 11 polygons. Its `cabanas` and
singular `stable` profiles load their matching photographs from the tracked
`data/media/infrastructure/` directory.
Land-use parcel profiles load matching repository photographs from the
`data/media/landuse/` timber, infrastructure, pasture, secondary-forest,
conventional-agriculture, and syntropic folders. Multi-image parcels use a
popup carousel; Syntropic 2 currently provides four views. Image filenames
are retained only as configuration metadata and are not drawn over photos.

## Repository-backed map data

The `data/` directory is tracked by the main RFI map repository being created
for the developer and end-user views. Its [`README.md`](data/README.md)
documents the manifest contract, validation, and publishing flow. In short:

```powershell
Set-Location .\rfi-interactive-map\data
.\validate-map-data.ps1
Set-Location ..\..
git push
```

Direct browser loading is intended for public map data. A private Git
repository needs an authenticated server-side proxy; never expose a repository
token in WordPress page markup or JavaScript.

## Local preview

From the workspace:

```powershell
& "C:\Program Files\QGIS 3.40.15\bin\python-qgis-ltr.bat" .\serve_rfi_map.py --map-dir .\rfi-interactive-map --open
```

Then open `http://localhost:8000/` for the end-user view or
`http://localhost:8000/preview/` for the developer/test view.

## Regenerating source data

The existing Python builder can export new browser-ready data from QGIS and
satellite inputs. Commit the root repository before regenerating. The builder
updates generated data while preserving the authoritative UI and WordPress
settings stored in this directory.
