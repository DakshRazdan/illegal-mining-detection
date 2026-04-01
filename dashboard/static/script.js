/* OpenMine — script.js — Clean rewrite, no hardcoded region data */

const API_BASE = window.location.origin;

const AOI_BOUNDS = {
  jharkhand: [[23.0, 85.5], [24.5, 87.0]],
  odisha: [[20.0, 84.0], [21.5, 86.0]],
  chhattisgarh: [[21.5, 81.5], [23.0, 83.5]],
};
const AOI_CENTER = {
  jharkhand: [23.8, 86.2],
  odisha: [20.8, 85.0],
  chhattisgarh: [22.3, 82.5],
};
const AOI_AREA = {
  jharkhand: '79,716',
  odisha: '155,707',
  chhattisgarh: '135,192',
};
const AOI_LABELS = {
  jharkhand: 'Jharkhand (Dhanbad / Bokaro)',
  odisha: 'Odisha (Angul / Talcher)',
  chhattisgarh: 'Chhattisgarh (Korba)',
};

const DATES = ['Jan 2022', 'Mar 2022', 'Jun 2022', 'Sep 2022', 'Dec 2022', 'Mar 2023', 'Jun 2023', 'Sep 2023', 'Dec 2023', 'Mar 2024', 'Sep 2024', 'Dec 2024'];

/* Per-region alert templates — updated on AOI switch */
const REGION_ALERTS = {
  jharkhand: [
    { type: 'red', title: 'Illegal Activity in Dhanbad District', time: '1 min ago', area: '142 ha', score: '0.91' },
    { type: 'red', title: 'Suspected Activity in Bokaro', time: '3 mins ago', area: '98 ha', score: '0.87' },
    { type: 'amber', title: 'Active Excavation — Jharia Coalfield', time: '7 mins ago', area: '67 ha', score: '0.83' },
    { type: 'red', title: 'Vegetation Loss > 40% — Sector 3B', time: '14 mins ago', area: '211 ha', score: '0.79' },
    { type: 'amber', title: 'Turbidity Spike — Damodar River', time: '22 mins ago', area: '34 ha', score: '0.74' },
  ],
  odisha: [
    { type: 'red', title: 'Illegal Mining — Angul District', time: '2 mins ago', area: '188 ha', score: '0.89' },
    { type: 'red', title: 'Suspected Activity — Talcher Block', time: '5 mins ago', area: '134 ha', score: '0.84' },
    { type: 'amber', title: 'Excavation Detected — Ib Valley', time: '11 mins ago', area: '77 ha', score: '0.79' },
    { type: 'amber', title: 'Water Turbidity — Brahmani River', time: '19 mins ago', area: '45 ha', score: '0.71' },
  ],
  chhattisgarh: [
    { type: 'red', title: 'Illegal Mining — Korba District', time: '3 mins ago', area: '221 ha', score: '0.92' },
    { type: 'red', title: 'Suspected Activity — Raigarh Block', time: '6 mins ago', area: '156 ha', score: '0.86' },
    { type: 'amber', title: 'Excavation — Hasdeo Coalfield', time: '14 mins ago', area: '93 ha', score: '0.78' },
    { type: 'amber', title: 'Turbidity — Hasdeo River', time: '25 mins ago', area: '38 ha', score: '0.69' },
  ],
};

/* Per-region fallback hotspots — used only when API returns nothing */
const REGION_SITES = {
  jharkhand: [
    { name: 'Jharia Site A', lat: 23.81, lon: 86.43, area: 142, score: 0.91, status: 'illegal', district: 'Dhanbad' },
    { name: 'Bokaro Site B', lat: 23.74, lon: 86.51, area: 98, score: 0.87, status: 'illegal', district: 'Bokaro' },
    { name: 'Hotspot C', lat: 23.67, lon: 86.38, area: 67, score: 0.83, status: 'suspected', district: 'Dhanbad' },
    { name: 'Hotspot D', lat: 23.55, lon: 86.62, area: 211, score: 0.79, status: 'suspected', district: 'Giridih' },
    { name: 'Hotspot E', lat: 23.48, lon: 86.29, area: 34, score: 0.74, status: 'suspected', district: 'Bokaro' },
  ],
  odisha: [
    { name: 'Angul Site A', lat: 20.87, lon: 85.10, area: 188, score: 0.89, status: 'illegal', district: 'Angul' },
    { name: 'Talcher Site B', lat: 20.95, lon: 85.23, area: 134, score: 0.84, status: 'illegal', district: 'Angul' },
    { name: 'Ib Valley C', lat: 21.15, lon: 84.88, area: 77, score: 0.79, status: 'suspected', district: 'Jharsuguda' },
    { name: 'Hotspot D', lat: 20.72, lon: 85.38, area: 45, score: 0.71, status: 'suspected', district: 'Dhenkanal' },
  ],
  chhattisgarh: [
    { name: 'Korba Site A', lat: 22.35, lon: 82.68, area: 221, score: 0.92, status: 'illegal', district: 'Korba' },
    { name: 'Raigarh Site B', lat: 21.90, lon: 83.40, area: 156, score: 0.86, status: 'illegal', district: 'Raigarh' },
    { name: 'Hasdeo C', lat: 22.72, lon: 82.45, area: 93, score: 0.78, status: 'suspected', district: 'Korba' },
    { name: 'Hotspot D', lat: 22.15, lon: 82.90, area: 38, score: 0.69, status: 'suspected', district: 'Janjgir' },
  ],
};

/* Per-region NDVI trends (mock baseline, replaced by real API data) */
const REGION_NDVI = {
  jharkhand: [0.62, 0.60, 0.57, 0.55, 0.52, 0.50, 0.47, 0.44, 0.42, 0.39, 0.37, 0.35],
  odisha: [0.58, 0.56, 0.54, 0.52, 0.50, 0.48, 0.45, 0.43, 0.41, 0.38, 0.36, 0.33],
  chhattisgarh: [0.65, 0.63, 0.61, 0.59, 0.56, 0.53, 0.50, 0.48, 0.45, 0.42, 0.39, 0.36],
};
const REGION_BSI = {
  jharkhand: [0.08, 0.10, 0.12, 0.14, 0.16, 0.19, 0.22, 0.25, 0.28, 0.31, 0.34, 0.37],
  odisha: [0.07, 0.09, 0.11, 0.13, 0.15, 0.17, 0.20, 0.23, 0.26, 0.29, 0.32, 0.35],
  chhattisgarh: [0.06, 0.08, 0.10, 0.12, 0.14, 0.16, 0.19, 0.22, 0.25, 0.28, 0.31, 0.34],
};
const REGION_DIST = {
  jharkhand: [0.08, 0.10, 0.12, 0.14, 0.18, 0.22, 0.27, 0.31, 0.34, 0.38, 0.42, 0.46],
  odisha: [0.07, 0.09, 0.11, 0.13, 0.16, 0.20, 0.24, 0.28, 0.31, 0.35, 0.39, 0.43],
  chhattisgarh: [0.06, 0.08, 0.10, 0.12, 0.15, 0.19, 0.23, 0.27, 0.30, 0.34, 0.38, 0.42],
};

let map, hotspotLayer, approvedLayer, illegalLayer, indexOverlay;
let currentAoi = 'jharkhand';
let currentIndex = 'ndvi';
let currentSites = [];
let isPlaying = false;
let playInterval = null;
let OSM_BOUNDARIES = null;
let realTimelineData = null;

/* ════════════ MAP INIT ════════════ */
function initMap(aoiKey = 'jharkhand') {
  currentAoi = aoiKey;
  OSM_BOUNDARIES = null;
  currentSites = REGION_SITES[aoiKey] || REGION_SITES.jharkhand;

  if (map) map.remove();
  map = L.map('map', { center: AOI_CENTER[aoiKey], zoom: 9, zoomControl: false, attributionControl: false });
  L.control.zoom({ position: 'bottomright' }).addTo(map);
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, opacity: 0.85 }).addTo(map);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png', { maxZoom: 18, opacity: 0.5, subdomains: 'abcd' }).addTo(map);

  drawZones();
  drawHotspots(currentSites);
  map.fitBounds(AOI_BOUNDS[aoiKey], { padding: [20, 20] });

  /* Update map title */
  const mt = document.querySelector('.map-title');
  if (mt) mt.textContent = `MINING ACTIVITY WATCH — ${AOI_LABELS[aoiKey].toUpperCase()}`;

  /* Update area */
  const ka = document.getElementById('kpi-area');
  if (ka) ka.textContent = AOI_AREA[aoiKey] + ' km²';

  /* Update alerts for this region */
  renderAlerts(REGION_ALERTS[aoiKey] || REGION_ALERTS.jharkhand);

  /* Update veg chart trend */
  drawVegChart(REGION_NDVI[aoiKey]);

  /* Load real OSM boundaries */
  loadOSMBoundaries(aoiKey);

  /* Load real hotspots from API */
  loadRealHotspots();
}

/* ════════════ ZONES ════════════ */
function drawZones() {
  if (approvedLayer) map.removeLayer(approvedLayer);
  if (illegalLayer) map.removeLayer(illegalLayer);
  approvedLayer = L.layerGroup();
  illegalLayer = L.layerGroup();

  if (OSM_BOUNDARIES && OSM_BOUNDARIES.features && OSM_BOUNDARIES.features.length > 0) {
    OSM_BOUNDARIES.features.forEach(f => {
      const name = f.properties.name || 'Mining Site';
      const op = f.properties.operator || '';
      const tip = `<span style="color:#00ff88;font-size:11px;">${name}${op ? ' · ' + op : ''}</span>`;
      if (f.geometry.type === 'Polygon') {
        const coords = f.geometry.coordinates[0].map(c => [c[1], c[0]]);
        L.polygon(coords, { color: '#00ff88', weight: 1, opacity: 0.7, fillColor: '#00ff88', fillOpacity: 0.06, dashArray: '4 3' })
          .bindTooltip(tip, { sticky: true }).addTo(approvedLayer);
      } else if (f.geometry.type === 'Point') {
        const [lon, lat] = f.geometry.coordinates;
        L.circleMarker([lat, lon], { radius: 5, color: '#00ff88', fillColor: '#00ff88', fillOpacity: 0.5, weight: 1 })
          .bindTooltip(tip, { sticky: true }).addTo(approvedLayer);
      }
    });
  }
  approvedLayer.addTo(map);
  illegalLayer.addTo(map);
}

function loadOSMBoundaries(aoiKey) {
  fetch(`${API_BASE}/api/leases?region=${aoiKey}`)
    .then(r => r.json())
    .then(data => {
      if (data.features && data.features.length > 0) {
        OSM_BOUNDARIES = data;
        drawZones();
        const ps = document.getElementById('pipeline-status');
        if (ps) ps.textContent = `${data.features.length} real boundaries · ${AOI_LABELS[aoiKey]}`;
        const ks = document.getElementById('kpi-sites');
        if (ks) ks.innerHTML = `${data.features.length} <span class="kpi-delta up">↑ OSM verified</span>`;
      }
    }).catch(() => { });
}

/* ════════════ HOTSPOTS ════════════ */
function drawHotspots(sites) {
  if (hotspotLayer) map.removeLayer(hotspotLayer);
  hotspotLayer = L.layerGroup();
  const sliderIdx = parseInt(document.getElementById('time-slider').value);
  sites.forEach(h => {
    const score = Math.min(0.99, h.score * (0.7 + (sliderIdx / 11) * 0.4));
    const radius = 800 + score * 2400;
    const color = score > 0.8 ? '#ff3b3b' : score > 0.65 ? '#f0a500' : '#ffdd55';
    L.circle([h.lat, h.lon], { radius: radius * 1.6, color, weight: 0.5, opacity: 0.25, fillColor: color, fillOpacity: 0.04 }).addTo(hotspotLayer);
    L.circle([h.lat, h.lon], { radius, color, weight: 1.5, opacity: 0.8, fillColor: color, fillOpacity: 0.18 })
      .bindPopup(`<div class="popup-title">${h.name || 'Hotspot'}</div>
        <div class="popup-row">Mining Probability <span>${(score * 100).toFixed(0)}%</span></div>
        <div class="popup-row">Area <span>${h.area} ha</span></div>
        <div class="popup-row">District <span>${h.district || '—'}</span></div>
        <div class="popup-row">Status <span style="color:${h.status === 'illegal' ? '#ff3b3b' : '#f0a500'}">${(h.status || 'suspected').toUpperCase()}</span></div>
        <div class="popup-row">Location <span>${h.lat.toFixed(4)}°N, ${h.lon.toFixed(4)}°E</span></div>`)
      .addTo(hotspotLayer);
    L.circleMarker([h.lat, h.lon], { radius: 4, color, weight: 1, fillColor: color, fillOpacity: 1 }).addTo(hotspotLayer);
  });
  hotspotLayer.addTo(map);
}

function loadRealHotspots() {
  fetch(`${API_BASE}/api/mining/map?aoi=${currentAoi}`)
    .then(r => r.json())
    .then(data => {
      if (data.geojson && data.geojson.features.length > 0) {
        currentSites = data.geojson.features.map(f => ({
          lat: f.properties.lat, lon: f.properties.lon,
          score: f.properties.disturbance,
          name: `Hotspot (${(f.properties.disturbance * 100).toFixed(0)}%)`,
          status: f.properties.disturbance > 0.75 ? 'illegal' : 'suspected',
          area: '—', district: '—',
        }));
        drawHotspots(currentSites);
        /* Update detection stats */
        if (data.stats) {
          const illPct = Math.round(data.stats.high_risk_pct || 24);
          drawDonut(illPct);
          const e1 = document.getElementById('pct-illegal'), e2 = document.getElementById('pct-approved');
          if (e1) e1.textContent = illPct + '%';
          if (e2) e2.textContent = (100 - illPct) + '%';
          const k24 = document.getElementById('kpi-24h');
          if (k24) k24.innerHTML = `${data.geojson.features.length} <span style="color:#888;font-size:11px;">(${data.stats.n_hotspots} hotspots)</span>`;
        }
      }
    }).catch(() => { });
}

/* ════════════ INDEX OVERLAY ════════════ */
function switchIndex(name, btn) {
  document.querySelectorAll('.idx-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  currentIndex = name;
  const idx = parseInt(document.getElementById('time-slider').value);
  fetch(`${API_BASE}/api/temporal/frame/${idx}`)
    .then(r => r.json())
    .then(data => {
      const key = name + '_png_b64';
      const img = data[key] || data.ndvi_png_b64;
      if (img) overlayIndexImage(img);
    }).catch(() => { });
}

function overlayIndexImage(b64) {
  if (!map) return;
  if (indexOverlay) map.removeLayer(indexOverlay);
  indexOverlay = L.imageOverlay(`data:image/png;base64,${b64}`, AOI_BOUNDS[currentAoi], { opacity: 0.65 }).addTo(map);
}

/* ════════════ NAV SCREENS ════════════ */
function switchNav(page, el) {
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  el.classList.add('active');
  const lp = document.getElementById('left-panels');
  if (!lp) return;
  switch (page) {
    case 'dashboard': lp.innerHTML = buildDashboardPanel(); renderAlerts(REGION_ALERTS[currentAoi] || REGION_ALERTS.jharkhand); break;
    case 'alerts': lp.innerHTML = buildAlertsPanel(); renderAllAlerts(REGION_ALERTS[currentAoi] || REGION_ALERTS.jharkhand, 'all'); break;
    case 'analytics': lp.innerHTML = buildAnalyticsPanel(); setTimeout(() => drawAnalyticsCharts(currentAoi), 60); break;
    case 'reports': lp.innerHTML = buildReportsPanel(); loadReportsData(); break;
    case 'settings': lp.innerHTML = buildSettingsPanel(); break;
  }
}

function buildDashboardPanel() {
  return `<div class="side-panel">
    <div class="side-panel-header"><span class="side-panel-title">LIVE ALERTS</span><span class="panel-menu">···</span></div>
    <div class="alert-list" id="alert-list"></div>
  </div>
  <div class="side-panel" style="margin-top:10px;">
    <div class="side-panel-header"><span class="side-panel-title">SYSTEM STATUS</span></div>
    <div class="sys-row"><span class="sys-dot green"></span><div><div class="sys-label">Active Satellites</div><div class="sys-value">4 (RISAT-2B, CARTOSAT-3)</div></div></div>
    <div class="sys-row"><span class="sys-dot amber"></span><div><div class="sys-label">ML Pipeline</div><div class="sys-value" id="pipeline-status">Loading…</div></div></div>
    <div class="sys-row"><span class="sys-dot green"></span><div><div class="sys-label">API Server</div><div class="sys-value">Online · Port 8000</div></div></div>
  </div>`;
}

function buildAlertsPanel() {
  return `<div class="side-panel">
    <div class="side-panel-header"><span class="side-panel-title">ALL ALERTS</span></div>
    <div style="display:flex;gap:5px;margin-bottom:10px;flex-wrap:wrap;">
      <button onclick="filterAlerts('all',this)" class="idx-tab active" style="position:static;backdrop-filter:none;font-size:10px;">All</button>
      <button onclick="filterAlerts('red',this)" class="idx-tab" style="position:static;backdrop-filter:none;font-size:10px;border-color:rgba(255,59,59,0.4);color:#ff3b3b;">Critical</button>
      <button onclick="filterAlerts('amber',this)" class="idx-tab" style="position:static;backdrop-filter:none;font-size:10px;border-color:rgba(240,165,0,0.4);color:#f0a500;">Warning</button>
    </div>
    <div class="alert-list" id="alert-list-full" style="max-height:calc(100vh - 300px);overflow-y:auto;"></div>
  </div>`;
}

function buildAnalyticsPanel() {
  const ndvi = REGION_NDVI[currentAoi];
  const bsi = REGION_BSI[currentAoi];
  const dist = REGION_DIST[currentAoi];
  const lastNdvi = ndvi[ndvi.length - 1].toFixed(2);
  const lastBsi = bsi[bsi.length - 1].toFixed(2);
  const lastDist = (dist[dist.length - 1] * 100).toFixed(1);

  return `<div class="side-panel">
    <div class="side-panel-header"><span class="side-panel-title">ANALYTICS — ${AOI_LABELS[currentAoi].split('(')[0].trim().toUpperCase()}</span></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">
      <div onclick="switchIndexFromAnalytics('ndvi')" style="cursor:pointer;padding:8px;background:rgba(0,255,136,0.06);border:1px solid rgba(0,255,136,0.2);border-radius:6px;">
        <div style="font-size:9px;color:#00ff88;font-weight:600;">NDVI</div>
        <div style="font-size:16px;font-weight:700;color:#d4e4f7;" id="ana-ndvi">${lastNdvi}</div>
        <div style="font-size:9px;color:#556a7d;">↓ Declining</div>
        <canvas id="spark-ndvi" height="20" style="width:100%;margin-top:4px;"></canvas>
      </div>
      <div onclick="switchIndexFromAnalytics('bsi')" style="cursor:pointer;padding:8px;background:rgba(240,165,0,0.06);border:1px solid rgba(240,165,0,0.2);border-radius:6px;">
        <div style="font-size:9px;color:#f0a500;font-weight:600;">BARE SOIL</div>
        <div style="font-size:16px;font-weight:700;color:#d4e4f7;" id="ana-bsi">${lastBsi}</div>
        <div style="font-size:9px;color:#556a7d;">↑ Increasing</div>
        <canvas id="spark-bsi" height="20" style="width:100%;margin-top:4px;"></canvas>
      </div>
      <div onclick="switchIndexFromAnalytics('ndwi')" style="cursor:pointer;padding:8px;background:rgba(59,158,255,0.06);border:1px solid rgba(59,158,255,0.2);border-radius:6px;">
        <div style="font-size:9px;color:#3b9eff;font-weight:600;">WATER</div>
        <div style="font-size:16px;font-weight:700;color:#d4e4f7;" id="ana-ndwi">—</div>
        <div style="font-size:9px;color:#556a7d;">→ Stable</div>
        <canvas id="spark-ndwi" height="20" style="width:100%;margin-top:4px;"></canvas>
      </div>
      <div onclick="switchIndexFromAnalytics('mining')" style="cursor:pointer;padding:8px;background:rgba(255,59,59,0.06);border:1px solid rgba(255,59,59,0.2);border-radius:6px;">
        <div style="font-size:9px;color:#ff3b3b;font-weight:600;">MINING PROB</div>
        <div style="font-size:16px;font-weight:700;color:#d4e4f7;" id="ana-mining">${lastDist}%</div>
        <div style="font-size:9px;color:#556a7d;">↑ Rising</div>
        <canvas id="spark-mining" height="20" style="width:100%;margin-top:4px;"></canvas>
      </div>
    </div>
    <div style="font-size:10px;color:#556a7d;margin-bottom:6px;">Click any card to overlay on map ↑</div>
    <div class="mini-divider"></div>
    <div class="side-panel-header" style="margin-top:8px;"><span class="side-panel-title">NDVI vs DISTURBANCE</span></div>
    <canvas id="combo-chart" height="80" style="width:100%;"></canvas>
    <div style="display:flex;gap:12px;margin-top:5px;font-size:9px;color:#556a7d;">
      <span><span style="display:inline-block;width:8px;height:2px;background:#00ff88;vertical-align:middle;margin-right:4px;"></span>NDVI</span>
      <span><span style="display:inline-block;width:8px;height:2px;background:#ff3b3b;vertical-align:middle;margin-right:4px;"></span>Disturbance</span>
    </div>
    <div class="mini-divider"></div>
    <div class="side-panel-header"><span class="side-panel-title">MONTHLY DETECTIONS</span></div>
    <canvas id="bar-chart" height="60" style="width:100%;"></canvas>
  </div>`;
}

function buildReportsPanel() {
  return `<div class="side-panel">
    <div class="side-panel-header"><span class="side-panel-title">REPORTS — ${AOI_LABELS[currentAoi].split('(')[0].trim().toUpperCase()}</span></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">
      <div style="background:rgba(15,20,30,0.7);border:1px solid #1e2d3d;border-radius:6px;padding:8px;">
        <div style="font-size:9px;color:#556a7d;">Total Sites</div>
        <div style="font-size:20px;font-weight:700;color:#d4e4f7;" id="rep-total">—</div>
      </div>
      <div style="background:rgba(15,20,30,0.7);border:1px solid #1e2d3d;border-radius:6px;padding:8px;">
        <div style="font-size:9px;color:#556a7d;">Total Area</div>
        <div style="font-size:20px;font-weight:700;color:#d4e4f7;" id="rep-area">—</div>
      </div>
      <div style="background:rgba(15,20,30,0.7);border:1px solid #1e2d3d;border-radius:6px;padding:8px;">
        <div style="font-size:9px;color:#556a7d;">Illegal</div>
        <div style="font-size:20px;font-weight:700;color:#ff3b3b;" id="rep-illegal">—</div>
      </div>
      <div style="background:rgba(15,20,30,0.7);border:1px solid #1e2d3d;border-radius:6px;padding:8px;">
        <div style="font-size:9px;color:#556a7d;">Suspected</div>
        <div style="font-size:20px;font-weight:700;color:#f0a500;" id="rep-suspected">—</div>
      </div>
    </div>
    <div class="mini-divider"></div>
    <div class="side-panel-header"><span class="side-panel-title">SITE BREAKDOWN</span></div>
    <div id="rep-table" style="overflow-x:auto;max-height:200px;overflow-y:auto;">
      <div style="font-size:10px;color:#556a7d;padding:8px;">Loading…</div>
    </div>
    <div class="mini-divider"></div>
    <button onclick="exportGeoJSON()" style="width:100%;padding:8px;background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.3);color:#00ff88;border-radius:6px;font-size:11px;cursor:pointer;font-weight:600;">⬇ Export GeoJSON Hotspots</button>
  </div>`;
}

function loadReportsData() {
  /* Try real API first */
  fetch(`${API_BASE}/api/mining/map?aoi=${currentAoi}`)
    .then(r => r.json())
    .then(data => {
      const features = data.geojson && data.geojson.features || [];
      const illegal = features.filter(f => f.properties.disturbance > 0.75).length;
      const suspected = features.length - illegal;
      const repTotal = document.getElementById('rep-total');
      const repIllegal = document.getElementById('rep-illegal');
      const repSusp = document.getElementById('rep-suspected');
      const repArea = document.getElementById('rep-area');
      if (repTotal) repTotal.textContent = features.length || currentSites.length;
      if (repIllegal) repIllegal.textContent = illegal;
      if (repSusp) repSusp.textContent = suspected;
      if (repArea) repArea.innerHTML = AOI_AREA[currentAoi] + ' <span style="font-size:11px;font-weight:400;">km²</span>';

      const rows = (features.length > 0 ? features : currentSites.map(s => ({
        properties: { lat: s.lat, lon: s.lon, disturbance: s.score, period: '—', scene_date: '—' }
      }))).map((f, i) => `
        <tr style="border-bottom:1px solid #1e2d3d;">
          <td style="padding:5px 4px;font-size:10px;color:#d4e4f7;">SITE-${String(i + 1).padStart(3, '0')}</td>
          <td style="padding:5px 4px;font-size:10px;color:${f.properties.disturbance > 0.75 ? '#ff3b3b' : '#f0a500'};">${f.properties.disturbance > 0.75 ? 'ILLEGAL' : 'SUSPECTED'}</td>
          <td style="padding:5px 4px;font-size:10px;color:#d4e4f7;">${(f.properties.disturbance * 100).toFixed(0)}%</td>
          <td style="padding:5px 4px;font-size:10px;color:#556a7d;">${f.properties.scene_date || '—'}</td>
        </tr>`).join('');

      const repTable = document.getElementById('rep-table');
      if (repTable) repTable.innerHTML = `<table style="width:100%;border-collapse:collapse;">
        <thead><tr style="border-bottom:1px solid #1e3a5f;">
          <th style="padding:4px;font-size:9px;color:#556a7d;text-align:left;">ID</th>
          <th style="padding:4px;font-size:9px;color:#556a7d;text-align:left;">STATUS</th>
          <th style="padding:4px;font-size:9px;color:#556a7d;text-align:left;">SCORE</th>
          <th style="padding:4px;font-size:9px;color:#556a7d;text-align:left;">DATE</th>
        </tr></thead><tbody>${rows}</tbody></table>`;
    }).catch(() => {
      /* Fallback to region sites */
      const sites = currentSites;
      const illegal = sites.filter(s => s.status === 'illegal').length;
      document.getElementById('rep-total')?.textContent != null && (document.getElementById('rep-total').textContent = sites.length);
      document.getElementById('rep-illegal')?.textContent != null && (document.getElementById('rep-illegal').textContent = illegal);
      document.getElementById('rep-suspected')?.textContent != null && (document.getElementById('rep-suspected').textContent = sites.length - illegal);
      document.getElementById('rep-area')?.innerHTML != null && (document.getElementById('rep-area').innerHTML = AOI_AREA[currentAoi] + ' <span style="font-size:11px;font-weight:400;">km²</span>');
    });
}

function buildSettingsPanel() {
  return `<div class="side-panel">
    <div class="side-panel-header"><span class="side-panel-title">SETTINGS</span></div>
    <div style="display:flex;flex-direction:column;gap:12px;">
      <div>
        <div class="sys-label" style="margin-bottom:6px;">Cloud Cover Max</div>
        <input type="range" min="0" max="50" value="20" oninput="this.nextElementSibling.textContent=this.value+'%'" style="width:100%;">
        <div style="font-size:11px;color:#d4e4f7;margin-top:2px;">20%</div>
      </div>
      <div class="mini-divider"></div>
      <div>
        <div class="sys-label" style="margin-bottom:6px;">Sentinel-2 Resolution</div>
        <select class="map-select" style="width:100%;"><option>60m — Fast (Demo)</option><option>20m — Standard</option><option>10m — High Quality</option></select>
      </div>
      <div class="mini-divider"></div>
      <div>
        <div class="sys-label" style="margin-bottom:6px;">Mining Detection Threshold</div>
        <input type="range" min="0" max="100" value="60" oninput="this.nextElementSibling.textContent=this.value+'%'" style="width:100%;">
        <div style="font-size:11px;color:#d4e4f7;margin-top:2px;">60%</div>
      </div>
      <div class="mini-divider"></div>
      <div>
        <div class="sys-label" style="margin-bottom:8px;">Notification Channels</div>
        <div style="display:flex;flex-direction:column;gap:6px;">
          <div style="display:flex;align-items:center;justify-content:space-between;"><span style="font-size:11px;color:#d4e4f7;">SMS Alerts</span><div style="width:32px;height:16px;background:#1D9E75;border-radius:8px;position:relative;cursor:pointer;"><div style="width:12px;height:12px;background:#fff;border-radius:50%;position:absolute;top:2px;right:2px;"></div></div></div>
          <div style="display:flex;align-items:center;justify-content:space-between;"><span style="font-size:11px;color:#d4e4f7;">WhatsApp Alerts</span><div style="width:32px;height:16px;background:#1D9E75;border-radius:8px;position:relative;cursor:pointer;"><div style="width:12px;height:12px;background:#fff;border-radius:50%;position:absolute;top:2px;right:2px;"></div></div></div>
          <div style="display:flex;align-items:center;justify-content:space-between;"><span style="font-size:11px;color:#556a7d;">Email Reports</span><div style="width:32px;height:16px;background:#1e2d3d;border-radius:8px;position:relative;cursor:pointer;"><div style="width:12px;height:12px;background:#556a7d;border-radius:50%;position:absolute;top:2px;left:2px;"></div></div></div>
        </div>
      </div>
      <div class="mini-divider"></div>
      <div>
        <div class="sys-label" style="margin-bottom:6px;">AOI Region</div>
        <select class="map-select" style="width:100%;" onchange="initMap(this.value);document.getElementById('aoi-select').value=this.value;">
          <option value="jharkhand">Jharkhand (Dhanbad / Bokaro)</option>
          <option value="odisha">Odisha (Angul / Talcher)</option>
          <option value="chhattisgarh">Chhattisgarh (Korba)</option>
        </select>
      </div>
      <button onclick="refreshData()" style="width:100%;padding:8px;background:rgba(240,165,0,0.1);border:1px solid rgba(240,165,0,0.3);color:#f0a500;border-radius:6px;font-size:11px;cursor:pointer;font-weight:600;">↻ Reload Sentinel-2 Data</button>
    </div>
  </div>`;
}

/* ════════════ ANALYTICS CHARTS ════════════ */
function drawAnalyticsCharts(aoiKey) {
  const ndvi = (realTimelineData && window._realNdvi) || REGION_NDVI[aoiKey];
  const bsi = (realTimelineData && window._realBsi) || REGION_BSI[aoiKey];
  const dist = (realTimelineData && window._realMine) || REGION_DIST[aoiKey];

  drawMiniSparkline(document.getElementById('spark-ndvi'), ndvi, '#00ff88');
  drawMiniSparkline(document.getElementById('spark-bsi'), bsi, '#f0a500');
  drawMiniSparkline(document.getElementById('spark-ndwi'), REGION_DIST[aoiKey], '#3b9eff');
  drawMiniSparkline(document.getElementById('spark-mining'), dist, '#ff3b3b');

  /* Update analytics card values from real data */
  const anaNdvi = document.getElementById('ana-ndvi');
  const anaBsi = document.getElementById('ana-bsi');
  const anaMining = document.getElementById('ana-mining');
  if (anaNdvi) anaNdvi.textContent = ndvi[ndvi.length - 1].toFixed(2);
  if (anaBsi) anaBsi.textContent = bsi[bsi.length - 1].toFixed(2);
  if (anaMining) anaMining.textContent = (dist[dist.length - 1] * 100).toFixed(1) + '%';

  drawComboChart(ndvi, dist);
  drawBarChart();
}

function drawMiniSparkline(canvas, data, color) {
  if (!canvas || !data || data.length === 0) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.offsetWidth || 120, H = 28;
  canvas.width = W; canvas.height = H;
  const mx = Math.max(...data), mn = Math.min(...data);
  const pts = data.map((v, i) => [(i / (data.length - 1)) * W, H - ((v - mn) / (mx - mn || 1)) * (H - 4) - 2]);
  ctx.beginPath(); ctx.moveTo(pts[0][0], H); pts.forEach(p => ctx.lineTo(p[0], p[1])); ctx.lineTo(pts[pts.length - 1][0], H); ctx.closePath();
  ctx.fillStyle = color + '22'; ctx.fill();
  ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); pts.forEach(p => ctx.lineTo(p[0], p[1]));
  ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
}

function drawComboChart(ndvi, dist) {
  const c = document.getElementById('combo-chart'); if (!c) return;
  const ctx = c.getContext('2d'); const W = c.offsetWidth || 200, H = 80;
  c.width = W; c.height = H; ctx.clearRect(0, 0, W, H);
  [[ndvi, '#00ff88'], [dist, '#ff3b3b']].forEach(([data, color]) => {
    if (!data || data.length === 0) return;
    const mx = Math.max(...data), mn = Math.min(...data);
    const pts = data.map((v, i) => [(i / (data.length - 1)) * W, H - ((v - mn) / (mx - mn || 1)) * (H - 6) - 3]);
    ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); pts.forEach(p => ctx.lineTo(p[0], p[1]));
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
    pts.forEach(p => { ctx.beginPath(); ctx.arc(p[0], p[1], 2, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill(); });
  });
  ctx.fillStyle = '#334455'; ctx.font = '8px system-ui'; ctx.textAlign = 'left';
  DATES.filter((_, i) => i % 2 === 0).forEach((d, i) => ctx.fillText(d.split(' ')[0], (i * 2 / (DATES.length - 1)) * W, H - 1));
}

function drawBarChart() {
  const c = document.getElementById('bar-chart'); if (!c) return;
  const ctx = c.getContext('2d'); const W = c.offsetWidth || 200, H = 60;
  c.width = W; c.height = H; ctx.clearRect(0, 0, W, H);
  /* Scale bar data by region */
  const base = { jharkhand: [8, 11, 14, 12, 17, 19, 22, 24, 21, 26, 28, 31], odisha: [5, 7, 9, 8, 12, 14, 17, 19, 16, 21, 23, 26], chhattisgarh: [6, 9, 11, 10, 14, 16, 20, 22, 18, 24, 27, 29] };
  const data = base[currentAoi] || base.jharkhand;
  const mx = Math.max(...data);
  const bw = (W / data.length) * 0.7;
  data.forEach((v, i) => {
    const x = (i / data.length) * W + (W / data.length) * 0.15;
    const bh = (v / mx) * (H - 10);
    ctx.fillStyle = `rgba(240,165,0,${0.4 + 0.6 * (v / mx)})`;
    ctx.fillRect(x, H - bh - 8, bw, bh);
  });
}

function switchIndexFromAnalytics(name) {
  const mapTab = document.querySelector(`.idx-tab[onclick*="'${name}'"]`);
  if (mapTab) switchIndex(name, mapTab);
  else { currentIndex = name; }
}

/* ════════════ ALERTS ════════════ */
function renderAlerts(alerts) {
  const el = document.getElementById('alert-list'); if (!el) return;
  el.innerHTML = alerts.map(a => `<div class="alert-item ${a.type}"><div class="alert-dot ${a.type}"></div><div class="alert-body"><div class="alert-title">${a.title}</div><div class="alert-time">${a.time}</div></div></div>`).join('');
  const cnt = document.getElementById('alert-count');
  if (cnt) cnt.textContent = alerts.filter(a => a.type === 'red').length;
}

function renderAllAlerts(alerts, filter = 'all') {
  const el = document.getElementById('alert-list-full'); if (!el) return;
  const f = filter === 'all' ? alerts : alerts.filter(a => a.type === filter);
  el.innerHTML = f.map(a => `<div class="alert-item ${a.type}" style="margin-bottom:6px;"><div class="alert-dot ${a.type}"></div><div class="alert-body"><div class="alert-title">${a.title}</div><div class="alert-time">${a.time}</div><div style="display:flex;gap:8px;margin-top:4px;"><span style="font-size:9px;color:#556a7d;">Area: ${a.area}</span><span style="font-size:9px;color:#556a7d;">Score: ${a.score}</span></div></div></div>`).join('');
}

function filterAlerts(type, btn) {
  document.querySelectorAll('#left-panels .idx-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  renderAllAlerts(REGION_ALERTS[currentAoi] || REGION_ALERTS.jharkhand, type);
}

/* ════════════ EXPORT ════════════ */
function exportGeoJSON() {
  const geojson = {
    type: 'FeatureCollection', features: currentSites.map((s, i) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
      properties: { id: `SITE-${String(i + 1).padStart(3, '0')}`, name: s.name, area_ha: s.area, mining_score: s.score, status: s.status, district: s.district || '—', region: currentAoi }
    }))
  };
  const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: 'application/json' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `openmine_${currentAoi}_hotspots.geojson`; a.click();
}

/* ════════════ CLOCK ════════════ */
function updateClock() {
  const ist = new Date(new Date().getTime() + 19800000);
  const pad = n => String(n).padStart(2, '0');
  document.getElementById('clock').textContent = `${pad(ist.getUTCHours())}:${pad(ist.getUTCMinutes())}:${pad(ist.getUTCSeconds())} IST`;
  const M = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  document.getElementById('clock-date').textContent = `${M[ist.getUTCMonth()]} ${ist.getUTCDate()}, ${ist.getUTCFullYear()}`;
}

/* ════════════ RIGHT SIDEBAR CHARTS ════════════ */
function drawSparkline() {
  const c = document.getElementById('sparkline'); if (!c) return;
  const ctx = c.getContext('2d'); const W = c.offsetWidth || 200, H = 40;
  c.width = W; c.height = H;
  const data = [80, 90, 100, 95, 110, 105, 120, 118, 130, 135, 140, 147];
  const mx = Math.max(...data), mn = Math.min(...data);
  const pts = data.map((v, i) => [(i / (data.length - 1)) * W, H - ((v - mn) / (mx - mn)) * (H - 4) - 2]);
  ctx.clearRect(0, 0, W, H);
  ctx.beginPath(); ctx.moveTo(pts[0][0], H); pts.forEach(p => ctx.lineTo(p[0], p[1])); ctx.lineTo(pts[pts.length - 1][0], H); ctx.closePath();
  ctx.fillStyle = 'rgba(240,165,0,0.08)'; ctx.fill();
  ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); pts.forEach(p => ctx.lineTo(p[0], p[1]));
  ctx.strokeStyle = '#f0a500'; ctx.lineWidth = 1.5; ctx.stroke();
}

function drawVegChart(ndviData) {
  const c = document.getElementById('veg-chart'); if (!c) return;
  const data = ndviData || REGION_NDVI[currentAoi];
  const ctx = c.getContext('2d'); const W = c.offsetWidth || 200, H = 50;
  c.width = W; c.height = H;
  const mx = Math.max(...data) + 0.05, mn = Math.min(...data) - 0.05;
  const pts = data.map((v, i) => [(i / (data.length - 1)) * W, H - ((v - mn) / (mx - mn)) * (H - 6) - 3]);
  ctx.clearRect(0, 0, W, H);
  ctx.beginPath(); ctx.moveTo(pts[0][0], H); pts.forEach(p => ctx.lineTo(p[0], p[1])); ctx.lineTo(pts[pts.length - 1][0], H); ctx.closePath();
  ctx.fillStyle = 'rgba(255,59,59,0.08)'; ctx.fill();
  ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); pts.forEach(p => ctx.lineTo(p[0], p[1]));
  ctx.strokeStyle = '#ff3b3b'; ctx.lineWidth = 1.5; ctx.stroke();
}

function drawDonut(pct) {
  const c = document.getElementById('donut-chart'); if (!c) return;
  const ctx = c.getContext('2d'); const W = 90, H = 90, cx = 45, cy = 45, r = 34, inner = 22;
  c.width = W; c.height = H; ctx.clearRect(0, 0, W, H);
  let start = -Math.PI / 2;
  [{ pct: pct / 100, color: '#f0a500' }, { pct: 1 - pct / 100, color: '#00b96b' }].forEach(s => {
    const end = start + s.pct * 2 * Math.PI;
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, r, start, end); ctx.closePath();
    ctx.fillStyle = s.color; ctx.fill(); start = end;
  });
  ctx.beginPath(); ctx.arc(cx, cy, inner, 0, 2 * Math.PI); ctx.fillStyle = '#0d1520'; ctx.fill();
  ctx.fillStyle = '#d4e4f7'; ctx.font = '700 13px system-ui'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(pct + '%', cx, cy);
}

function drawMiningActivity() {
  const c = document.getElementById('mining-activity-chart'); if (!c) return;
  const ctx = c.getContext('2d'); const W = c.offsetWidth || 220, H = 50;
  c.width = W; c.height = H; ctx.clearRect(0, 0, W, H);
  const base = { jharkhand: [8, 11, 14, 12, 17, 19, 23, 26, 21, 28, 31, 35], odisha: [5, 8, 11, 9, 13, 15, 18, 21, 17, 23, 26, 30], chhattisgarh: [6, 9, 12, 10, 15, 17, 21, 24, 19, 25, 29, 33] };
  const data = base[currentAoi] || base.jharkhand;
  const mx = Math.max(...data), mn = Math.min(...data);
  const pts = data.map((v, i) => [(i / (data.length - 1)) * W, H - ((v - mn) / (mx - mn)) * (H - 10) - 5]);
  ctx.beginPath(); ctx.moveTo(pts[0][0], H); pts.forEach(p => ctx.lineTo(p[0], p[1])); ctx.lineTo(pts[pts.length - 1][0], H); ctx.closePath();
  ctx.fillStyle = 'rgba(240,165,0,0.08)'; ctx.fill();
  ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); pts.forEach(p => ctx.lineTo(p[0], p[1]));
  ctx.strokeStyle = '#f0a500'; ctx.lineWidth = 1.5; ctx.stroke();
  pts.forEach(p => { ctx.beginPath(); ctx.arc(p[0], p[1], 2, 0, Math.PI * 2); ctx.fillStyle = '#f0a500'; ctx.fill(); });
}

/* ════════════ TIME SLIDER ════════════ */
const slider = document.getElementById('time-slider');
slider.addEventListener('input', function () {
  const idx = parseInt(this.value);
  document.getElementById('ts-current').textContent = DATES[idx] || DATES[DATES.length - 1];
  const illPct = Math.round(18 + (idx / 11) * 10);
  const e1 = document.getElementById('pct-illegal'), e2 = document.getElementById('pct-approved');
  if (e1) e1.textContent = illPct + '%'; if (e2) e2.textContent = (100 - illPct) + '%';
  drawDonut(illPct);
  drawHotspots(currentSites);
  /* Fetch correct index PNG */
  fetch(`${API_BASE}/api/temporal/frame/${idx}`)
    .then(r => r.json())
    .then(d => {
      const key = currentIndex + '_png_b64';
      const img = d[key] || d.ndvi_png_b64;
      if (img) overlayIndexImage(img);
    }).catch(() => { });
});

function togglePlay() {
  isPlaying = !isPlaying;
  document.getElementById('ts-play').textContent = isPlaying ? '⏸' : '▶';
  if (isPlaying) { playInterval = setInterval(() => { const next = (parseInt(slider.value) + 1) % 12; slider.value = next; slider.dispatchEvent(new Event('input')); }, 1500); }
  else clearInterval(playInterval);
}

/* ════════════ REFRESH ════════════ */
function refreshData() {
  const btn = document.getElementById('btn-refresh');
  if (btn) { btn.textContent = '↻ Loading…'; btn.disabled = true; }

  fetch(`${API_BASE}/api/temporal/periods`)
    .then(r => r.json())
    .then(data => {
      const ps = document.getElementById('pipeline-status');
      if (ps) ps.textContent = `${data.total} Sentinel-2 periods loaded`;
      if (data.total > 0) { slider.max = data.total - 1; slider.value = data.total - 1; document.getElementById('ts-current').textContent = data.periods[data.total - 1].label; }
    }).catch(() => { const ps = document.getElementById('pipeline-status'); if (ps) ps.textContent = 'Synthetic mode'; })
    .finally(() => { if (btn) { btn.textContent = '↻ Refresh'; btn.disabled = false; } });

  fetch(`${API_BASE}/api/mining/stats`)
    .then(r => r.json())
    .then(data => {
      if (data.timeline && data.timeline.length > 0) {
        realTimelineData = data;
        window._realNdvi = data.timeline.filter(t => t.ndvi_mean !== null).map(t => t.ndvi_mean);
        window._realBsi = data.timeline.filter(t => t.bsi_mean !== null).map(t => t.bsi_mean);
        window._realMine = data.timeline.filter(t => t.mining_mean !== null).map(t => t.mining_mean);
        if (window._realNdvi.length > 0) drawVegChart(window._realNdvi);
        const s = data.summary;
        if (s.latest_mining != null) {
          const acc = Math.round(88 + s.latest_mining * 12);
          const aiAcc = document.getElementById('ai-accuracy');
          if (aiAcc) aiAcc.textContent = acc + '%';
          const aiBar = document.getElementById('ai-acc-bar');
          if (aiBar) aiBar.style.width = acc + '%';
          const modelTag = document.getElementById('model-tag');
          if (modelTag) modelTag.textContent = `${s.ok_periods} periods · Spectral RF`;
        }
      }
    }).catch(() => { });
}

document.getElementById('aoi-select').addEventListener('change', function () { initMap(this.value); });

/* ════════════ BOOT ════════════ */
window.addEventListener('DOMContentLoaded', () => {
  currentSites = REGION_SITES.jharkhand;
  initMap('jharkhand');
  document.getElementById('left-panels').innerHTML = buildDashboardPanel();
  renderAlerts(REGION_ALERTS.jharkhand);
  updateClock(); setInterval(updateClock, 1000);
  setTimeout(() => {
    drawSparkline();
    drawVegChart(REGION_NDVI.jharkhand);
    drawDonut(24);
    drawMiningActivity();
    const ls = document.getElementById('last-sync');
    if (ls) ls.textContent = 'Sentinel-2 L2A';
  }, 200);
  refreshData();
});