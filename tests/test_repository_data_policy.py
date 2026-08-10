import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_rfi_map


class RepositoryDataPolicyTests(unittest.TestCase):
    def test_active_manifest_uses_repository_laf_user_map(self):
        repository_root = Path(__file__).resolve().parents[1]
        data_root = repository_root / "rfi-interactive-map" / "data"
        config = json.loads((data_root / "map-config.json").read_text(encoding="utf-8"))
        public_html = (repository_root / "rfi-interactive-map" / "index.html").read_text(encoding="utf-8")
        preview_html = (repository_root / "rfi-interactive-map" / "preview" / "index.html").read_text(encoding="utf-8")

        self.assertEqual(len(config["layers"]), 13)
        for standalone_html in (public_html, preview_html):
            self.assertNotIn("<header", standalone_html)
            self.assertNotIn("<h1>", standalone_html)
            self.assertNotIn("Explore land use", standalone_html)
            self.assertIn("--rfi-map-height:100vh", standalone_html)
            self.assertIn("border-radius: 0", standalone_html)
        self.assertNotIn("Find me", public_html)
        self.assertNotIn("Reset view", public_html)
        self.assertTrue(config["basemaps"][0]["visible"])
        self.assertTrue(config["basemaps"][0]["locked"])
        self.assertIn("mt1.google.com/vt/lyrs=s", config["basemaps"][0]["url"])
        infrastructure = next(layer for layer in config["layers"] if layer["id"] == "laf-infrastructure")
        self.assertEqual(infrastructure["popup"]["hide_media_by_name"], ["Main road"])
        self.assertEqual(
            infrastructure["popup"]["hide_history_by_name"],
            [
                "Water tank",
                "Cacao fermentation & storage facility",
                "Massbu Microfactory",
                "Farmkeepers house",
                "Cow stables",
                "Stables",
                "Mirador",
                "Lucas oshun residence",
                "Main building",
            ],
        )
        infrastructure_media = infrastructure["popup"]["media_by_name"]
        self.assertEqual(infrastructure_media["cow stables"][0]["url"], "media/infrastructure/cow-stables-fid-7.jpg")
        self.assertEqual(infrastructure_media["Stables"][0]["url"], "media/infrastructure/stable.jpg")
        self.assertEqual(len(infrastructure_media["Stables"]), 2)
        self.assertEqual(len(infrastructure_media["cabanas"]), 3)
        self.assertEqual(len(infrastructure_media["Massbu Microfactory"]), 3)
        self.assertEqual(infrastructure_media["Water tank"][0]["url"], "media/landuse/infrastructure/water-reservoir.jpg")
        self.assertEqual(infrastructure_media["El Arbolito"][0]["url"], "media/infrastructure/el-arbolito.jpg")
        self.assertEqual(len(infrastructure_media["El Arbolito"]), 2)
        self.assertEqual(
            infrastructure_media["El Arbolito"][1]["url"],
            "media/infrastructure/el-arbolito-vertical.jpg",
        )
        infrastructure_geojson = json.loads(
            (data_root / "laf-user-view-map" / "infrastructure.geojson").read_text(encoding="utf-8")
        )
        water_tank = next(
            feature["properties"]
            for feature in infrastructure_geojson["features"]
            if feature["properties"].get("Name") == "Water tank"
        )
        self.assertEqual(
            water_tank["Usage"],
            "250 Gallon water storage unit that provides irrigation to nearby syntropics",
        )
        cacao_facility = next(
            feature["properties"]
            for feature in infrastructure_geojson["features"]
            if feature["properties"].get("Name") == "Cacao fermentation & storage facility"
        )
        self.assertEqual(
            cacao_facility["Usage"],
            "Multi stage fermentation process building with an attached storage component.",
        )
        cow_stables = next(
            feature["properties"]
            for feature in infrastructure_geojson["features"]
            if feature["properties"].get("Name") == "Cow stables"
        )
        self.assertEqual(cow_stables["Usage"], "Cow stables")
        stables = next(
            feature["properties"]
            for feature in infrastructure_geojson["features"]
            if feature["properties"].get("Name") == "Stables"
        )
        self.assertEqual(stables["_rfi_source_fid"], 10)
        self.assertEqual(stables["Usage"], "Stable for Sebastian the packmule")
        for layer in config["layers"]:
            popup = layer.get("popup", {})
            for media_map_name in ("media_by_name", "media_by_feature_index"):
                for media_items in popup.get(media_map_name, {}).values():
                    for media_item in media_items:
                        self.assertTrue((data_root / media_item["url"]).is_file(), media_item["url"])
        for layer in config["layers"]:
            if layer.get("section") != "land-use" or layer.get("interactive") is False:
                continue
            popup = layer.get("popup", {})
            if popup.get("hide_media"):
                continue
            hidden_names = {name.casefold() for name in popup.get("hide_media_by_name", [])}
            geojson = json.loads((data_root / layer["url"]).read_text(encoding="utf-8"))
            media_by_name = popup.get("media_by_name", {})
            for feature_index, feature in enumerate(geojson["features"], start=1):
                properties = feature.get("properties", {})
                feature_name = str(properties.get("Name") or "")
                if feature_name.casefold() in hidden_names:
                    continue
                matching_name = next(
                    (name for name in media_by_name if name.casefold() == feature_name.casefold()),
                    None,
                )
                media_items = (
                    media_by_name.get(matching_name, [])
                    or popup.get("media_by_feature_index", {}).get(str(feature_index), [])
                    or properties.get("_rfi_media", [])
                )
                self.assertTrue(media_items, f"Visible image pane is empty: {layer['name']} / {feature_name}")
        boundary = next(layer for layer in config["layers"] if layer["primary_boundary"])
        self.assertEqual(boundary["id"], "rfi-map-border")
        self.assertTrue(boundary["locked"])
        self.assertTrue(boundary["zoom_on_load"])
        self.assertEqual(boundary["style"]["color"], "#0ecce1")
        self.assertEqual(boundary["style"]["weight"], 3.63)
        self.assertEqual(boundary["style"]["line_cap"], "square")
        self.assertEqual(boundary["style"]["line_join"], "bevel")
        self.assertEqual(boundary["style"]["qgis_renderer"], "singleSymbol:SimpleLine")
        self.assertEqual(boundary["style"]["qgis_line_color_rgba"], "14,204,225,255")
        self.assertEqual(boundary["style"]["qgis_line_width_mm"], 0.96)
        self.assertEqual(boundary["style"]["qgis_line_style"], "solid")

        expected_counts = {
            "bamboo.geojson": 10,
            "conventional-agriculture.geojson": 3,
            "infrastructure.geojson": 12,
            "laf-dem-formap.geojson": 70,
            "laf-border.geojson": 1,
            "howler-monkey-sighting-points.geojson": 12,
            "howler-monkey-study-transects.geojson": 3,
            "rivers_reproj.geojson": 50,
            "pastures.geojson": 6,
            "riparian-area.geojson": 1,
            "secondary-forest.geojson": 3,
            "syntropic.geojson": 12,
            "timber.geojson": 5,
        }
        capitalized_popup_fields = {
            "Name", "Title", "Land-use parcel",
            "Landuse description", "Land use description", "Description", "Insights", "Usage",
            "Past use history", "Past usage", "Past use", "History",
        }
        for layer in config["layers"]:
            web_path = data_root / layer["url"]
            source_path = data_root / layer["source_reference"]
            self.assertTrue(web_path.is_file(), web_path)
            self.assertTrue(source_path.is_file(), source_path)
            geojson = json.loads(web_path.read_text(encoding="utf-8"))
            self.assertEqual(len(geojson["features"]), expected_counts[web_path.name])
            for feature_index, feature in enumerate(geojson["features"], start=1):
                for field, value in feature.get("properties", {}).items():
                    if field not in capitalized_popup_fields or not isinstance(value, str) or not value.strip():
                        continue
                    first_letter = next((character for character in value if character.isalpha()), "")
                    self.assertTrue(
                        not first_letter or first_letter.isupper(),
                        f"{web_path.name} feature {feature_index} field {field} must begin with a capital letter: {value!r}",
                    )
            if layer.get("style", {}).get("kind") == "qgis-polygon":
                self.assertEqual(layer["style"]["fill_opacity"], 0.75)

        contours = next(layer for layer in config["layers"] if layer["id"] == "laf-dem-formap")
        self.assertEqual(contours["section"], "contours")
        self.assertEqual(contours["style"]["field"], "ELEV_MAX")
        self.assertEqual(contours["style"]["colours"], ["#d7191c", "#fdae61", "#ffffbf", "#abdda4", "#2b83ba"])
        self.assertEqual(contours["style"]["outline_color"], "#232323")
        self.assertEqual(contours["style"]["weight"], 0.245)
        rivers = next(layer for layer in config["layers"] if layer["id"] == "laf-river-network")
        self.assertEqual(rivers["section"], "contours")
        self.assertEqual(rivers["style"]["kind"], "watershed-rivers")
        self.assertEqual(rivers["style"]["color"], "#00d4ff")
        self.assertEqual(rivers["legend"]["items"][0]["label"], "River network")
        self.assertEqual(rivers["source_reference"], "source/laf-user-view-map/rivers.geojson")
        riparian = next(layer for layer in config["layers"] if layer["id"] == "laf-riparian-area")
        self.assertEqual(riparian["name"], "Riparian area (10 m)")
        self.assertTrue(riparian["visible"])
        self.assertEqual(riparian["style"]["kind"], "qgis-line-pattern-fill")
        self.assertEqual(riparian["style"]["pattern_color"], "#1b87dd")
        self.assertEqual(riparian["style"]["pattern_angle"], 135)
        self.assertFalse(riparian["style"]["pattern_crosshatch"])
        self.assertEqual(riparian["style"]["fill_opacity"], 0.75)
        self.assertEqual(riparian["style"]["qgis_pattern_distance_mm"], 2)
        self.assertEqual(riparian["style"]["qgis_pattern_line_width_mm"], 0.3)
        self.assertEqual(riparian["style"]["outline_color"], "#00bcff")
        self.assertEqual(riparian["style"]["weight"], 1.89)
        self.assertEqual(riparian["style"]["qgis_outline_width_mm"], 0.5)
        self.assertEqual(riparian["popup"]["title"], "Riparian area")
        self.assertIn("transition zones along watercourses or water bodies", riparian["popup"]["description"])
        self.assertIn("nrcs.usda.gov", riparian["popup"]["description_source_url"])
        self.assertTrue(riparian["popup"]["hide_composition"])
        self.assertTrue(riparian["popup"]["hide_history"])
        self.assertTrue(riparian["popup"]["hide_media"])
        riparian_geojson = json.loads(
            (data_root / "laf-user-view-map" / "riparian-area.geojson").read_text(encoding="utf-8")
        )

        def coordinate_points(value):
            if (
                isinstance(value, list)
                and len(value) >= 2
                and all(isinstance(coordinate, (int, float)) for coordinate in value[:2])
            ):
                yield value
                return
            if isinstance(value, list):
                for child in value:
                    yield from coordinate_points(child)

        riparian_points = list(coordinate_points(riparian_geojson["features"][0]["geometry"]["coordinates"]))
        self.assertEqual(len(riparian_points), 1671)
        self.assertEqual(
            tuple(round(value, 8) for value in (
                min(point[0] for point in riparian_points),
                min(point[1] for point in riparian_points),
                max(point[0] for point in riparian_points),
                max(point[1] for point in riparian_points),
            )),
            (-80.04767307, -0.5763495, -80.04242568, -0.56928006),
        )
        rivers_geojson = json.loads(
            (data_root / "qgis" / "rivers_reproj.geojson").read_text(encoding="utf-8")
        )
        river_features = [feature for feature in rivers_geojson["features"] if feature.get("geometry")]
        river_points = [
            point
            for feature in river_features
            for point in coordinate_points(feature["geometry"]["coordinates"])
        ]
        self.assertEqual(len(rivers_geojson["features"]), 50)
        self.assertEqual(len(river_features), 25)
        self.assertEqual(len(river_points), 808)
        self.assertEqual(
            tuple(round(value, 8) for value in (
                min(point[0] for point in river_points),
                min(point[1] for point in river_points),
                max(point[0] for point in river_points),
                max(point[1] for point in river_points),
            )),
            (-80.04758321, -0.57626012, -80.04251554, -0.56937052),
        )
        qgis_fill_colours = {
            "laf-timber": "#a96952",
            "laf-infrastructure": "#f3a6b2",
            "laf-secondary-forest": "#00882a",
            "laf-pastures": "#e5b636",
            "laf-conventional-agriculture": "#b7093f",
            "laf-syntropic": "#987db7",
        }
        for layer_id, colour in qgis_fill_colours.items():
            layer = next(layer for layer in config["layers"] if layer["id"] == layer_id)
            self.assertEqual(layer["style"]["fill_color"], colour)
        bamboo = next(layer for layer in config["layers"] if layer["id"] == "laf-bamboo")
        self.assertTrue(bamboo["visible"])
        self.assertFalse(bamboo["interactive"])
        self.assertTrue(bamboo["show_in_legend"])
        self.assertEqual(bamboo["style"]["kind"], "qgis-line-pattern-fill")
        self.assertEqual(bamboo["style"]["pattern_color"], "#00ff51")
        self.assertEqual(bamboo["style"]["pattern_angle"], 45)
        self.assertEqual(bamboo["style"]["qgis_pattern_distance_mm"], 2)
        self.assertEqual(bamboo["style"]["qgis_pattern_line_width_mm"], 0.3)
        self.assertEqual(bamboo["style"]["qgis_outline_width_mm"], 0.46)
        self.assertEqual(bamboo["style"]["qgis_line_style"], "dash dot")
        syntropic = next(layer for layer in config["layers"] if layer["id"] == "laf-syntropic")
        self.assertEqual(syntropic["source_reference"], "source/laf-user-view-map/syntropic with census.gpkg")
        self.assertIn("source/laf-user-view-map/syntropic.gpkg", config["sources"]["data_references"])
        self.assertTrue((data_root / "source" / "laf-user-view-map" / "syntropic.gpkg").is_file())
        census_strata = syntropic["popup"]["census_strata_by_species"]
        self.assertEqual(len(census_strata), 27)
        self.assertEqual(census_strata["Cacao"], {"source": "Middle", "display": "Medium"})
        self.assertEqual(census_strata["Trichanthera"], {"source": "variable", "display": "Low"})
        self.assertEqual(census_strata["Jaboncillo"], {"source": "mid/high", "display": "High"})
        syntropic_media = syntropic["popup"]["media_by_name"]
        self.assertEqual(len(syntropic_media["Syntropic 1"]), 1)
        self.assertEqual(len(syntropic_media["Syntropic 2"]), 5)
        self.assertEqual(len(syntropic_media["syntropic 3"]), 1)
        self.assertEqual(len(syntropic_media["Loma Nueva"]), 1)
        self.assertEqual(len(syntropic_media["Loma de La Cancha"]), 1)
        self.assertEqual(len(syntropic_media["Loma de Amarillos"]), 3)
        self.assertEqual(len(syntropic_media["Moral Fino"]), 2)
        self.assertEqual(len(syntropic_media["Loma Guachapeli"]), 3)
        self.assertEqual(len(syntropic_media["Loma Terraces"]), 7)
        self.assertEqual(len(syntropic_media["Loma de Curcuma"]), 1)
        self.assertEqual(len(syntropic_media["Syntropic Taller de mauro"]), 2)
        self.assertEqual(len(syntropic_media["syntropic taller de mauro 2"]), 1)
        for items in syntropic_media.values():
            for item in items:
                self.assertTrue((data_root / item["url"]).is_file(), item["url"])
        timber = next(layer for layer in config["layers"] if layer["id"] == "laf-timber")
        self.assertEqual(len(timber["popup"]["media_by_name"]["Balsa"]), 2)
        self.assertEqual(len(timber["popup"]["media_by_name"]["Baby teak"]), 2)
        pastures = next(layer for layer in config["layers"] if layer["id"] == "laf-pastures")
        self.assertEqual(len(pastures["popup"]["media_by_name"]["Semango Pasture"]), 1)
        self.assertEqual(len(pastures["popup"]["media_by_name"]["Silvopasture"]), 2)
        conventional = next(layer for layer in config["layers"] if layer["id"] == "laf-conventional-agriculture")
        self.assertEqual(len(conventional["popup"]["media_by_name"]["Mandarin-cacao"]), 2)
        self.assertEqual(len(conventional["popup"]["media_by_name"]["Mandarin Cacao"]), 3)
        self.assertEqual(len(conventional["popup"]["media_by_name"]["Orange & Cacao"]), 2)
        conventional_geojson = json.loads(
            (data_root / "laf-user-view-map" / "conventional-agriculture.geojson").read_text(encoding="utf-8")
        )
        conventional_by_name = {
            feature["properties"]["Name"]: feature["properties"]
            for feature in conventional_geojson["features"]
        }
        self.assertEqual(conventional_by_name["Orange & Cacao"]["Landuse description"], "Mixed orange and cacao")
        self.assertEqual(conventional_by_name["Orange & Cacao"]["Past use history"], "Pasture")
        for feature_name in ("Mandarin-cacao", "Mandarin Cacao"):
            self.assertEqual(
                conventional_by_name[feature_name]["Landuse description"],
                "Mixed mandarin and cacao",
            )
            self.assertEqual(conventional_by_name[feature_name]["Past use history"], "Pasture")
        secondary = next(layer for layer in config["layers"] if layer["id"] == "laf-secondary-forest")
        secondary_media = secondary["popup"]["media_by_feature_index"]
        self.assertIn("bamboo-enriched-next-to-syntropic-3.jpg", secondary_media["2"][0]["url"])
        self.assertIn("secondary-forest-next-to-teak.jpg", secondary_media["3"][0]["url"])
        secondary_geojson = json.loads(
            (data_root / "laf-user-view-map" / "secondary-forest.geojson").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {feature["properties"]["Landuse description"] for feature in secondary_geojson["features"]},
            {"Forest regenerated through largely natural processes after human disturbances."},
        )
        self.assertEqual(
            {feature["properties"]["Past use history"] for feature in secondary_geojson["features"]},
            {"Pasture"},
        )
        syntropic_geojson = json.loads(
            (data_root / "laf-user-view-map" / "syntropic.geojson").read_text(encoding="utf-8")
        )
        census_by_name = {
            feature["properties"]["Name"]: feature["properties"].get("Plant census")
            for feature in syntropic_geojson["features"]
        }
        self.assertEqual(len(census_by_name), 12)
        loma_de_la_cancha = next(
            feature for feature in syntropic_geojson["features"]
            if feature["properties"].get("_rfi_source_fid") == 3
        )
        self.assertEqual(
            sum(
                len(ring)
                for polygon in loma_de_la_cancha["geometry"]["coordinates"]
                for ring in polygon
            ),
            46,
        )
        self.assertEqual(
            loma_de_la_cancha["geometry"]["coordinates"][0][0][0],
            [-80.0453359, -0.5716504],
        )
        details_by_name = {
            feature["properties"]["Name"]: feature["properties"]
            for feature in syntropic_geojson["features"]
        }
        self.assertTrue(all(properties.get("Landuse description") for properties in details_by_name.values()))
        self.assertTrue(all(properties.get("Past use history") for properties in details_by_name.values()))
        self.assertEqual(details_by_name["Syntropic 1"]["Past use history"], "Mandarins and cacao")
        self.assertIn("Recently cleared area", details_by_name["Syntropic 3"]["Landuse description"])
        census_tree_types = {
            row.split("\t")[0].strip().casefold()
            for census in census_by_name.values()
            if census
            for row in census.splitlines()
            if row.split("\t")[0].strip()
        }
        self.assertEqual(census_tree_types, {name.casefold() for name in census_strata})
        self.assertIn("Cacao\t105", census_by_name["Loma Guachapeli"])
        self.assertEqual(
            sum(
                int(row.split("\t")[1])
                for row in census_by_name["Loma Guachapeli"].splitlines()
                if len(row.split("\t")) > 1 and row.split("\t")[1].strip()
            ),
            681,
        )

        infrastructure = json.loads(
            (data_root / "laf-user-view-map" / "infrastructure.geojson").read_text(encoding="utf-8")
        )
        infrastructure_by_name = {
            feature["properties"]["Name"].casefold(): feature for feature in infrastructure["features"]
        }
        self.assertIn("open air lookout", infrastructure_by_name["mirador"]["properties"]["Usage"])
        self.assertIn("irrigation", infrastructure_by_name["water tank"]["properties"]["Usage"])
        self.assertEqual(infrastructure_by_name["el arbolito"]["properties"]["_rfi_source_fid"], 12)
        self.assertEqual(infrastructure_by_name["el arbolito"]["properties"]["Date added"], "2026-07-25")
        self.assertIn("edible produce", infrastructure_by_name["el arbolito"]["properties"]["Usage"])
        pastures_geojson = json.loads(
            (data_root / "laf-user-view-map" / "pastures.geojson").read_text(encoding="utf-8")
        )
        self.assertTrue(all(feature["properties"].get("Landuse description") for feature in pastures_geojson["features"]))
        self.assertEqual(
            {feature["properties"]["Landuse description"] for feature in pastures_geojson["features"]},
            {"Used in a grazing rotation for the cows and other stable animals on the farm"},
        )
        self.assertEqual(
            {feature["properties"]["Past use history"] for feature in pastures_geojson["features"]},
            {"Pasture"},
        )
        timber_geojson = json.loads(
            (data_root / "laf-user-view-map" / "timber.geojson").read_text(encoding="utf-8")
        )
        timber_by_name = {feature["properties"]["Name"]: feature["properties"] for feature in timber_geojson["features"]}
        self.assertIn("dimensional timber", timber_by_name["Big Teak"]["Landuse description"])
        self.assertEqual(
            timber_by_name["Baby teak"]["Landuse description"],
            timber_by_name["Big Teak"]["Landuse description"],
        )
        self.assertTrue(all(feature["properties"].get("Past use history") for feature in timber_geojson["features"]))

        monkey_layers = [layer for layer in config["layers"] if layer.get("section") == "monkey-study"]
        self.assertEqual(len(monkey_layers), 2)
        monkey_styles = {layer["style"]["kind"] for layer in monkey_layers}
        self.assertEqual(monkey_styles, {"monkey-transects", "monkey-heatmap"})
        sightings = next(layer for layer in monkey_layers if layer["style"]["kind"] == "monkey-heatmap")
        self.assertEqual(sightings["style"]["radius"], 38)
        self.assertEqual(len(sightings["style"]["colours"]), 9)
        self.assertEqual(sightings["style"]["colours"][0], "#fff5f0")
        self.assertEqual(sightings["style"]["colours"][-1], "#67000d")
        self.assertEqual(sightings["style"]["qgis_renderer"], "heatmapRenderer")
        self.assertEqual(sightings["style"]["qgis_radius_mm"], 10)
        transects = next(layer for layer in monkey_layers if layer["style"]["kind"] == "monkey-transects")
        self.assertEqual(transects["style"]["color"], "#fab519")
        self.assertEqual(transects["style"]["color_field"], "color")
        self.assertEqual(
            transects["style"]["feature_colors"],
            {"T1": "#00E5FF", "T2": "#FF4FD8", "T3": "#FFE34D"},
        )
        self.assertEqual(transects["style"]["qgis_line_width_mm"], 0.26)
        self.assertEqual(transects["style"]["weight"], 1.18)
        self.assertEqual(transects["style"]["display_width_multiplier"], 1.2)
        self.assertEqual(
            [item["label"] for item in sightings["legend"]["items"]],
            ["Transect T1", "Transect T2", "Transect T3", "Frequency of monkey observations"],
        )
        self.assertEqual(
            [item["color"] for item in sightings["legend"]["items"][:3]],
            ["#00E5FF", "#FF4FD8", "#FFE34D"],
        )
        self.assertEqual(sightings["legend"]["items"][3]["shape"], "heat")

        environmental = config["environmental_health"]
        self.assertEqual(environmental["section"], "environmental-health-analysis")
        self.assertEqual(environmental["years"], list(range(2019, 2027)))
        self.assertEqual(
            [analysis["metric"] for analysis in environmental["analyses"]],
            ["NDVI", "EVI", "MIR_reflectance", "NDMI", "Health_score"],
        )
        descriptions = {
            analysis["metric"]: analysis["legend"]["description"]
            for analysis in environmental["analyses"]
        }
        self.assertEqual(
            descriptions["NDVI"],
            "Shows how green and actively growing the vegetation is. Higher values usually mean denser, healthier plant cover. Lower values may indicate bare soil, water, recently cleared land, or stressed vegetation.",
        )
        self.assertEqual(
            descriptions["EVI"],
            "Shows how strongly vegetation is growing, especially where plant cover is thick. It is similar to NDVI but is better at showing differences in dense vegetation and is less affected by haze or visible soil.",
        )
        self.assertEqual(
            descriptions["MIR_reflectance"],
            "Highlights how dry or exposed the land surface is. Higher values usually mean drier vegetation, bare soil, or less moisture. Lower values usually indicate wetter ground or denser plant cover.",
        )
        self.assertEqual(
            descriptions["NDMI"],
            "Shows how much moisture is held in vegetation and the near-surface land. Higher values indicate wetter plant canopies and ground conditions, while lower values suggest dryness or possible water stress.",
        )
        referenced_images = []
        for analysis in environmental["analyses"]:
            self.assertNotIn("overview_url", analysis)
            referenced_images.extend(
                data_root / analysis["timeline_url"].replace("{year}", str(year))
                for year in environmental["years"]
            )
            self.assertEqual(len(analysis["legend"]["stops"]), 5)
        self.assertEqual(len(referenced_images), 40)
        for image in referenced_images:
            self.assertTrue(image.is_file(), image)

        script = (repository_root / "rfi-interactive-map" / "assets" / "rfi-map.js").read_text(encoding="utf-8")
        self.assertIn("config.environmental_health", script)
        self.assertIn("className: 'rfi-primary-boundary-feature'", script)
        self.assertIn("lineCap: layer.style.line_cap || 'round'", script)
        self.assertIn("lineJoin: layer.style.line_join || 'round'", script)
        self.assertIn("activeSection !== 'environmental-health-analysis'", script)
        self.assertIn("analysis.timeline_url.replace('{year}'", script)
        self.assertIn("rfi-timeline__description", script)
        self.assertIn("analysis.legend.description", script)
        self.assertNotIn("Overall median", script)
        self.assertNotIn("mouseover: event =>", script)
        self.assertNotIn("geojson.resetStyle(event.target)", script)
        self.assertIn("className: 'rfi-landuse-feature'", script)
        self.assertIn("const layerClassFor = layer =>", script)
        self.assertIn("className: `rfi-landuse-feature ${layerClassFor(layer)}`", script)
        hover_styles = (repository_root / "rfi-interactive-map" / "assets" / "rfi-map.css").read_text(encoding="utf-8")
        self.assertIn(".rfi-landuse-feature:hover", hover_styles)
        self.assertIn("fill: #fff36b !important", hover_styles)
        self.assertIn("layer.style?.kind === 'monkey-transects'", script)
        self.assertIn("const createMonkeyHeatLayer = (data, style = {})", script)
        self.assertIn("layer.style?.kind === 'monkey-heatmap'", script)
        self.assertIn("rfi-monkey-heatmap", script)
        self.assertIn("rfi-monkey-transect", script)
        self.assertIn("weight: (layer.style.weight ?? .983) * (layer.style.display_width_multiplier ?? 1)", script)
        self.assertIn("bubblingMouseEvents: false", script)
        self.assertIn("clearMonkeyTransectSelection", script)
        self.assertIn("rfi-monkey-transect--selected", script)
        self.assertIn("rfi-legend__symbol--${shape}", script)
        self.assertIn(".rfi-legend__symbol--line", hover_styles)
        self.assertIn(".rfi-legend__symbol--heat", hover_styles)
        self.assertIn(".rfi-legend__heat-labels", hover_styles)
        self.assertIn(".rfi-monkey-transect { outline: none; filter: drop-shadow", hover_styles)
        self.assertNotIn(".rfi-monkey-transect:hover", hover_styles)
        self.assertIn(".rfi-monkey-transect--selected", hover_styles)
        self.assertIn(".rfi-monkey-transect:focus", hover_styles)

    def test_build_includes_satellite_xyz_basemap(self):
        with tempfile.TemporaryDirectory() as output_name:
            with patch("sys.argv", ["build_rfi_map.py", "--output", output_name]):
                build_rfi_map.main()

            config = json.loads((Path(output_name) / "data" / "map-config.json").read_text(encoding="utf-8"))
            self.assertEqual(len(config["basemaps"]), 1)
            basemap = config["basemaps"][0]
            self.assertEqual(basemap["type"], "xyz")
            self.assertIn("mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", basemap["url"])
            self.assertTrue(basemap["visible"])
            self.assertIn("Google", basemap["attribution"])
            public_html = (Path(output_name) / "index.html").read_text(encoding="utf-8")
            for section_name in ("Land use", "Elevation and watershed", "Monkey study", "Environmental health analysis"):
                self.assertIn(section_name, public_html)
        self.assertNotIn("rfi-map__layers-tab", public_html)
        self.assertIn("rfi-map__layer-store", public_html)
        self.assertIn('data-rfi-section="land-use" aria-pressed="true"', public_html)
        self.assertNotIn('class="rfi-map__toolbar"', public_html)
        self.assertIn('rfi-map__status screen-reader-text', public_html)

    def test_parcel_popup_template_is_shipped_with_the_authoritative_shell(self):
        repository_root = Path(__file__).resolve().parents[1]
        script = (repository_root / "rfi-interactive-map" / "assets" / "rfi-map.js").read_text(encoding="utf-8")
        stylesheet = (repository_root / "rfi-interactive-map" / "assets" / "rfi-map.css").read_text(encoding="utf-8")

        for section_name in ("No image available", "Past use history"):
            self.assertIn(section_name, script)
        self.assertIn('>Composition</h3>', script)
        self.assertNotIn('>Current use / composition</h3>', script)
        for removed_section in ("Wildlife", "Soil study", "IR data"):
            self.assertNotIn(removed_section, script)
        self.assertIn("buildParcelPopup(layer, f, resolveUrl)", script)
        self.assertIn("const capitalizeFirstLetter = value =>", script)
        self.assertNotIn("rfi-parcel-popup__eyebrow", script)
        self.assertNotIn("rfi-parcel-popup__eyebrow", stylesheet)
        self.assertIn("const popupOptions = layer.popup || {}", script)
        self.assertIn("popupOptions.hide_media_by_name", script)
        self.assertIn("popupOptions.hide_history_by_name", script)
        self.assertIn("const mediaPanel = hideMedia ? '' : firstMediaUrl", script)
        self.assertIn("rfi-parcel-popup__hero--without-media", script)
        self.assertIn(".rfi-parcel-popup__hero--without-media", stylesheet)
        self.assertIn("popupOptions.hide_composition", script)
        self.assertIn("popupOptions.hide_history", script)
        self.assertIn("const historyPanel = hideHistory ? ''", script)
        self.assertIn("No land-use description has been entered for this parcel.", script)
        self.assertIn("No past-use history has been entered for this parcel.", script)
        self.assertNotIn("Lorem ipsum dolor sit amet, consectetur adipiscing elit.", script)
        self.assertNotIn("path.rfi-riparian-feature { pointer-events: visibleFill; }", stylesheet)
        self.assertIn("properties._rfi_media", script)
        self.assertIn("rfi-parcel-popup__media-image", script)
        self.assertIn("resolved.searchParams.set('v', configVersion)", script)
        self.assertIn("geometryAreaHectares(feature?.geometry)", script)
        self.assertIn("data-rfi-area-hectares", script)
        self.assertIn("const date = propertyValue(properties, ['Date created', 'Date Created', 'Date planted', 'Date added', 'Date'])\n      || '-';", script)
        self.assertIn("updateSectionVisibility", script)
        self.assertIn("input.checked !== matchesSection", script)
        self.assertNotIn("fitFarmInAvailablePane", script)
        self.assertNotIn("popupOpenZoom", script)
        self.assertNotIn("map.setZoomAround", script)
        self.assertNotIn("map.panBy", script)
        self.assertIn("--rfi-popup-left", stylesheet)
        self.assertIn("--rfi-popup-max-height", stylesheet)
        self.assertIn("top: var(--rfi-popup-top, 0) !important", stylesheet)
        self.assertNotIn("height: var(--rfi-popup-height, 500px)", stylesheet)
        self.assertIn("positionParcelPopup(map, popup)", script)
        self.assertIn("const panelBottom = 14", script)
        self.assertIn("const panelTopClearance = 72", script)
        self.assertIn("const popupHeight = Math.min(popupElement.getBoundingClientRect().height, maximumHeight)", script)
        self.assertIn("const panelTop = mapBounds.bottom - panelBottom - popupHeight", script)
        self.assertIn("popupElement.style.removeProperty('--rfi-popup-height')", script)
        self.assertIn("right: 14px", stylesheet)
        self.assertIn("bottom: 14px", stylesheet)
        self.assertIn("position: 'bottomleft'", script)
        self.assertIn("leaflet-bottom.leaflet-left", stylesheet)
        self.assertIn("leaflet-control-zoom { order: 1", stylesheet)
        self.assertIn('viewBox="0 0 34 72"', script)
        self.assertIn('fill-rule="evenodd"', script)
        self.assertNotIn("rfi-rotate-control__needle-inset", script)
        self.assertIn("rfi-rotate-control__needle-body", stylesheet)
        self.assertIn("width: 94px; height: 94px", stylesheet)
        self.assertIn("background: transparent", stylesheet)
        self.assertIn("border: 4.5px solid #fff", stylesheet)
        self.assertIn("width: 24px; height: 49px", stylesheet)
        self.assertIn(".rfi-rotate-control__needle-body { fill: #fff;", stylesheet)
        self.assertIn("rfi-parcel-popup__pie", stylesheet)
        self.assertIn("const isSyntropic = layerSymbol?.key === 'syntropic'", script)
        self.assertIn("const parsePlantCensus = value =>", script)
        self.assertIn("const summarizeCensusStrata = (census, configuredMapping = {}) =>", script)
        self.assertIn("const censusPieGradient = strata =>", script)
        self.assertIn("count > 0 ? {name, count: Math.round(count)} : null", script)
        self.assertIn("See full tree census", script)
        self.assertIn("Tree type", script)
        self.assertIn("Percentage of total trees", script)
        self.assertIn("Composition by tree stratum", script)
        self.assertIn("rfi-parcel-popup__pie-total", script)
        self.assertIn(".rfi-parcel-popup__pie-total", stylesheet)
        for stratum in ("Emergent", "High", "Medium", "Low"):
            self.assertIn(f"label: '{stratum}'", script)
        self.assertIn("const compositionPanel = isSyntropic && !popupOptions.hide_composition ?", script)
        self.assertIn("No plant census has been entered for this parcel.", script)
        self.assertIn("riparianPane.style.zIndex = '350'", script)
        self.assertIn("riparianDisplayPane.style.zIndex = '410'", script)
        self.assertIn("riparianDisplayPane.style.pointerEvents = 'none'", script)
        self.assertIn("map.createPane('rfiRiparianDisplayPane', map.getPane('overlayPane')?.parentNode)", script)
        self.assertIn("interactive: false", script)
        self.assertIn("riparianDisplay?.addTo(map)", script)
        self.assertIn("rfi-parcel-popup__composition--without-chart", script)
        self.assertIn("rfi-parcel-popup__composition--census", script)
        self.assertIn(".rfi-parcel-popup__composition--census { align-items: start; }", stylesheet)
        self.assertIn("${showCompositionChart ? `<div class=\"rfi-parcel-popup__pie-group\">", script)
        self.assertIn(".rfi-parcel-popup__census-details { grid-column: 1 / -1;", stylesheet)
        self.assertIn(".rfi-parcel-popup__strata li", stylesheet)
        self.assertIn(".rfi-parcel-popup__composition--without-chart { grid-template-columns: 1fr; }", stylesheet)
        self.assertIn(".rfi-parcel-popup__media-image", stylesheet)
        self.assertIn("--rfi-popup-padding: .5cm", stylesheet)
        self.assertIn("padding: var(--rfi-popup-padding)", stylesheet)
        self.assertIn("data-media-items", script)
        self.assertIn("popupOptions.media_by_name", script)
        self.assertIn("const showImage = index =>", script)
        self.assertIn("--rfi-parcel-symbol", stylesheet)
        self.assertIn("Land use groups", script)
        self.assertIn("const visible = activeSection === 'land-use'", script)
        self.assertIn("registerLanduseLegend(layer)", script)
        self.assertIn("const qgisLinePatternFill = style =>", script)
        self.assertIn("const qgisLinePatternPreview = style =>", script)
        self.assertIn("if (style.pattern_crosshatch) addLine", script)
        self.assertIn("if (dashArray) line.setAttribute('stroke-dasharray', dashArray)", script)
        self.assertIn("const passivePatternOverlay = layer.style?.kind === 'qgis-line-pattern-fill' && layer.interactive === false", script)
        self.assertIn("interactive: layer.interactive !== false", script)
        self.assertIn("const isParcel = layer.interactive !== false", script)
        self.assertIn("map.createPane('rfiRiparianPane')", script)
        self.assertIn("'qgis-line-pattern-fill'", script)
        self.assertIn("mapBox.right - popupBox.left + 10", script)
        self.assertIn("map.on('popupclose', () => {", script)
        self.assertIn("landuseLegendPanel.style.removeProperty('right')", script)
        self.assertIn("if (!popup?.isOpen?.()) return", script)
        self.assertIn("if (popup?.isOpen?.() && popup.getElement?.()?.classList.contains('rfi-parcel-popup-shell'))", script)
        self.assertIn("landuseLegendPanel.dataset.rfiVisible = String(visible)", script)
        self.assertIn("root.classList.toggle('rfi-map--landuse-active', visible)", script)
        self.assertIn("map.on('zoomstart zoomanim zoom zoomend moveend', keepLanduseLegendVisible)", script)
        self.assertNotIn("closedZoom", script)
        self.assertIn('[data-rfi-visible="true"] { display: block !important; }', stylesheet)
        self.assertIn(".rfi-map.rfi-map--landuse-active .rfi-map__landuse-legend", stylesheet)
        self.assertIn("width: 14px; height: 14px", stylesheet)
        self.assertIn(".rfi-map__landuse-legend { z-index: 720; transform: translateZ(0); }", stylesheet)

    def test_geojson_is_copied_and_manifest_reference_is_local(self):
        with tempfile.TemporaryDirectory() as source_name, tempfile.TemporaryDirectory() as output_name:
            source_root = Path(source_name)
            data_root = Path(output_name)
            source = source_root / "boundary.geojson"
            source.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")

            layers, notices = build_rfi_map.qgis_layers(source_root, data_root)

            self.assertEqual(notices, [])
            self.assertEqual(layers[0]["url"], "qgis/boundary.geojson")
            self.assertEqual(layers[0]["source_reference"], "qgis/boundary.geojson")
            self.assertTrue((data_root / "qgis" / "boundary.geojson").is_file())

    def test_bounded_raster_and_sidecar_are_copied(self):
        with tempfile.TemporaryDirectory() as source_name, tempfile.TemporaryDirectory() as output_name:
            source_root = Path(source_name)
            data_root = Path(output_name)
            image = source_root / "health.png"
            image.write_bytes(b"placeholder")
            bounds = image.with_name(image.name + ".bounds.json")
            bounds.write_text("[[-1, -2], [3, 4]]", encoding="utf-8")

            assets = build_rfi_map.satellite_layers(source_root, data_root)

            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0]["url"], "satellite/health.png")
            self.assertEqual(assets[0]["source_reference"], "satellite/health.png")
            self.assertTrue((data_root / "satellite" / "health.png").is_file())
            self.assertTrue((data_root / "satellite" / "health.png.bounds.json").is_file())

    def test_unbounded_raster_is_not_referenced(self):
        with tempfile.TemporaryDirectory() as source_name, tempfile.TemporaryDirectory() as output_name:
            source_root = Path(source_name)
            image = source_root / "unbounded.png"
            image.write_bytes(b"placeholder")

            assets = build_rfi_map.satellite_layers(source_root, Path(output_name))

            self.assertEqual(assets, [])


if __name__ == "__main__":
    unittest.main()
