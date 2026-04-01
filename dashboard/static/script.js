/* OpenMine — script.js */

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
const DATES = ['Jan 2022', 'Mar 2022', 'Jun 2022', 'Sep 2022', 'Dec 2022', 'Mar 2023', 'Jun 2023', 'Sep 2023', 'Dec 2023', 'Mar 2024', 'Sep 2024', 'Dec 2024'];
const NDVI_TREND = [0.62, 0.60, 0.57, 0.55, 0.52, 0.50, 0.47, 0.44, 0.42, 0.39, 0.37, 0.35];
const BSI_TREND = [0.08, 0.10, 0.12, 0.14, 0.16, 0.19, 0.22, 0.25, 0.28, 0.31, 0.34, 0.37];
const DIST_TREND = [0.08, 0.10, 0.12, 0.14, 0.18, 0.22, 0.27, 0.31, 0.34, 0.38, 0.42, 0.46];
const TURB_TREND = [0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.17, 0.18, 0.18, 0.19];

const MOCK_ALERTS = [
  { type: 'red', title: 'Illegal Activity in Dhanbad District', time: '1 min ago', lat: 23.81, lon: 86.43, area: '142 ha', score: '0.91' },
  { type: 'red', title: 'Suspected Activity in Bokaro', time: '3 mins ago', lat: 23.74, lon: 86.51, area: '98 ha', score: '0.87' },
  { type: 'amber', title: 'Active Excavation — Site Alpha', time: '7 mins ago', lat: 23.67, lon: 86.38, area: '67 ha', score: '0.83' },
  { type: 'red', title: 'Vegetation Loss > 40% — Sector 3B', time: '14 mins ago', lat: 23.55, lon: 86.62, area: '211 ha', score: '0.79' },
  { type: 'amber', title: 'Water Turbidity — Damodar River', time: '22 mins ago', lat: 23.48, lon: 86.29, area: '34 ha', score: '0.74' },
];

const SITES = [
  { id: 'SITE-001', name: 'Site Alpha', lat: 23.81, lon: 86.43, area: 142, score: 0.91, status: 'illegal', district: 'Dhanbad', date: 'Mar 2024' },
  { id: 'SITE-002', name: 'Site Beta', lat: 23.74, lon: 86.51, area: 98, score: 0.87, status: 'illegal', district: 'Bokaro', date: 'Jan 2024' },
  { id: 'SITE-003', name: 'Hotspot C', lat: 23.67, lon: 86.38, area: 67, score: 0.83, status: 'suspected', district: 'Dhanbad', date: 'Sep 2023' },
  { id: 'SITE-004', name: 'Hotspot D', lat: 23.55, lon: 86.62, area: 211, score: 0.79, status: 'suspected', district: 'Giridih', date: 'Jun 2023' },
  { id: 'SITE-005', name: 'Hotspot E', lat: 23.48, lon: 86.29, area: 34, score: 0.74, status: 'suspected', district: 'Bokaro', date: 'Mar 2023' },
  { id: 'SITE-006', name: 'Hotspot F', lat: 23.91, lon: 86.57, area: 89, score: 0.68, status: 'suspected', district: 'Dhanbad', date: 'Jan 2023' },
  { id: 'SITE-007', name: 'Hotspot G', lat: 23.39, lon: 86.44, area: 156, score: 0.63, status: 'suspected', district: 'Ramgarh', date: 'Sep 2022' },
];

let OSM_BOUNDARIES = null;
const APPROVED_ZONES_FALLBACK = [
  { name: 'Zone A — Dhanbad Coalfield', coords: [[24.2, 86.2], [24.4, 86.5], [24.3, 86.8], [24.0, 86.7], [23.9, 86.4]] },
  { name: 'Zone B — Bokaro Block', coords: [[23.6, 85.9], [23.8, 86.1], [23.7, 86.4], [23.5, 86.3], [23.4, 86.0]] },
  { name: 'Zone C — Ramgarh', coords: [[23.3, 85.7], [23.5, 85.9], [23.4, 86.1], [23.2, 86.0], [23.1, 85.8]] },
];
const ILLEGAL_ZONES = [
  { name: 'SUSPECTED ILLEGAL — Site Alpha', coords: [[23.78, 86.38], [23.84, 86.42], [23.83, 86.48], [23.77, 86.46]] },
  { name: 'SUSPECTED ILLEGAL — Site Beta', coords: [[23.70, 86.48], [23.76, 86.52], [23.74, 86.58], [23.68, 86.55]] },
];

const INDEX_CONFIG = {
  ndvi: { label: 'NDVI', color: '#00ff88', desc: 'Vegetation health', stat: 'Mean NDVI', val: '0.35', unit: '', trend: NDVI_TREND },
  bsi: { label: 'Bare Soil', color: '#f0a500', desc: 'Bare soil exposure', stat: 'BSI Mean', val: '0.37', unit: '', trend: BSI_TREND },
  ndwi: { label: 'Water', color: '#3b9eff', desc: 'Water body index', stat: 'Water Cover', val: '12.4', unit: '%', trend: TURB_TREND },
  turbidity: { label: 'Turbidity', color: '#c084fc', desc: 'Sediment in water', stat: 'Turb. Index', val: '0.19', unit: '', trend: TURB_TREND },
  mining: { label: 'Mining', color: '#ff3b3b', desc: 'Mining probability', stat: 'High Risk', val: '22.1', unit: '%', trend: DIST_TREND },
};

let map, hotspotLayer, approvedLayer, illegalLayer, indexOverlay, statCard;
let currentAoi = 'jharkhand';
let currentIndex = 'ndvi';
let isPlaying = false;
let playInterval = null;

/* ════════════ MAP ════════════ */
function initMap(aoiKey = 'jharkhand') {
  currentAoi = aoiKey;
  if (map) map.remove();
  map = L.map('map', { center: AOI_CENTER[aoiKey], zoom: 9, zoomControl: false, attributionControl: false });
  L.control.zoom({ position: 'bottomright' }).addTo(map);
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, opacity: 0.85 }).addTo(map);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png', { maxZoom: 18, opacity: 0.5, subdomains: 'abcd' }).addTo(map);
  drawZones(); drawHotspots(SITES);
  map.fitBounds(AOI_BOUNDS[aoiKey], { padding: [20, 20] });
  loadOSMBoundaries(aoiKey);
}

function drawZones() {
  if (approvedLayer) map.removeLayer(approvedLayer);
  if (illegalLayer) map.removeLayer(illegalLayer);
  approvedLayer = L.layerGroup(); illegalLayer = L.layerGroup();

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
  } else {
    APPROVED_ZONES_FALLBACK.forEach(z => L.polygon(z.coords, { color: '#00ff88', weight: 1.5, opacity: 0.85, fillColor: '#00ff88', fillOpacity: 0.04, dashArray: '4 3' }).bindTooltip(`<span style="color:#00ff88;font-size:11px;">${z.name}</span>`, { sticky: true }).addTo(approvedLayer));
  }
  ILLEGAL_ZONES.forEach(z => L.polygon(z.coords, { color: '#ff3b3b', weight: 2, opacity: 0.9, fillColor: '#ff3b3b', fillOpacity: 0.08 }).bindTooltip(`<span style="color:#ff3b3b;font-size:11px;">⚠ ${z.name}</span>`, { sticky: true }).addTo(illegalLayer));
  approvedLayer.addTo(map); illegalLayer.addTo(map);
}

function loadOSMBoundaries(aoiKey) {
  const regionFile = { 'jharkhand': 'jharkhand', 'odisha': 'odisha', 'chhattisgarh': 'chhattisgarh' }[aoiKey] || 'jharkhand';
  fetch(`${API_BASE}/api/leases?region=${regionFile}`)
    .then(r => r.json())
    .then(data => {
      if (data.features && data.features.length > 0) {
        OSM_BOUNDARIES = data;
        drawZones();
        const ps = document.getElementById('pipeline-status');
        if (ps) ps.textContent = `${data.features.length} real mine boundaries loaded`;
      }
    })
    .catch(() => { });
}

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
      .bindPopup(`<div class="popup-title">${h.name || h.label}</div>
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

/* ════════════ INDEX OVERLAY STAT CARD ════════════ */
function showIndexStatCard(indexKey) {
  const cfg = INDEX_CONFIG[indexKey];
  if (!cfg) return;
  const existing = document.getElementById('index-stat-card');
  if (existing) existing.remove();
  const card = document.createElement('div');
  card.id = 'index-stat-card';
  card.style.cssText = `position:absolute;top:80px;right:14px;z-index:600;background:rgba(8,13,20,0.92);border:1px solid ${cfg.color}44;border-left:3px solid ${cfg.color};border-radius:6px;padding:10px 12px;min-width:140px;backdrop-filter:blur(4px);`;
  card.innerHTML = `
    <div style="font-size:10px;color:${cfg.color};font-weight:600;letter-spacing:0.08em;margin-bottom:6px;">${cfg.label.toUpperCase()}</div>
    <div style="font-size:10px;color:#556a7d;margin-bottom:2px;">${cfg.desc}</div>
    <div style="font-size:22px;font-weight:700;color:#d4e4f7;margin-bottom:4px;">${cfg.val}<span style="font-size:12px;font-weight:400;">${cfg.unit}</span></div>
    <div style="font-size:10px;color:#556a7d;">Current period</div>
    <canvas id="idx-sparkline" height="28" style="margin-top:6px;width:100%;"></canvas>
  `;
  document.querySelector('.map-container').appendChild(card);
  setTimeout(() => {
    const c = document.getElementById('idx-sparkline');
    if (!c) return;
    drawMiniSparkline(c, cfg.trend, cfg.color);
  }, 30);
}

function drawMiniSparkline(canvas, data, color) {
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

function switchIndex(name, btn) {
  document.querySelectorAll('.idx-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  currentIndex = name;
  const existing = document.getElementById('index-stat-card');
  if (existing) existing.remove();
  fetch(`${API_BASE}/api/temporal/frame/${parseInt(document.getElementById('time-slider').value)}`)
    .then(r => r.json())
    .then(data => { if (data.ndvi_png_b64) overlayIndexImage(data.ndvi_png_b64); })
    .catch(() => { });
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
    case 'dashboard': lp.innerHTML = buildDashboardPanel(); renderAlerts(MOCK_ALERTS); break;
    case 'alerts': lp.innerHTML = buildAlertsPanel(); renderAllAlerts(MOCK_ALERTS, 'all'); break;
    case 'analytics': lp.innerHTML = buildAnalyticsPanel(); setTimeout(drawAnalyticsCharts, 60); break;
    case 'reports': lp.innerHTML = buildReportsPanel(); break;
    case 'settings': lp.innerHTML = buildSettingsPanel(); break;
  }
}

/* ─── DASHBOARD ─── */
function buildDashboardPanel() {
  return `
  <div class="side-panel">
    <div class="side-panel-header"><span class="side-panel-title">LIVE ALERTS</span><span class="panel-menu">···</span></div>
    <div class="alert-list" id="alert-list"></div>
  </div>
  <div class="side-panel" style="margin-top:10px;">
    <div class="side-panel-header"><span class="side-panel-title">SYSTEM STATUS</span></div>
    <div class="sys-row"><span class="sys-dot green"></span><div><div class="sys-label">Active Satellites</div><div class="sys-value">4 (RISAT-2B, CARTOSAT-3)</div></div></div>
    <div class="sys-row"><span class="sys-dot amber"></span><div><div class="sys-label">ML Pipeline</div><div class="sys-value" id="pipeline-status">Synthetic mode</div></div></div>
    <div class="sys-row"><span class="sys-dot green"></span><div><div class="sys-label">API Server</div><div class="sys-value">Online · Port 8000</div></div></div>
  </div>`;
}

/* ─── ALERTS ─── */
function buildAlertsPanel() {
  return `
  <div class="side-panel">
    <div class="side-panel-header"><span class="side-panel-title">ALL ALERTS</span></div>
    <div style="display:flex;gap:5px;margin-bottom:10px;flex-wrap:wrap;">
      <button onclick="filterAlerts('all',this)" class="idx-tab active" style="position:static;backdrop-filter:none;font-size:10px;">All</button>
      <button onclick="filterAlerts('red',this)" class="idx-tab" style="position:static;backdrop-filter:none;font-size:10px;border-color:rgba(255,59,59,0.4);color:#ff3b3b;">Critical</button>
      <button onclick="filterAlerts('amber',this)" class="idx-tab" style="position:static;backdrop-filter:none;font-size:10px;border-color:rgba(240,165,0,0.4);color:#f0a500;">Warning</button>
    </div>
    <div class="alert-list" id="alert-list-full" style="max-height:calc(100vh - 300px);overflow-y:auto;"></div>
  </div>`;
}

/* ─── ANALYTICS ─── */
function buildAnalyticsPanel() {
  return `
  <div class="side-panel">
    <div class="side-panel-header"><span class="side-panel-title">ANALYTICS</span></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">
      <div class="metric-card" onclick="switchIndexFromAnalytics('ndvi')" style="cursor:pointer;padding:8px;background:rgba(0,255,136,0.06);border:1px solid rgba(0,255,136,0.2);border-radius:6px;">
        <div style="font-size:9px;color:#00ff88;font-weight:600;letter-spacing:0.08em;">NDVI</div>
        <div style="font-size:16px;font-weight:700;color:#d4e4f7;">0.35</div>
        <div style="font-size:9px;color:#556a7d;">↓ Declining</div>
        <canvas id="spark-ndvi" height="20" style="width:100%;margin-top:4px;"></canvas>
      </div>
      <div class="metric-card" onclick="switchIndexFromAnalytics('bsi')" style="cursor:pointer;padding:8px;background:rgba(240,165,0,0.06);border:1px solid rgba(240,165,0,0.2);border-radius:6px;">
        <div style="font-size:9px;color:#f0a500;font-weight:600;letter-spacing:0.08em;">BARE SOIL</div>
        <div style="font-size:16px;font-weight:700;color:#d4e4f7;">0.37</div>
        <div style="font-size:9px;color:#556a7d;">↑ Increasing</div>
        <canvas id="spark-bsi" height="20" style="width:100%;margin-top:4px;"></canvas>
      </div>
      <div class="metric-card" onclick="switchIndexFromAnalytics('ndwi')" style="cursor:pointer;padding:8px;background:rgba(59,158,255,0.06);border:1px solid rgba(59,158,255,0.2);border-radius:6px;">
        <div style="font-size:9px;color:#3b9eff;font-weight:600;letter-spacing:0.08em;">WATER</div>
        <div style="font-size:16px;font-weight:700;color:#d4e4f7;">12.4%</div>
        <div style="font-size:9px;color:#556a7d;">→ Stable</div>
        <canvas id="spark-ndwi" height="20" style="width:100%;margin-top:4px;"></canvas>
      </div>
      <div class="metric-card" onclick="switchIndexFromAnalytics('mining')" style="cursor:pointer;padding:8px;background:rgba(255,59,59,0.06);border:1px solid rgba(255,59,59,0.2);border-radius:6px;">
        <div style="font-size:9px;color:#ff3b3b;font-weight:600;letter-spacing:0.08em;">MINING PROB</div>
        <div style="font-size:16px;font-weight:700;color:#d4e4f7;">22.1%</div>
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

/* ─── REPORTS ─── */
function buildReportsPanel() {
  const rows = SITES.map(s => `
    <tr style="border-bottom:1px solid #1e2d3d;">
      <td style="padding:5px 4px;font-size:10px;color:#d4e4f7;">${s.id}</td>
      <td style="padding:5px 4px;font-size:10px;color:${s.status === 'illegal' ? '#ff3b3b' : '#f0a500'};">${s.status.toUpperCase()}</td>
      <td style="padding:5px 4px;font-size:10px;color:#d4e4f7;">${s.area} ha</td>
      <td style="padding:5px 4px;font-size:10px;color:#d4e4f7;">${(s.score * 100).toFixed(0)}%</td>
      <td style="padding:5px 4px;font-size:10px;color:#556a7d;">${s.district}</td>
    </tr>`).join('');
  return `
  <div class="side-panel">
    <div class="side-panel-header"><span class="side-panel-title">REPORTS</span></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">
      <div style="background:rgba(15,20,30,0.7);border:1px solid #1e2d3d;border-radius:6px;padding:8px;">
        <div style="font-size:9px;color:#556a7d;">Total Sites</div>
        <div style="font-size:20px;font-weight:700;color:#d4e4f7;">147</div>
      </div>
      <div style="background:rgba(15,20,30,0.7);border:1px solid #1e2d3d;border-radius:6px;padding:8px;">
        <div style="font-size:9px;color:#556a7d;">Total Area</div>
        <div style="font-size:20px;font-weight:700;color:#d4e4f7;">2,847<span style="font-size:11px;font-weight:400;"> ha</span></div>
      </div>
      <div style="background:rgba(15,20,30,0.7);border:1px solid #1e2d3d;border-radius:6px;padding:8px;">
        <div style="font-size:9px;color:#556a7d;">Illegal</div>
        <div style="font-size:20px;font-weight:700;color:#ff3b3b;">35</div>
      </div>
      <div style="background:rgba(15,20,30,0.7);border:1px solid #1e2d3d;border-radius:6px;padding:8px;">
        <div style="font-size:9px;color:#556a7d;">Suspected</div>
        <div style="font-size:20px;font-weight:700;color:#f0a500;">112</div>
      </div>
    </div>
    <div class="mini-divider"></div>
    <div class="side-panel-header"><span class="side-panel-title">SITE BREAKDOWN</span></div>
    <div style="overflow-x:auto;max-height:200px;overflow-y:auto;">
      <table style="width:100%;border-collapse:collapse;">
        <thead><tr style="border-bottom:1px solid #1e3a5f;">
          <th style="padding:4px;font-size:9px;color:#556a7d;text-align:left;">ID</th>
          <th style="padding:4px;font-size:9px;color:#556a7d;text-align:left;">STATUS</th>
          <th style="padding:4px;font-size:9px;color:#556a7d;text-align:left;">AREA</th>
          <th style="padding:4px;font-size:9px;color:#556a7d;text-align:left;">SCORE</th>
          <th style="padding:4px;font-size:9px;color:#556a7d;text-align:left;">DISTRICT</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <div class="mini-divider"></div>
    <button onclick="exportGeoJSON()" style="width:100%;padding:8px;background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.3);color:#00ff88;border-radius:6px;font-size:11px;cursor:pointer;font-weight:600;letter-spacing:0.05em;">⬇ Export GeoJSON Hotspots</button>
  </div>`;
}

/* ─── SETTINGS ─── */
function buildSettingsPanel() {
  return `
  <div class="side-panel">
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
        <select class="map-select" style="width:100%;">
          <option>60m — Fast (Demo)</option>
          <option>20m — Standard</option>
          <option>10m — High Quality</option>
        </select>
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
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <span style="font-size:11px;color:#d4e4f7;">SMS Alerts</span>
            <div style="width:32px;height:16px;background:#1D9E75;border-radius:8px;position:relative;cursor:pointer;"><div style="width:12px;height:12px;background:#fff;border-radius:50%;position:absolute;top:2px;right:2px;"></div></div>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <span style="font-size:11px;color:#d4e4f7;">WhatsApp Alerts</span>
            <div style="width:32px;height:16px;background:#1D9E75;border-radius:8px;position:relative;cursor:pointer;"><div style="width:12px;height:12px;background:#fff;border-radius:50%;position:absolute;top:2px;right:2px;"></div></div>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <span style="font-size:11px;color:#556a7d;">Email Reports</span>
            <div style="width:32px;height:16px;background:#1e2d3d;border-radius:8px;position:relative;cursor:pointer;"><div style="width:12px;height:12px;background:#556a7d;border-radius:50%;position:absolute;top:2px;left:2px;"></div></div>
          </div>
        </div>
      </div>
      <div class="mini-divider"></div>
      <div>
        <div class="sys-label" style="margin-bottom:6px;">AOI Region</div>
        <select class="map-select" style="width:100%;" onchange="initMap(this.value)">
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
function drawAnalyticsCharts() {
  drawMiniSparkline(document.getElementById('spark-ndvi'), NDVI_TREND, '#00ff88');
  drawMiniSparkline(document.getElementById('spark-bsi'), BSI_TREND, '#f0a500');
  drawMiniSparkline(document.getElementById('spark-ndwi'), TURB_TREND, '#3b9eff');
  drawMiniSparkline(document.getElementById('spark-mining'), DIST_TREND, '#ff3b3b');
  drawComboChart();
  drawBarChart();
}

function drawComboChart() {
  const c = document.getElementById('combo-chart');
  if (!c) return;
  const ctx = c.getContext('2d');
  const W = c.offsetWidth || 200, H = 80;
  c.width = W; c.height = H;
  ctx.clearRect(0, 0, W, H);

  [[NDVI_TREND, '#00ff88'], [DIST_TREND, '#ff3b3b']].forEach(([data, color]) => {
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
  const c = document.getElementById('bar-chart');
  if (!c) return;
  const ctx = c.getContext('2d');
  const W = c.offsetWidth || 200, H = 60;
  c.width = W; c.height = H;
  ctx.clearRect(0, 0, W, H);
  const data = [8, 11, 14, 12, 17, 19, 22, 24, 21, 26, 28, 31];
  const mx = Math.max(...data);
  const bw = (W / data.length) * 0.7;
  data.forEach((v, i) => {
    const x = (i / data.length) * W + (W / data.length) * 0.15;
    const bh = (v / mx) * (H - 10);
    const alpha = 0.4 + 0.6 * (v / mx);
    ctx.fillStyle = `rgba(240,165,0,${alpha})`;
    ctx.fillRect(x, H - bh - 8, bw, bh);
  });
}

function switchIndexFromAnalytics(name) {
  const mapTab = document.querySelector(`.idx-tab[onclick*="${name}"]`);
  if (mapTab) switchIndex(name, mapTab);
  else { currentIndex = name; }
}

/* ════════════ ALERT HELPERS ════════════ */
function renderAlerts(alerts) {
  const el = document.getElementById('alert-list');
  if (!el) return;
  el.innerHTML = alerts.map(a => `<div class="alert-item ${a.type}"><div class="alert-dot ${a.type}"></div><div class="alert-body"><div class="alert-title">${a.title}</div><div class="alert-time">${a.time}</div></div></div>`).join('');
  const cnt = document.getElementById('alert-count');
  if (cnt) cnt.textContent = alerts.filter(a => a.type === 'red').length;
}

function renderAllAlerts(alerts, filter = 'all') {
  const el = document.getElementById('alert-list-full');
  if (!el) return;
  const filtered = filter === 'all' ? alerts : alerts.filter(a => a.type === filter);
  el.innerHTML = filtered.map(a => `
    <div class="alert-item ${a.type}" style="margin-bottom:6px;">
      <div class="alert-dot ${a.type}"></div>
      <div class="alert-body">
        <div class="alert-title">${a.title}</div>
        <div class="alert-time">${a.time}</div>
        <div style="display:flex;gap:8px;margin-top:4px;">
          <span style="font-size:9px;color:#556a7d;">Area: ${a.area}</span>
          <span style="font-size:9px;color:#556a7d;">Score: ${a.score}</span>
        </div>
      </div>
    </div>`).join('');
}

function filterAlerts(type, btn) {
  document.querySelectorAll('#left-panels .idx-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  renderAllAlerts(MOCK_ALERTS, type);
}

/* ════════════ EXPORT ════════════ */
function exportGeoJSON() {
  const geojson = {
    type: 'FeatureCollection',
    features: SITES.map(s => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
      properties: { id: s.id, name: s.name, area_ha: s.area, mining_score: s.score, status: s.status, district: s.district, date: s.date }
    }))
  };
  const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: 'application/json' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'openmine_hotspots.geojson'; a.click();
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

function drawVegChart() {
  const c = document.getElementById('veg-chart'); if (!c) return;
  const ctx = c.getContext('2d'); const W = c.offsetWidth || 200, H = 50;
  c.width = W; c.height = H;
  const mx = 0.65, mn = 0.30;
  const pts = NDVI_TREND.map((v, i) => [(i / (NDVI_TREND.length - 1)) * W, H - ((v - mn) / (mx - mn)) * (H - 6) - 3]);
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

/* ════════════ MINING ACTIVITY LINE CHART ════════════ */
function drawMiningActivity() {
  const c = document.getElementById('mining-activity-chart');
  if (!c) return;
  const ctx = c.getContext('2d');
  const W = c.offsetWidth || 220, H = 50;
  c.width = W; c.height = H;
  ctx.clearRect(0, 0, W, H);

  const data = [8, 11, 14, 12, 17, 19, 23, 26, 21, 28, 31, 35];
  const mx = Math.max(...data), mn = Math.min(...data);
  const pts = data.map((v, i) => [
    (i / (data.length - 1)) * W,
    H - ((v - mn) / (mx - mn)) * (H - 10) - 5
  ]);

  /* Area fill */
  ctx.beginPath();
  ctx.moveTo(pts[0][0], H);
  pts.forEach(p => ctx.lineTo(p[0], p[1]));
  ctx.lineTo(pts[pts.length - 1][0], H);
  ctx.closePath();
  ctx.fillStyle = 'rgba(240,165,0,0.08)';
  ctx.fill();

  /* Line */
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  pts.forEach(p => ctx.lineTo(p[0], p[1]));
  ctx.strokeStyle = '#f0a500';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  /* Dots at each point */
  pts.forEach(p => {
    ctx.beginPath();
    ctx.arc(p[0], p[1], 2, 0, Math.PI * 2);
    ctx.fillStyle = '#f0a500';
    ctx.fill();
  });

  /* X-axis labels */
  const labels = ['Jan', 'Apr', 'Jul', 'Oct', 'Jan', 'Apr', 'Jul', 'Oct', 'Jan', 'Apr', 'Sep', 'Dec'];
  ctx.fillStyle = '#334455';
  ctx.font = '7px system-ui';
  ctx.textAlign = 'center';
  [0, 3, 6, 9, 11].forEach(i => {
    ctx.fillText(labels[i], pts[i][0], H - 1);
  });
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
  drawHotspots(SITES);
  fetch(`${API_BASE}/api/temporal/frame/${idx}`).then(r => r.json()).then(d => { if (d.ndvi_png_b64) overlayIndexImage(d.ndvi_png_b64); }).catch(() => { });
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
  fetch(`${API_BASE}/api/temporal/periods`).then(r => r.json()).then(data => {
    const ps = document.getElementById('pipeline-status');
    if (ps) ps.textContent = `${data.total} periods loaded`;
    if (data.total > 0) { slider.max = data.total - 1; slider.value = data.total - 1; document.getElementById('ts-current').textContent = data.periods[data.total - 1].label; }
  }).catch(() => { const ps = document.getElementById('pipeline-status'); if (ps) ps.textContent = 'Synthetic mode'; })
    .finally(() => { if (btn) { btn.textContent = '↻ Refresh'; btn.disabled = false; } });

  fetch(`${API_BASE}/api/mining/map`).then(r => r.json()).then(data => {
    if (data.geojson && data.geojson.features.length > 0) {
      const hs = data.geojson.features.map(f => ({ lat: f.properties.lat, lon: f.properties.lon, score: f.properties.disturbance, name: `Hotspot (${(f.properties.disturbance * 100).toFixed(0)}%)`, status: f.properties.disturbance > 0.75 ? 'illegal' : 'suspected', area: '—', district: '—' }));
      drawHotspots(hs);
    }
  }).catch(() => { });
}

document.getElementById('aoi-select').addEventListener('change', function () { initMap(this.value); });

/* ════════════ BOOT ════════════ */
window.addEventListener('DOMContentLoaded', () => {
  initMap('jharkhand');
  document.getElementById('left-panels').innerHTML = buildDashboardPanel();
  renderAlerts(MOCK_ALERTS);
  updateClock(); setInterval(updateClock, 1000);
  setTimeout(() => { drawSparkline(); drawVegChart(); drawDonut(24); drawMiningActivity(); const ls = document.getElementById('last-sync'); if (ls) ls.textContent = 'Synthetic'; }, 200);
  refreshData();
});