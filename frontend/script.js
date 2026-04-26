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
let currentWeather = 'sunny';
let customStintInitialized = false;

const DRY_TIRES = ['Soft', 'Medium', 'Hard'];
const TIRE_WEAR_FACTORS = { FL: 0.98, FR: 0.97, RL: 0.96, RR: 0.95 };
const CLIFF_AGES = { Soft: 18, Medium: 28, Hard: 40, Intermediate: 24, Wet: 20 };


const telemetryState = {
    points: [],
    trackMap: null,
    frameIndex: 0,
    timer: null,
    playing: false
};

let minimapRenderRequest = null;
let minimapLastFrameIndex = -1;
window.carTrail = window.carTrail || [];

document.addEventListener('DOMContentLoaded', async () => {
    initTabs();
    initAllWeatherSelectors();
    initWarningToast();
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
    )).join('') + '<option value="__custom__">\u270f\ufe0f Custom Strategy</option>';

    if (!strategySelectInitialized) {
        select.addEventListener('change', () => {
            const val = select.value;
            const builder = document.getElementById('custom-strategy-builder');
            if (val === '__custom__') {
                builder.classList.remove('hidden');
                updateCustomLapsLabel();
            } else {
                builder.classList.add('hidden');
                renderStintVisual(val);
            }
        });
        document.getElementById('btn-simulate').addEventListener('click', runDeterministicSim);
        strategySelectInitialized = true;
    }
    initCustomStrategyBuilder();

    if (allStrategies.length > 0 && select.value !== '__custom__') {
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
    const isCustom = strategyName === '__custom__';

    if (['rain', 'heavy_rain'].includes(currentWeather)) {
        const stints = isCustom ? gatherCustomStints() : getStrategyStints(strategyName);
        const hasDry = stints.some(s => DRY_TIRES.includes(s.compound));
        if (hasDry) {
            showWarning('\u26a0\ufe0f Ban kering (Soft/Medium/Hard) tidak aman di kondisi hujan! Ganti ke Intermediate/Wet.');
            return;
        }
    }

    button.disabled = true;
    button.textContent = 'Running...';

    try {
        const payload = {
            circuit: currentCircuit,
            weather: currentWeather,
            timestep_s: 0.5,
            max_points: 1500,
            response_shape: 'v2'
        };
        if (isCustom) {
            payload.custom_stints = gatherCustomStints();
        } else {
            payload.strategy_name = strategyName;
        }
        const raw = await fetchJSON(`${API_BASE}/simulate/telemetry`, {
            method: 'POST',
            body: JSON.stringify(payload)
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
        const compareWeather = getWeatherFromSelector('compare-weather-selector');
        const data = await fetchJSON(`${API_BASE}/compare`, {
            method: 'POST',
            body: JSON.stringify({ strategy_names: checked, circuit: currentCircuit, weather: compareWeather })
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
        const mcWeather = getWeatherFromSelector('mc-weather-selector');
        const data = await fetchJSON(`${API_BASE}/simulate/monte-carlo`, {
            method: 'POST',
            body: JSON.stringify({ strategy_names: checked, iterations, circuit: currentCircuit, weather: mcWeather })
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
    window.carTrail = [];
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
    const tireAge = Number(point.tire_age) || 0;
    const compound = point.compound || 'Medium';
    const cliffAge = CLIFF_AGES[compound] || 25;
    const baseHealth = Math.round(clamp(100 - (tireAge / cliffAge) * 100, 0, 100));
    const tireAgeLabel = Number.isFinite(tireAge) ? `${tireAge} lap` : '0 lap';

    setText('telemetry-compound-value', compound);
    setText('telemetry-tire-age-value', tireAgeLabel);

    // Update 4 separate tires with individual wear factors
    for (const [pos, factor] of Object.entries(TIRE_WEAR_FACTORS)) {
        const pct = Math.round(clamp(baseHealth * factor, 0, 100));
        const color = getTireHealthColor(pct);
        const cell = document.getElementById(`tire-${pos}`);
        if (!cell) continue;
        const ring = cell.querySelector('.tire-ring-sm');
        const strong = cell.querySelector('strong');
        if (ring) {
            ring.style.setProperty('--ring-value', `${pct}%`);
            ring.style.setProperty('--ring-color', color);
        }
        if (strong) {
            strong.textContent = `${pct}%`;
            strong.style.color = color;
        }
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

    // Background: dark satellite-style base with dotted tactical grid and vignette.
    drawMinimapBackground(ctx, width, height);
    if (!path.length) {
        drawMissingTrackMessage(ctx);
        setText('telemetry-circuit-label', currentCircuit || '-');
        return;
    }

    const projectedPath = projectTrackPath(path, width, height, 34);
    if (!projectedPath.length) {
        return;
    }

    const progress = clamp(Number(point?.progress ?? point?.lap_progress ?? 0), 0, 1);
    const progressIndex = point ? Math.floor(progress * projectedPath.length) : 0;
    const safeProgressIndex = Math.max(0, Math.min(progressIndex, projectedPath.length - 1));
    const passedPath = projectedPath.slice(0, safeProgressIndex + 1);

    // Track: F1 Manager-style glow, red outside edge, green inside edge, asphalt center.
    drawTrackHalo(ctx, projectedPath);
    drawTrackLayer(ctx, projectedPath, 'rgba(255, 255, 255, 0.06)', 32, 1, true);
    drawTrackLayer(ctx, projectedPath, '#f44336', 26, 1, true);
    drawTrackLayer(ctx, projectedPath, '#1e2235', 22, 1, true);
    drawTrackLayer(ctx, projectedPath, '#252840', 18, 1, true);
    drawSectorOverlay(ctx, projectedPath);
    if (passedPath.length > 1) {
        drawTrackLayer(ctx, passedPath, 'rgba(255, 255, 100, 0.2)', 10, 1, false);
    }
    drawTrackLayer(ctx, projectedPath, '#00c853', 14, 1, true);
    drawTrackLayer(ctx, projectedPath, '#252840', 10, 1, true);
    drawPitLane(ctx, projectedPath, trackMap);
    drawCenterLine(ctx, projectedPath);
    drawCheckerFinishLine(ctx, projectedPath);
    drawMinimapLegend(ctx, width, height);
    drawOverlay(ctx, width, height, trackMap, point);

    if (point) {
        const carPoint = getCarCanvasPoint(projectedPath, safeProgressIndex);
        const heading = getTrackHeading(projectedPath, safeProgressIndex);
        const compoundColor = getF1ManagerCompoundColor(point.compound);
        updateCarTrail(carPoint);
        drawExhaustTrail(ctx, window.carTrail, compoundColor);
        drawCarMarkers(ctx, carPoint, heading, point);
        drawF1ManagerCar(ctx, carPoint, heading, compoundColor, point);
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
    ctx.fillStyle = '#080c14';
    ctx.fillRect(0, 0, width, height);

    // Dot grid pattern: subtle strategy-map texture.
    ctx.save();
    ctx.fillStyle = 'rgba(255, 255, 255, 0.03)';
    for (let x = 9; x < width; x += 18) {
        for (let y = 9; y < height; y += 18) {
            ctx.beginPath();
            ctx.arc(x, y, 1, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    ctx.restore();

    // Satellite-like vignette haze.
    const gradient = ctx.createRadialGradient(width / 2, height / 2, 20, width / 2, height / 2, Math.max(width, height) * 0.62);
    gradient.addColorStop(0, 'rgba(30, 40, 80, 0.3)');
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0.85)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
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

function drawTrackHalo(ctx, points) {
    ctx.save();
    ctx.shadowColor = 'rgba(200, 220, 255, 0.16)';
    ctx.shadowBlur = 28;
    drawTrackLayer(ctx, points, 'rgba(200, 220, 255, 0.04)', 45, 1, true);
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
    const sectorColors = [
        'rgba(0, 150, 255, 0.15)',
        'rgba(180, 0, 255, 0.15)',
        'rgba(255, 50, 50, 0.15)'
    ];
    const segmentSize = Math.floor(points.length / 3);
    sectorColors.forEach((color, sector) => {
        const start = sector * segmentSize;
        const end = sector === 2 ? points.length : (sector + 1) * segmentSize + 1;
        drawTrackLayer(ctx, points.slice(start, end), color, 18, 1);
    });
}

function drawCenterLine(ctx, points) {
    drawTrackLayer(ctx, points, 'rgba(255, 255, 255, 0.25)', 1, 1, true, [6, 8]);
}

function drawPitLane(ctx, points, trackMap) {
    const entry = Number(trackMap?.pit_entry_progress);
    const exit = Number(trackMap?.pit_exit_progress);
    if (!Number.isFinite(entry) || !Number.isFinite(exit) || points.length < 4) {
        return;
    }

    const pitSegment = getProgressSegment(points, clamp(entry, 0, 1), clamp(exit, 0, 1));
    const pitLane = offsetPath(pitSegment, 12);
    drawTrackLayer(ctx, pitLane, '#3a3f5c', 6, 1);
    drawTrackLayer(ctx, pitLane, 'rgba(255, 255, 255, 0.35)', 1, 1, false, [4, 5]);
    drawPitLaneLabel(ctx, pitLane);
}

function drawPitLaneLabel(ctx, points) {
    if (points.length < 2) {
        return;
    }
    const mid = points[Math.floor(points.length / 2)];
    ctx.save();
    ctx.font = "700 9px 'Orbitron', monospace";
    ctx.textAlign = 'center';
    ctx.fillStyle = '#a0a0c0';
    ctx.shadowColor = 'rgba(0, 0, 0, 0.75)';
    ctx.shadowBlur = 8;
    ctx.fillText('PIT LANE', mid.x, mid.y - 8);
    ctx.restore();
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
    const heading = Math.atan2(next.y - start.y, next.x - start.x);
    const perpAngle = heading + (Math.PI / 2);
    const cells = 6;
    const cellSize = 8;
    const totalWidth = cells * cellSize;

    ctx.save();
    ctx.translate(start.x, start.y);
    ctx.rotate(perpAngle);
    for (let i = 0; i < cells; i += 1) {
        ctx.fillStyle = i % 2 === 0 ? '#ffffff' : '#05050a';
        ctx.fillRect((-totalWidth / 2) + (i * cellSize), -8, cellSize, 8);
        ctx.fillStyle = i % 2 === 0 ? '#05050a' : '#ffffff';
        ctx.fillRect((-totalWidth / 2) + (i * cellSize), 0, cellSize, 8);
    }
    ctx.restore();
}

function getCarCanvasPoint(projectedPath, progressIndex) {
    return projectedPath[progressIndex] || projectedPath[0];
}

function updateCarTrail(carPoint) {
    const currentFrame = telemetryState.frameIndex;
    if (currentFrame <= minimapLastFrameIndex || currentFrame - minimapLastFrameIndex > 2) {
        window.carTrail = [];
    }
    if (currentFrame !== minimapLastFrameIndex) {
        window.carTrail.push({ cx: carPoint.x, cy: carPoint.y });
        window.carTrail = window.carTrail.slice(-20);
        minimapLastFrameIndex = currentFrame;
    }
}

function getTrackHeading(projectedPath, progressIndex) {
    const current = projectedPath[progressIndex] || projectedPath[0];
    const next = projectedPath[(progressIndex + 1) % projectedPath.length] || current;
    const previous = projectedPath[Math.max(progressIndex - 1, 0)] || current;
    const dx = next.x - previous.x;
    const dy = next.y - previous.y;
    return Math.atan2(dy, dx);
}

function drawExhaustTrail(ctx, trail, compoundColor) {
    trail.forEach((pt, index) => {
        const fade = (index + 1) / 20;
        ctx.save();
        ctx.globalAlpha = fade * 0.5;
        ctx.fillStyle = compoundColor;
        ctx.beginPath();
        ctx.arc(pt.cx, pt.cy, 3 * fade, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    });
}

function drawCarMarkers(ctx, carPoint, heading, point) {
    drawThrottleParticles(ctx, carPoint, heading, point);
    drawBrakeMarker(ctx, carPoint, heading, point);
}

function drawThrottleParticles(ctx, carPoint, heading, point) {
    const throttle = Number(point.throttle) || 0;
    if (throttle <= 0.75) {
        return;
    }
    ctx.save();
    for (let i = 0; i < 3; i += 1) {
        const spread = (i - 1) * 4;
        const distance = 13 + (i * 4);
        const x = carPoint.x - Math.cos(heading) * distance + Math.cos(heading + Math.PI / 2) * spread;
        const y = carPoint.y - Math.sin(heading) * distance + Math.sin(heading + Math.PI / 2) * spread;
        ctx.globalAlpha = 0.55 - (i * 0.12);
        ctx.fillStyle = '#ff9800';
        ctx.beginPath();
        ctx.arc(x, y, 2.2 - (i * 0.25), 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.restore();
}

function drawBrakeMarker(ctx, carPoint, heading, point) {
    const brake = Number(point.brake) || 0;
    if (brake <= 0.4) {
        return;
    }
    ctx.save();
    ctx.fillStyle = '#ff2a00';
    ctx.shadowColor = '#ff2a00';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(carPoint.x + Math.cos(heading) * 12, carPoint.y + Math.sin(heading) * 12, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
}

function drawF1ManagerCar(ctx, carPoint, heading, compoundColor, point) {
    const isPit = Boolean(point.is_pit_lap || point.in_pit);

    // Car marker: compound-colored dot with strong glow and white outer ring.
    ctx.save();
    ctx.shadowColor = compoundColor;
    ctx.shadowBlur = 16;
    ctx.fillStyle = compoundColor;
    ctx.beginPath();
    ctx.arc(carPoint.x, carPoint.y, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(carPoint.x, carPoint.y, 9, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    drawCarLabel(ctx, carPoint, compoundColor, point, isPit);
}

function drawCarLabel(ctx, carPoint, compoundColor, point, isPit) {
    const compound = point.compound || '-';
    const label = isPit ? 'PIT IN' : `LAP ${point.lap ?? '-'} | ${compound.charAt(0).toUpperCase()}`;
    const font = "700 10px 'Orbitron', monospace";
    const y = carPoint.y - 28;

    ctx.save();
    ctx.font = font;
    const textWidth = ctx.measureText(label).width;
    const boxWidth = textWidth + 14;
    const boxHeight = 18;
    const x = carPoint.x - (boxWidth / 2);

    ctx.fillStyle = isPit ? 'rgba(255, 180, 0, 0.9)' : 'rgba(0, 0, 0, 0.85)';
    drawRoundRect(ctx, x, y, boxWidth, boxHeight, 4);
    ctx.fill();
    if (!isPit) {
        ctx.fillStyle = compoundColor;
        drawRoundRect(ctx, x, y, 3, boxHeight, 2);
        ctx.fill();
    }
    ctx.fillStyle = isPit ? '#050505' : '#ffffff';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, x + 8, y + (boxHeight / 2) + 0.5);
    ctx.restore();
}

function drawOverlay(ctx, width, height, trackMap, point) {
    const circuit = trackMap?.circuit || currentCircuit || '-';
    const lap = point?.lap ?? '-';
    const totalLaps = document.getElementById('total-laps')?.textContent || '-';
    const speed = Math.round(Number(point?.speed_kmh) || 0);
    const compound = String(point?.compound || '-').toUpperCase();
    const tireAge = Number.isFinite(Number(point?.tire_age)) ? `${point.tire_age}L` : '-';

    // Left HUD panel.
    ctx.save();
    ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
    drawRoundRect(ctx, 14, 14, 154, 72, 4);
    ctx.fill();
    ctx.font = "800 12px 'Orbitron', monospace";
    ctx.fillStyle = '#ffffff';
    ctx.fillText('F1', 26, 34);
    ctx.fillStyle = '#f44336';
    ctx.fillRect(54, 22, 2, 18);
    ctx.fillStyle = '#ffffff';
    ctx.fillText('Q1', 68, 34);
    ctx.font = "800 13px 'Orbitron', monospace";
    ctx.fillText(`LAP ${lap} / ${totalLaps}`, 26, 58);
    ctx.font = "600 10px 'Orbitron', monospace";
    ctx.fillStyle = '#a0a0c0';
    ctx.fillText(circuit, 26, 76);

    // Right speed panel.
    const panelWidth = 128;
    ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
    drawRoundRect(ctx, width - panelWidth - 14, 14, panelWidth, 58, 4);
    ctx.fill();
    ctx.font = "800 19px 'Orbitron', monospace";
    ctx.fillStyle = '#ffffff';
    ctx.fillText(`${speed} km/h`, width - panelWidth, 39);
    ctx.font = "700 10px 'Orbitron', monospace";
    ctx.fillStyle = '#a0a0c0';
    ctx.fillText(`${compound} \u00b7 ${tireAge}`, width - panelWidth, 59);
    ctx.restore();
}

function drawMinimapLegend(ctx, width, height) {
    const items = [
        { label: 'S', color: '#ff1744' },
        { label: 'M', color: '#ffd600' },
        { label: 'H', color: '#ffffff' }
    ];

    ctx.save();
    ctx.font = "700 11px 'Orbitron', monospace";
    items.forEach((item, index) => {
        const x = 18 + (index * 40);
        const y = height - 20;
        ctx.fillStyle = item.color;
        ctx.beginPath();
        ctx.arc(x, y - 4, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.fillText(item.label, x + 10, y);
    });
    ctx.restore();
}

function getF1ManagerCompoundColor(compound) {
    const colors = {
        Soft: '#ff1744',
        Medium: '#ffd600',
        Hard: '#ffffff'
    };
    return colors[compound] || getCompoundColor(compound || 'Hard');
}

function drawRoundRect(ctx, x, y, width, height, radius) {
    const safeRadius = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + safeRadius, y);
    ctx.lineTo(x + width - safeRadius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
    ctx.lineTo(x + width, y + height - safeRadius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
    ctx.lineTo(x + safeRadius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
    ctx.lineTo(x, y + safeRadius);
    ctx.quadraticCurveTo(x, y, x + safeRadius, y);
    ctx.closePath();
}

// ======================== WEATHER SELECTOR ========================
function initAllWeatherSelectors() {
    document.querySelectorAll('.weather-selector').forEach(selector => {
        selector.addEventListener('click', event => {
            const btn = event.target.closest('.weather-btn');
            if (!btn) return;
            selector.querySelectorAll('.weather-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // Update global weather for the simulator tab
            if (selector.id === 'weather-selector') {
                currentWeather = btn.dataset.weather;
            }
        });
    });
}

function getWeatherFromSelector(selectorId) {
    const selector = document.getElementById(selectorId);
    if (!selector) return 'sunny';
    const active = selector.querySelector('.weather-btn.active');
    return active ? active.dataset.weather : 'sunny';
}

// ======================== WARNING TOAST ========================
function initWarningToast() {
    const closeBtn = document.getElementById('warning-toast-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            document.getElementById('warning-toast').classList.add('hidden');
        });
    }
}

function showWarning(msg) {
    const toast = document.getElementById('warning-toast');
    const msgEl = document.getElementById('warning-toast-msg');
    if (toast && msgEl) {
        msgEl.textContent = msg;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 6000);
    }
}

// ======================== CUSTOM STRATEGY BUILDER ========================
function initCustomStrategyBuilder() {
    if (customStintInitialized) return;
    const addBtn = document.getElementById('btn-add-stint');
    if (!addBtn) return;

    addBtn.addEventListener('click', () => {
        const container = document.getElementById('custom-stints-container');
        const rows = container.querySelectorAll('.custom-stint-row');
        const num = rows.length + 1;
        const row = document.createElement('div');
        row.className = 'custom-stint-row';
        row.innerHTML = `
            <label class="stint-number">${num}</label>
            <select class="custom-compound-select select-input">
                <option value="Soft">Soft</option><option value="Medium">Medium</option><option value="Hard" selected>Hard</option>
                <option value="Intermediate">Intermediate</option><option value="Wet">Wet</option>
            </select>
            <input type="number" class="custom-stint-laps" placeholder="Laps" min="1" max="78" value="15">
            <button class="btn-remove-stint" type="button">&times;</button>
        `;
        container.appendChild(row);
        updateCustomLapsLabel();
    });

    document.getElementById('custom-stints-container').addEventListener('click', event => {
        if (event.target.closest('.btn-remove-stint')) {
            const row = event.target.closest('.custom-stint-row');
            const container = document.getElementById('custom-stints-container');
            if (container.querySelectorAll('.custom-stint-row').length > 1) {
                row.remove();
                renumberStints();
                updateCustomLapsLabel();
            }
        }
    });

    document.getElementById('custom-stints-container').addEventListener('input', () => {
        updateCustomLapsLabel();
    });

    customStintInitialized = true;
}

function renumberStints() {
    document.querySelectorAll('#custom-stints-container .custom-stint-row').forEach((row, i) => {
        const label = row.querySelector('.stint-number');
        if (label) label.textContent = i + 1;
    });
}

function updateCustomLapsLabel() {
    const total = gatherCustomStints().reduce((sum, s) => sum + s.laps, 0);
    const label = document.getElementById('custom-total-laps-label');
    if (label) label.textContent = `Total: ${total} laps`;
}

function gatherCustomStints() {
    const rows = document.querySelectorAll('#custom-stints-container .custom-stint-row');
    const stints = [];
    rows.forEach(row => {
        const compound = row.querySelector('.custom-compound-select')?.value || 'Medium';
        const laps = parseInt(row.querySelector('.custom-stint-laps')?.value, 10) || 10;
        stints.push({ compound, laps });
    });
    return stints;
}

function getStrategyStints(strategyName) {
    const strategy = allStrategies.find(s => s.name === strategyName);
    if (!strategy) return [];
    return strategy.stints.map(s => ({ compound: s.compound, laps: s.length }));
}
