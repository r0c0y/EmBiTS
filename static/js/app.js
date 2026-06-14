document.addEventListener("DOMContentLoaded", () => {
    const userSelect = document.getElementById("user-selector");
    const userDept = document.getElementById("user-dept-display");
    const overlay = document.getElementById("viewer-overlay");

    const parseMD = (t) => t
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/\n[-\*]\s+([^\n]+)/g, "<br>• $1")
        .replace(/\n\n/g, "<br><br>")
        .replace(/Result: (Yes|No|Down|Up)/g, "<br><br><strong>Result: $1</strong>");

    document.querySelectorAll(".nav-btn").forEach(btn => btn.addEventListener("click", () => {
        document.querySelectorAll(".nav-btn, .tab-content").forEach(el => el.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById(btn.dataset.tab).classList.add("active");
        document.getElementById("tab-title").innerText = btn.innerText.replace(/[▲🔍📋🛡️]/g, "").trim();
        if (btn.dataset.tab === "audit-tab") loadAudits();
    }));

    userSelect.addEventListener("change", () => {
        userDept.innerText = "Dept: " + userSelect.options[userSelect.selectedIndex].dataset.dept;
    });

    fetch("/api/projects").then(res => res.json()).then(data => {
        const lotSelect = document.getElementById("upload-lot");
        const tbody = document.querySelector("#registry-table tbody");
        lotSelect.innerHTML = ""; tbody.innerHTML = "";
        data.lots.forEach(lot => {
            lotSelect.innerHTML += `<option value="${lot.id}">${lot.name} (${lot.id})</option>`;
            tbody.innerHTML += `<tr><td>SCL-555 Chip</td><td>${lot.id}</td><td>${lot.date}</td><td><span class="badge">In Progress</span></td></tr>`;
        });
    });

    const loadAudits = () => {
        fetch("/api/audit_logs").then(res => res.json()).then(data => {
            const tbody = document.querySelector("#audit-table tbody");
            tbody.innerHTML = data.logs.length ? "" : '<tr><td colspan="5">No actions logged.</td></tr>';
            data.logs.forEach(l => {
                tbody.innerHTML += `<tr><td>${new Date(l.timestamp).toLocaleString()}</td><td>${l.username}</td><td>${l.department}</td><td><span class="badge">${l.action_type}</span></td><td>${l.details}</td></tr>`;
            });
        });
    };

    const postForm = (url, body, callback) => fetch(url, { method: "POST", body }).then(res => res.json()).then(callback);

    document.getElementById("search-form").addEventListener("submit", (e) => {
        e.preventDefault();
        document.getElementById("ai-answer").innerHTML = '<div class="spinner"></div>';
        document.getElementById("citations-list").innerHTML = '<p class="text-muted">Loading citations...</p>';
        const body = new FormData();
        body.append("query", document.getElementById("query-input").value);
        body.append("department", document.getElementById("dept-filter").value);
        body.append("user", userSelect.value);
        body.append("user_dept", userSelect.options[userSelect.selectedIndex].dataset.dept);

        postForm("/api/search", body, data => {
            document.getElementById("ai-answer").innerHTML = `<p>${parseMD(data.answer)}</p>`;
            const citations = document.getElementById("citations-list");
            citations.innerHTML = data.citations.length ? "" : '<p class="text-muted">No matching citations.</p>';
            data.citations.forEach(c => {
                citations.innerHTML += `<details class="disclosure">
                    <summary>[${c.meeting_id}] ${c.meeting_title}</summary>
                    <div>
                        <p><strong>Date:</strong> ${c.date} | <strong>Dept:</strong> ${c.department}</p>
                        <p style="margin-top: 8px;">${c.text}</p>
                        <button class="view-doc-btn" data-id="${c.meeting_id}" data-text="${c.text.replace(/"/g, '&quot;')}" style="margin-top: 8px; background: none; border: 1px solid var(--border); padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer;">🔍 View Full Document</button>
                    </div>
                </details>`;
            });
        });
    });

    document.getElementById("upload-form").addEventListener("submit", (e) => {
        e.preventDefault();
        const fileInput = document.getElementById("file-input");
        const status = document.getElementById("upload-status");
        if (!fileInput.files.length) return;
        const body = new FormData();
        body.append("file", fileInput.files[0]);
        body.append("lot_id", document.getElementById("upload-lot").value);
        body.append("user", userSelect.value);
        body.append("user_dept", userSelect.options[userSelect.selectedIndex].dataset.dept);
        status.innerText = "Ingesting...";
        postForm("/api/upload", body, data => {
            status.innerText = data.status === "success" ? `Success! ID: ${data.document_id}` : "Ingestion failed.";
            fileInput.value = "";
        });
    });

    const openViewer = (id, text) => {
        fetch("/api/document/" + id).then(res => res.json()).then(doc => {
            document.getElementById("viewer-title").innerText = `[${doc.id}] ${doc.title}`;
            document.getElementById("viewer-snippet-text").innerText = text;
            document.getElementById("viewer-meta-dept").innerText = "Dept: " + doc.department;
            document.getElementById("viewer-meta-date").innerText = "Date: " + doc.date;
            document.getElementById("viewer-full-text").innerText = doc.transcript_text;
            overlay.style.display = "flex";
        });
    };

    document.getElementById("citations-list").addEventListener("click", e => {
        const btn = e.target.closest(".view-doc-btn");
        if (btn) openViewer(btn.dataset.id, btn.dataset.text);
    });

    document.getElementById("viewer-close").addEventListener("click", () => overlay.style.display = "none");
    overlay.addEventListener("click", e => { if (e.target === overlay) overlay.style.display = "none"; });

    if (window.lucide) window.lucide.createIcons();
});
