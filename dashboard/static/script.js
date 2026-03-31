/* ═══════════════════════════════════════════════
   KhanVigil — script.js
═══════════════════════════════════════════════ */

const API_BASE = 'http://127.0.0.1:5000';

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

let map, hotspotLayer, approvedLayer, illegalLayer;
let currentSceneIds = [];
let isPlaying = false;
let playInterval = null;

function initMap(aoiKey = 'jharkhand') {
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
            .bindPopup(`<div class="popup-title">${h.label}</div><div class="popup-row">Mining Probability <span>${(h.score * 100).toFixed(0)}%</span></div><div class="popup-row">Status <span style="color:${h.type === 'illegal' ? '#ff3b3b' : '#f0a500'}">${h.type.toUpperCase()}</span></div><div class="popup-row">Location <span>${h.lat.toFixed(4)}°N, ${h.lon.toFixed(4)}°E</span></div>`)
            .addTo(hotspotLayer);
        L.circleMarker([h.lat, h.lon], { radius: 4, color, weight: 1, fillColor: color, fillOpacity: 1 }).addTo(hotspotLayer);
    });
    hotspotLayer.addTo(map);
}

function renderAlerts(alerts) {
    document.getElementById('alert-list').innerHTML = alerts.map(a => `
    <div class="alert-item ${a.type}">
      <div class="alert-dot ${a.type}"></div>
      <div class="alert-body"><div class="alert-title">${a.title}</div><div class="alert-time">${a.time}</div></div>
    </div>`).join('');
    document.getElementById('alert-count').textContent = alerts.filter(a => a.type === 'red').length;
}

function updateClock() {
    const now = new Date();
    const ist = new Date(now.getTime() + 19800000);
    const pad = n => String(n).padStart(2, '0');
    document.getElementById('clock').textContent = `${pad(ist.getUTCHours())}:${pad(ist.getUTCMinutes())}:${pad(ist.getUTCSeconds())} IST`;
    const M = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    document.getElementById('clock-date').textContent = `${M[ist.getUTCMonth()]} ${ist.getUTCDate()}, ${ist.getUTCFullYear()}`;
}

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
    const data = [0.62, 0.60, 0.57, 0.55, 0.52, 0.50, 0.47, 0.44, 0.42, 0.39, 0.37, 0.35];
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

const slider = document.getElementById('time-slider');
slider.addEventListener('input', function () {
    const idx = parseInt(this.value);
    document.getElementById('ts-current').textContent = DATES[idx] || DATES[DATES.length - 1];
    const illPct = Math.round(18 + (idx / 11) * 10);
    document.getElementById('pct-illegal').textContent = illPct + '%';
    document.getElementById('pct-approved').textContent = (100 - illPct) + '%';
    drawDonut(illPct);
});

function togglePlay() {
    isPlaying = !isPlaying;
    document.getElementById('ts-play').textContent = isPlaying ? '⏸' : '▶';
    if (isPlaying) {
        playInterval = setInterval(() => {
            const next = (parseInt(slider.value) + 1) % 12;
            slider.value = next;
            slider.dispatchEvent(new Event('input'));
        }, 1200);
    } else { clearInterval(playInterval); }
}

function switchIndex(name, btn) {
    document.querySelectorAll('.idx-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    /* Wire to /api/mining/analyze for real overlay — see mining_endpoints.py */
}

function refreshData() {
    const btn = document.getElementById('btn-refresh');
    btn.textContent = '↻ Loading…';
    btn.disabled = true;

    fetch(`${API_BASE}/api/mining/scenes`)
        .then(r => r.json())
        .then(data => {
            currentSceneIds = data.scenes.map(s => s.scene_id);
            document.getElementById('pipeline-status').textContent = `${data.count} scenes loaded`;
        })
        .catch(() => { document.getElementById('pipeline-status').textContent = 'Synthetic mode'; })
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

document.getElementById('aoi-select').addEventListener('change', function () { initMap(this.value); });
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        this.classList.add('active');
    });
});

window.addEventListener('DOMContentLoaded', () => {
    initMap('jharkhand');
    renderAlerts(MOCK_ALERTS);
    updateClock();
    setInterval(updateClock, 1000);
    setTimeout(() => {
        drawSparkline(); drawVegChart(); drawDonut(24);
        document.getElementById('last-sync').textContent = 'Synthetic';
        document.getElementById('pipeline-status').textContent = 'Ready (synthetic)';
    }, 200);
    refreshData();
});