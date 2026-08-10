# Repository layout

This repository is the single source of truth for the RFI map's active source
data, browser-ready data, deployable end-user map, and core maintenance tools.

```text
RFI map/
|-- index.html                 Static-host landing page
|-- README.md                  Setup, development, and deployment guide
|-- docs/                      Architecture and operating notes
|-- build_rfi_map.py           Map-data localization/build tool
|-- serve_rfi_map.py           Local preview server
|-- tests/                     Automated tests
|-- vendor/                    Builder dependency copied into the map bundle
`-- rfi-interactive-map/       Deployable application bundle
    |-- index.html             Clean end-user static view
    |-- preview/index.html     Developer/debug view
    |-- assets/                Shared JavaScript, CSS, and Leaflet rotation code
    |-- data/                  Browser-ready config, GeoJSON, and raster previews
    `-- rfi-interactive-map.php  WordPress plugin entry point
```

## Where new files belong

| File type | Repository location | Commit to Git? |
|---|---|---|
| Core map build/preview code | Repository root | Yes |
| Builder dependencies | `vendor/` | Yes when imported by `build_rfi_map.py` |
| Automated tests | `tests/` | Yes |
| Documentation and decisions | `docs/` | Yes |
| Active browser-ready GeoJSON | `rfi-interactive-map/data/laf-user-view-map/` or `data/qgis/` | Yes when referenced by the manifest |
| Active source GeoPackage/GeoJSON | `rfi-interactive-map/data/source/` | Yes when referenced by the manifest |
| Active environmental PNGs | `rfi-interactive-map/data/satellite/timeline/` | Yes when referenced by the manifest |
| Map configuration | `rfi-interactive-map/data/map-config.json` | Yes |
| Shared end-user and developer JavaScript/CSS | `rfi-interactive-map/assets/` | Yes |
| Developer-only HTML shell | `rfi-interactive-map/preview/` | Yes |
| End-user static HTML shell | `rfi-interactive-map/index.html` | Yes |
| WordPress entry point | `rfi-interactive-map/rfi-interactive-map.php` | Yes |
| Python caches, secrets, editor state, logs | Local working tree only | No; covered by `.gitignore` |

Working outputs, raw analysis workspaces, superseded exports, auxiliary raster
sidecars, and unrelated tools belong in an external backup rather than the
deployable Git repository. The complete `data/media/landuse/` directory is an
explicit retention exception and must not be pruned based on manifest use.

The `rfi-interactive-map/` directory must remain self-contained: every map-data
URL used for project-specific layers, imagery, or downloads must resolve within
that directory. Runtime code may still come from an explicit library CDN, and
an explicitly configured global basemap may use a hosted tile service. The
satellite basemap is the only current hosted-data exception.

## Development view versus end-user view

Both views intentionally load the same `assets/` and `data/`. Changes to map
behavior therefore appear in both views without maintaining duplicate code.

- Developer view: `http://127.0.0.1:8000/preview/`
- End-user view: `http://127.0.0.1:8000/`

The developer/test path renders the same complete controls as the public page,
which keeps local testing faithful to the deployed experience. The end-user
view is the entry point to deploy through static hosting. WordPress renders the
same shared application through the plugin shortcode.
