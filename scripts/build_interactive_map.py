"""Build a standalone Folium map from the validated GIS outputs."""

from pathlib import Path
import shutil

import folium
import geopandas as gpd
from branca.colormap import LinearColormap


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MAPS = ROOT / "maps"
DOCS = ROOT / "docs"

STRAIGHT_COLORS = {
    "High": "#2E7D32",
    "Moderate": "#A6D96A",
    "Low": "#FDAE61",
    "Very Low": "#D73027",
}
DRIVE_COLORS = {
    "High": "#2166AC",
    "Moderate": "#67A9CF",
    "Low": "#FDAE61",
    "Very Low": "#B2182B",
}


def category_style(feature: dict, field: str, colors: dict[str, str]) -> dict:
    category = feature["properties"][field]
    return {
        "fillColor": colors.get(category, "#CCCCCC"),
        "color": "#555555",
        "weight": 0.6,
        "fillOpacity": 0.72,
    }


def main() -> None:
    MAPS.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    straight = gpd.read_file(
        PROCESSED / "state_park_accessibility.gpkg",
        layer="county_accessibility",
    )
    # Simplify display geometry to keep the standalone HTML and Pages site small.
    straight["geometry"] = straight.geometry.simplify(150, preserve_topology=True)
    straight = straight.to_crs("EPSG:4326")
    parks = gpd.read_file(
        PROCESSED / "park_points.gpkg", layer="park_points"
    ).to_crs("EPSG:4326")

    drive_path = PROCESSED / "drive_time_accessibility.gpkg"
    if drive_path.exists():
        drive = gpd.read_file(drive_path, layer="county_drive_time")
        drive["geometry"] = drive.geometry.simplify(150, preserve_topology=True)
        drive = drive.to_crs("EPSG:4326")
    else:
        drive = None

    web_map = folium.Map(
        location=[32.75, -83.45],
        zoom_start=7,
        tiles="CartoDB positron",
        control_scale=True,
    )

    straight_layer = folium.FeatureGroup(
        name="Straight-line accessibility", show=drive is None
    )
    folium.GeoJson(
        straight,
        name="Straight-line county access",
        style_function=lambda feature: category_style(
            feature, "access_category", STRAIGHT_COLORS
        ),
        highlight_function=lambda feature: {
            "weight": 2,
            "color": "#111111",
            "fillOpacity": 0.85,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "county",
                "population",
                "nearest_park",
                "park_distance_miles",
                "access_category",
            ],
            aliases=[
                "County",
                "Population",
                "Nearest park",
                "Straight-line distance (miles)",
                "Straight-line category",
            ],
            localize=True,
            sticky=False,
        ),
        popup=folium.GeoJsonPopup(
            fields=[
                "county",
                "nearest_park",
                "park_distance_miles",
                "access_category",
            ],
            aliases=[
                "County",
                "Nearest park",
                "Straight-line distance (miles)",
                "Category",
            ],
            localize=True,
        ),
    ).add_to(straight_layer)
    straight_layer.add_to(web_map)

    if drive is not None:
        drive_layer = folium.FeatureGroup(name="Estimated drive-time accessibility")
        folium.GeoJson(
            drive,
            name="Drive-time county access",
            style_function=lambda feature: category_style(
                feature, "drive_access_category", DRIVE_COLORS
            ),
            highlight_function=lambda feature: {
                "weight": 2,
                "color": "#111111",
                "fillOpacity": 0.85,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[
                    "county",
                    "population",
                    "nearest_drive_park",
                    "drive_time_minutes",
                    "drive_distance_miles",
                    "drive_access_category",
                ],
                aliases=[
                    "County",
                    "Population",
                    "Nearest park by drive time",
                    "Estimated drive time (minutes)",
                    "Estimated route distance (miles)",
                    "Drive-time category",
                ],
                localize=True,
                sticky=False,
            ),
        ).add_to(drive_layer)
        drive_layer.add_to(web_map)

    parks_layer = folium.FeatureGroup(name="State parks", show=True)
    for _, park in parks.iterrows():
        folium.CircleMarker(
            location=[park.geometry.y, park.geometry.x],
            radius=4,
            color="#FFFFFF",
            weight=1,
            fill=True,
            fill_color="#111111",
            fill_opacity=1,
            tooltip=park["park_name"],
            popup=folium.Popup(f"<strong>{park['park_name']}</strong>", max_width=250),
        ).add_to(parks_layer)
    parks_layer.add_to(web_map)

    title = """
    <div style="position: fixed; top: 12px; left: 50%; transform: translateX(-50%);
                z-index: 9999; background: rgba(255,255,255,.94); padding: 8px 14px;
                border: 1px solid #999; border-radius: 4px; font-family: sans-serif;
                font-size: 18px; font-weight: 700; white-space: nowrap;">
      Georgia State Park Accessibility
    </div>
    """
    web_map.get_root().html.add_child(folium.Element(title))

    legend = """
    <div style="position: fixed; right: 10px; bottom: 28px; z-index: 9999;
                background: rgba(255,255,255,.95); padding: 10px 12px;
                border: 1px solid #999; border-radius: 4px; font: 12px sans-serif;
                line-height: 1.45;">
      <strong>Drive-time categories</strong><br>
      <span style="color:#2166AC">■</span> High: ≤30 minutes<br>
      <span style="color:#67A9CF">■</span> Moderate: &gt;30–45<br>
      <span style="color:#FDAE61">■</span> Low: &gt;45–60<br>
      <span style="color:#B2182B">■</span> Very Low: &gt;60<br>
      <hr style="margin:6px 0">
      <strong>Straight-line categories</strong><br>
      <span style="color:#2E7D32">■</span> High: ≤10 miles<br>
      <span style="color:#A6D96A">■</span> Moderate: &gt;10–20<br>
      <span style="color:#FDAE61">■</span> Low: &gt;20–30<br>
      <span style="color:#D73027">■</span> Very Low: &gt;30<br>
      <div style="margin-top:6px; max-width:220px; color:#555;">
        Screening estimates from county centroids to park representative points.
      </div>
    </div>
    """
    web_map.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(web_map)
    web_map.save(MAPS / "interactive_accessibility_map.html")
    shutil.copyfile(MAPS / "interactive_accessibility_map.html", DOCS / "index.html")
    print(f"Saved {MAPS / 'interactive_accessibility_map.html'}")
    print(f"Saved {DOCS / 'index.html'}")


if __name__ == "__main__":
    main()
