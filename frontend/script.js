const API_BASE = (window.location.protocol === 'file:')
    ? 'http://localhost:5000/api'
    : window.location.origin + '/api';

Chart.defaults.color = '#a0a0c0';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = "'Inter', sans-serif";

const COMPOUND_COLORS = {
    Soft: '#ff3333',
    Medium: '#ffd700',
    Hard: '#cccccc',
    Intermediate: '#00cc66',
    Wet: '#0066ff'
};

const STRATEGY_COLORS = [
    '#00d2ff', '#3a7bd5', '#6dd5ed', '#2193b0',
    '#e94560', '#fc5c7d', '#ff7eb3', '#f093fb', '#4facfe'
];

const charts = {};

let availableCircuits = {};
let currentCircuit = 'Silverstone';
let degradationData = null;
let allStrategies = [];
let circuitControlInitialized = false;
let strategySelectInitialized = false;
let compareControlInitialized = false;
let mcControlInitialized = false;
let telemetryControlInitialized = false;

const telemetryState = {
    points: [],
    trackMap: null,
    frameIndex: 0,
    timer: null,
    playing: false
};

let minimapRenderRequest = null;
let minimapLastFrameIndex = -1;
let carTrail = [];

document.addEventListener('DOMContentLoaded', async () => {
    initTabs();
    await initializeApp();
});

async function initializeApp() {
    await loadCircuits();
    await refreshCircuitData();
}

function initTabs() {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.nav-tab').forEach(item => item.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`panel-${tab.dataset.tab}`).classList.add('active');
        });
    });
}

async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: response.statusText }));
        throw new Error(error.error || 'API Error');
    }
    return response.json();
}

function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = (seconds % 60).toFixed(3);
    return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s.padStart(6, '0')}` : `${m}:${s.padStart(6, '0')}`;
}

function destroyChart(id) {
    if (charts[id]) {
        charts[id].destroy();
        delete charts[id];
    }
}

function getCircuitQuery() {
    return `circuit=${encodeURIComponent(currentCircuit)}`;
}

async function loadCircuits() {
    const select = document.getElementById('circuit-select');
    try {
        const data = await fetchJSON(`${API_BASE}/circuits`);
        availableCircuits = data.circuits || {};

        const circuitNames = Object.keys(availableCircuits);
        if (circuitNames.length === 0) {
            throw new Error('No circuits returned by API.');
        }

        if (!availableCircuits[currentCircuit]) {
            currentCircuit = circuitNames[0];
        }

        select.innerHTML = circuitNames.map(name => (
            `<option value="${name}" ${name === currentCircuit ? 'selected' : ''}>${name}</option>`
        )).join('');

        if (!circuitControlInitialized) {
            select.addEventListener('change', async event => {
                currentCircuit = event.target.value;
                await refreshCircuitData();
            });
            circuitControlInitialized = true;
        }
    } catch (error) {
        console.error('Failed to load circuits:', error);
        select.innerHTML = '<option value="">Circuits unavailable</option>';
        document.getElementById('circuit-name').textContent = 'Offline';
    }
}

async function refreshCircuitData() {
    clearRenderedResults();
    await Promise.all([
        loadCircuitInfo(),
        loadDegradationData(),
        loadStrategies()
    ]);
}

function clearRenderedResults() {
    ['grip', 'laptime-deg', 'sim-laptime', 'sim-grip', 'sim-cumulative', 'compare', 'mc-box', 'mc-winprob']
        .forEach(destroyChart);
    document.getElementById('sim-results').classList.add('hidden');
    document.getElementById('compare-results').classList.add('hidden');
    document.getElementById('mc-results').classList.add('hidden');
    document.getElementById('mc-loading').classList.add('hidden');
    document.getElementById('sim-table-body').innerHTML = '';
    document.getElementById('compare-table-body').innerHTML = '';
    document.getElementById('mc-table-body').innerHTML = '';
    document.getElementById('sim-highlight').innerHTML = '';
    document.getElementById('compare-highlight').innerHTML = '';
    document.getElementById('mc-highlight').innerHTML = '';
    resetTelemetryState();
}

async function loadCircuitInfo() {
    try {
        const data = await fetchJSON(`${API_BASE}/compounds?${getCircuitQuery()}`);
        document.getElementById('circuit-name').textContent = data.circuit;
        document.getElementById('total-laps').textContent = data.total_laps;
        document.getElementById('base-time').textContent = `${data.base_lap_time}s`;
        document.title = `F1 Pit Stop Strategy Simulator - ${data.circuit}`;
    } catch (error) {
        console.error('Failed to load circuit info:', error);
        document.getElementById('circuit-name').textContent = 'Offline';
        document.getElementById('total-laps').textContent = '—';
        document.getElementById('base-time').textContent = '—';
    }
}

async function loadDegradationData() {
    try {
        const data = await fetchJSON(`${API_BASE}/degradation?${getCircuitQuery()}`);
        degradationData = data.compounds;
        syncCompoundToggles();
        renderDegradationCharts();
        renderCompoundCards();
        initCompoundToggles();
    } catch (error) {
        console.error('Failed to load degradation data:', error);
    }
}

function syncCompoundToggles() {
    const container = document.getElementById('compound-toggles');
    const compounds = Object.keys(degradationData || {});
    container.innerHTML = compounds.map(name => {
        const lower = name.toLowerCase();
        return `
            <label class="toggle-chip toggle-${lower} active">
                <input type="checkbox" checked data-compound="${name}"> ${name}
            </label>
        `;
    }).join('');
}

function renderDegradationCharts() {
    if (!degradationData) {
        return;
    }

    const active = getActiveCompounds();

    destroyChart('grip');
    const gripDatasets = active.map(name => {
        const compound = degradationData[name];
        const color = compound.color === '#FFFFFF' ? '#cccccc' : compound.color;
        return {
            label: compound.label,
            data: compound.grip.map((grip, index) => ({ x: compound.laps[index], y: grip })),
            borderColor: color,
            backgroundColor: `${color}22`,
            borderWidth: 2.5,
            pointRadius: 0,
            fill: true,
            tension: 0.3
        };
    });

    charts.grip = new Chart(document.getElementById('chart-grip'), {
        type: 'line',
        data: { datasets: gripDatasets },
        options: {
            responsive: true,
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Tire Age (Lap)' }, min: 0, max: 50 },
                y: { title: { display: true, text: 'Grip Level' }, min: 0.45, max: 1.05 }
            },
            plugins: {
                legend: { labels: { usePointStyle: true, pointStyle: 'circle' } }
            }
        }
    });

    destroyChart('laptime-deg');
    const lapTimeDatasets = active.map(name => {
        const compound = degradationData[name];
        const color = compound.color === '#FFFFFF' ? '#cccccc' : compound.color;
        return {
            label: compound.label,
            data: compound.lap_times.map((lapTime, index) => ({ x: compound.laps[index], y: lapTime })),
            borderColor: color,
            borderWidth: 2.5,
            pointRadius: 0,
            tension: 0.3
        };
    });

    charts['laptime-deg'] = new Chart(document.getElementById('chart-laptime-deg'), {
        type: 'line',
        data: { datasets: lapTimeDatasets },
        options: {
            responsive: true,
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Tire Age (Lap)' }, min: 0, max: 50 },
                y: { title: { display: true, text: 'Lap Time (s)' } }
            },
            plugins: {
                legend: { labels: { usePointStyle: true, pointStyle: 'circle' } }
            }
        }
    });
}

function renderCompoundCards() {
    const container = document.getElementById('compound-cards');
    container.innerHTML = Object.entries(degradationData).map(([name, compound]) => {
        const lower = name.toLowerCase();
        return `
            <div class="compound-card card-${lower}">
                <div class="cc-name">${compound.label}</div>
                <div class="cc-stat"><span class="stat-label">Initial Grip</span><span class="stat-value">${compound.initial_grip ?? '—'}</span></div>
                <div class="cc-stat"><span class="stat-label">Deg Rate</span><span class="stat-value">${compound.degradation_rate ?? '—'}</span></div>
                <div class="cc-stat"><span class="stat-label">Cliff Point</span><span class="stat-value">Lap ${compound.cliff_point}</span></div>
                <div class="cc-stat"><span class="stat-label">Warm-up</span><span class="stat-value">${compound.warmup_laps} lap</span></div>
            </div>
        `;
    }).join('');
}

function getActiveCompounds() {
    const active = [];
    document.querySelectorAll('#compound-toggles input').forEach(input => {
        if (input.checked) {
            active.push(input.dataset.compound);
        }
    });
    return active;
}

function initCompoundToggles() {
    document.querySelectorAll('#compound-toggles .toggle-chip').forEach(chip => {
        chip.addEventListener('click', event => {
            event.preventDefault();
            const checkbox = chip.querySelector('input');
            checkbox.checked = !checkbox.checked;
            chip.classList.toggle('active', checkbox.checked);
            renderDegradationCharts();
        });
    });
}

async function loadStrategies() {
    try {
        const data = await fetchJSON(`${API_BASE}/strategies?${getCircuitQuery()}`);
        allStrategies = data.strategies;
        populateStrategySelect();
        populateCompareCheckboxes();
        populateMCCheckboxes();
    } catch (error) {
        console.error('Failed to load strategies:', error);
        allStrategies = [];
    }
}

function populateStrategySelect() {
    const select = document.getElementById('strategy-select');
    select.innerHTML = allStrategies.map(strategy => (
        `<option value="${strategy.name}">${strategy.name} (${strategy.num_stops}-stop)</option>`
    )).join('');

    if (!strategySelectInitialized) {
        select.addEventListener('change', () => renderStintVisual(select.value));
        document.getElementById('btn-simulate').addEventListener('click', runDeterministicSim);
        strategySelectInitialized = true;
    }

    if (allStrategies.length > 0) {
        renderStintVisual(select.value);
    } else {
        document.getElementById('stint-visual').innerHTML = '';
    }
}

function renderStintVisual(strategyName) {
    const strategy = allStrategies.find(item => item.name === strategyName);
    const container = document.getElementById('stint-visual');
    if (!strategy) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = strategy.stints.map(stint => {
        const lower = stint.compound.toLowerCase();
        return `
            <div
                class="stint-block ${lower}"
                style="flex:${stint.length}"
                title="${stint.compound}: Lap ${stint.start_lap}-${stint.end_lap} (${stint.length} laps)"
            >
                ${stint.compound[0]} · ${stint.length}L
            </div>
        `;
    }).join('');
}

async function runDeterministicSim() {
    const strategyName = document.getElementById('strategy-select').value;
    const button = document.getElementById('btn-simulate');
    button.disabled = true;
    button.textContent = 'Running...';

    try {
        const raw = await fetchJSON(`${API_BASE}/simulate/telemetry`, {
            method: 'POST',
            body: JSON.stringify({
                strategy_name: strategyName,
                circuit: currentCircuit,
                timestep_s: 0.5,
                max_points: 1500,
                response_shape: 'v2'
            })
        });
        const data = normalizeTelemetryResponse(raw);
        displaySimResults(data);
    } catch (error) {
        alert(`Error: ${error.message}`);
    } finally {
        button.disabled = false;
        button.innerHTML = '<span class="btn-icon">&#9654;</span> Run Simulation';
    }
}

function displaySimResults(data) {
    const panel = document.getElementById('sim-results');
    panel.classList.remove('hidden');

    document.getElementById('sim-highlight').innerHTML = `
        <div class="highlight-text">
            <div class="hl-title">STRATEGY RESULT</div>
            <div class="hl-value">${data.strategy.name}</div>
            <div class="hl-detail">${data.circuit} · ${data.strategy.num_stops} pit stop(s)</div>
        </div>
        <div class="highlight-stats">
            <div class="hl-stat"><div class="hl-stat-label">Total Time</div><div class="hl-stat-value">${data.summary.total_race_time_formatted}</div></div>
            <div class="hl-stat"><div class="hl-stat-label">Avg Lap</div><div class="hl-stat-value">${Number(data.summary.avg_lap_time).toFixed(3)}s</div></div>
            <div class="hl-stat"><div class="hl-stat-label">Fastest</div><div class="hl-stat-value">${Number(data.summary.fastest_lap).toFixed(3)}s</div></div>
            <div class="hl-stat"><div class="hl-stat-label">Pit Loss</div><div class="hl-stat-value">${Number(data.summary.total_pit_time_lost).toFixed(1)}s</div></div>
        </div>
    `;

    const laps = data.laps;
    const normalLaps = laps.filter(lap => !lap.is_pit_lap);

    destroyChart('sim-laptime');
    charts['sim-laptime'] = new Chart(document.getElementById('chart-sim-laptime'), {
        type: 'line',
        data: { datasets: buildCompoundSegments(normalLaps) },
        options: {
            responsive: true,
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Lap' }, min: 1 },
                y: { title: { display: true, text: 'Lap Time (s)' } }
            },
            plugins: { legend: { labels: { usePointStyle: true } } }
        }
    });

    destroyChart('sim-grip');
    charts['sim-grip'] = new Chart(document.getElementById('chart-sim-grip'), {
        type: 'line',
        data: { datasets: buildCompoundSegments(laps, 'grip') },
        options: {
            responsive: true,
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Lap' } },
                y: { title: { display: true, text: 'Grip' }, min: 0.5, max: 1.05 }
            }
        }
    });

    destroyChart('sim-cumulative');
    charts['sim-cumulative'] = new Chart(document.getElementById('chart-sim-cumulative'), {
        type: 'line',
        data: {
            datasets: [{
                label: 'Cumulative Time',
                data: laps.map(lap => ({ x: lap.lap, y: lap.cumulative_time })),
                borderColor: '#00d2ff',
                borderWidth: 2,
                pointRadius: 0,
                fill: false
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Lap' } },
                y: { title: { display: true, text: 'Time (s)' } }
            }
        }
    });

    document.getElementById('sim-table-body').innerHTML = laps.map(lap => `
        <tr>
            <td>${lap.lap}</td>
            <td style="color:${COMPOUND_COLORS[lap.compound] || '#ffffff'}">${lap.compound}</td>
            <td>${lap.tire_age}</td>
            <td>${Number(lap.grip).toFixed(4)}</td>
            <td>${Number(lap.final_lap_time).toFixed(3)}</td>
            <td>${formatTime(lap.cumulative_time)}</td>
            <td>${lap.is_pit_lap ? '<span class="pit-badge">PIT</span>' : ''}</td>
        </tr>
    `).join('');

    renderTelemetryPlayback(data);
}

function normalizeTelemetryResponse(payload) {
    if (payload && payload.result) {
        return payload.result;
    }
    return payload;
}

function buildCompoundSegments(laps, field = 'final_lap_time') {
    const segments = [];
    let current = null;

    laps.forEach(lap => {
        if (!current || current.compound !== lap.compound) {
            if (current) {
                segments.push(current);
            }
            current = {
                compound: lap.compound,
                label: lap.compound,
                data: [],
                borderColor: COMPOUND_COLORS[lap.compound] || '#ffffff',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.2
            };
        }
        current.data.push({ x: lap.lap, y: lap[field] });
    });

    if (current) {
        segments.push(current);
    }
    return segments;
}

function populateCompareCheckboxes() {
    const grid = document.getElementById('compare-checkboxes');
    grid.innerHTML = allStrategies.map(strategy => `
        <label class="checkbox-item">
            <input type="checkbox" value="${strategy.name}" checked> ${strategy.name}
        </label>
    `).join('');

    if (!compareControlInitialized) {
        document.getElementById('btn-compare').addEventListener('click', runComparison);
        compareControlInitialized = true;
    }
}

async function runComparison() {
    const checked = [...document.querySelectorAll('#compare-checkboxes input:checked')].map(input => input.value);
    if (checked.length < 2) {
        alert('Pilih minimal 2 strategi!');
        return;
    }

    const button = document.getElementById('btn-compare');
    button.disabled = true;
    button.textContent = 'Comparing...';

    try {
        const data = await fetchJSON(`${API_BASE}/compare`, {
            method: 'POST',
            body: JSON.stringify({ strategy_names: checked, circuit: currentCircuit })
        });
        displayCompareResults(data);
    } catch (error) {
        alert(`Error: ${error.message}`);
    } finally {
        button.disabled = false;
        button.innerHTML = '<span class="btn-icon">&#9776;</span> Compare Strategies';
    }
}

function displayCompareResults(data) {
    document.getElementById('compare-results').classList.remove('hidden');
    const best = data.results[0];

    document.getElementById('compare-highlight').innerHTML = `
        <div class="highlight-text">
            <div class="hl-title">FASTEST STRATEGY</div>
            <div class="hl-value">${best.name}</div>
            <div class="hl-detail">${data.circuit} · ${best.num_stops} pit stop(s) · ${best.total_race_time_formatted}</div>
        </div>
    `;

    destroyChart('compare');
    charts.compare = new Chart(document.getElementById('chart-compare'), {
        type: 'bar',
        data: {
            labels: data.results.map(result => result.name),
            datasets: [{
                label: 'Total Race Time (s)',
                data: data.results.map(result => result.total_race_time),
                backgroundColor: data.results.map((_, index) => `${STRATEGY_COLORS[index % STRATEGY_COLORS.length]}cc`),
                borderColor: data.results.map((_, index) => STRATEGY_COLORS[index % STRATEGY_COLORS.length]),
                borderWidth: 1.5,
                borderRadius: 6
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            scales: { x: { title: { display: true, text: 'Total Race Time (s)' } } },
            plugins: { legend: { display: false } }
        }
    });

    document.getElementById('compare-table-body').innerHTML = data.results.map(result => {
        const rankClass = result.rank <= 3 ? `rank-${result.rank}` : '';
        return `
            <tr>
                <td class="${rankClass}">${result.rank}</td>
                <td>${result.name}</td>
                <td>${result.num_stops}</td>
                <td>${result.total_race_time_formatted}</td>
                <td>${Number(result.avg_lap_time).toFixed(3)}s</td>
                <td>${Number(result.fastest_lap).toFixed(3)}s</td>
                <td>${result.delta > 0 ? `+${Number(result.delta).toFixed(3)}s` : 'FASTEST'}</td>
            </tr>
        `;
    }).join('');
}

function populateMCCheckboxes() {
    const grid = document.getElementById('mc-checkboxes');
    grid.innerHTML = allStrategies.map(strategy => `
        <label class="checkbox-item">
            <input type="checkbox" value="${strategy.name}" checked> ${strategy.name}
        </label>
    `).join('');

    if (!mcControlInitialized) {
        const slider = document.getElementById('mc-iterations');
        const label = document.getElementById('mc-iter-value');
        slider.addEventListener('input', () => {
            label.textContent = slider.value;
        });
        document.getElementById('btn-montecarlo').addEventListener('click', runMonteCarlo);
        mcControlInitialized = true;
    }
}

async function runMonteCarlo() {
    const checked = [...document.querySelectorAll('#mc-checkboxes input:checked')].map(input => input.value);
    if (checked.length < 1) {
        alert('Pilih minimal 1 strategi!');
        return;
    }

    const iterations = parseInt(document.getElementById('mc-iterations').value, 10);
    const button = document.getElementById('btn-montecarlo');
    button.disabled = true;
    document.getElementById('mc-loading').classList.remove('hidden');
    document.getElementById('mc-results').classList.add('hidden');

    try {
        const data = await fetchJSON(`${API_BASE}/simulate/monte-carlo`, {
            method: 'POST',
            body: JSON.stringify({ strategy_names: checked, iterations, circuit: currentCircuit })
        });
        displayMCResults(data);
    } catch (error) {
        alert(`Error: ${error.message}`);
    } finally {
        button.disabled = false;
        button.innerHTML = '<span class="btn-icon">&#9733;</span> Run Monte Carlo';
        document.getElementById('mc-loading').classList.add('hidden');
    }
}

function displayMCResults(data) {
    document.getElementById('mc-results').classList.remove('hidden');
    const best = data.results[0];

    document.getElementById('mc-highlight').innerHTML = `
        <div class="highlight-text">
            <div class="hl-title">BEST STRATEGY (MONTE CARLO)</div>
            <div class="hl-value">${best.name}</div>
            <div class="hl-detail">${data.circuit} · Win Probability: ${best.win_probability}% · Mean: ${best.mean_formatted}</div>
        </div>
        <div class="highlight-stats">
            <div class="hl-stat"><div class="hl-stat-label">Iterations</div><div class="hl-stat-value">${data.iterations}</div></div>
            <div class="hl-stat"><div class="hl-stat-label">Std Dev</div><div class="hl-stat-value">${Number(best.std).toFixed(1)}s</div></div>
            <div class="hl-stat"><div class="hl-stat-label">95% CI</div><div class="hl-stat-value">${formatTime(best.ci_lower)} - ${formatTime(best.ci_upper)}</div></div>
        </div>
    `;

    destroyChart('mc-box');
    charts['mc-box'] = new Chart(document.getElementById('chart-mc-box'), {
        type: 'bar',
        data: {
            labels: data.results.map(result => result.name),
            datasets: [{
                label: 'Mean Race Time',
                data: data.results.map(result => result.mean),
                backgroundColor: data.results.map((_, index) => `${STRATEGY_COLORS[index % STRATEGY_COLORS.length]}88`),
                borderColor: data.results.map((_, index) => STRATEGY_COLORS[index % STRATEGY_COLORS.length]),
                borderWidth: 2,
                borderRadius: 4
            }, {
                label: 'Min',
                data: data.results.map(result => result.min),
                type: 'scatter',
                pointStyle: 'triangle',
                pointRadius: 6,
                backgroundColor: '#00d2ff',
                borderColor: '#00d2ff'
            }, {
                label: 'Max',
                data: data.results.map(result => result.max),
                type: 'scatter',
                pointStyle: 'triangle',
                pointRadius: 6,
                rotation: 180,
                backgroundColor: '#e94560',
                borderColor: '#e94560'
            }]
        },
        options: {
            responsive: true,
            scales: { y: { title: { display: true, text: 'Total Race Time (s)' } } },
            plugins: { legend: { labels: { usePointStyle: true } } }
        }
    });

    destroyChart('mc-winprob');
    const winResults = data.results.filter(result => result.win_probability > 0);
    charts['mc-winprob'] = new Chart(document.getElementById('chart-mc-winprob'), {
        type: 'doughnut',
        data: {
            labels: winResults.map(result => result.name),
            datasets: [{
                data: winResults.map(result => result.win_probability),
                backgroundColor: winResults.map((_, index) => STRATEGY_COLORS[index % STRATEGY_COLORS.length]),
                borderColor: '#0a0a1a',
                borderWidth: 3,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            cutout: '55%',
            plugins: {
                legend: {
                    position: 'right',
                    labels: { usePointStyle: true, pointStyle: 'circle', padding: 15, font: { size: 11 } }
                },
                tooltip: {
                    callbacks: { label: context => `${context.label}: ${context.parsed}%` }
                }
            }
        }
    });

    document.getElementById('mc-table-body').innerHTML = data.results.map((result, index) => {
        const rankClass = index < 3 ? `rank-${index + 1}` : '';
        return `
            <tr>
                <td class="${rankClass}">${index + 1}</td>
                <td>${result.name}</td>
                <td>${result.mean_formatted}</td>
                <td>${Number(result.std).toFixed(3)}s</td>
                <td>${formatTime(result.ci_lower)} - ${formatTime(result.ci_upper)}</td>
                <td>${formatTime(result.min)}</td>
                <td>${formatTime(result.max)}</td>
                <td style="font-weight:700;color:${result.win_probability > 0 ? '#00d2ff' : '#666'}">${result.win_probability}%</td>
            </tr>
        `;
    }).join('');
}

function resetTelemetryState() {
    if (telemetryState.timer) {
        clearInterval(telemetryState.timer);
    }
    telemetryState.points = [];
    telemetryState.trackMap = null;
    telemetryState.frameIndex = 0;
    telemetryState.timer = null;
    telemetryState.playing = false;
    minimapLastFrameIndex = -1;
    carTrail = [];
    if (minimapRenderRequest) {
        cancelAnimationFrame(minimapRenderRequest);
        minimapRenderRequest = null;
    }

    const scrub = document.getElementById('telemetry-scrub');
    const frameLabel = document.getElementById('telemetry-frame-label');
    const playBtn = document.getElementById('btn-telemetry-play');
    const sampling = document.getElementById('telemetry-sampling');
    if (scrub) {
        scrub.max = 0;
        scrub.value = 0;
    }
    if (frameLabel) {
        frameLabel.textContent = 'Frame 0 / 0';
    }
    if (playBtn) {
        playBtn.textContent = 'Play';
    }
    if (sampling) {
        sampling.textContent = 'Sampling: -';
    }

    updateTelemetryWidgets({}, 0);
    drawMiniMap(null, null);
}

function initTelemetryControls() {
    if (telemetryControlInitialized) {
        return;
    }

    const playBtn = document.getElementById('btn-telemetry-play');
    const scrub = document.getElementById('telemetry-scrub');

    playBtn.addEventListener('click', () => {
        if (telemetryState.playing) {
            stopTelemetryPlayback();
        } else {
            startTelemetryPlayback();
        }
    });

    scrub.addEventListener('input', event => {
        const index = Number(event.target.value);
        drawTelemetryFrame(index);
    });

    telemetryControlInitialized = true;
}

function renderTelemetryPlayback(data) {
    initTelemetryControls();
    stopTelemetryPlayback();

    const points = data.telemetry || [];
    telemetryState.points = points;
    telemetryState.trackMap = data.track_map || null;
    telemetryState.frameIndex = 0;

    const scrub = document.getElementById('telemetry-scrub');
    const sampling = data.sampling || {};
    scrub.max = Math.max(points.length - 1, 0);
    scrub.value = 0;
    document.getElementById('telemetry-sampling').textContent =
        `Sampling: dt=${Number(sampling.applied_timestep_s || 0).toFixed(2)}s, points=${sampling.returned_points ?? points.length}, downsample=${sampling.downsample_factor ?? 1}x`;

    if (points.length === 0) {
        drawMiniMap(telemetryState.trackMap, null);
        updateTelemetryWidgets({}, 0);
        return;
    }

    drawTelemetryFrame(0);
}

function startTelemetryPlayback() {
    if (!telemetryState.points.length) {
        return;
    }
    telemetryState.playing = true;
    document.getElementById('btn-telemetry-play').textContent = 'Pause';
    telemetryState.timer = setInterval(() => {
        const nextIndex = telemetryState.frameIndex + 1;
        if (nextIndex >= telemetryState.points.length) {
            stopTelemetryPlayback();
            return;
        }
        drawTelemetryFrame(nextIndex);
    }, 45);
}

function stopTelemetryPlayback() {
    telemetryState.playing = false;
    if (telemetryState.timer) {
        clearInterval(telemetryState.timer);
        telemetryState.timer = null;
    }
    const playBtn = document.getElementById('btn-telemetry-play');
    if (playBtn) {
        playBtn.textContent = 'Play';
    }
}

function drawTelemetryFrame(index) {
    if (!telemetryState.points.length) {
        return;
    }
    const safeIndex = Math.max(0, Math.min(index, telemetryState.points.length - 1));
    telemetryState.frameIndex = safeIndex;
    const point = telemetryState.points[safeIndex];

    document.getElementById('telemetry-scrub').value = safeIndex;
    document.getElementById('telemetry-frame-label').textContent = `Frame ${safeIndex + 1} / ${telemetryState.points.length}`;

    updateTelemetryWidgets(point, safeIndex);
    drawMiniMap(telemetryState.trackMap, point);
}

function updateTelemetryWidgets(point, index = 0) {
    updateTelemetryHeader(point, index);
    updatePedalGauge('throttle', point.throttle);
    updatePedalGauge('brake', point.brake);
    updateTireCondition(point);
    updateTireTemperature(point);
}

function updateTelemetryHeader(point, index) {
    const circuit = telemetryState.trackMap?.circuit || currentCircuit || '-';
    const lap = point.lap ?? '-';
    const speed = Math.round(Number(point.speed_kmh) || 0);
    const time = Number(point.t ?? point.time_s ?? (index * 0.5));
    const pitText = (point.is_pit_lap || point.in_pit) ? 'PIT' : 'RACE';

    setText('telemetry-circuit-label', circuit);
    setText('telemetry-lap-value', lap);
    setText('telemetry-speed-value', speed);
    setText('telemetry-time-value', `${time.toFixed(1)}s`);
    setText('telemetry-pit-value', pitText);
}

function updatePedalGauge(kind, rawValue) {
    const value = clamp(Number(rawValue) || 0, 0, 1);
    const pct = Math.round(value * 100);
    setText(`telemetry-${kind}-value`, `${pct}%`);

    const fill = document.getElementById(`telemetry-${kind}-fill`);
    if (fill) {
        fill.style.height = `${pct}%`;
    }
}

function updateTireCondition(point) {
    const grip = Number(point.grip);
    const healthFromGrip = Number.isFinite(grip)
        ? Math.round(clamp(((grip - 0.5) / 0.5) * 100, 0, 100))
        : null;
    const healthPct = healthFromGrip ?? (Number.isFinite(Number(point.tire_health_pct))
        ? Math.round(clamp(Number(point.tire_health_pct), 0, 100))
        : 0);
    const ringColor = point.tire_health_color || getTireHealthColor(healthPct);
    const compound = point.compound || '-';
    const compoundColor = getCompoundColor(compound);
    const status = getTireHealthStatus(healthPct);
    const tireAge = Number(point.tire_age);
    const tireAgeLabel = Number.isFinite(tireAge) ? `${tireAge} lap` : '0 lap';

    setText('telemetry-health-value', `${healthPct}%`);
    setText('telemetry-health-status', status);
    setText('telemetry-compound-value', compound);
    setText('telemetry-tire-age-value', tireAgeLabel);

    const ring = document.getElementById('telemetry-tire-ring');
    if (ring) {
        ring.style.setProperty('--ring-value', `${healthPct}%`);
        ring.style.setProperty('--ring-color', ringColor);
        ring.style.setProperty('--compound-color', compoundColor);
    }
}

function updateTireTemperature(point) {
    const temp = Number(point.tire_temp ?? point.tire_temp_c ?? point.temperature_c);
    const safeTemp = Number.isFinite(temp) ? temp : 0;
    const tempState = getTemperatureState(safeTemp);
    const fillPct = clamp(((safeTemp - 50) / 90) * 100, 0, 100);

    setText('telemetry-temp-value', `${safeTemp.toFixed(1)} \u00b0C`);
    setText('telemetry-temp-status', tempState.label);

    const fill = document.getElementById('telemetry-temp-fill');
    if (fill) {
        fill.style.height = `${fillPct}%`;
        fill.style.background = tempState.color;
    }

    const widget = document.querySelector('.telemetry-temp-widget');
    if (widget) {
        widget.classList.toggle('temp-critical', tempState.label === 'CRITICAL');
    }
}

function getTireHealthColor(pct) {
    if (pct >= 80) {
        return '#00e676';
    }
    if (pct >= 50) {
        return '#ffd700';
    }
    if (pct >= 30) {
        return '#ff9800';
    }
    return '#f44336';
}

function getTireHealthStatus(pct) {
    if (pct >= 80) {
        return 'PRIME';
    }
    if (pct >= 30) {
        return 'WORN';
    }
    return 'CLIFF';
}

function getTemperatureState(temp) {
    if (temp < 80) {
        return { label: 'COLD', color: '#2196f3' };
    }
    if (temp <= 100) {
        return { label: 'OPTIMAL', color: '#00e676' };
    }
    if (temp <= 115) {
        return { label: 'HOT', color: '#ff9800' };
    }
    return { label: 'CRITICAL', color: '#f44336' };
}

function getCompoundColor(compound) {
    const color = COMPOUND_COLORS[compound] || '#cccccc';
    return color === '#FFFFFF' ? '#ffffff' : color;
}

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function clamp(value, min, max) {
    return Math.max(min, Math.min(value, max));
}

function drawMiniMap(trackMap, point) {
    const canvas = document.getElementById('minimap-canvas');
    if (!canvas) {
        return;
    }
    if (minimapRenderRequest) {
        cancelAnimationFrame(minimapRenderRequest);
    }
    minimapRenderRequest = requestAnimationFrame(() => renderMiniMapFrame(canvas, trackMap, point));
}

function renderMiniMapFrame(canvas, trackMap, point) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const path = trackMap?.path || [];

    drawMinimapBackground(ctx, width, height);
    if (!path.length) {
        drawMissingTrackMessage(ctx);
        setText('telemetry-circuit-label', currentCircuit || '-');
        return;
    }

    const projectedPath = projectTrackPath(path, width, height, 20);
    if (!projectedPath.length) {
        return;
    }

    const progress = clamp(Number(point?.progress ?? point?.lap_progress ?? 0), 0, 1);
    const progressIndex = point ? Math.floor(progress * (projectedPath.length - 1)) : 0;
    const passedPath = projectedPath.slice(0, progressIndex + 1);

    // Track layers: shadow, asphalt, sectors, passed lap, center markings.
    drawTrackLayer(ctx, projectedPath, '#1a1a2e', 22, 0.95, true);
    drawTrackLayer(ctx, projectedPath, '#2d2d3d', 14, 1, true);
    drawSectorOverlay(ctx, projectedPath);
    if (passedPath.length > 1) {
        drawTrackLayer(ctx, passedPath, '#4a4a5e', 14, 0.85, false);
    }
    drawRacingLine(ctx, projectedPath);
    drawCenterLine(ctx, projectedPath);
    drawPitLane(ctx, projectedPath, trackMap);
    drawCheckerFinishLine(ctx, projectedPath);
    drawMinimapLegend(ctx, width, height);
    drawOverlay(ctx, width, height, trackMap, point);

    if (point) {
        const carPoint = getCarCanvasPoint(point, projectedPath, progressIndex);
        updateCarTrail(carPoint);
        const heading = getCarHeading(carPoint, projectedPath, progressIndex);
        const compoundColor = getCompoundColor(point.compound || 'Hard');
        drawExhaustTrail(ctx, carTrail, compoundColor);
        drawThrottleParticles(ctx, carPoint, heading, point);
        drawCarF1(ctx, carPoint, heading, compoundColor, point);
    }
    minimapRenderRequest = null;
}

function projectTrackPath(path, width, height, padding = 10) {
    const numeric = path.map(pt => ({
        x: Number(pt.x),
        y: Number(pt.y)
    })).filter(pt => Number.isFinite(pt.x) && Number.isFinite(pt.y));

    if (!numeric.length) {
        return [];
    }

    const xs = numeric.map(pt => pt.x);
    const ys = numeric.map(pt => pt.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const sourceWidth = Math.max(maxX - minX, 0.001);
    const sourceHeight = Math.max(maxY - minY, 0.001);
    const drawableWidth = width - (padding * 2);
    const drawableHeight = height - (padding * 2);
    const scale = Math.min(drawableWidth / sourceWidth, drawableHeight / sourceHeight);
    const offsetX = (width - (sourceWidth * scale)) / 2;
    const offsetY = (height - (sourceHeight * scale)) / 2;

    return numeric.map(pt => ({
        sourceX: pt.x,
        sourceY: pt.y,
        x: offsetX + ((pt.x - minX) * scale),
        y: offsetY + ((pt.y - minY) * scale)
    }));
}

function drawMinimapBackground(ctx, width, height) {
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#0a0a14';
    ctx.fillRect(0, 0, width, height);

    // Subtle game-strategy grid dots.
    ctx.save();
    ctx.fillStyle = 'rgba(255, 255, 255, 0.055)';
    for (let x = 10; x < width; x += 20) {
        for (let y = 10; y < height; y += 20) {
            ctx.beginPath();
            ctx.arc(x, y, 1, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    ctx.restore();
}

function drawMissingTrackMessage(ctx) {
    ctx.fillStyle = '#a0a0c0';
    ctx.font = "600 14px 'Orbitron', monospace";
    ctx.fillText('Track map unavailable', 20, 32);
}

function drawTrackLayer(ctx, points, color, width, alpha = 1, closePath = false, dash = []) {
    if (!points.length) {
        return;
    }
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.setLineDash(dash);
    traceTrackPath(ctx, points, closePath);
    ctx.stroke();
    ctx.restore();
}

function traceTrackPath(ctx, points, closePath = false) {
    ctx.beginPath();
    points.forEach((pt, idx) => {
        if (idx === 0) {
            ctx.moveTo(pt.x, pt.y);
        } else {
            ctx.lineTo(pt.x, pt.y);
        }
    });
    if (closePath) {
        ctx.closePath();
    }
}

function drawSectorOverlay(ctx, points) {
    const sectorColors = ['#00d2ff', '#8b5cf6', '#e8002d'];
    const segmentSize = Math.floor(points.length / 3);
    sectorColors.forEach((color, sector) => {
        const start = sector * segmentSize;
        const end = sector === 2 ? points.length : (sector + 1) * segmentSize + 1;
        drawTrackLayer(ctx, points.slice(start, end), color, 7, 0.4);
    });
}

function drawRacingLine(ctx, points) {
    drawTrackLayer(ctx, points, 'rgba(255, 200, 0, 0.15)', 2, 1, true);
}

function drawCenterLine(ctx, points) {
    drawTrackLayer(ctx, points, 'rgba(255, 255, 255, 0.72)', 1.5, 1, true, [8, 6]);
}

function drawPitLane(ctx, points, trackMap) {
    const entry = Number(trackMap?.pit_entry_progress);
    const exit = Number(trackMap?.pit_exit_progress);
    if (!Number.isFinite(entry) || !Number.isFinite(exit) || points.length < 4) {
        return;
    }

    const pitSegment = getProgressSegment(points, clamp(entry, 0, 1), clamp(exit, 0, 1));
    const pitLane = offsetPath(pitSegment, 15);
    drawTrackLayer(ctx, pitLane, '#11111c', 8, 0.95);
    drawTrackLayer(ctx, pitLane, '#ffd700', 2, 0.8, false, [6, 6]);
}

function getProgressSegment(points, startProgress, endProgress) {
    const startIndex = Math.floor(startProgress * (points.length - 1));
    const endIndex = Math.floor(endProgress * (points.length - 1));
    if (endIndex >= startIndex) {
        return points.slice(startIndex, endIndex + 1);
    }
    return [...points.slice(startIndex), ...points.slice(0, endIndex + 1)];
}

function offsetPath(points, distance) {
    return points.map((pt, index) => {
        const prev = points[Math.max(index - 1, 0)];
        const next = points[Math.min(index + 1, points.length - 1)];
        const angle = Math.atan2(next.y - prev.y, next.x - prev.x) + (Math.PI / 2);
        return {
            ...pt,
            x: pt.x + Math.cos(angle) * distance,
            y: pt.y + Math.sin(angle) * distance
        };
    });
}

function drawCheckerFinishLine(ctx, points) {
    if (points.length < 2) {
        return;
    }
    const start = points[0];
    const next = points[1];
    const angle = Math.atan2(next.y - start.y, next.x - start.x) + (Math.PI / 2);
    const cells = 6;
    const cellSize = 4;
    const totalWidth = cells * cellSize;

    ctx.save();
    ctx.translate(start.x, start.y);
    ctx.rotate(angle);
    for (let i = 0; i < cells; i += 1) {
        ctx.fillStyle = i % 2 === 0 ? '#ffffff' : '#05050a';
        ctx.fillRect((-totalWidth / 2) + (i * cellSize), -5, cellSize, 5);
        ctx.fillStyle = i % 2 === 0 ? '#05050a' : '#ffffff';
        ctx.fillRect((-totalWidth / 2) + (i * cellSize), 0, cellSize, 5);
    }
    ctx.restore();
}

function getCarCanvasPoint(point, projectedPath, progressIndex) {
    const rawX = Number(point.x);
    const rawY = Number(point.y);
    if (Number.isFinite(rawX) && Number.isFinite(rawY)) {
        let closest = projectedPath[progressIndex] || projectedPath[0];
        let bestDistance = Infinity;
        projectedPath.forEach(projected => {
            const distance = Math.hypot(projected.sourceX - rawX, projected.sourceY - rawY);
            if (distance < bestDistance) {
                bestDistance = distance;
                closest = projected;
            }
        });
        return closest;
    }
    return projectedPath[progressIndex] || projectedPath[0];
}

function updateCarTrail(carPoint) {
    const currentFrame = telemetryState.frameIndex;
    if (currentFrame <= minimapLastFrameIndex || currentFrame - minimapLastFrameIndex > 2) {
        carTrail = [];
    }
    if (currentFrame !== minimapLastFrameIndex) {
        carTrail.push({ x: carPoint.x, y: carPoint.y });
        carTrail = carTrail.slice(-15);
        minimapLastFrameIndex = currentFrame;
    }
}

function getCarHeading(carPoint, projectedPath, progressIndex) {
    const previous = carTrail.length > 1 ? carTrail[carTrail.length - 2] : null;
    if (previous && Math.hypot(carPoint.x - previous.x, carPoint.y - previous.y) > 0.1) {
        return Math.atan2(carPoint.y - previous.y, carPoint.x - previous.x);
    }
    const next = projectedPath[Math.min(progressIndex + 1, projectedPath.length - 1)] || carPoint;
    return Math.atan2(next.y - carPoint.y, next.x - carPoint.x);
}

function drawExhaustTrail(ctx, trail, compoundColor) {
    const previousPoints = trail.slice(0, -1).slice(-12);
    previousPoints.forEach((pt, index) => {
        const fade = (index + 1) / previousPoints.length;
        ctx.save();
        ctx.globalAlpha = 0.08 + (fade * 0.22);
        ctx.fillStyle = compoundColor;
        ctx.shadowColor = compoundColor;
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 2 + (fade * 3.5), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    });
}

function drawThrottleParticles(ctx, carPoint, heading, point) {
    const throttle = Number(point.throttle) || 0;
    if (throttle <= 0.7) {
        return;
    }
    ctx.save();
    for (let i = 0; i < 5; i += 1) {
        const spread = (Math.random() - 0.5) * 9;
        const distance = 14 + (Math.random() * 18);
        const x = carPoint.x - Math.cos(heading) * distance + Math.cos(heading + Math.PI / 2) * spread;
        const y = carPoint.y - Math.sin(heading) * distance + Math.sin(heading + Math.PI / 2) * spread;
        ctx.globalAlpha = 0.25 + Math.random() * 0.45;
        ctx.fillStyle = Math.random() > 0.5 ? '#ff9800' : '#f44336';
        ctx.beginPath();
        ctx.arc(x, y, 1.4 + Math.random() * 1.8, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.restore();
}

function drawCarF1(ctx, carPoint, angle, compoundColor, point) {
    const isPit = Boolean(point.is_pit_lap || point.in_pit);
    const glowColor = isPit ? '#ffd700' : compoundColor;

    ctx.save();
    ctx.translate(carPoint.x, carPoint.y);
    ctx.rotate(angle);
    ctx.shadowColor = glowColor;
    ctx.shadowBlur = 12;

    // Main slim F1 arrow body.
    ctx.fillStyle = compoundColor;
    ctx.beginPath();
    ctx.moveTo(11, 0);
    ctx.lineTo(3, -4);
    ctx.lineTo(-8, -3);
    ctx.lineTo(-10, 0);
    ctx.lineTo(-8, 3);
    ctx.lineTo(3, 4);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Wings and cockpit details.
    ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.75)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(7, -5);
    ctx.lineTo(7, 5);
    ctx.moveTo(-8, -6);
    ctx.lineTo(-8, 6);
    ctx.stroke();

    ctx.fillStyle = '#08080e';
    ctx.beginPath();
    ctx.arc(1, 0, 2.2, 0, Math.PI * 2);
    ctx.fill();

    if ((Number(point.brake) || 0) > 0.3) {
        ctx.fillStyle = '#ff3d00';
        ctx.shadowColor = '#ff3d00';
        ctx.shadowBlur = 8;
        [-4, 4].forEach(offset => {
            ctx.beginPath();
            ctx.arc(4, offset, 2.2, 0, Math.PI * 2);
            ctx.fill();
        });
    }
    ctx.restore();

    if (isPit) {
        drawPitLabel(ctx, carPoint);
    }
}

function drawPitLabel(ctx, carPoint) {
    ctx.save();
    ctx.font = "700 11px 'Orbitron', monospace";
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ffd700';
    ctx.shadowColor = '#ffd700';
    ctx.shadowBlur = 10;
    ctx.fillText('PIT IN', carPoint.x, carPoint.y - 18);
    ctx.restore();
}

function drawOverlay(ctx, width, height, trackMap, point) {
    const circuit = trackMap?.circuit || currentCircuit || '-';
    const lap = point?.lap ?? '-';
    const totalLaps = document.getElementById('total-laps')?.textContent || '-';
    const speed = Math.round(Number(point?.speed_kmh) || 0);

    ctx.save();
    ctx.font = "800 15px 'Orbitron', monospace";
    ctx.fillStyle = '#ffffff';
    ctx.shadowColor = 'rgba(0, 0, 0, 0.8)';
    ctx.shadowBlur = 8;
    ctx.fillText(`${circuit}  LAP ${lap} / ${totalLaps}`, 16, 26);

    const speedText = `${speed} km/h`;
    ctx.font = "800 18px 'Orbitron', monospace";
    const speedWidth = ctx.measureText(speedText).width + 24;
    ctx.fillStyle = 'rgba(0, 0, 0, 0.58)';
    ctx.fillRect(width - speedWidth - 14, 12, speedWidth, 34);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.strokeRect(width - speedWidth - 14, 12, speedWidth, 34);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(speedText, width - speedWidth - 2, 35);
    ctx.restore();
}

function drawMinimapLegend(ctx, width, height) {
    const items = [
        { label: 'S', color: COMPOUND_COLORS.Soft },
        { label: 'M', color: COMPOUND_COLORS.Medium },
        { label: 'H', color: COMPOUND_COLORS.Hard }
    ];

    ctx.save();
    ctx.font = "700 10px 'Orbitron', monospace";
    items.forEach((item, index) => {
        const x = 16 + (index * 34);
        const y = height - 18;
        ctx.fillStyle = item.color;
        ctx.beginPath();
        ctx.arc(x, y - 3, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.fillText(item.label, x + 8, y);
    });
    ctx.restore();
}

