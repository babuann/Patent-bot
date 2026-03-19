let globalPatents = [];
let globalKeywords = [];

document.getElementById('runBtn').addEventListener('click', async () => {
    const topic = document.getElementById('topicInput').value;
    const apiKey = document.getElementById('apiKeyInput').value;

    if (!topic) return alert("Please enter a topic.");

    // Initial UI reset
    document.getElementById('resultsArea').style.display = 'block';
    resetProgress();

    const runBtn = document.getElementById('runBtn');
    runBtn.textContent = "INITIALIZING...";
    runBtn.disabled = true;

    // Simulate Agent Steps passing over real API call to visualize progress
    simulateAgentSteps();

    try {
        const response = await fetch('/api/research', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic, api_key: apiKey })
        });

        if (!response.ok) throw new Error("API call failed");

        const data = await response.json();

        // Finalize steps
        setStep(4, 'completed');
        setStep(5, 'completed');

        renderData(data);

    } catch (err) {
        console.error(err);
        alert("Error in multi-agent pipeline: " + err.message);
    } finally {
        runBtn.textContent = "INITIALIZE";
        runBtn.disabled = false;
    }
});

// Mock step animations
function simulateAgentSteps() {
    setTimeout(() => { setStep(1, 'completed'); setStep(2, 'active'); }, 800);
    setTimeout(() => { setStep(2, 'completed'); setStep(3, 'active'); }, 2500); // Simulate mock generation time
    setTimeout(() => { setStep(3, 'completed'); setStep(4, 'active'); }, 5000); // Extraction
}

function resetProgress() {
    for (let i = 1; i <= 5; i++) {
        const el = document.getElementById(`step${i}`);
        el.className = 'step';
        if (i === 1) el.classList.add('active');
    }
}

function setStep(num, status) {
    const el = document.getElementById(`step${num}`);
    if (el) el.className = `step ${status}`;
}

function renderData(data) {
    globalPatents = data.patents;
    globalKeywords = data.keywords.map(kw => ({ ...kw, state: 'not-searched' }));

    // Sub-Domains
    const subList = document.getElementById('subDomainsList');
    subList.innerHTML = data.sub_domains.map(sd => `<li>${sd}</li>`).join('');

    // Patents
    document.getElementById('patentCount').innerText = globalPatents.length;
    const patsHTML = globalPatents.map(p => `
        <div class="patent-card">
            <div class="patent-meta">
                <a href="https://patents.google.com/patent/${p.publication_number}/en" target="_blank" class="pub-number">${p.publication_number}</a>
                <span class="assignee">${p.assignee} | ${p.date}</span>
            </div>
            <h3 class="patent-title">${p.title}</h3>
            <p class="patent-abstract">${p.abstract}</p>
            <div class="cpc-tags">
                ${p.cpc_codes.map(c => `<span class="cpc-tag">${c}</span>`).join('')}
            </div>
        </div>
    `).join('');
    document.getElementById('patentsList').innerHTML = patsHTML;

    // Keywords
    renderKeywords();
}

function renderKeywords() {
    document.getElementById('keywordCount').innerText = globalKeywords.length;

    const list = document.getElementById('keywordsList');
    list.innerHTML = globalKeywords.map((kw, idx) => `
        <div class="keyword-row">
            <div class="kw-info">
                <span class="dot ${kw.state}"></span>
                <span class="kw-text">${kw.keyword}</span>
                <span class="kw-cluster">[${kw.cluster}]</span>
            </div>
            <div class="kw-actions">
                <button class="btn-state" onclick="toggleState(${idx}, 'searched')">CHK</button>
                <button class="btn-state" onclick="toggleState(${idx}, 'flagged')">FLG</button>
                <a class="btn-wipo" href="https://patentscope.wipo.int/search/en/search.jsf?q=${encodeURIComponent(kw.keyword)}" target="_blank" onclick="toggleState(${idx}, 'searched')">WIPO</a>
            </div>
        </div>
    `).join('');
}

window.toggleState = function (idx, newState) {
    globalKeywords[idx].state = newState;
    renderKeywords();
};

// CSV Export logic
document.getElementById('exportPatentsBtn').addEventListener('click', () => {
    if (globalPatents.length === 0) return;

    const headers = ["Publication Number", "Title", "Assignee", "Date", "CPC Codes", "Abstract"];
    const rows = globalPatents.map(p => [
        p.publication_number,
        `"${p.title.replace(/"/g, '""')}"`,
        `"${p.assignee}"`,
        p.date,
        `"${p.cpc_codes.join(', ')}"`,
        `"${p.abstract.replace(/"/g, '""')}"`
    ]);

    downloadCSV([headers, ...rows], 'patents_export.csv');
});

document.getElementById('exportKeywordsBtn').addEventListener('click', () => {
    if (globalKeywords.length === 0) return;

    const headers = ["Keyword", "Cluster", "Relevance Score", "Status"];
    const rows = globalKeywords.map(k => [
        `"${k.keyword}"`,
        k.cluster,
        k.score,
        k.state
    ]);

    downloadCSV([headers, ...rows], 'keywords_export.csv');
});

function downloadCSV(dataArray, filename) {
    const csvContent = dataArray.map(e => e.join(",")).join("\n");
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
