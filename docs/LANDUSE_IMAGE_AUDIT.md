# Land-use popup image audit

Updated 2026-08-09 from the nested folders in `landuse images/` and the
repository GeoPackages. The top-level folder selects the GeoPackage group and
the nested folder selects the parcel popup.

## Coverage

- The complete source tree was scanned recursively: 93 image files across all
  nested folders.
- After consolidating 10 exact duplicate files and four RAW/JPG camera pairs,
  79 unique captures remained. A normalized pixel comparison verified that all
  79 have a corresponding optimized image inside the repository.
- 52 land-use polygons were audited.
- All 40 clickable polygons that display an image pane now have at least one
  matching repository image.
- No visible image panes are empty, and no configured image references point to
  missing files.
- Twelve polygons intentionally have no image pane: the ten unclickable bamboo
  polygons, Main road, and Riparian area.

## Newly populated parcel folders

- Timber: Balsa.
- Pastures: Semango Pasture.
- Syntropic: Loma de Amarillos, Moral Fino, Loma Guachapeli, Loma Terraces,
  and Loma de Curcuma (sourced from the `loma de los aguacates` folder).
- Conventional agriculture: the two Mandarin-cacao parcels received the new
  folder images and DNG-derived web previews.

## Images reused by multiple polygons

- The two Balsa images are shared by all three Balsa polygons because the
  source filenames do not identify individual feature IDs.
- `media/landuse/pasture/pasture.jpg` is shared by the two Pasture polygons.
- `media/landuse/conventional-agriculture/mandarin-cacao.jpg` is shared by the
  two Mandarin-cacao polygons; parcel-specific images are also included in
  their respective galleries.

## Source duplicates and non-image files

- `syntropic/loma nueva/loma nueva 2.JPG` and `loma nueva.JPG` are
  byte-for-byte duplicates. The popup shows one optimized copy rather than the
  same photograph twice.
- `infrastructure/main buildin.JPG` and `main building 1..JPG` are
  byte-for-byte duplicates and likewise use one optimized copy.
- `syntropic/syntropic 1 and 2 sky view.MP4` is a video, so it is not assigned
  to the image-only popup carousel.
