// script.js - Three.js Globe and API fetch logic

let scene, camera, renderer, globe;

function init3D() {
    const container = document.getElementById('canvas-container');
    
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0f1a);
    // Add subtle fog for depth
    scene.fog = new THREE.FogExp2(0x0a0f1a, 0.002);
    
    camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.z = 120;
    camera.position.y = 10;
    
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);
    
    // Create the Earth Sphere (Wireframe/Tech aesthetic)
    const geometry = new THREE.SphereGeometry(40, 64, 64);
    const material = new THREE.MeshBasicMaterial({
        color: 0x1a2639,
        wireframe: true,
        transparent: true,
        opacity: 0.15
    });
    
    globe = new THREE.Mesh(geometry, material);
    scene.add(globe);
    
    // Add glowing core
    const coreGeom = new THREE.SphereGeometry(39.5, 32, 32);
    const coreMat = new THREE.MeshBasicMaterial({
        color: 0x050a14,
    });
    const core = new THREE.Mesh(coreGeom, coreMat);
    scene.add(core);

    // Particle field (Stars/Satellites)
    const particlesGeom = new THREE.BufferGeometry();
    const particlesCount = 1000;
    const posArray = new Float32Array(particlesCount * 3);
    for(let i=0; i<particlesCount*3; i++) {
        posArray[i] = (Math.random() - 0.5) * 300;
    }
    particlesGeom.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
    const particlesMat = new THREE.PointsMaterial({
        size: 0.5,
        color: 0xFF9933,
        transparent: true,
        opacity: 0.6
    });
    const particlesMesh = new THREE.Points(particlesGeom, particlesMat);
    scene.add(particlesMesh);
    
    window.addEventListener('resize', onWindowResize, false);
    animate();
}

function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
    requestAnimationFrame(animate);
    globe.rotation.y += 0.001;
    renderer.render(scene, camera);
}

// Data Fetching Logic
async function fetchLatestData() {
    try {
        const [statsRes, alertsRes] = await Promise.all([
            fetch('/api/stats'),
            fetch('/api/alerts')
        ]);
        
        const stats = await statsRes.json();
        const alertsData = await alertsRes.json();
        
        updateStatsPanel(stats);
        updateAlertsFeed(alertsData.alerts);
        updateRiskBar(stats.by_risk_level, stats.total_detections);
        
    } catch (error) {
        console.error("Failed to fetch telemetry:", error);
    }
}

function updateStatsPanel(stats) {
    const container = document.getElementById('stats-container');
    if (!stats.run_id) {
        container.innerHTML = `<p class="text-sm text-yellow-500">Pipeline hasn't generated data yet.</p>`;
        return;
    }
    
    const isReady = stats.total_detections > 0;
    document.getElementById('system-status-indicator').className = `w-2 h-2 rounded-full ${isReady ? 'bg-indiaGreen' : 'bg-saffron'}`;
    document.getElementById('run-id-display').innerText = stats.run_id;

    container.innerHTML = `
        <div class="grid grid-cols-2 gap-4">
            <div class="bg-white/5 p-3 rounded border border-white/5">
                <div class="text-xs text-gray-400">Total Detections</div>
                <div class="text-2xl font-bold">${stats.total_detections}</div>
            </div>
            <div class="bg-white/5 p-3 rounded border border-white/5">
                <div class="text-xs text-gray-400">Total Area (ha)</div>
                <div class="text-2xl font-bold">${stats.total_area_ha}</div>
            </div>
            <div class="bg-white/5 p-3 rounded border border-white/5">
                <div class="text-xs text-red-400">Illegal Validations</div>
                <div class="text-2xl font-bold text-red-500">${stats.illegal_count}</div>
            </div>
            <div class="bg-white/5 p-3 rounded border border-white/5">
                <div class="text-xs text-green-400">Legal Sites</div>
                <div class="text-2xl font-bold text-green-500">${stats.legal_count}</div>
            </div>
        </div>
    `;
}

function updateRiskBar(risks, total) {
    const bar = document.getElementById('risk-bar');
    const labels = document.getElementById('risk-labels');
    
    if (total === 0) {
        bar.innerHTML = '';
        labels.innerHTML = '';
        return;
    }
    
    const critPct = (risks['CRITICAL'] / total) * 100;
    const highPct = (risks['HIGH'] / total) * 100;
    const medPct = (risks['MEDIUM'] / total) * 100;
    const lowPct = (risks['LOW'] / total) * 100;
    
    bar.innerHTML = `
        <div style="width: ${critPct}%" class="bg-red-500 transition-all duration-1000"></div>
        <div style="width: ${highPct}%" class="bg-orange-500 transition-all duration-1000"></div>
        <div style="width: ${medPct}%" class="bg-yellow-500 transition-all duration-1000"></div>
        <div style="width: ${lowPct}%" class="bg-green-500 transition-all duration-1000"></div>
    `;
    
    labels.innerHTML = `
        <span class="text-red-500">C: ${risks['CRITICAL']}</span>
        <span class="text-orange-500">H: ${risks['HIGH']}</span>
        <span class="text-yellow-500">M: ${risks['MEDIUM']}</span>
        <span class="text-green-500">L: ${risks['LOW']}</span>
    `;
}

function updateAlertsFeed(alerts) {
    const container = document.getElementById('alerts-container');
    if (!alerts || alerts.length === 0) {
        container.innerHTML = `<p class="text-sm text-gray-400">No verification events tracked.</p>`;
        return;
    }
    
    let html = '';
    // Sort critical first
    const sorted = [...alerts].sort((a, b) => b.risk_score - a.risk_score);
    
    sorted.forEach(alert => {
        const clsName = `alert-${alert.risk_level.toLowerCase()}`;
        const timeStr = alert.dispatched_at ? new Date(alert.dispatched_at).toLocaleTimeString() : 'N/A';
        
        html += `
        <div class="alert-card ${clsName} bg-white/5 p-3 rounded flex flex-col space-y-2">
            <div class="flex justify-between items-start">
                <span class="text-xs font-mono text-gray-300">${alert.detection_id}</span>
                <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-black/30">${alert.risk_level}</span>
            </div>
            <p class="text-sm font-medium leading-snug">${alert.message}</p>
            <div class="flex justify-between items-end pt-2">
                <span class="text-[10px] text-gray-500">Vol: ${alert.area_ha}ha | Loc: ${alert.lat.toFixed(3)}, ${alert.lon.toFixed(3)}</span>
                <span class="text-[10px] text-gray-400">${timeStr}</span>
            </div>
        </div>
        `;
    });
    
    container.innerHTML = html;
}

// Init
document.addEventListener("DOMContentLoaded", () => {
    init3D();
    fetchLatestData();
    // Poll every 10 seconds
    setInterval(fetchLatestData, 10000);
});
