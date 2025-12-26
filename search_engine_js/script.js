let db;

async function initDB() {
    const SQL = await initSqlJs({ locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/${file}` });
    const response = await fetch('db.sqlite3');
    const buffer = await response.arrayBuffer();
    db = new SQL.Database(new Uint8Array(buffer));

    // Erstelle FTS5 Tabelle
    db.run(`
        CREATE VIRTUAL TABLE IF NOT EXISTS crawled_fts USING fts5(
            url, title, description, headings, paragraphs, link_count, crawled_at, status_code
        );
    `);

    // Kopiere Daten in FTS5 Tabelle, wenn nicht schon da
    const count = db.exec("SELECT COUNT(*) FROM crawled_fts")[0].values[0][0];
    if (count == 0) {
        const data = db.exec("SELECT url, title, description, headings, paragraphs, link_count, crawled_at, status_code FROM crawled");
        data[0].values.forEach(row => {
            db.run("INSERT INTO crawled_fts (url, title, description, headings, paragraphs, link_count, crawled_at, status_code) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row);
        });
    }
}

function search() {
    const query = document.getElementById('searchInput').value;
    if (!query) return;

    const results = db.exec(`SELECT url, title, description, crawled_at FROM crawled_fts WHERE crawled_fts MATCH ?`, [query]);
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = '';

    if (results.length > 0) {
        results[0].values.forEach(row => {
            const div = document.createElement('div');
            div.className = 'result';
            div.innerHTML = `
                <h3><a href="${row[0]}" target="_blank">${row[1] || 'Kein Titel'}</a></h3>
                <p>${row[2] || 'Keine Beschreibung'}</p>
                <small>Gecrawlt am: ${row[3]}</small>
            `;
            resultsDiv.appendChild(div);
        });
    } else {
        resultsDiv.innerHTML = '<p>Keine Ergebnisse gefunden.</p>';
    }
}

initDB();