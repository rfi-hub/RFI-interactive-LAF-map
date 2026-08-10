# Deployment and device transfer

## Use on another device

1. Install Git and clone the remote repository.
2. From the cloned repository root, run:

   ```powershell
   py .\serve_rfi_map.py --map-dir .\rfi-interactive-map
   ```

3. Open the end-user view at `http://127.0.0.1:8000/` or the developer view at
   `http://127.0.0.1:8000/preview/`.

The browser view needs no Python packages beyond the standard library. The GIS
build scripts that import `osgeo` and `numpy` should be run with a QGIS Python
environment, as described in the main README.

## Host as a static repository website

The root `index.html` forwards to `rfi-interactive-map/index.html`, so a service
that publishes the repository root can serve the end-user map directly. For
GitHub Pages, configure Pages to deploy the `main` branch from `/ (root)`.

Static hosting serves the HTML, CSS, JavaScript, GeoJSON, JSON, and PNG files in
the repository. PHP is not executed on static hosts. Leaflet is currently loaded
from `unpkg.com`, so visitors need internet access even if all map data is local.

## Host in WordPress

Copy the complete `rfi-interactive-map/` directory to
`wp-content/plugins/rfi-interactive-map/`, activate **RFI Interactive Map**, and
place `[rfi_interactive_map]` on a WordPress page.

## Publishing future changes

After editing shared assets or data, verify both URLs locally. Commit and push
the source and the updated `rfi-interactive-map/` bundle together so another
device receives a matching application and dataset.

Common hosted Git providers reject individual files around 100 MB. Before adding
large rasters or drone video, use Git LFS or external object storage and record
the durable download location in `docs/`.
