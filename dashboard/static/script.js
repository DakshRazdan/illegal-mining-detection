/* ═══════════════════════════════════════════════
   OpenMine — script.js
═══════════════════════════════════════════════ */

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
const DATES = [
    'Jan 2022', 'Mar 2022', 'Jun 2022', 'Sep 2022',
    'Dec 2022', 'Mar 2023', 'Jun 2023', 'Sep 2023',
    'Dec 2023', 'Mar 2024', 'Sep 2024', 'Dec 2024',
];
const MOCK_ALERTS = [
    { type: 'red', title: 'Illegal Activity in Dhanbad District', time: '1 min ago' },
    { type: 'red', title: 'Suspected Activity in Bokaro', time: '3 mins ago' },
    { type: 'amber', title: 'Active Excavation — Site Alpha', time: '7 mins ago' },
    { type: 'red', title: 'Vegetation Loss > 40% — Sector 3B', time: '14 mins ago' },
    { type: 'amber', title: 'Water Turbidity Spike — Damodar River', time: '22 mins ago' },
];
const MOCK_HOTSPOTS = [
    { lat: 23.81, lon: 86.43, score: 0.91, label: 'Site Alpha', type: 'illegal' },
    { lat: 23.74, lon: 86.51, score: 0.87, label: 'Site Beta', type: 'illegal' },
    { lat: 23.67, lon: 86.38, score: 0.83, label: 'Hotspot C', type: 'suspected' },
    { lat: 23.55, lon: 86.62, score: 0.79, label: 'Hotspot D', type: 'suspected' },
    { lat: 23.48, lon: 86.29, score: 0.74, label: 'Hotspot E', type: 'suspected' },
    { lat: 23.91, lon: 86.57, score: 0.68, label: 'Hotspot F', type: 'suspected' },
];
const APPROVED_ZONES = [
    { name: 'Zone A — Dhanbad Coalfield', coords: [[24.2, 86.2], [24.4, 86.5], [24.3, 86.8], [24.0, 86.7], [23.9, 86.4]] },
    { name: 'Zone B — Bokaro Block', coords: [[23.6, 85.9], [23.8, 86.1], [23.7, 86.4], [23.5, 86.3], [23.4, 86.0]] },
    { name: 'Zone C — Ramgarh', coords: [[23.3, 85.7], [23.5, 85.9], [23.4, 86.1], [23.2, 86.0], [23.1, 85.8]] },
];
const ILLEGAL_ZONES = [
    { name: 'SUSPECTED ILLEGAL — Site Alpha', coords: [[23.78, 86.38], [23.84, 86.42], [23.83, 86.48], [23.77, 86.46]] },
    { name: 'SUSPECTED ILLEGAL — Site Beta', coords: [[23.70, 86.48], [23.76, 86.52], [23.74, 86.58], [23.68, 86.55]] },
];

/* ── NDVI values per date for slider (mock, replaced by API) ── */
const NDVI_BY_DATE = [0.62, 0.60, 0.57, 0.55, 0.52, 0.50, 0.47, 0.44, 0.42, 0.39, 0.37, 0.35];
const DIST_BY_DATE = [0.08, 0.10, 0.12, 0.14, 0.18, 0.22, 0.27, 0.31, 0.34, 0.38, 0.42, 0.46];

let map, hotspotLayer, approvedLayer, illegalLayer, indexOverlay;
let currentSceneIds = [];
let isPlaying = false;
let playInterval = null;
let currentAoi = 'jharkhand';
let currentIndex = 'ndvi';

/* ══════════════════ MAP ══════════════════ */
function initMap(aoiKey = 'jharkhand') {
    currentAoi = aoiKey;
    if (map) { map.remove(); }
    map = L.map('map', { center: AOI_CENTER[aoiKey], zoom: 9, zoomControl: true, attributionControl: false });
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, opacity: 0.85 }).addTo(map);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png', { maxZoom: 18, opacity: 0.5, subdomains: 'abcd' }).addTo(map);
    drawZones();
    drawHotspots(MOCK_HOTSPOTS);
    map.fitBounds(AOI_BOUNDS[aoiKey], { padding: [20, 20] });
}

function drawZones() {
    if (approvedLayer) map.removeLayer(approvedLayer);
    if (illegalLayer) map.removeLayer(illegalLayer);
    approvedLayer = L.layerGroup();
    illegalLayer = L.layerGroup();
    APPROVED_ZONES.forEach(z => {
        L.polygon(z.coords, { color: '#00ff88', weight: 1.5, opacity: 0.85, fillColor: '#00ff88', fillOpacity: 0.04, dashArray: '4 3' })
            .bindTooltip(`<span style="color:#00ff88;font-size:11px;">${z.name}</span>`, { sticky: true })
            .addTo(approvedLayer);
    });
    ILLEGAL_ZONES.forEach(z => {
        L.polygon(z.coords, { color: '#ff3b3b', weight: 2, opacity: 0.9, fillColor: '#ff3b3b', fillOpacity: 0.08 })
            .bindTooltip(`<span style="color:#ff3b3b;font-size:11px;">⚠ ${z.name}</span>`, { sticky: true })
            .addTo(illegalLayer);
    });
    approvedLayer.addTo(map);
    illegalLayer.addTo(map);
}

function drawHotspots(hotspots) {
    if (hotspotLayer) map.removeLayer(hotspotLayer);
    hotspotLayer = L.layerGroup();
    hotspots.forEach(h => {
        const radius = 800 + h.score * 2400;
        const color = h.score > 0.8 ? '#ff3b3b' : h.score > 0.65 ? '#f0a500' : '#ffdd55';
        L.circle([h.lat, h.lon], { radius: radius * 1.6, color, weight: 0.5, opacity: 0.3, fillColor: color, fillOpacity: 0.04 }).addTo(hotspotLayer);
        L.circle([h.lat, h.lon], { radius, color, weight: 1.5, opacity: 0.8, fillColor: color, fillOpacity: 0.18 })
            .bindPopup(`<div class="popup-title">${h.label}</div>
        <div class="popup-row">Mining Probability <span>${(h.score * 100).toFixed(0)}%</span></div>
        <div class="popup-row">Status <span style="color:${h.type === 'illegal' ? '#ff3b3b' : '#f0a500'}">${h.type.toUpperCase()}</span></div>
        <div class="popup-row">Location <span>${h.lat.toFixed(4)}°N, ${h.lon.toFixed(4)}°E</span></div>`)
            .addTo(hotspotLayer);
        L.circleMarker([h.lat, h.lon], { radius: 4, color, weight: 1, fillColor: color, fillOpacity: 1 }).addTo(hotspotLayer);
    });
    hotspotLayer.addTo(map);
}

/* ══════════════════ NAV PANELS ══════════════════ */
const NAV_PANELS = {
    dashboard: `
    <div class="side-panel">
      <div class="side-panel-header"><span class="side-panel-title">LIVE ALERTS</span><span class="panel-menu">···</span></div>
      <div class="alert-list" id="alert-list"></div>
    </div>
    <div class="side-panel" style="margin-top:10px;">
      <div class="side-panel-header"><span class="side-panel-title">SYSTEM STATUS</span></div>
      <div class="sys-row"><span class="sys-dot green"></span><div><div class="sys-label">Active Satellites</div><div class="sys-value">4 (RISAT-2B, CARTOSAT-3)</div></div></div>
      <div class="sys-row"><span class="sys-dot amber"></span><div><div class="sys-label">ML Pipeline</div><div class="sys-value" id="pipeline-status">Synthetic mode</div></div></div>
      <div class="sys-row"><span class="sys-dot green"></span><div><div class="sys-label">API Server</div><div class="sys-value">Online · Port 8000</div></div></div>
    </div>`,

    alerts: `
    <div class="side-panel">
      <div class="side-panel-header"><span class="side-panel-title">ALL ALERTS</span></div>
      <div style="margin-bottom:8px;display:flex;gap:6px;">
        <button onclick="filterAlerts('all',this)" class="idx-tab active" style="position:static;backdrop-filter:none;">All</button>
        <button onclick="filterAlerts('red',this)" class="idx-tab" style="position:static;backdrop-filter:none;">Critical</button>
        <button onclick="filterAlerts('amber',this)" class="idx-tab" style="position:static;backdrop-filter:none;">Warning</button>
      </div>
      <div class="alert-list" id="alert-list-full"></div>
    </div>`,

    analytics: `
    <div class="side-panel">
      <div class="side-panel-header"><span class="side-panel-title">ANALYTICS</span></div>
      <div class="kpi-row"><div class="kpi-label">NDVI Trend</div></div>
      <canvas id="ndvi-trend" height="60"></canvas>
      <div class="mini-divider"></div>
      <div class="kpi-row"><div class="kpi-label">Disturbance Score</div></div>
      <canvas id="dist-trend" height="60"></canvas>
      <div class="mini-divider"></div>
      <div class="kpi-row"><div class="kpi-label">Total Area Disturbed</div><div class="kpi-value">2,847 ha</div></div>
      <div class="kpi-row"><div class="kpi-label">Active Sites</div><div class="kpi-value">23</div></div>
    </div>`,

    reports: `
    <div class="side-panel">
      <div class="side-panel-header"><span class="side-panel-title">REPORTS</span></div>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <div class="alert-item amber" style="cursor:pointer;" onclick="downloadReport('monthly')">
          <div class="alert-dot amber"></div>
          <div class="alert-body"><div class="alert-title">Monthly Detection Report</div><div class="alert-time">Mar 2024 · PDF</div></div>
        </div>
        <div class="alert-item" style="border-left-color:#3b9eff;cursor:pointer;" onclick="downloadReport('ndvi')">
          <div class="alert-dot" style="background:#3b9eff;box-shadow:0 0 6px #3b9eff;"></div>
          <div class="alert-body"><div class="alert-title">NDVI Change Analysis</div><div class="alert-time">Q1 2024 · CSV</div></div>
        </div>
        <div class="alert-item" style="border-left-color:#00ff88;cursor:pointer;" onclick="downloadReport('sites')">
          <div class="alert-dot" style="background:#00ff88;box-shadow:0 0 6px #00ff88;"></div>
          <div class="alert-body"><div class="alert-title">Verified Sites Summary</div><div class="alert-time">2022–2024 · JSON</div></div>
        </div>
      </div>
      <div class="mini-divider"></div>
      <div style="font-size:10px;color:#556a7d;">Reports generated from Sentinel-2 L2A data via Microsoft Planetary Computer.</div>
    </div>`,

    settings: `
    <div class="side-panel">
      <div class="side-panel-header"><span class="side-panel-title">SETTINGS</span></div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <div>
          <div class="sys-label" style="margin-bottom:4px;">Cloud Cover Threshold</div>
          <input type="range" min="0" max="50" value="20" oninput="this.nextElementSibling.textContent=this.value+'%'">
          <div style="font-size:11px;color:#d4e4f7;margin-top:2px;">20%</div>
        </div>
        <div class="mini-divider"></div>
        <div>
          <div class="sys-label" style="margin-bottom:4px;">Resolution</div>
          <select class="map-select" style="width:100%;">
            <option>60m (Fast)</option>
            <option>20m (Standard)</option>
            <option>10m (High)</option>
          </select>
        </div>
        <div class="mini-divider"></div>
        <div>
          <div class="sys-label" style="margin-bottom:4px;">Detection Threshold</div>
          <input type="range" min="0" max="100" value="60" oninput="this.nextElementSibling.textContent=this.value+'%'">
          <div style="font-size:11px;color:#d4e4f7;margin-top:2px;">60%</div>
        </div>
        <div class="mini-divider"></div>
        <div>
          <div class="sys-label" style="margin-bottom:4px;">Alert Notifications</div>
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <span style="font-size:11px;color:#d4e4f7;">SMS Alerts</span>
            <div style="width:32px;height:16px;background:#1D9E75;border-radius:8px;position:relative;cursor:pointer;">
              <div style="width:12px;height:12px;background:#fff;border-radius:50%;position:absolute;top:2px;right:2px;"></div>
            </div>
          </div>
        </div>
      </div>
    </div>`
};

function switchNav(page, el) {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    el.classList.add('active');

    const leftPanels = document.getElementById('left-panels');
    leftPanels.innerHTML = NAV_PANELS[page] || NAV_PANELS.dashboard;

    if (page === 'dashboard') renderAlerts(MOCK_ALERTS);
    if (page === 'alerts') renderAllAlerts(MOCK_ALERTS);
    if (page === 'analytics') { setTimeout(() => { drawTrendChart('ndvi-trend', NDVI_BY_DATE, '#00ff88'); drawTrendChart('dist-trend', DIST_BY_DATE, '#f0a500'); }, 50); }
}

function renderAlerts(alerts) {
    const el = document.getElementById('alert-list');
    if (!el) return;
    el.innerHTML = alerts.map(a => `
    <div class="alert-item ${a.type}">
      <div class="alert-dot ${a.type}"></div>
      <div class="alert-body"><div class="alert-title">${a.title}</div><div class="alert-time">${a.time}</div></div>
    </div>`).join('');
    const cnt = document.getElementById('alert-count');
    if (cnt) cnt.textContent = alerts.filter(a => a.type === 'red').length;
}

function renderAllAlerts(alerts, filter = 'all') {
    const el = document.getElementById('alert-list-full');
    if (!el) return;
    const filtered = filter === 'all' ? alerts : alerts.filter(a => a.type === filter);
    el.innerHTML = filtered.map(a => `
    <div class="alert-item ${a.type}">
      <div class="alert-dot ${a.type}"></div>
      <div class="alert-body"><div class="alert-title">${a.title}</div><div class="alert-time">${a.time}</div></div>
    </div>`).join('');
}

function filterAlerts(type, btn) {
    document.querySelectorAll('#left-panels .idx-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    renderAllAlerts(MOCK_ALERTS, type);
}

function downloadReport(type) {
    alert(`Report "${type}" would download here when backend is connected.`);
}

function drawTrendChart(id, data, color) {
    const c = document.getElementById(id);
    if (!c) return;
    const ctx = c.getContext('2d');
    const W = c.offsetWidth || 200, H = 60;
    c.width = W; c.height = H;
    const mx = Math.max(...data), mn = Math.min(...data);
    const pts = data.map((v, i) => [(i / (data.length - 1)) * W, H - ((v - mn) / (mx - mn)) * (H - 6) - 3]);
    ctx.clearRect(0, 0, W, H);
    ctx.beginPath(); ctx.moveTo(pts[0][0], H); pts.forEach(p => ctx.lineTo(p[0], p[1])); ctx.lineTo(pts[pts.length - 1][0], H); ctx.closePath();
    ctx.fillStyle = color + '22'; ctx.fill();
    ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); pts.forEach(p => ctx.lineTo(p[0], p[1]));
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
}

/* ══════════════════ TIME SLIDER ══════════════════ */
const slider = document.getElementById('time-slider');

slider.addEventListener('input', function () {
    const idx = parseInt(this.value);
    const date = DATES[idx] || DATES[DATES.length - 1];
    document.getElementById('ts-current').textContent = date;

    /* Update metrics */
    const illPct = Math.round(18 + (idx / 11) * 10);
    const el1 = document.getElementById('pct-illegal');
    const el2 = document.getElementById('pct-approved');
    if (el1) el1.textContent = illPct + '%';
    if (el2) el2.textContent = (100 - illPct) + '%';
    drawDonut(illPct);

    /* Update hotspot sizes to simulate change over time */
    const scaledHotspots = MOCK_HOTSPOTS.map(h => ({
        ...h,
        score: Math.min(0.99, h.score * (0.7 + (idx / 11) * 0.4))
    }));
    drawHotspots(scaledHotspots);

    /* Try to fetch real NDVI frame from backend */
    fetch(`${API_BASE}/api/temporal/frame/${idx}`)
        .then(r => r.json())
        .then(data => {
            if (data.ndvi_png_b64) overlayIndexImage(data.ndvi_png_b64);
            if (data.ndvi_mean) {
                const el = document.getElementById('kpi-sites');
                if (el) el.innerHTML = `${Math.round(data.ndvi_mean * 1000)} <span class="kpi-delta up">↑ ${idx}%</span>`;
            }
        })
        .catch(() => { });
});

function overlayIndexImage(b64png) {
    if (!map) return;
    if (indexOverlay) map.removeLayer(indexOverlay);
    const bounds = AOI_BOUNDS[currentAoi];
    indexOverlay = L.imageOverlay(`data:image/png;base64,${b64png}`, bounds, { opacity: 0.65 }).addTo(map);
}

function togglePlay() {
    isPlaying = !isPlaying;
    const btn = document.getElementById('ts-play');
    btn.textContent = isPlaying ? '⏸' : '▶';
    if (isPlaying) {
        playInterval = setInterval(() => {
            const next = (parseInt(slider.value) + 1) % 12;
            slider.value = next;
            slider.dispatchEvent(new Event('input'));
        }, 1500);
    } else {
        clearInterval(playInterval);
    }
}

/* ══════════════════ INDEX TABS ══════════════════ */
function switchIndex(name, btn) {
    document.querySelectorAll('.idx-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    currentIndex = name;

    const idx = parseInt(slider.value);
    fetch(`${API_BASE}/api/temporal/frame/${idx}`)
        .then(r => r.json())
        .then(data => {
            const key = name === 'ndvi' ? 'ndvi_png_b64' : 'rgb_png_b64';
            if (data[key]) overlayIndexImage(data[key]);
        })
        .catch(() => { });
}

/* ══════════════════ CLOCK ══════════════════ */
function updateClock() {
    const now = new Date();
    const ist = new Date(now.getTime() + 19800000);
    const pad = n => String(n).padStart(2, '0');
    document.getElementById('clock').textContent = `${pad(ist.getUTCHours())}:${pad(ist.getUTCMinutes())}:${pad(ist.getUTCSeconds())} IST`;
    const M = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    document.getElementById('clock-date').textContent = `${M[ist.getUTCMonth()]} ${ist.getUTCDate()}, ${ist.getUTCFullYear()}`;
}

/* ══════════════════ CHARTS ══════════════════ */
function drawSparkline() {
    const c = document.getElementById('sparkline');
    if (!c) return;
    const ctx = c.getContext('2d');
    const W = c.offsetWidth || 200, H = 40;
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
    const c = document.getElementById('veg-chart');
    if (!c) return;
    const ctx = c.getContext('2d');
    const W = c.offsetWidth || 200, H = 50;
    c.width = W; c.height = H;
    const data = NDVI_BY_DATE;
    const mx = 0.65, mn = 0.30;
    const pts = data.map((v, i) => [(i / (data.length - 1)) * W, H - ((v - mn) / (mx - mn)) * (H - 6) - 3]);
    ctx.clearRect(0, 0, W, H);
    ctx.beginPath(); ctx.moveTo(pts[0][0], H); pts.forEach(p => ctx.lineTo(p[0], p[1])); ctx.lineTo(pts[pts.length - 1][0], H); ctx.closePath();
    ctx.fillStyle = 'rgba(255,59,59,0.08)'; ctx.fill();
    ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); pts.forEach(p => ctx.lineTo(p[0], p[1]));
    ctx.strokeStyle = '#ff3b3b'; ctx.lineWidth = 1.5; ctx.stroke();
}

function drawDonut(illegalPct) {
    const c = document.getElementById('donut-chart');
    if (!c) return;
    const ctx = c.getContext('2d');
    const W = 90, H = 90, cx = 45, cy = 45, r = 34, inner = 22;
    c.width = W; c.height = H;
    ctx.clearRect(0, 0, W, H);
    const slices = [{ pct: illegalPct / 100, color: '#f0a500' }, { pct: 1 - illegalPct / 100, color: '#00b96b' }];
    let start = -Math.PI / 2;
    slices.forEach(s => {
        const end = start + s.pct * 2 * Math.PI;
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, r, start, end); ctx.closePath();
        ctx.fillStyle = s.color; ctx.fill(); start = end;
    });
    ctx.beginPath(); ctx.arc(cx, cy, inner, 0, 2 * Math.PI); ctx.fillStyle = '#0d1520'; ctx.fill();
    ctx.fillStyle = '#d4e4f7'; ctx.font = '700 13px system-ui'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(illegalPct + '%', cx, cy);
}

/* ══════════════════ AOI + REFRESH ══════════════════ */
document.getElementById('aoi-select').addEventListener('change', function () { initMap(this.value); });

function refreshData() {
    const btn = document.getElementById('btn-refresh');
    btn.textContent = '↻ Loading…';
    btn.disabled = true;

    fetch(`${API_BASE}/api/temporal/periods`)
        .then(r => r.json())
        .then(data => {
            const ps = document.getElementById('pipeline-status');
            if (ps) ps.textContent = `${data.total} periods loaded`;
            if (data.total > 0) {
                slider.max = data.total - 1;
                slider.value = data.total - 1;
                document.getElementById('ts-current').textContent = data.periods[data.total - 1].label;
            }
        })
        .catch(() => {
            const ps = document.getElementById('pipeline-status');
            if (ps) ps.textContent = 'Synthetic mode';
        })
        .finally(() => { btn.textContent = '↻ Refresh'; btn.disabled = false; });

    fetch(`${API_BASE}/api/mining/map`)
        .then(r => r.json())
        .then(data => {
            if (data.geojson && data.geojson.features.length > 0) {
                const hotspots = data.geojson.features.map(f => ({
                    lat: f.properties.lat, lon: f.properties.lon,
                    score: f.properties.disturbance,
                    label: `Hotspot (${(f.properties.disturbance * 100).toFixed(0)}%)`,
                    type: f.properties.disturbance > 0.75 ? 'illegal' : 'suspected',
                }));
                drawHotspots(hotspots);
            }
        })
        .catch(() => { });
}

/* ══════════════════ BOOT ══════════════════ */
window.addEventListener('DOMContentLoaded', () => {
    initMap('jharkhand');
    renderAlerts(MOCK_ALERTS);
    updateClock();
    setInterval(updateClock, 1000);
    setTimeout(() => {
        drawSparkline();
        drawVegChart();
        drawDonut(24);
        document.getElementById('last-sync').textContent = 'Synthetic';
    }, 200);
    refreshData();
});