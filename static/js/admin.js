document.addEventListener("DOMContentLoaded", () => {
    const title = document.getElementById("admin-title");
    const subtitle = document.getElementById("admin-subtitle");

    const renderChart = (elId, data, colorKey = true) => {
        const el = document.getElementById(elId);
        if (!el || !data.length) { if (el) el.innerHTML = '<p class="text-muted">No data.</p>'; return; }
        const max = Math.max(...data.map(d => d.cnt || d.doc_count || 0));
        el.innerHTML = data.map(d => {
            const label = Object.values(d).find(v => typeof v === 'string') || Object.keys(d)[0];
            const val = d.cnt || d.doc_count || 0;
            const pct = max ? (val / max * 100) : 0;
            const labelText = d.action_type || d.project_id || d.source_type || Object.keys(d)[0];
            const color = colorKey ? (d.action_type === 'UPLOAD' ? '#10b981' : d.action_type === 'OCR_CORRECT' ? '#f59e0b' : '#38bdf8') : '#38bdf8';
            return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:12px"><span style="width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${labelText}">${labelText}</span><div style="flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden"><div style="width:${pct}%;height:100%;background:${color};border-radius:4px"></div></div><span style="width:40px;text-align:right;color:var(--text-muted)">${val}</span></div>`;
        }).join('');
    };

    window.timeframeData = null;
    window.changeTimeframeRange = (range) => {
        document.querySelectorAll("#timeframe-switch .tb-btn").forEach(b => {
            b.classList.toggle("active", b.dataset.range === range);
        });
        if (window.timeframeData) {
            document.getElementById("tf-uploads").textContent = window.timeframeData.uploads[range] || 0;
            document.getElementById("tf-activity").textContent = window.timeframeData.activity[range] || 0;
        }
    };

    async function loadDashboard() {
        const r = await fetch("/admin/dashboard").then(r => r.json());
        document.getElementById("stat-docs").textContent = r.total_docs;
        document.getElementById("stat-projects").textContent = r.total_projects;
        document.getElementById("stat-chunks").textContent = r.total_chunks;
        document.getElementById("stat-audits").textContent = r.total_audits;
        
        window.timeframeData = r.timeframe_stats;
        window.changeTimeframeRange("weekly");
        
        renderChart("admin-actions-chart", r.action_stats);
        renderChart("admin-sources-chart", r.source_stats, false);
        renderChart("admin-projects-chart", r.project_stats, false);
    }

    async function loadAudits() {
        const r = await fetch("/admin/audits?limit=100").then(r => r.json());
        const tbody = document.querySelector("#admin-audit-table tbody");
        tbody.innerHTML = r.logs.length ? r.logs.map(l => `<tr><td>${l.timestamp}</td><td>${l.username}</td><td>${l.action_type}</td><td>${l.details}</td></tr>`).join('') : '<tr><td colspan="4" class="text-muted">No logs.</td></tr>';
    }

    async function loadDocuments() {
        const search = document.getElementById("admin-doc-search").value;
        const proj = document.getElementById("admin-doc-project").value;
        const qs = new URLSearchParams({ limit: "100", project: proj });
        if (search) qs.set("title", search);
        const r = await fetch(`/admin/documents?${qs}`).then(r => r.json());
        const tbody = document.querySelector("#admin-doc-table tbody");
        tbody.innerHTML = r.documents.length ? r.documents.map(d => `<tr><td>${d.id}</td><td>${d.title}</td><td>${d.project_id||''}</td><td>${d.source_type||''}</td><td>${d.file_size_bytes?`${(d.file_size_bytes/1024).toFixed(1)} KB`:'—'}</td><td>${d.created_at||''}</td><td><button class="view-doc-btn" style="background:#ef4444; color:#fff; border-color:#ef4444; padding:2px 8px; font-size:11px;" onclick="window.deleteAdminDocument('${d.id.replace(/'/g, "\\'")}')">Delete</button></td></tr>`).join('') : '<tr><td colspan="7" class="text-muted">No documents.</td></tr>';
    }

    async function loadProjects() {
        const r = await fetch("/admin/projects").then(r => r.json());
        const tbody = document.querySelector("#admin-project-table tbody");
        tbody.innerHTML = r.projects.length ? r.projects.map(p => `<tr><td>${p.project_id}</td><td>${p.doc_count}</td><td>${p.total_size?`${(p.total_size/1024).toFixed(1)} KB`:'—'}</td><td>${p.last_updated||''}</td><td><button class="view-doc-btn" style="background:#ef4444; color:#fff; border-color:#ef4444; padding:2px 8px; font-size:11px;" onclick="window.deleteAdminProject('${p.project_id.replace(/'/g, "\\'")}')">Delete</button></td></tr>`).join('') : '<tr><td colspan="5" class="text-muted">No projects.</td></tr>';
    }

    window.deleteAdminDocument = async (docId) => {
        if (!confirm(`Are you sure you want to delete document "${docId}"?`)) return;
        const creds = JSON.parse(localStorage.getItem("scl_auth") || "{}");
        const key = creds.api_key || "";
        const r = await fetch(`/admin/documents/${encodeURIComponent(docId)}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${key}` }
        }).then(r => r.json());
        if (r.status === "success") {
            alert("Document deleted successfully.");
            loadDocuments();
            loadDashboard(); // Refresh counts
        } else {
            alert("Error: " + (r.detail || "Could not delete document."));
        }
    };

    window.deleteAdminProject = async (projectId) => {
        if (!confirm(`Are you sure you want to delete project "${projectId}" and all of its documents?`)) return;
        const creds = JSON.parse(localStorage.getItem("scl_auth") || "{}");
        const key = creds.api_key || "";
        const r = await fetch(`/admin/projects/${encodeURIComponent(projectId)}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${key}` }
        }).then(r => r.json());
        if (r.status === "success") {
            const custom = JSON.parse(localStorage.getItem("scl_custom_projects") || "[]");
            const filtered = custom.filter(p => p !== projectId);
            localStorage.setItem("scl_custom_projects", JSON.stringify(filtered));
            
            alert("Project deleted successfully.");
            loadProjects();
            loadDocuments();
            loadDashboard(); // Refresh counts
        } else {
            alert("Error: " + (r.detail || "Could not delete project."));
        }
    };

    async function loadUsers() {
        const creds = JSON.parse(localStorage.getItem("scl_auth") || "{}");
        const key = creds.api_key || "";
        const r = await fetch("/admin/users", {
            headers: { "Authorization": `Bearer ${key}` }
        }).then(r => r.json());
        const tbody = document.querySelector("#admin-user-table tbody");
        tbody.innerHTML = r.users.length ? r.users.map(u => {
            const roleSelect = `
                <select onchange="window.updateUserRole('${u.email.replace(/'/g, "\\'")}', this.value)" style="padding:4px;border:1px solid var(--border);border-radius:4px;background:var(--bg-card);color:var(--text);font-size:12px">
                    <option value="user" ${u.role === 'user' ? 'selected' : ''}>Normal User</option>
                    <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Admin</option>
                </select>
            `;
            const deleteBtn = `<button class="view-doc-btn" style="background:#ef4444; color:#fff; border-color:#ef4444; padding:2px 8px; font-size:11px;" onclick="window.deleteAdminUser('${u.email.replace(/'/g, "\\'")}')">Delete</button>`;
            return `<tr><td>${u.name}</td><td>${u.email}</td><td>${roleSelect}</td><td>${deleteBtn}</td></tr>`;
        }).join('') : '<tr><td colspan="4" class="text-muted">No users found.</td></tr>';
    }

    window.deleteAdminUser = async (email) => {
        if (!confirm(`Are you sure you want to delete user "${email}"?`)) return;
        const creds = JSON.parse(localStorage.getItem("scl_auth") || "{}");
        const key = creds.api_key || "";
        const r = await fetch(`/admin/users/${encodeURIComponent(email)}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${key}` }
        }).then(r => r.json());
        if (r.status === "success") {
            alert("User deleted successfully.");
            loadUsers();
        } else {
            alert("Error: " + (r.detail || "Could not delete user."));
        }
    };

    window.updateUserRole = async (email, newRole) => {
        const creds = JSON.parse(localStorage.getItem("scl_auth") || "{}");
        const key = creds.api_key || "";
        const r = await fetch(`/admin/users/${encodeURIComponent(email)}/role`, {
            method: "PUT",
            headers: { 
                "Authorization": `Bearer ${key}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ role: newRole })
        }).then(r => r.json());
        if (r.status === "success") {
            alert("User role updated successfully.");
            loadUsers();
        } else {
            alert("Error: " + (r.detail || "Could not update user role."));
        }
    };

    window.openAddUserModal = () => {
        document.getElementById("add-user-modal").style.display = "flex";
    };
    window.closeAddUserModal = () => {
        document.getElementById("add-user-modal").style.display = "none";
        document.getElementById("add-user-form").reset();
    };
    window.handleAddUser = async (e) => {
        e.preventDefault();
        const name = document.getElementById("new-user-name").value.trim();
        const email = document.getElementById("new-user-email").value.trim();
        const password = document.getElementById("new-user-pass").value;
        const role = document.getElementById("new-user-role").value;
        
        const creds = JSON.parse(localStorage.getItem("scl_auth") || "{}");
        const key = creds.api_key || "";
        const r = await fetch("/admin/users", {
            method: "POST",
            headers: { 
                "Authorization": `Bearer ${key}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ name, email, password, role })
        }).then(r => r.json());
        
        if (r.status === "success") {
            alert("User added successfully.");
            closeAddUserModal();
            loadUsers();
        } else {
            alert("Error: " + (r.detail || "Could not add user."));
        }
    };

    async function populateProjectFilter() {
        const sel = document.getElementById("admin-doc-project");
        const r = await fetch("/api/projects").then(r => r.json());
        r.projects.forEach(p => { const o = document.createElement("option"); o.value = p.id; o.textContent = p.name; sel.appendChild(o); });
    }

    let mapProjectsLoaded = false;
    async function loadKnowledgeMap() {
        const creds = JSON.parse(localStorage.getItem("scl_auth") || "{}");
        const key = creds.api_key || "";
        const filterSelect = document.getElementById("map-project-filter");
        
        if (!mapProjectsLoaded && filterSelect) {
            filterSelect.innerHTML = '<option value="">All Projects</option>';
            const r = await fetch("/api/projects").then(r => r.json());
            const projects = r.projects || [];
            projects.forEach(p => {
                const o = document.createElement("option");
                o.value = p.id || p;
                const name = p.name || p;
                o.textContent = name.replace(/_/g, " ");
                filterSelect.appendChild(o);
            });
            mapProjectsLoaded = true;
            filterSelect.addEventListener("change", () => loadKnowledgeMap());
        }
        
        const projVal = filterSelect ? filterSelect.value : "";
        const url = `/admin/knowledge-map` + (projVal ? `?project=${encodeURIComponent(projVal)}` : '');
        const data = await fetch(url, {
            headers: { "Authorization": `Bearer ${key}` }
        }).then(r => r.json());
        
        renderAdminGraph(data);
    }

    function renderAdminGraph(data) {
        const container = document.getElementById("cy-admin-container");
        if (!container) return;
        container.innerHTML = "";
        
        const elements = [];
        const projects = data.projects || [];
        projects.forEach(p => {
            const label = p.replace(/_/g, " ");
            elements.push({
                group: 'nodes',
                data: {
                    id: 'proj-' + p,
                    label: label.length > 20 ? label.substring(0, 18) + '…' : label,
                    type: 'project'
                }
            });
        });
        
        const documents = data.documents || [];
        documents.forEach(d => {
            const label = d.title || d.id;
            const cleanLabel = label.replace(/_/g, " ");
            elements.push({
                group: 'nodes',
                data: {
                    id: d.id,
                    label: cleanLabel.length > 20 ? cleanLabel.substring(0, 18) + '…' : cleanLabel,
                    type: 'document'
                }
            });
        });
        
        const decisions = data.decisions || [];
        decisions.forEach(dec => {
            const label = dec.summary || dec.id;
            elements.push({
                group: 'nodes',
                data: {
                    id: 'dec-' + dec.id,
                    label: label.length > 25 ? label.substring(0, 23) + '…' : label,
                    type: 'decision',
                    status: dec.status
                }
            });
        });
        
        const nodeIds = new Set(elements.map(e => e.data.id));
        
        documents.forEach(d => {
            if (d.project_id && d.project_id !== "Unknown") {
                const src = 'proj-' + d.project_id;
                const tgt = d.id;
                if (nodeIds.has(src) && nodeIds.has(tgt)) {
                    elements.push({
                        group: 'edges',
                        data: {
                            id: src + '-' + tgt,
                            source: src,
                            target: tgt,
                            type: 'project_to_doc'
                        }
                    });
                }
            }
        });
        
        decisions.forEach(dec => {
            if (dec.meeting_id) {
                const src = dec.meeting_id;
                const tgt = 'dec-' + dec.id;
                if (nodeIds.has(src) && nodeIds.has(tgt)) {
                    elements.push({
                        group: 'edges',
                        data: {
                            id: src + '-' + tgt,
                            source: src,
                            target: tgt,
                            type: 'doc_to_dec'
                        }
                    });
                }
            }
        });
        
        const lineage = data.lineage || [];
        lineage.forEach((l, idx) => {
            const src = l.from_node_id;
            const tgt = l.to_node_id;
            if (nodeIds.has(src) && nodeIds.has(tgt)) {
                elements.push({
                    group: 'edges',
                    data: {
                        id: 'lineage-' + idx,
                        source: src,
                        target: tgt,
                        type: 'lineage',
                        relation: l.relation_type,
                        rationale: l.rationale
                    }
                });
            }
        });
        
        if (!elements.length) {
            container.innerHTML = '<p class="text-muted" style="padding:2rem;text-align:center">No nodes or relations found in the database.</p>';
            return;
        }
        
        const cy = cytoscape({
            container,
            elements,
            style: [
                {
                    selector: 'node',
                    style: {
                        'shape': 'round-rectangle',
                        'width': 160,
                        'height': 50,
                        'background-color': '#0d0e12',
                        'border-width': 1.5,
                        'border-color': '#333',
                        'content': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'color': '#fff',
                        'font-size': '11px',
                        'text-wrap': 'wrap',
                        'text-max-width': 140,
                        'transition-property': 'opacity, border-width, border-color',
                        'transition-duration': '0.2s'
                    }
                },
                {
                    selector: 'node[type="project"]',
                    style: {
                        'border-color': '#38bdf8',
                        'background-color': '#0f172a',
                        'border-width': 2.5,
                        'font-weight': 'bold',
                        'font-size': '12px',
                        'width': 180,
                        'height': 55
                    }
                },
                {
                    selector: 'node[type="document"]',
                    style: {
                        'border-color': '#10b981',
                        'border-width': 2,
                        'shape': 'round-rectangle',
                        'cursor': 'pointer'
                    }
                },
                {
                    selector: 'node[type="decision"]',
                    style: {
                        'border-color': '#f59e0b',
                        'border-width': 1.5,
                        'font-size': '10px',
                        'height': 42,
                        'width': 150
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 1.5,
                        'line-color': 'rgba(255, 255, 255, 0.15)',
                        'target-arrow-color': 'rgba(255, 255, 255, 0.15)',
                        'target-arrow-shape': 'none',
                        'curve-style': 'bezier',
                        'transition-property': 'opacity',
                        'transition-duration': '0.2s'
                    }
                },
                {
                    selector: 'edge[type="project_to_doc"]',
                    style: {
                        'line-color': 'rgba(56, 189, 248, 0.3)',
                        'target-arrow-color': 'rgba(56, 189, 248, 0.3)',
                        'target-arrow-shape': 'triangle',
                        'width': 2
                    }
                },
                {
                    selector: 'edge[type="doc_to_dec"]',
                    style: {
                        'line-color': 'rgba(245, 158, 11, 0.3)',
                        'target-arrow-color': 'rgba(245, 158, 11, 0.3)',
                        'target-arrow-shape': 'triangle'
                    }
                },
                {
                    selector: 'edge[type="lineage"]',
                    style: {
                        'line-color': '#f43f5e',
                        'line-style': 'dashed',
                        'target-arrow-color': '#f43f5e',
                        'target-arrow-shape': 'triangle',
                        'width': 2
                    }
                },
                {
                    selector: '.faded',
                    style: {
                        'opacity': 0.1
                    }
                },
                {
                    selector: '.pinned',
                    style: {
                        'border-width': 4,
                        'border-color': '#00e5ff',
                        'z-index': 999
                    }
                }
            ],
            layout: {
                name: 'cose',
                idealEdgeLength: 140,
                nodeOverlap: 30,
                refresh: 20,
                fit: true,
                padding: 50,
                randomize: false,
                componentSpacing: 140,
                nodeRepulsion: 600000,
                edgeElasticity: 80,
                nestingFactor: 5,
                gravity: 60,
                numIter: 1500,
                initialTemp: 200,
                coolingFactor: 0.95,
                minTemp: 1.0
            },
            zoomingEnabled: true,
            userZoomingEnabled: true,
            panningEnabled: true,
            userPanningEnabled: true
        });
        
        // ponytail: pinned node state for click-to-stick
        let pinnedNode = null;
        
        const highlightNeighborhood = (n) => {
            cy.elements().addClass('faded');
            n.removeClass('faded').addClass('pinned');
            n.connectedEdges().forEach(e => {
                e.removeClass('faded');
                e.connectedNodes().forEach(n2 => n2.removeClass('faded'));
            });
        };
        
        const clearHighlight = () => {
            pinnedNode = null;
            cy.elements().removeClass('faded').removeClass('pinned');
        };
        
        // Single click: pin/select node
        cy.on('tap', 'node', function(evt) {
            const n = evt.target;
            if (pinnedNode && pinnedNode.id() === n.id()) {
                clearHighlight();
                return;
            }
            pinnedNode = n;
            highlightNeighborhood(n);
        });
        
        // Double click: open document viewer
        cy.on('dbltap', 'node', function(evt) {
            const n = evt.target;
            if (n.data('type') === 'document' && typeof openViewer === 'function') {
                openViewer(n.data('id'), '');
            }
        });
        
        // Click background: clear pin
        cy.on('tap', function(evt) {
            if (evt.target === cy) clearHighlight();
        });
        
        // Hover: only highlight if nothing is pinned
        cy.on('mouseover', 'node', function(evt) {
            if (pinnedNode) return;
            highlightNeighborhood(evt.target);
        });
        
        cy.on('mouseout', 'node', function() {
            if (pinnedNode) return;
            cy.elements().removeClass('faded').removeClass('pinned');
        });
        
        cy.on('mouseover', 'edge', function(evt) {
            const e = evt.target;
            const r = e.data('rationale');
            if (e.data('type') === 'lineage' && r) {
                container.title = `Relation: ${e.data('relation')}\nRationale: ${r}`;
            }
        });
        
        cy.on('mouseout', 'edge', function() {
            container.title = '';
        });
        
        window.cyAdmin = cy;
    }

    const sections = {
        "dashboard": { title: "Dashboard", subtitle: "System overview and management.", load: loadDashboard },
        "audits": { title: "Audits", subtitle: "Compliance and security audit trail.", load: loadAudits },
        "documents": { title: "Documents", subtitle: "All ingested documents across projects.", load: loadDocuments },
        "projects": { title: "Projects", subtitle: "Active projects in the system.", load: loadProjects },
        "users": { title: "User Directory", subtitle: "Manage user directory, registration and role tags.", load: loadUsers },
        "knowledge-map": { title: "Knowledge Map", subtitle: "Live interactive map of projects, documents, decisions, and lineages.", load: loadKnowledgeMap }
    };

    document.querySelectorAll(".admin-nav-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".admin-nav-btn,.admin-section").forEach(e => e.classList.remove("active"));
            btn.classList.add("active");
            const page = btn.dataset.page;
            document.getElementById(`admin-${page}`).classList.add("active");
            if (sections[page]) {
                title.textContent = sections[page].title;
                subtitle.textContent = sections[page].subtitle;
                sections[page].load();
            }
            if (window.lucide) window.lucide.createIcons();
        });
    });

    // Theme toggling
    const initTheme = () => {
        const tb = document.getElementById("theme-btn");
        if (!tb) return;
        const st = (dark) => {
            document.documentElement.classList.toggle("light", !dark);
            tb.innerHTML = dark ? '<re-icon icon="sun" size="20"></re-icon>' : '<re-icon icon="moon3" weight="filled" size="20"></re-icon>';
            localStorage.setItem('scl-theme', dark ? 'dark' : 'light');
        };
        const currentTheme = localStorage.getItem('scl-theme') || 'dark';
        st(currentTheme === 'dark');
        tb.addEventListener("click", () => st(document.documentElement.classList.contains("light")));
    };
    initTheme();

    ["admin-doc-search", "admin-doc-project"].forEach(id => document.getElementById(id).addEventListener("input", loadDocuments));
    populateProjectFilter();
    loadDashboard();
});
