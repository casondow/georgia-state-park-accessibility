"""Build a standalone Folium map from the validated GIS outputs."""

from pathlib import Path
import shutil
import json

import folium
import geopandas as gpd
import pandas as pd
from branca.colormap import LinearColormap
from branca.element import MacroElement, Template


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


class LocationAccessibilityControl(MacroElement):
    """Leaflet control for on-demand browser geolocation and OSRM routing."""

    _template = Template(
        """
        {% macro header(this, kwargs) %}
        <style>
          .locate-access-button, .map-help-button {
            width: 34px; height: 34px; border: 0; background: #fff;
            cursor: pointer; font-size: 18px; line-height: 34px; text-align: center;
          }
          .locate-access-button:hover, .map-help-button:hover { background: #f4f4f4; }
          .location-results, .map-help-panel {
            position: fixed; left: 12px; bottom: 32px; z-index: 10000;
            width: 310px; max-height: 45vh; overflow-y: auto;
            background: rgba(255,255,255,.97); border: 1px solid #888;
            border-radius: 5px; padding: 11px 12px; font: 12px/1.4 sans-serif;
            box-shadow: 0 1px 6px rgba(0,0,0,.25); display: none;
          }
          .location-results h3 { margin: 0 0 7px; font-size: 15px; }
          .location-results .route-card {
            margin: 7px 0; padding: 7px; border-left: 5px solid #555;
            background: #f7f7f7;
          }
          .location-results .state-route { border-left-color: #0057B8; }
          .location-results .local-route { border-left-color: #8E24AA; }
          .location-results .privacy-note {
            color: #555; font-size: 10px; margin-top: 7px;
          }
          .location-results .directions-link {
            display: inline-block; margin-top: 5px; color: #0645AD;
            font-weight: 700; text-decoration: none;
          }
          .location-results .directions-link:hover { text-decoration: underline; }
          .location-results button, .map-help-panel button {
            float: right; border: 0; background: transparent; cursor: pointer;
            font-size: 16px;
          }
          .map-help-panel h3 { margin: 0 0 8px; font-size: 15px; }
          .map-help-panel ul { margin: 6px 0 8px; padding-left: 18px; }
          .map-help-panel li { margin: 4px 0; }
          @media (max-width: 600px) {
            .map-title {
              top: 8px !important; max-width: 58vw; white-space: normal !important;
              text-align: center; font-size: 14px !important; padding: 6px 9px !important;
            }
            .location-results, .map-help-panel {
              left: 8px; right: 8px; bottom: 8px; width: auto;
              max-height: 44vh; box-sizing: border-box;
            }
            .map-legend { display: none; }
            .leaflet-control-layers {
              max-width: 48vw; max-height: 42vh; overflow-y: auto;
              font-size: 11px;
            }
          }
        </style>
        {% endmacro %}
        {% macro html(this, kwargs) %}
        <div id="location-results" class="location-results">
          <button id="location-results-close" aria-label="Close">×</button>
          <h3>Access from your location</h3>
          <div id="location-results-body">Finding your location…</div>
          <div class="privacy-note">
            Your location is not stored by this site. Coordinates are sent to the
            public OSRM service to estimate routes. Results exclude live traffic
            and should be verified before travel.
          </div>
        </div>
        <div id="map-help-panel" class="map-help-panel">
          <button id="map-help-close" aria-label="Close help">×</button>
          <h3>How to use this map</h3>
          <ul>
            <li><strong>⌖ Locate me:</strong> compare estimated driving access to a state park and a nearby recreation option.</li>
            <li><strong>Blue route:</strong> selected Georgia state park.</li>
            <li><strong>Purple route:</strong> selected local recreation option.</li>
            <li><strong>Layer menu:</strong> switch accessibility methods, recreation suggestions, park points, and labels.</li>
            <li><strong>Park points:</strong> click a marker for its name.</li>
          </ul>
          <div>
            Times use public OSRM/OpenStreetMap routing without live traffic.
            Local recreation data and destination entrances should be verified before travel.
          </div>
        </div>
        {% endmacro %}
        {% macro script(this, kwargs) %}
        (function() {
          const map = {{ this._parent.get_name() }};
          const stateParks = {{ this.state_parks_json }};
          const localOptions = {{ this.local_options_json }};
          let userMarker = null;
          let routeLayers = [];

          function miles(metres) { return metres / 1609.344; }
          function directionsUrl(latitude, longitude, item) {
            return 'https://www.google.com/maps/dir/?api=1&origin=' +
              latitude.toFixed(6) + ',' + longitude.toFixed(6) +
              '&destination=' + item.lat.toFixed(6) + ',' + item.lon.toFixed(6) +
              '&travelmode=driving';
          }
          function escapeHtml(value) {
            return String(value).replace(/[&<>"']/g, function(char) {
              return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char];
            });
          }
          function haversine(lat1, lon1, lat2, lon2) {
            const radius = 6371;
            const toRad = Math.PI / 180;
            const dLat = (lat2-lat1) * toRad;
            const dLon = (lon2-lon1) * toRad;
            const a = Math.sin(dLat/2)**2 +
              Math.cos(lat1*toRad) * Math.cos(lat2*toRad) *
              Math.sin(dLon/2)**2;
            return radius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
          }
          function closestCandidates(items, latitude, longitude, count) {
            return items.map(function(item) {
              return Object.assign({}, item, {
                air_km: haversine(latitude, longitude, item.lat, item.lon)
              });
            }).sort(function(a,b) { return a.air_km - b.air_km; }).slice(0, count);
          }
          async function fastestOption(latitude, longitude, items) {
            const coordinates = [[longitude, latitude]].concat(
              items.map(function(item) { return [item.lon, item.lat]; })
            );
            const coordinateText = coordinates.map(function(point) {
              return point[0].toFixed(6) + ',' + point[1].toFixed(6);
            }).join(';');
            const destinations = items.map(function(_, index) {
              return index + 1;
            }).join(';');
            const url = 'https://router.project-osrm.org/table/v1/driving/' +
              coordinateText + '?sources=0&destinations=' + destinations +
              '&annotations=duration,distance';
            const response = await fetch(url);
            if (!response.ok) throw new Error('Routing request failed.');
            const payload = await response.json();
            if (payload.code !== 'Ok') throw new Error('No route matrix returned.');
            let bestIndex = -1;
            let bestDuration = Infinity;
            payload.durations[0].forEach(function(duration, index) {
              if (duration !== null && duration < bestDuration) {
                bestDuration = duration;
                bestIndex = index;
              }
            });
            if (bestIndex < 0) throw new Error('No drivable option was found.');
            return {
              item: items[bestIndex],
              duration: payload.durations[0][bestIndex],
              distance: payload.distances[0][bestIndex]
            };
          }
          async function drawRoute(latitude, longitude, result, color) {
            const url = 'https://router.project-osrm.org/route/v1/driving/' +
              longitude.toFixed(6) + ',' + latitude.toFixed(6) + ';' +
              result.item.lon.toFixed(6) + ',' + result.item.lat.toFixed(6) +
              '?overview=full&geometries=geojson';
            const response = await fetch(url);
            if (!response.ok) return null;
            const payload = await response.json();
            if (payload.code !== 'Ok' || !payload.routes.length) return null;
            const layer = L.geoJSON(payload.routes[0].geometry, {
              style: {color: color, weight: 5, opacity: .8}
            }).addTo(map);
            routeLayers.push(layer);
            return layer;
          }
          async function calculate(latitude, longitude) {
            const panel = document.getElementById('location-results');
            const body = document.getElementById('location-results-body');
            panel.style.display = 'block';
            body.innerHTML = 'Calculating estimated drive access…';
            routeLayers.forEach(function(layer) { map.removeLayer(layer); });
            routeLayers = [];
            if (userMarker) map.removeLayer(userMarker);
            userMarker = L.circleMarker([latitude, longitude], {
              radius: 7, color: '#111', weight: 2, fillColor: '#FFEB3B',
              fillOpacity: 1
            }).bindTooltip('Your location').addTo(map);

            try {
              const stateCandidates = closestCandidates(
                stateParks, latitude, longitude, 25
              );
              const localCandidates = closestCandidates(
                localOptions, latitude, longitude, 25
              );
              const results = await Promise.all([
                fastestOption(latitude, longitude, stateCandidates),
                fastestOption(latitude, longitude, localCandidates)
              ]);
              const stateResult = results[0];
              const localResult = results[1];
              const routes = await Promise.all([
                drawRoute(latitude, longitude, stateResult, '#0057B8'),
                drawRoute(latitude, longitude, localResult, '#8E24AA')
              ]);
              body.innerHTML =
                '<div class="route-card state-route"><strong>Nearest state park by estimated drive time</strong><br>' +
                escapeHtml(stateResult.item.name) + '<br>' +
                (stateResult.duration/60).toFixed(1) + ' minutes · ' +
                miles(stateResult.distance).toFixed(1) + ' miles<br>' +
                '<a class="directions-link" target="_blank" rel="noopener noreferrer" href="' +
                directionsUrl(latitude, longitude, stateResult.item) +
                '">Open driving directions ↗</a></div>' +
                '<div class="route-card local-route"><strong>Nearby recreation option by estimated drive time</strong><br>' +
                escapeHtml(localResult.item.name) + ' (' +
                escapeHtml(localResult.item.type.replaceAll('_',' ')) + ')<br>' +
                (localResult.duration/60).toFixed(1) + ' minutes · ' +
                miles(localResult.distance).toFixed(1) + ' miles<br>' +
                '<a class="directions-link" target="_blank" rel="noopener noreferrer" href="' +
                directionsUrl(latitude, longitude, localResult.item) +
                '">Open driving directions ↗</a></div>' +
                '<div><strong>Route colors:</strong> blue = state park; purple = nearby recreation.</div>';
              const bounds = L.latLngBounds([[latitude, longitude]]);
              routes.forEach(function(layer) {
                if (layer) bounds.extend(layer.getBounds());
              });
              map.fitBounds(bounds.pad(.12));
            } catch (error) {
              body.innerHTML = '<strong>Unable to calculate routes.</strong><br>' +
                escapeHtml(error.message) + ' Please try again shortly.';
            }
          }

          const LocateControl = L.Control.extend({
            options: {position: 'topleft'},
            onAdd: function() {
              const container = L.DomUtil.create('div', 'leaflet-bar');
              const button = L.DomUtil.create('button', 'locate-access-button', container);
              button.type = 'button';
              button.title = 'Locate me and estimate park drive access';
              button.setAttribute('aria-label', button.title);
              button.innerHTML = '⌖';
              L.DomEvent.disableClickPropagation(container);
              L.DomEvent.on(button, 'click', function() {
                const panel = document.getElementById('location-results');
                const body = document.getElementById('location-results-body');
                panel.style.display = 'block';
                body.innerHTML = 'Requesting your location…';
                if (!navigator.geolocation) {
                  body.innerHTML = 'Geolocation is not supported by this browser.';
                  return;
                }
                navigator.geolocation.getCurrentPosition(
                  function(position) {
                    calculate(position.coords.latitude, position.coords.longitude);
                  },
                  function(error) {
                    body.innerHTML = '<strong>Location unavailable.</strong><br>' +
                      escapeHtml(error.message) +
                      '<br>Check the browser location permission and try again.';
                  },
                  {enableHighAccuracy: true, timeout: 15000, maximumAge: 60000}
                );
              });
              const helpButton = L.DomUtil.create('button', 'map-help-button', container);
              helpButton.type = 'button';
              helpButton.title = 'How to use this map';
              helpButton.setAttribute('aria-label', helpButton.title);
              helpButton.innerHTML = '?';
              L.DomEvent.on(helpButton, 'click', function() {
                const panel = document.getElementById('map-help-panel');
                panel.style.display = panel.style.display === 'block' ? 'none' : 'block';
              });
              return container;
            }
          });
          map.addControl(new LocateControl());
          document.getElementById('location-results-close').addEventListener(
            'click', function() {
              document.getElementById('location-results').style.display = 'none';
            }
          );
          document.getElementById('map-help-close').addEventListener(
            'click', function() {
              document.getElementById('map-help-panel').style.display = 'none';
            }
          );
        })();
        {% endmacro %}
        """
    )

    def __init__(self, state_parks: list[dict], local_options: list[dict]) -> None:
        super().__init__()
        self._name = "LocationAccessibilityControl"
        self.state_parks_json = json.dumps(state_parks, ensure_ascii=False)
        self.local_options_json = json.dumps(local_options, ensure_ascii=False)


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
    all_local_options = gpd.read_file(
        PROCESSED / "local_recreation_options.gpkg",
        layer="named_recreation_options",
    ).to_crs("EPSG:4326")

    drive_path = PROCESSED / "drive_time_accessibility.gpkg"
    if drive_path.exists():
        drive = gpd.read_file(drive_path, layer="county_drive_time")
        popup_path = PROCESSED / "local_park_popup_text.csv"
        if popup_path.exists():
            drive = drive.merge(
                pd.read_csv(popup_path),
                on="county",
                how="left",
                validate="one_to_one",
            )
            drive["nearby_recreation_options"] = drive[
                "nearby_recreation_options"
            ].fillna("State park access category is High or Moderate")
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
                    "nearby_recreation_options",
                ],
                aliases=[
                    "County",
                    "Population",
                    "Nearest park by drive time",
                    "Estimated drive time (minutes)",
                    "Estimated route distance (miles)",
                    "Drive-time category",
                    "Nearby recreation options",
                ],
                localize=True,
                sticky=False,
            ),
        ).add_to(drive_layer)
        drive_layer.add_to(web_map)

    suggestions_path = PROCESSED / "local_park_suggestions.gpkg"
    if suggestions_path.exists():
        suggestions = gpd.read_file(
            suggestions_path,
            layer="suggested_recreation_options",
        ).to_crs("EPSG:4326")
        local_layer = folium.FeatureGroup(
            name="Suggested nearby recreation options",
            show=False,
        )
        for _, option in suggestions.iterrows():
            folium.CircleMarker(
                location=[option.geometry.y, option.geometry.x],
                radius=4,
                color="#6A1B9A",
                weight=1,
                fill=True,
                fill_color="#CE93D8",
                fill_opacity=0.95,
                tooltip=option["name"],
                popup=folium.Popup(
                    (
                        f"<strong>{option['name']}</strong><br>"
                        f"OSM type: {option['fclass'].replace('_', ' ')}<br>"
                        "<em>Informational suggestion; verify ownership, hours, "
                        "entrance, and public access before visiting.</em>"
                    ),
                    max_width=320,
                ),
            ).add_to(local_layer)
        local_layer.add_to(web_map)

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

    park_labels_layer = folium.FeatureGroup(name="State park labels", show=False)
    for _, park in parks.iterrows():
        folium.Marker(
            location=[park.geometry.y, park.geometry.x],
            icon=folium.DivIcon(
                icon_size=(180, 24),
                icon_anchor=(-6, 11),
                html=(
                    '<div class="park-name-label" style="font: 10px/1.15 sans-serif; font-weight: 700; '
                    'color:#111; white-space:nowrap; text-shadow:'
                    '-1px -1px 0 #fff,1px -1px 0 #fff,-1px 1px 0 #fff,'
                    '1px 1px 0 #fff;">'
                    f"{park['park_name']}</div>"
                ),
            ),
            tooltip=park["park_name"],
        ).add_to(park_labels_layer)
    park_labels_layer.add_to(web_map)

    state_park_locations = [
        {
            "name": row["park_name"],
            "lat": row.geometry.y,
            "lon": row.geometry.x,
            "type": "state park",
        }
        for _, row in parks.iterrows()
    ]
    local_option_locations = [
        {
            "name": row["name"],
            "lat": row.geometry.y,
            "lon": row.geometry.x,
            "type": row["fclass"],
        }
        for _, row in all_local_options.iterrows()
    ]
    LocationAccessibilityControl(
        state_park_locations,
        local_option_locations,
    ).add_to(web_map)

    title = """
    <div class="map-title" style="position: fixed; top: 12px; left: 50%; transform: translateX(-50%);
                z-index: 9999; background: rgba(255,255,255,.94); padding: 8px 14px;
                border: 1px solid #999; border-radius: 4px; font-family: sans-serif;
                font-size: 18px; font-weight: 700; white-space: nowrap;">
      Georgia State and Local Park Accessibility by County
    </div>
    """
    web_map.get_root().html.add_child(folium.Element(title))

    legend = """
    <div class="map-legend" style="position: fixed; right: 10px; bottom: 28px; z-index: 9999;
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
        Purple markers are unverified OpenStreetMap recreation suggestions.
        Turn on state park labels after zooming in for the clearest view.
      </div>
    </div>
    """
    web_map.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=True).add_to(web_map)
    web_map.save(MAPS / "interactive_accessibility_map.html")
    shutil.copyfile(MAPS / "interactive_accessibility_map.html", DOCS / "index.html")
    print(f"Saved {MAPS / 'interactive_accessibility_map.html'}")
    print(f"Saved {DOCS / 'index.html'}")


if __name__ == "__main__":
    main()
