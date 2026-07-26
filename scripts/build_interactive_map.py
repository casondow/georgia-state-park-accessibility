"""Build a standalone Folium map from the validated GIS outputs."""

from pathlib import Path
import shutil
import json
import html

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

OFFICIAL_PARK_PAGES = {
    "A. H. STEPHENS SP": ("A.H. Stephens State Park", "https://gastateparks.org/AHStephens"),
    "AMICALOLA FALLS SP": ("Amicalola Falls State Park & Lodge", "https://gastateparks.org/AmicalolaFalls"),
    "BLACK ROCK MOUNTAIN SP": ("Black Rock Mountain State Park", "https://gastateparks.org/BlackRockMountain"),
    "CHATTAHOOCHEE BEND SP": ("Chattahoochee Bend State Park", "https://gastateparks.org/ChattahoocheeBend"),
    "CLOUDLAND CANYON SP": ("Cloudland Canyon State Park", "https://gastateparks.org/CloudlandCanyon"),
    "CROOKED RIVER SP": ("Crooked River State Park", "https://gastateparks.org/CrookedRiver"),
    "DON CARTER SP": ("Don Carter State Park", "https://gastateparks.org/DonCarter"),
    "ELIJAH CLARKE SP": ("Elijah Clark State Park", "https://gastateparks.org/ElijahClark"),
    "F. D. ROOSEVELT SP": ("F.D. Roosevelt State Park", "https://gastateparks.org/FDRoosevelt"),
    "FLORENCE MARINA SP": ("Florence Marina State Park", "https://gastateparks.org/FlorenceMarina"),
    "FORT MCALLISTER SP": ("Fort McAllister State Park", "https://gastateparks.org/FortMcAllister"),
    "FORT MOUNTAIN SP": ("Fort Mountain State Park", "https://gastateparks.org/FortMountain"),
    "FORT YARGO SP": ("Fort Yargo State Park", "https://gastateparks.org/FortYargo"),
    "GENERAL COFFEE SP": ("General Coffee State Park", "https://gastateparks.org/GeneralCoffee"),
    "GEORGE BAGBY SP": ("George T. Bagby State Park", "https://gastateparks.org/GeorgeTBagby"),
    "GEORGE L. SMITH SP": ("George L. Smith State Park", "https://gastateparks.org/GeorgeLSmith"),
    "GEORGIA VETERANS SP": ("Georgia Veterans State Park & Resort", "https://gastateparks.org/GeorgiaVeterans"),
    "GORDONIA-ALATAMAHA SP": ("Jack Hill State Park", "https://gastateparks.org/JackHill"),
    "HARD LABOR CREEK SP": ("Hard Labor Creek State Park", "https://gastateparks.org/HardLaborCreek"),
    "HIGH FALLS SP": ("High Falls State Park", "https://gastateparks.org/HighFalls"),
    "INDIAN SPRINGS SP": ("Indian Springs State Park", "https://gastateparks.org/IndianSprings"),
    'JAMES H."SLOPPY" FLOYD SP': ("James H. “Sloppy” Floyd State Park", "https://gastateparks.org/JamesHFloyd"),
    "KOLOMOKI MOUNDS SP": ("Kolomoki Mounds State Park", "https://gastateparks.org/KolomokiMounds"),
    "LAURA WALKER SP": ("Laura S. Walker State Park", "https://gastateparks.org/LauraSWalker"),
    "LITTLE OCMULGEE SP": ("Little Ocmulgee State Park & Lodge", "https://gastateparks.org/LittleOcmulgee"),
    "MAGNOLIA SPRINGS SP": ("Magnolia Springs State Park", "https://gastateparks.org/MagnoliaSprings"),
    "MISTLETOE SP": ("Mistletoe State Park", "https://gastateparks.org/Mistletoe"),
    "MOCCASIN CREEK SP": ("Moccasin Creek State Park", "https://gastateparks.org/MoccasinCreek"),
    "PANOLA MOUNTAIN SP": ("Panola Mountain State Park", "https://gastateparks.org/PanolaMountain"),
    "RED TOP MOUNTAIN SP": ("Red Top Mountain State Park", "https://gastateparks.org/RedTopMountain"),
    "REED BINGHAM SP": ("Reed Bingham State Park", "https://gastateparks.org/ReedBingham"),
    "RICHARD B. RUSSELL SP": ("Richard B. Russell State Park", "https://gastateparks.org/RichardBRussell"),
    "SEMINOLE SP": ("Seminole State Park", "https://gastateparks.org/Seminole"),
    "SKIDAWAY ISLAND SP": ("Skidaway Island State Park", "https://gastateparks.org/SkidawayIsland"),
    "SMITHGALL WOODS-DUKES CREEK SP": ("Smithgall Woods State Park", "https://gastateparks.org/SmithgallWoods"),
    "STANDING BOY CREEK SP": ("Standing Boy Creek State Park", "https://gastateparks.org/StandingBoyCreek"),
    "STEPHEN C. FOSTER SP": ("Stephen C. Foster State Park", "https://gastateparks.org/StephenCFoster"),
    "SWEETWATER CREEK SP": ("Sweetwater Creek State Park", "https://gastateparks.org/SweetwaterCreek"),
    "TALLULAH GORGE SP": ("Tallulah Gorge State Park", "https://gastateparks.org/TallulahGorge"),
    "TUGALOO SP": ("Tugaloo State Park", "https://gastateparks.org/Tugaloo"),
    "UNICOI SP": ("Unicoi State Park & Lodge", "https://gastateparks.org/Unicoi"),
    "VICTORIA BRYANT SP": ("Victoria Bryant State Park", "https://gastateparks.org/VictoriaBryant"),
    "VOGEL SP": ("Vogel State Park", "https://gastateparks.org/Vogel"),
    "WATSON MILL BRIDGE SP": ("Watson Mill Bridge State Park", "https://gastateparks.org/WatsonMillBridge"),
}
OFFICIAL_PARK_DIRECTORY = "https://gastateparks.org/AllParks"


class LocationAccessibilityControl(MacroElement):
    """Leaflet control for on-demand browser geolocation and OSRM routing."""

    _template = Template(
        """
        {% macro header(this, kwargs) %}
        <style>
          .locate-access-button, .address-search-button, .county-search-button,
          .map-help-button {
            width: 34px; height: 34px; border: 0; background: #fff;
            cursor: pointer; font-size: 18px; line-height: 34px; text-align: center;
          }
          .locate-access-button:hover, .address-search-button:hover,
          .county-search-button:hover, .map-help-button:hover { background: #f4f4f4; }
          .location-results, .address-search-panel, .county-search-panel,
          .map-help-panel {
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
          .location-results button, .address-search-panel > button,
          .county-search-panel > button, .map-help-panel button {
            float: right; border: 0; background: transparent; cursor: pointer;
            font-size: 16px;
          }
          .address-search-panel h3 { margin: 0 0 8px; font-size: 15px; }
          .address-search-panel form { display: flex; gap: 6px; }
          .address-search-panel input {
            min-width: 0; flex: 1; padding: 7px; border: 1px solid #888;
            border-radius: 3px; font: inherit;
          }
          .address-search-panel form button {
            border: 1px solid #666; border-radius: 3px; padding: 6px 9px;
            background: #f4f4f4; cursor: pointer; font: inherit; font-weight: 700;
          }
          .address-search-panel .search-status { margin-top: 7px; }
          .address-search-panel .search-note {
            color: #555; font-size: 10px; margin-top: 7px;
          }
          .county-search-panel h3 { margin: 0 0 8px; font-size: 15px; }
          .county-search-panel select {
            width: 100%; padding: 7px; border: 1px solid #888;
            border-radius: 3px; font: inherit; background: #fff;
          }
          .county-search-panel .county-details {
            margin-top: 8px; line-height: 1.5;
          }
          .county-search-panel .county-details hr { margin: 6px 0; }
          .location-results .share-summary-button,
          .county-search-panel .share-summary-button {
            float: none; display: inline-block; margin-top: 8px; padding: 6px 9px;
            border: 1px solid #666; border-radius: 3px; background: #f4f4f4;
            cursor: pointer; font: inherit; font-weight: 700;
          }
          .map-help-panel h3 { margin: 0 0 8px; font-size: 15px; }
          .map-help-panel ul { margin: 6px 0 8px; padding-left: 18px; }
          .map-help-panel li { margin: 4px 0; }
          @media (max-width: 600px) {
            .map-title {
              top: 8px !important; max-width: 58vw; white-space: normal !important;
              text-align: center; font-size: 14px !important; padding: 6px 9px !important;
            }
            .location-results, .address-search-panel, .county-search-panel,
            .map-help-panel {
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
          <h3 id="location-results-heading">Access from your location</h3>
          <div id="location-results-body">Finding your location…</div>
          <div class="privacy-note">
            Your location is not stored by this site. Coordinates are sent to the
            public OSRM service to estimate routes. Results exclude live traffic
            and should be verified before travel.
          </div>
        </div>
        <div id="address-search-panel" class="address-search-panel">
          <button id="address-search-close" aria-label="Close address search">×</button>
          <h3>Search a Georgia location</h3>
          <form id="address-search-form">
            <label for="address-search-input" style="position:absolute;left:-9999px;">
              Georgia address, city, or ZIP code
            </label>
            <input id="address-search-input" type="search"
                   placeholder="Address, city, or ZIP code" autocomplete="street-address" required>
            <button type="submit">Search</button>
          </form>
          <div id="address-search-status" class="search-status"></div>
          <div class="search-note">
            Search text is sent to OpenStreetMap's Nominatim service. Results are
            restricted to Georgia and should be verified before travel.
          </div>
        </div>
        <div id="county-search-panel" class="county-search-panel">
          <button id="county-search-close" aria-label="Close county explorer">×</button>
          <h3>Explore a Georgia county</h3>
          <label for="county-search-select" style="position:absolute;left:-9999px;">
            Select a Georgia county
          </label>
          <select id="county-search-select">
            <option value="">Select a county…</option>
          </select>
          <div id="county-search-details" class="county-details">
            Choose a county to view its park-access results.
          </div>
        </div>
        <div id="map-help-panel" class="map-help-panel">
          <button id="map-help-close" aria-label="Close help">×</button>
          <h3>How to use this map</h3>
          <ul>
            <li><strong>⌖ Locate me:</strong> compare estimated driving access to a state park and a nearby recreation option.</li>
            <li><strong>Search:</strong> analyze any Georgia address, city, or ZIP code.</li>
            <li><strong>County explorer:</strong> review county population, access categories, travel estimates, and recreation suggestions.</li>
            <li><strong>Share result:</strong> share or copy a concise location or county summary.</li>
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
          const countyData = {{ this.county_data_json }};
          let userMarker = null;
          let routeLayers = [];
          const interactivePanelIds = [
            'location-results',
            'address-search-panel',
            'county-search-panel',
            'map-help-panel'
          ];

          function miles(metres) { return metres / 1609.344; }
          function showOnlyPanel(panelId) {
            interactivePanelIds.forEach(function(id) {
              document.getElementById(id).style.display =
                id === panelId ? 'block' : 'none';
            });
          }
          function toggleExclusivePanel(panelId) {
            const panel = document.getElementById(panelId);
            const wasOpen = window.getComputedStyle(panel).display === 'block';
            interactivePanelIds.forEach(function(id) {
              document.getElementById(id).style.display = 'none';
            });
            if (!wasOpen) panel.style.display = 'block';
            return !wasOpen;
          }
          function formatNumber(value) {
            return Number(value).toLocaleString('en-US');
          }
          function installShareButton(buttonId, title, summary) {
            const button = document.getElementById(buttonId);
            if (!button) return;
            button.addEventListener('click', async function() {
              try {
                if (navigator.share) {
                  await navigator.share({
                    title: title,
                    text: summary,
                    url: window.location.href
                  });
                  button.textContent = 'Shared';
                } else {
                  await navigator.clipboard.writeText(
                    summary + '\\n' + window.location.href
                  );
                  button.textContent = 'Copied';
                }
                window.setTimeout(function() {
                  button.textContent = 'Share result';
                }, 1800);
              } catch (error) {
                if (error.name !== 'AbortError') {
                  button.textContent = 'Unable to share';
                  window.setTimeout(function() {
                    button.textContent = 'Share result';
                  }, 1800);
                }
              }
            });
          }
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
          async function calculate(latitude, longitude, locationLabel) {
            const panel = document.getElementById('location-results');
            const body = document.getElementById('location-results-body');
            const heading = document.getElementById('location-results-heading');
            showOnlyPanel('location-results');
            heading.textContent = locationLabel || 'Access from selected location';
            body.innerHTML = 'Calculating estimated drive access…';
            routeLayers.forEach(function(layer) { map.removeLayer(layer); });
            routeLayers = [];
            if (userMarker) map.removeLayer(userMarker);
            userMarker = L.circleMarker([latitude, longitude], {
              radius: 7, color: '#111', weight: 2, fillColor: '#FFEB3B',
              fillOpacity: 1
            }).bindTooltip(locationLabel || 'Selected location').addTo(map);

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
                '">Open driving directions ↗</a>' +
                (stateResult.item.official_url ?
                  '<br><a class="directions-link" target="_blank" rel="noopener noreferrer" href="' +
                  escapeHtml(stateResult.item.official_url) +
                  '">Official park details ↗</a>' : '') +
                '</div>' +
                '<div class="route-card local-route"><strong>Nearby recreation option by estimated drive time</strong><br>' +
                escapeHtml(localResult.item.name) + ' (' +
                escapeHtml(localResult.item.type.replaceAll('_',' ')) + ')<br>' +
                (localResult.duration/60).toFixed(1) + ' minutes · ' +
                miles(localResult.distance).toFixed(1) + ' miles<br>' +
                '<a class="directions-link" target="_blank" rel="noopener noreferrer" href="' +
                directionsUrl(latitude, longitude, localResult.item) +
                '">Open driving directions ↗</a></div>' +
                '<div><strong>Route colors:</strong> blue = state park; purple = nearby recreation.</div>' +
                '<button id="location-share-summary" class="share-summary-button" type="button">Share result</button>';
              const locationSummary =
                (locationLabel || 'Selected location') + ': nearest state park ' +
                stateResult.item.name + ' — ' +
                (stateResult.duration/60).toFixed(1) + ' minutes, ' +
                miles(stateResult.distance).toFixed(1) +
                ' miles. Nearby recreation option: ' + localResult.item.name +
                ' — ' + (localResult.duration/60).toFixed(1) + ' minutes, ' +
                miles(localResult.distance).toFixed(1) + ' miles.';
              installShareButton(
                'location-share-summary',
                'Georgia park accessibility result',
                locationSummary
              );
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
                showOnlyPanel('location-results');
                body.innerHTML = 'Requesting your location…';
                if (!navigator.geolocation) {
                  body.innerHTML = 'Geolocation is not supported by this browser.';
                  return;
                }
                navigator.geolocation.getCurrentPosition(
                  function(position) {
                    calculate(
                      position.coords.latitude,
                      position.coords.longitude,
                      'Access from your location'
                    );
                  },
                  function(error) {
                    body.innerHTML = '<strong>Location unavailable.</strong><br>' +
                      escapeHtml(error.message) +
                      '<br>Check the browser location permission and try again.';
                  },
                  {enableHighAccuracy: true, timeout: 15000, maximumAge: 60000}
                );
              });
              const searchButton = L.DomUtil.create(
                'button', 'address-search-button', container
              );
              searchButton.type = 'button';
              searchButton.title = 'Search a Georgia address, city, or ZIP code';
              searchButton.setAttribute('aria-label', searchButton.title);
              searchButton.innerHTML = '⌕';
              L.DomEvent.on(searchButton, 'click', function() {
                if (toggleExclusivePanel('address-search-panel')) {
                  document.getElementById('address-search-input').focus();
                }
              });
              const countyButton = L.DomUtil.create(
                'button', 'county-search-button', container
              );
              countyButton.type = 'button';
              countyButton.title = 'Explore accessibility by Georgia county';
              countyButton.setAttribute('aria-label', countyButton.title);
              countyButton.innerHTML = '▦';
              L.DomEvent.on(countyButton, 'click', function() {
                if (toggleExclusivePanel('county-search-panel')) {
                  document.getElementById('county-search-select').focus();
                }
              });
              const helpButton = L.DomUtil.create('button', 'map-help-button', container);
              helpButton.type = 'button';
              helpButton.title = 'How to use this map';
              helpButton.setAttribute('aria-label', helpButton.title);
              helpButton.innerHTML = '?';
              L.DomEvent.on(helpButton, 'click', function() {
                toggleExclusivePanel('map-help-panel');
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
          document.getElementById('address-search-close').addEventListener(
            'click', function() {
              document.getElementById('address-search-panel').style.display = 'none';
            }
          );
          document.getElementById('county-search-close').addEventListener(
            'click', function() {
              document.getElementById('county-search-panel').style.display = 'none';
            }
          );
          const countySelect = document.getElementById('county-search-select');
          countyData.forEach(function(county, index) {
            const option = document.createElement('option');
            option.value = String(index);
            option.textContent = county.county + ' County';
            countySelect.appendChild(option);
          });
          countySelect.addEventListener('change', function() {
            const details = document.getElementById('county-search-details');
            if (this.value === '') {
              details.textContent = 'Choose a county to view its park-access results.';
              return;
            }
            const county = countyData[Number(this.value)];
            const driveDetails = county.drive_time_minutes === null ?
              'Not available' :
              county.drive_time_minutes.toFixed(1) + ' minutes · ' +
              county.drive_distance_miles.toFixed(1) + ' miles';
            const officialLink = county.official_url ?
              '<br><a class="directions-link" target="_blank" rel="noopener noreferrer" href="' +
              escapeHtml(county.official_url) + '">Official park details ↗</a>' : '';
            details.innerHTML =
              '<strong>' + escapeHtml(county.county) + ' County</strong><br>' +
              'Population: ' + formatNumber(county.population) + '<hr>' +
              '<strong>Straight-line access</strong><br>' +
              escapeHtml(county.nearest_park) + '<br>' +
              county.park_distance_miles.toFixed(1) + ' miles · ' +
              escapeHtml(county.access_category) + '<hr>' +
              '<strong>Estimated drive access</strong><br>' +
              escapeHtml(county.nearest_drive_park || 'Not available') + '<br>' +
              driveDetails +
              (county.drive_access_category ?
                ' · ' + escapeHtml(county.drive_access_category) : '') +
              officialLink + '<hr>' +
              '<strong>Nearby recreation suggestions</strong><br>' +
              escapeHtml(county.local_suggestions) +
              '<br><button id="county-share-summary" class="share-summary-button" type="button">Share result</button>';
            const countySummary =
              county.county + ' County park accessibility: population ' +
              formatNumber(county.population) + '. Straight-line: ' +
              county.nearest_park + ', ' +
              county.park_distance_miles.toFixed(1) + ' miles (' +
              county.access_category + '). Estimated drive access: ' +
              (county.nearest_drive_park || 'not available') + ', ' +
              driveDetails +
              (county.drive_access_category ?
                ' (' + county.drive_access_category + ')' : '') +
              '. Nearby recreation suggestions: ' + county.local_suggestions + '.';
            installShareButton(
              'county-share-summary',
              county.county + ' County park accessibility',
              countySummary
            );
            map.fitBounds(county.bounds, {padding: [24, 24]});
          });
          document.getElementById('address-search-form').addEventListener(
            'submit', async function(event) {
              event.preventDefault();
              const input = document.getElementById('address-search-input');
              const status = document.getElementById('address-search-status');
              const query = input.value.trim();
              if (!query) return;
              status.textContent = 'Searching Georgia…';
              try {
                const params = new URLSearchParams({
                  format: 'jsonv2',
                  q: query,
                  countrycodes: 'us',
                  viewbox: '-85.6052,35.0009,-80.7514,30.3579',
                  bounded: '1',
                  limit: '1'
                });
                const response = await fetch(
                  'https://nominatim.openstreetmap.org/search?' + params.toString(),
                  {headers: {'Accept': 'application/json'}}
                );
                if (!response.ok) throw new Error('Location search failed.');
                const results = await response.json();
                if (!results.length) {
                  status.textContent = 'No Georgia match found. Try a fuller address or ZIP code.';
                  return;
                }
                const result = results[0];
                const latitude = Number(result.lat);
                const longitude = Number(result.lon);
                status.textContent = 'Using: ' + result.display_name;
                document.getElementById('address-search-panel').style.display = 'none';
                calculate(latitude, longitude, 'Access from searched location');
              } catch (error) {
                status.textContent = error.message + ' Please try again shortly.';
              }
            }
          );
        })();
        {% endmacro %}
        """
    )

    def __init__(
        self,
        state_parks: list[dict],
        local_options: list[dict],
        county_data: list[dict],
    ) -> None:
        super().__init__()
        self._name = "LocationAccessibilityControl"
        self.state_parks_json = json.dumps(state_parks, ensure_ascii=False)
        self.local_options_json = json.dumps(local_options, ensure_ascii=False)
        self.county_data_json = json.dumps(county_data, ensure_ascii=False)


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
        park_name = str(park["park_name"])
        official = OFFICIAL_PARK_PAGES.get(park_name)
        if official:
            official_name, official_url = official
            official_details = (
                f'<a href="{html.escape(official_url)}" target="_blank" '
                'rel="noopener noreferrer"><strong>Official park details ↗</strong></a>'
                "<br><span>Current alerts, hours, facilities, reservations, "
                "trail maps, and events.</span>"
            )
            if park_name == "GORDONIA-ALATAMAHA SP":
                official_details = (
                    f"<span>Current official listing: {html.escape(official_name)}</span><br>"
                    + official_details
                )
        else:
            official_details = (
                "<span>No dedicated visitor page was matched in the current "
                "Georgia State Parks directory.</span><br>"
                f'<a href="{OFFICIAL_PARK_DIRECTORY}" target="_blank" '
                'rel="noopener noreferrer">Check the official park directory ↗</a>'
            )
        popup_html = (
            f"<strong>{html.escape(park_name)}</strong><hr style='margin:5px 0'>"
            f"{official_details}<br><small>Verify public access and the correct "
            "entrance before traveling.</small>"
        )
        folium.CircleMarker(
            location=[park.geometry.y, park.geometry.x],
            radius=4,
            color="#FFFFFF",
            weight=1,
            fill=True,
            fill_color="#111111",
            fill_opacity=1,
            tooltip=park_name,
            popup=folium.Popup(popup_html, max_width=300),
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
            "official_url": (
                OFFICIAL_PARK_PAGES[row["park_name"]][1]
                if row["park_name"] in OFFICIAL_PARK_PAGES
                else None
            ),
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
    suggestion_csv = PROCESSED / "local_park_suggestions.csv"
    if suggestion_csv.exists():
        suggestion_table = pd.read_csv(suggestion_csv).sort_values(
            ["county", "rank"]
        )
        county_suggestions = (
            suggestion_table.groupby("county")["local_option"]
            .apply(lambda values: ", ".join(values.astype(str)))
            .to_dict()
        )
    else:
        county_suggestions = {}

    county_source = drive if drive is not None else straight
    county_records = []
    for _, row in county_source.sort_values("county").iterrows():
        min_x, min_y, max_x, max_y = row.geometry.bounds
        nearest_drive_park = (
            str(row["nearest_drive_park"])
            if "nearest_drive_park" in row and pd.notna(row["nearest_drive_park"])
            else None
        )
        official_lookup_name = nearest_drive_park or str(row["nearest_park"])
        county_records.append(
            {
                "county": str(row["county"]),
                "population": int(row["population"]),
                "nearest_park": str(row["nearest_park"]),
                "park_distance_miles": float(row["park_distance_miles"]),
                "access_category": str(row["access_category"]),
                "nearest_drive_park": nearest_drive_park,
                "drive_time_minutes": (
                    float(row["drive_time_minutes"])
                    if "drive_time_minutes" in row
                    and pd.notna(row["drive_time_minutes"])
                    else None
                ),
                "drive_distance_miles": (
                    float(row["drive_distance_miles"])
                    if "drive_distance_miles" in row
                    and pd.notna(row["drive_distance_miles"])
                    else None
                ),
                "drive_access_category": (
                    str(row["drive_access_category"])
                    if "drive_access_category" in row
                    and pd.notna(row["drive_access_category"])
                    else None
                ),
                "local_suggestions": county_suggestions.get(
                    str(row["county"]),
                    "No curated suggestions were generated for this county.",
                ),
                "official_url": (
                    OFFICIAL_PARK_PAGES[official_lookup_name][1]
                    if official_lookup_name in OFFICIAL_PARK_PAGES
                    else None
                ),
                "bounds": [[min_y, min_x], [max_y, max_x]],
            }
        )
    LocationAccessibilityControl(
        state_park_locations,
        local_option_locations,
        county_records,
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
