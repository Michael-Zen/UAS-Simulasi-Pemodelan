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

    const totalLaps = strategy.stints.reduce((sum, stint) => sum + stint.length, 0);
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
        const data = await fetchJSON(`${API_BASE}/simulate/deterministic`, {
            method: 'POST',
            body: JSON.stringify({ strategy_name: strategyName, circuit: currentCircuit })
        });
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
