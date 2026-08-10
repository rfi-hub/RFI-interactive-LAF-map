# RFI Map

Portable, self-contained repository for the RFI map's end-user view, developer
preview, active GIS data, source-data provenance, and WordPress plugin.

## Open the map locally

From the repository root:

```powershell
py .\serve_rfi_map.py --map-dir .\rfi-interactive-map
```

- End-user view: `http://127.0.0.1:8000/`
- Developer/test view: `http://127.0.0.1:8000/preview/`

Both pages use the same JavaScript, CSS, configuration, and tracked map data.

## Repository contents

| Location | Purpose |
|---|---|
| `rfi-interactive-map/index.html` | Static end-user entry point |
| `rfi-interactive-map/preview/` | Local developer/test entry point |
| `rfi-interactive-map/assets/` | Shared application JavaScript and CSS |
| `rfi-interactive-map/data/` | Tracked config, schema, validation, GeoJSON, and satellite previews |
| `rfi-interactive-map/rfi-interactive-map.php` | WordPress plugin entry point and manifest settings |
| `build_rfi_map.py` | Map-data build and repository-localization tool |
| `serve_rfi_map.py` | Dependency-free local preview server |
| `tests/` | Automated tests |
| `docs/` | Repository layout and deployment instructions |

`rfi-interactive-map/data/` is an ordinary directory tracked directly by this
root repository. It is not a nested repository or submodule.

See [docs/REPOSITORY_LAYOUT.md](docs/REPOSITORY_LAYOUT.md) for exactly where to
place each kind of new file. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for
another-device, static-hosting, and WordPress instructions.

## Active-data policy

`rfi-interactive-map/data/map-config.json` is the dependency source of truth.
The repository retains every file referenced by its layer URLs,
`source_reference` entries, source-data inventory, media entries, and annual
environmental-analysis patterns. Legacy exports, temporary files, superseded
analysis workspaces, and auxiliary raster sidecars are kept outside this Git
working tree. The entire `data/media/landuse/` tree is retained even when an
individual image is not yet linked from the manifest.

## Build or refresh map data

Run `build_rfi_map.py` against folders containing exported QGIS data and
satellite/NDVI data. The checked-in `rfi-interactive-map/` UI shell is
authoritative; a data rebuild does not overwrite its UI or WordPress settings.

```powershell
python .\build_rfi_map.py `
  --qgis-dir .\qgis `
  --satellite-dir .\satellite `
  --output .\rfi-interactive-map
```

Browser-ready vectors and bounded raster previews are always copied into the
repository. External project-data URLs are rejected so a clone contains every
project layer, overlay, and download referenced by the active manifest. The
global satellite basemap is the only hosted-data exception.

## Add the GitHub-backed map to WordPress

The WordPress installation has two parts:

1. The `rfi-interactive-map/` plugin directory supplies the PHP shortcode and
   the map's JavaScript and CSS. This directory must be installed on the
   WordPress server.
2. The public GitHub repository supplies `map-config.json` and every relative
   data or media file referenced by it. After the initial setup, data changes
   can be published with Git without rebuilding the WordPress page.

GitHub does not execute WordPress PHP, so installing only a GitHub URL is not
enough. Conversely, the WordPress plugin does not need a separate copy of the
active dataset when it is configured to use the GitHub manifest.

### 1. Publish the repository on GitHub

Create an empty GitHub repository, then push this repository's `main` branch.
Replace the example URL with the HTTPS or SSH URL shown by GitHub:

```powershell
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

The repository must be **public** for a visitor's browser to load the map files
without credentials. Do not put a GitHub personal access token in WordPress,
the shortcode, or browser JavaScript. A private repository requires a separate
authenticated server-side proxy and is not supported by the default plugin.

Confirm that this file opens without signing in:

```text
https://raw.githubusercontent.com/OWNER/REPOSITORY/main/rfi-interactive-map/data/map-config.json
```

Use the raw-file URL above, not a GitHub page URL containing `/blob/`. The
manifest's relative paths are resolved against its directory. For example,
`landuse/landuse.geojson` is requested from the same GitHub branch under
`rfi-interactive-map/data/landuse/landuse.geojson`. This is why all referenced
GeoJSON, JSON, images, and analysis files must be committed and pushed with the
manifest.

### 2. Package and install the WordPress plugin

From the repository root, create an uploadable ZIP containing the complete
plugin directory:

```powershell
Compress-Archive -Path .\rfi-interactive-map -DestinationPath .\rfi-interactive-map.zip -Force
```

In the WordPress administrator dashboard:

1. Open **Plugins → Add New Plugin → Upload Plugin**.
2. Select `rfi-interactive-map.zip`, choose **Install Now**, and then activate
   **RFI Interactive Map**.

As an alternative, use the host's file manager, SFTP, or SSH to copy the
complete directory to:

```text
wp-content/plugins/rfi-interactive-map/
```

The PHP file must end up at
`wp-content/plugins/rfi-interactive-map/rfi-interactive-map.php`. Do not upload
GitHub's ZIP of the entire repository through **Upload Plugin** because the
plugin is nested one directory below the repository root.

### 3. Connect WordPress to the GitHub data

Use either the site-wide setting or a shortcode-specific URL.

For one GitHub source used by every map on the site:

1. In WordPress, open **Settings → RFI Map**.
2. Paste the raw manifest URL:

   ```text
   https://raw.githubusercontent.com/OWNER/REPOSITORY/main/rfi-interactive-map/data/map-config.json
   ```

3. Select **Save Changes**.

To select the repository separately on an individual page, leave the site-wide
field empty and use `data_url` in the shortcode:

```text
[rfi_interactive_map data_url="https://raw.githubusercontent.com/OWNER/REPOSITORY/main/rfi-interactive-map/data/map-config.json"]
```

The shortcode URL overrides the site-wide setting. If both are empty, the map
uses the data bundled inside the installed plugin.

### 4. Insert the map on a WordPress page

1. Open **Pages → Add New** or edit an existing page.
2. Add a **Shortcode** block.
3. Enter `[rfi_interactive_map]`.
4. Publish or update the page, then inspect the public page while signed out.

Optional shortcode attributes control the map height and accessible title:

```text
[rfi_interactive_map height="720px" title="Los Arboles Farm interactive map"]
```

The `height` value must include a supported CSS unit such as `px`, `vh`, `vw`,
`rem`, `em`, or `%`. The default is `680px`.

### 5. Publish later map-data changes

After updating QGIS exports, map configuration, photographs, or analysis
images, validate the repository and push the related files together:

```powershell
.\rfi-interactive-map\data\validate-map-data.ps1
git status --short
git add -A
git commit -m "Update RFI map data"
git push origin main
```

WordPress will continue requesting the same raw manifest URL, so no page edit
is required for ordinary data updates. GitHub and browser caches can briefly
delay a change; reload the public page without cache when checking a new push.

Changes to `rfi-interactive-map.php`, `assets/rfi-map.js`, or
`assets/rfi-map.css` are plugin-code changes, not just data changes. Rebuild the
plugin ZIP and replace/update the installed WordPress plugin when those files
change. Keep the GitHub commit and installed plugin version aligned so the
manifest is not consumed by incompatible older code.

### 6. Verify and troubleshoot the published page

- If the map uses bundled or old data, verify the saved URL under
  **Settings → RFI Map** and make sure it contains `/raw.githubusercontent.com/`
  rather than `/github.com/.../blob/`.
- If the map is blank, open the raw manifest URL in a private browser window.
  A `404` usually means the owner, repository, branch, capitalization, or file
  path is incorrect.
- If only one layer or image is missing, open its repository path and confirm
  that it was committed and pushed. GitHub paths are case-sensitive.
- If WordPress rejects the manifest setting, confirm that it is a complete
  public `https://` URL; the plugin deliberately rejects HTTP URLs.
- If a security or optimization plugin blocks the requests, allow HTTPS
  connections to `raw.githubusercontent.com` in its Content Security Policy or
  remote-resource rules.
- The satellite basemap and Leaflet library are externally hosted, so the
  visitor still needs internet access even though project data is stored in
  GitHub.

For a static site instead of WordPress, publish the repository's `main` branch
from the repository root. The root `index.html` forwards visitors to
`rfi-interactive-map/`. Static hosts do not execute the WordPress PHP entry
point.

## Use the repository on another device

After creating an empty remote repository on the Git host:

```powershell
git remote add origin <repository-url>
git push -u origin main
```

On the other device:

```powershell
git clone <repository-url>
cd <cloned-folder>
py .\serve_rfi_map.py --map-dir .\rfi-interactive-map
```

The active files are small enough for ordinary Git. Large future videos or raw
rasters should use Git LFS or external object storage rather than being added to
the deployable repository.

## Verify the repository

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\build_rfi_map.py .\serve_rfi_map.py
.\rfi-interactive-map\data\validate-map-data.ps1
```

## Simple WordPress website-builder walkthrough

This walkthrough explains how to place the existing map on a normal WordPress
website using the WordPress dashboard and block-based website editor. It does
not require rewriting the map as a WordPress theme. The map remains one
self-contained page component, while WordPress controls the page header,
navigation, surrounding text, footer, and overall website design.

Before beginning, make sure that:

- You can sign in to WordPress as an administrator.
- The WordPress installation or hosting plan permits custom plugins.
- This repository has been pushed to a **public** GitHub repository.
- The raw GitHub manifest opens in a browser without requiring a GitHub login.

The raw manifest address has this format:

```text
https://raw.githubusercontent.com/OWNER/REPOSITORY/main/rfi-interactive-map/data/map-config.json
```

Replace `OWNER` with the GitHub account or organization name and `REPOSITORY`
with the repository name.

### Step 1: Install the map component in WordPress

The repository contains the map as a WordPress plugin. Create the plugin ZIP
from the repository root:

```powershell
Compress-Archive -Path .\rfi-interactive-map -DestinationPath .\rfi-interactive-map.zip -Force
```

Then use the WordPress dashboard:

1. Select **Plugins → Add New Plugin**.
2. Select **Upload Plugin** near the top of the screen.
3. Choose `rfi-interactive-map.zip` from the computer.
4. Select **Install Now**.
5. When installation finishes, select **Activate Plugin**.

This adds the map shortcode and its display code to WordPress. It does not
automatically add the map to a public page yet.

### Step 2: Tell the map where its GitHub data is stored

1. In the WordPress dashboard, select **Settings → RFI Map**.
2. Paste the complete raw GitHub `map-config.json` address into **Raw manifest
   URL**.
3. Select **Save Changes**.

This setting connects the WordPress map to the repository. The configuration
file then points the map to the repository's parcel files, boundary, elevation,
watershed, monkey-study data, environmental analyses, and photographs. Because
those paths are relative to `map-config.json`, their folder structure must not
be changed after publishing unless the manifest is updated at the same time.

### Step 3: Create the map page with the WordPress block editor

1. Select **Pages → Add New Page**.
2. Enter a page title, such as **RFI Interactive Map**.
3. Select the **+** block inserter.
4. Search for **Shortcode** and add the Shortcode block. Do not use a Code block
   or Custom HTML block.
5. Paste the following into the Shortcode block:

   ```text
   [rfi_interactive_map height="780px" title="Los Arboles Farm interactive map"]
   ```

6. Use WordPress's **Preview** option to confirm that the map appears.
7. Select **Publish** when the page is ready.

The `height` value determines how tall the map appears. A value between `680px`
and `850px` works well for most desktop pages. The map automatically adapts to
narrower tablet and phone screens.

### Step 4: Give the map enough page width

The map is easiest to use when the page is full-width or wide-width:

1. With the page open in the editor, open the page **Settings** sidebar.
2. Look for **Template**, **Page layout**, or **Content width**. The exact name
   depends on the active WordPress theme.
3. Choose a **Full Width**, **Wide**, or similarly named layout when available.
4. Remove unnecessary sidebars from this page.
5. Keep a modest amount of space above and below the Shortcode block so the map
   does not touch the website header or footer.

If the theme uses the WordPress Site Editor, select **Appearance → Editor** to
adjust the page template. The website header, logo, colors, typography,
navigation, and footer can be designed there without changing the map plugin.
Avoid editing the map's internal controls in the Site Editor; those controls
are styled by `rfi-interactive-map/assets/rfi-map.css` in the repository.

### Step 5: Add the map page to the website navigation

Publishing a page does not always place it in the website menu automatically.

1. Open **Appearance → Editor → Navigation**. Some themes instead use
   **Appearance → Menus**.
2. Edit the primary navigation menu.
3. Add the newly published **RFI Interactive Map** page.
4. Choose its position in the menu and save the navigation.
5. Open the public website in a private browser window and follow the menu link
   to confirm that ordinary visitors can reach the map.

### Step 6: Check the finished page

Test the published page on both a desktop-sized window and a phone-sized
window. Confirm that:

- Satellite imagery appears behind the project layers.
- The RFI boundary is visible when the page opens.
- Land use, Elevation and watershed, Monkey study, and Environmental health
  analysis switch correctly from the top navigation.
- Parcel popups, photographs, legends, and environmental timeline controls
  work as expected.
- The WordPress header or cookie banner does not cover the map controls.

If the map frame appears but its data does not, return to **Settings → RFI
Map** and verify the raw manifest URL. If the shortcode itself appears as plain
text, confirm that **RFI Interactive Map** is activated under **Plugins** and
that a Shortcode block was used.

### Step 7: Update the map after the website is published

For changes to data, symbology settings, descriptions, or repository images,
validate, commit, and push the repository. The WordPress page and shortcode do
not need to be recreated:

```powershell
.\rfi-interactive-map\data\validate-map-data.ps1
git add -A
git commit -m "Update published RFI map"
git push origin main
```

For changes to the PHP plugin, map JavaScript, or map CSS, create a new plugin
ZIP and update the installed WordPress plugin as well. GitHub supplies the map
data, but WordPress still runs its installed copy of the plugin code.
