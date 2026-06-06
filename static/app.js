// Global chart reference
window.myChart = null;

document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.view-panel').forEach(p => p.classList.add('hidden'));
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(btn.getAttribute('data-target')).classList.remove('hidden');
        btn.classList.add('active');
    });
});

function initHexaChart(labels, data) {
    const ctx = document.getElementById('hexaChart').getContext('2d');
    if (window.myChart) window.myChart.destroy();
    
    window.myChart = new Chart(ctx, {
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
            
            initHexaChart(top.radar_metrics.labels, top.radar_metrics.data);
            
            loader.classList.add('hidden'); resultsBox.classList.remove('hidden');
        } else { alert(data.error); loader.classList.add('hidden'); }
    } catch (err) { alert("Error connecting to Engine."); loader.classList.add('hidden'); }
});

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