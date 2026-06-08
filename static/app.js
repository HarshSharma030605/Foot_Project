// Global chart references
window.myChart = null;
window.rostChart = null;

// Fetch and populate Teams on load
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch('/api/teams');
        const teams = await res.json();
        
        const searchSelect = document.getElementById('teamId');
        const auditSelect = document.getElementById('auditTeamId');
        const rosterSelect = document.getElementById('rosterTeamId');
        
        teams.forEach(t => {
            if (searchSelect) searchSelect.innerHTML += `<option value="${t.team_id}">${t.team_name}</option>`;
            if (auditSelect) auditSelect.innerHTML += `<option value="${t.team_id}">${t.team_name}</option>`;
            if (rosterSelect) rosterSelect.innerHTML += `<option value="${t.team_id}">${t.team_name}</option>`;
        });
    } catch (err) {
        console.error("Failed to load teams", err);
    }
});

document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.view-panel').forEach(p => p.classList.add('hidden'));
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(btn.getAttribute('data-target')).classList.remove('hidden');
        btn.classList.add('active');
    });
});

// Dynamic chart initializer
function initHexaChart(labels, data, canvasId, chartVar) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    if (window[chartVar]) window[chartVar].destroy();
    
    window[chartVar] = new Chart(ctx, {
        type: 'radar',
        data: { 
            labels: labels, 
            datasets: [{ 
                data: data, 
                backgroundColor: 'rgba(16, 185, 129, 0.2)', 
                borderColor: '#10b981', 
                pointBackgroundColor: '#38bdf8', 
                borderWidth: 2 
            }] 
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            scales: { 
                r: { 
                    min: 0, 
                    max: 100, 
                    grid: { color: '#1e293b' }, 
                    angleLines: { color: '#1e293b' }, 
                    ticks: { display: false }, 
                    pointLabels: { color: '#94a3b8', font: { size: 10, weight: 'bold' } } 
                } 
            }, 
            plugins: { legend: { display: false } } 
        }
    });
}

// 1. Archetype Engine Logic
document.getElementById('runArchetypeBtn').addEventListener('click', async () => {
    const loader = document.getElementById('archetype-loader');
    const resultsBox = document.getElementById('archetype-results-box');
    loader.classList.remove('hidden'); resultsBox.classList.add('hidden');
    
    try {
        const res = await fetch('/api/scout', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ team_id: document.getElementById('teamId').value, archetype: document.getElementById('archetype').value })
        });
        const data = await res.json();
        
        if (res.ok) {
            const top = data.candidates[0];
            document.getElementById('featPlayerName').textContent = data.top_target;
            document.getElementById('featPlayerAge').textContent = top.candidate_profile.age;
            document.getElementById('featPlayerClub').textContent = top.candidate_profile.current_club;
            document.getElementById('featSuitScore').textContent = top.explainable_ai_matrix.composite_suit_score.toFixed(1);
            document.getElementById('featPlayerImg').src = data.top_image_url;
            document.getElementById('scoutNarrativeText').innerHTML = data.executive_brief.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
            
            initHexaChart(top.radar_metrics.labels, top.radar_metrics.data, 'hexaChart', 'myChart');
            
            loader.classList.add('hidden'); resultsBox.classList.remove('hidden');
        } else { alert(data.error); loader.classList.add('hidden'); }
    } catch (err) { alert("Error connecting to Engine."); loader.classList.add('hidden'); }
});

// 2. Macro Audit Logic
document.getElementById('runAuditBtn').addEventListener('click', async () => {
    const grid = document.getElementById('auditCardsGrid');
    const headerInfo = document.getElementById('auditHeaderInfo');
    grid.innerHTML = '<div class="loader"><div class="spinner"></div></div>'; headerInfo.classList.add('hidden');
    
    try {
        const res = await fetch('/api/macro-audit', { 
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ team_id: document.getElementById('auditTeamId').value })
        });
        const data = await res.json();
        
        if (!res.ok) return grid.innerHTML = `<p style="color: #ef4444;">Error: ${data.error}</p>`;
        
        const fmt = new Intl.NumberFormat('en-EU', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
        document.getElementById('audClub').textContent = data.team_name;
        document.getElementById('audBudget').textContent = fmt.format(data.budget);
        document.getElementById('audMetric').textContent = data.success_metric;
        document.getElementById('audWindow').textContent = data.urgency_months;
        headerInfo.classList.remove('hidden');

        if (data.vulnerabilities.length === 0) return grid.innerHTML = '<p style="color: var(--pitch-green);">✅ Roster Stable.</p>';

        grid.innerHTML = data.vulnerabilities.map(vuln => {
            let sol = vuln.internal_solution ? `<div style="margin-top: 1rem; padding: 1rem; background: rgba(16, 185, 129, 0.1); border: 1px solid var(--pitch-green); border-radius: 6px;"><span style="color: var(--pitch-green); font-size: 0.8rem; font-weight: bold; display: block;">💡 INTERNAL ACADEMY</span><strong>${vuln.internal_solution.name}</strong> (${vuln.internal_solution.role})</div>` : 
                      (vuln.external_targets.length > 0 ? `<div style="margin-top: 1rem; padding: 1rem; background: rgba(56, 189, 248, 0.1); border: 1px solid var(--neon-glow); border-radius: 6px;"><span style="color: var(--neon-glow); font-size: 0.8rem; font-weight: bold; display: block;">🚨 MARKET TARGETS</span><ul style="padding-left: 15px; margin: 0;">${vuln.external_targets.map(t => `<li style="font-size: 0.85rem;"><strong>${t.name}</strong> - ${fmt.format(t.value)}</li>`).join('')}</ul></div>` : `<div style="margin-top: 1rem; color: #ef4444; font-size: 0.85rem;">⚠️ No targets found.</div>`);
            
            return `<div class="player-card"><h4 style="color: #ef4444; margin: 0;">⚠️ ${vuln.distressed_player}</h4><p style="margin: 5px 0;">${vuln.position} | ${vuln.archetype}</p><p style="color: var(--text-dim); font-size: 0.85rem;">Expires in: <span style="color: white; font-weight: bold;">${vuln.months_left} Months</span></p>${sol}</div>`;
        }).join('');
    } catch (err) { grid.innerHTML = '<p style="color: #ef4444;">Audit Error.</p>'; }
});

// 3. Squad Roster Logic
if (document.getElementById('runRosterBtn')) {
    document.getElementById('runRosterBtn').addEventListener('click', async () => {
        const list = document.getElementById('rosterList');
        list.innerHTML = '<div class="loader"><div class="spinner"></div></div>';
        
        try {
            const res = await fetch('/api/roster', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ team_id: document.getElementById('rosterTeamId').value })
            });
            const players = await res.json();
            
            list.innerHTML = players.map(p => `
                <div class="player-card" style="padding: 1rem; cursor: pointer; border-left: 3px solid var(--tactical-blue);" onclick="loadPlayerProfile(${p.player_id})">
                    <h4 style="margin: 0; color: var(--neon-glow);">${p.player_name}</h4>
                    <p style="margin: 5px 0 0 0; font-size: 0.85rem; color: var(--text-dim);">${p.position} | ${p.archetype_label || 'Unassigned'}</p>
                </div>
            `).join('');
        } catch (err) { list.innerHTML = '<p style="color: #ef4444;">Error loading roster.</p>'; }
    });
}

// Global scope function for onclick attribute in the list
window.loadPlayerProfile = async function(playerId) {
    const detailBox = document.getElementById('rosterDetailBox');
    detailBox.classList.remove('hidden');
    document.getElementById('rostNarrativeText').innerHTML = '<div class="loader"><div class="spinner"></div></div>';
    
    try {
        const res = await fetch(`/api/player/${playerId}`);
        const data = await res.json();
        
        if (res.ok) {
            const prof = data.profile;
            document.getElementById('rostPlayerName').textContent = prof.candidate_profile.name;
            document.getElementById('rostPlayerAge').textContent = prof.candidate_profile.age;
            document.getElementById('rostPlayerPos').textContent = prof.candidate_profile.position;
            document.getElementById('rostPlayerArch').textContent = prof.archetype || 'Unassigned';
            document.getElementById('rostPlayerConf').textContent = prof.confidence ? (prof.confidence * 100).toFixed(1) : '0.0';
            document.getElementById('rostPlayerImg').src = data.image_url;
            
            document.getElementById('rostNarrativeText').innerHTML = data.brief.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
            
            initHexaChart(prof.radar_metrics.labels, prof.radar_metrics.data, 'rostHexaChart', 'rostChart');
        } else {
            alert(data.error);
        }
    } catch (err) { alert("Error loading profile data."); }
};