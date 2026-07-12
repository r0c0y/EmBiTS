document.addEventListener("DOMContentLoaded", () => {
    const ov = document.getElementById("viewer-overlay");
    let sumMode = 'elaborate', parsedC = '', parsedE = '';
    let currentLang = 'English', translationCache = {}, rawC = '', rawE = '', rpl = null;
    let renderSummary = null;

    // Auth module logic
    const checkAuth = () => {
        const authData = localStorage.getItem("scl_auth");
        if (authData) {
            try {
                const user = JSON.parse(authData);
                document.getElementById("login-overlay").style.display = "none";
                document.getElementById("app-content-wrapper").style.display = "flex";
                
                const dispName = document.getElementById("user-display-name");
                if (dispName) dispName.textContent = user.name || user.email;
                const dispEmail = document.getElementById("user-display-email");
                if (dispEmail) dispEmail.textContent = user.email;
                const avatar = document.getElementById("user-avatar-initial");
                if (avatar) {
                    avatar.textContent = (user.name || user.email || 'U').charAt(0).toUpperCase();
                    avatar.setAttribute("data-tooltip", `${user.name || user.email} (${user.role.toUpperCase()})`);
                }
                
                if (user.role === 'admin') {
                    document.getElementById("admin-panel-link").style.display = "flex";
                    const docLink = document.getElementById("docs-panel-link");
                    if (docLink) docLink.style.display = "flex";
                    document.getElementById("nav-registry-btn").style.display = "flex";
                    document.getElementById("nav-audits-btn").style.display = "flex";
                    const regActivity = document.getElementById("reg-activity");
                    if (regActivity) regActivity.style.display = "block";
                } else {
                    document.getElementById("admin-panel-link").style.display = "none";
                    const docLink = document.getElementById("docs-panel-link");
                    if (docLink) docLink.style.display = "none";
                    document.getElementById("nav-registry-btn").style.display = "flex";
                    document.getElementById("nav-audits-btn").style.display = "none";
                    const regActivity = document.getElementById("reg-activity");
                    if (regActivity) regActivity.style.display = "none";
                }
                if (window.lucide) lucide.createIcons();
            } catch (e) {
                console.error("checkAuth crash:", e);
                localStorage.removeItem("scl_auth");
                showLogin();
            }
        } else {
            showLogin();
        }
    };

    const showLogin = () => {
        document.getElementById("login-overlay").style.display = "flex";
        document.getElementById("app-content-wrapper").style.display = "none";
    };



    let authMode = "signin";

    const toggleLink = document.getElementById("auth-toggle-link");
    if (toggleLink) {
        toggleLink.addEventListener("click", (e) => {
            e.preventDefault();
            const nameGrp = document.getElementById("login-name-group");
            const title = document.getElementById("auth-title");
            const subtitle = document.getElementById("auth-subtitle");
            const btn = document.getElementById("login-submit-btn");
            const errorMsg = document.getElementById("login-error-msg");
            
            errorMsg.style.display = "none";
            if (authMode === "signin") {
                authMode = "signup";
                nameGrp.style.display = "block";
                title.textContent = "Sign Up";
                subtitle.textContent = "Register a new ScribeLink account";
                btn.textContent = "Sign Up";
                toggleLink.textContent = "Already have an account? Sign In";
            } else {
                authMode = "signin";
                nameGrp.style.display = "none";
                title.textContent = "Sign In";
                subtitle.textContent = "Access the secure ScribeLink platform";
                btn.textContent = "Sign In";
                toggleLink.textContent = "New to ScribeLink? Sign Up";
            }
        });
    }

    const handleAuthSubmit = () => {
        const email = document.getElementById("login-email").value.trim();
        const pass = document.getElementById("login-password").value;
        const errorMsg = document.getElementById("login-error-msg");
        errorMsg.style.display = "none";
        console.log("handleAuthSubmit called:", authMode, email);

        if (!email || !pass) {
            errorMsg.textContent = "Email and Password are required";
            errorMsg.style.display = "block";
            return;
        }

        const fd = new FormData();
        fd.append("email", email);
        fd.append("password", pass);

        if (authMode === "signup") {
            const name = document.getElementById("login-name").value.trim();
            if (!name) {
                errorMsg.textContent = "Full Name is required";
                errorMsg.style.display = "block";
                return;
            }
            fd.append("name", name);
            
            console.log("Submitting signup fetch request...");
            fetch("/api/auth/signup", { method: "POST", body: fd })
                .then(r => r.json().then(d => ({ status: r.status, body: d })))
                .then(res => {
                    console.log("signup response:", res);
                    if (res.status === 200) {
                        localStorage.setItem("scl_auth", JSON.stringify(res.body.user));
                        checkAuth();
                    } else {
                        errorMsg.textContent = res.body.detail || "Sign up failed.";
                        errorMsg.style.display = "block";
                    }
                }).catch(err => {
                    console.error("signup fetch error:", err);
                    errorMsg.textContent = "An error occurred during registration.";
                    errorMsg.style.display = "block";
                });
        } else {
            console.log("Submitting signin fetch request...");
            fetch("/api/auth/signin", { method: "POST", body: fd })
                .then(r => r.json().then(d => ({ status: r.status, body: d })))
                .then(res => {
                    console.log("signin response:", res);
                    if (res.status === 200) {
                        localStorage.setItem("scl_auth", JSON.stringify(res.body.user));
                        checkAuth();
                    } else {
                        errorMsg.textContent = res.body.detail || "Invalid email or password.";
                        errorMsg.style.display = "block";
                    }
                }).catch(err => {
                    console.error("signin fetch error:", err);
                    errorMsg.textContent = "An error occurred during sign in.";
                    errorMsg.style.display = "block";
                });
        }
    };

    document.getElementById("login-submit-btn").addEventListener("click", handleAuthSubmit);

    document.querySelectorAll("#login-name, #login-email, #login-password").forEach(input => {
        input.addEventListener("keydown", e => {
            if (e.key === "Enter") {
                handleAuthSubmit();
            }
        });
    });

    checkAuth();

    // Dedicated Sign Out button trigger
    const logoutBtn = document.getElementById("btn-logout");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            if (confirm("Are you sure you want to sign out?")) {
                localStorage.removeItem("scl_auth");
                window.location.reload();
            }
        });
    }

    // Sidebar Navigation Tabs
    document.querySelectorAll(".nav-menu .nav-btn").forEach(b => b.addEventListener("click", () => {
        if (b.classList.contains("admin-only-link")) return; // Admin link is href redirect, not tab
        document.querySelectorAll(".nav-btn,.tab-content").forEach(e => e.classList.remove("active"));
        b.classList.add("active");
        if (b.dataset.tab) {
            const tabEl = document.getElementById(b.dataset.tab);
            if (tabEl) tabEl.classList.add("active");
        }
        const titleText = b.getAttribute("data-tooltip") || "";
        document.getElementById("tab-title").textContent = titleText;
        const subs = {
            "search-tab": "Query SCL meeting records.",
            "upload-tab": "Upload documents to the knowledge base.",
            "registry-tab": "View all indexed documents.",
            "audit-tab": "Security and compliance audit trail."
        };
        document.getElementById("tab-subtitle").textContent = subs[b.dataset.tab] || "";
        if (b.dataset.tab === "audit-tab") loadAudits();
        if (b.dataset.tab === "registry-tab") loadRegistry();
    }));

    // Remove legacy local storage entry once
    localStorage.removeItem("scl_custom_projects");
    const sessionCustomProjects = [];

    // Global helper to create/add a project
    const addCustomProject = (projName) => {
        const cleanId = projName.trim().replace(/\s+/g, "_");
        if (!cleanId) return;
        
        if (!sessionCustomProjects.includes(cleanId)) {
            sessionCustomProjects.push(cleanId);
        }
        
        const uploadInput = document.getElementById("upload-project");
        if (uploadInput) uploadInput.value = cleanId;

        refreshProjectDropdowns();
    };

    // Searchable dropdown list generator
    const mkProj = (input, menu, sharedAll, createNew = true) => {
        const render = (q = '') => {
            const s = q.toLowerCase();
            const items = sharedAll.filter(p => !s || p.toLowerCase().includes(s));
            let h = items.map(p => `<div class="proj-item" data-p="${p}">${p.replace(/_/g, " ")}</div>`).join('');
            if (createNew && s && !sharedAll.some(p => p.toLowerCase() === s)) {
                h += `<div class="proj-item proj-new" data-new="1" data-p="${q}">+ Create "${q}"</div>`;
            }
            menu.innerHTML = h || '<div class="proj-item" style="color:var(--text-muted);cursor:default">No projects found</div>';
            
            menu.querySelectorAll('.proj-item:not([style])').forEach(el => el.addEventListener('mousedown', e => {
                e.preventDefault();
                const selectedProject = el.dataset.p;
                if (el.dataset.new) {
                    addCustomProject(selectedProject);
                } else {
                    input.value = selectedProject;
                }
                input.dispatchEvent(new Event('change'));
                input.dispatchEvent(new Event('input'));
                menu.classList.remove('active');
            }));
        };

        if (input.readOnly) {
            input.addEventListener('mousedown', e => {
                e.stopPropagation();
                e.preventDefault();
                const isActive = menu.classList.contains('active');
                document.querySelectorAll('.proj-menu').forEach(m => m.classList.remove('active'));
                if (!isActive) {
                    menu.classList.add('active');
                    render(input.value);
                } else {
                    menu.classList.remove('active');
                }
            });
        } else {
            input.addEventListener('focus', () => {
                document.querySelectorAll('.proj-menu').forEach(m => m.classList.remove('active'));
                menu.classList.add('active');
                render(input.value);
            });
            input.addEventListener('input', () => {
                menu.classList.add('active');
                render(input.value);
            });
            input.addEventListener('keydown', e => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const s = input.value.trim();
                    if (s) {
                        if (createNew) {
                            addCustomProject(s);
                        } else {
                            const clean = s.replace(/\s+/g, "_");
                            const matched = sharedAll.find(p => p.toLowerCase() === clean.toLowerCase());
                            if (matched) input.value = matched;
                        }
                    }
                    input.dispatchEvent(new Event('change'));
                    input.dispatchEvent(new Event('input'));
                    menu.classList.remove('active');
                }
            });
        }

        document.addEventListener('mousedown', e => {
            if (!menu.contains(e.target) && e.target !== input) menu.classList.remove('active');
        });
    };

    // Multi-select searchable checkbox dropdown generator
    // ponytail: guards re-init — only binds event listeners once per input
    const mkMultiSelect = (input, menu, items, placeholder, onChange) => {
        // If already initialized, just update items/onChange and re-render
        if (input._msInit) {
            input._msItems = items;
            input._msOnChange = onChange || null;
            input._msSelected = [];
            input.value = "";
            input.placeholder = placeholder;
            input._msRender();
            return;
        }
        input._msInit = true;
        input._msItems = items;
        input._msOnChange = onChange || null;
        input._msSelected = [];

        input._msRender = () => {
            const sel = input._msSelected;
            const itms = input._msItems;
            let h = itms.map(item => {
                const val = item.id || item;
                const rawDisplay = item.title || (typeof item === 'string' ? item : item.id || '');
                const display = (rawDisplay || '').replace(/_/g, " ");
                const isChecked = sel.includes(val);
                return `
                    <div class="proj-item multi-item ${isChecked ? 'sel' : ''}" data-val="${val}" style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;cursor:pointer;width:100%;box-sizing:border-box;color:var(--text);font-size:13px;border-bottom:1px solid var(--border);">
                        <span style="text-align:left;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${display}</span>
                        ${isChecked ? '<span class="check-mark" style="color:#38bdf8;font-weight:bold;margin-left:8px;flex-shrink:0;">✓</span>' : ''}
                    </div>
                `;
            }).join('');
            
            menu.innerHTML = h || `<div class="proj-item" style="color:var(--text-muted);cursor:default;font-size:13px;padding:10px 14px;">No options available</div>`;
            
            menu.querySelectorAll('.proj-item[data-val]').forEach(el => {
                el.addEventListener('click', e => {
                    e.preventDefault();
                    e.stopPropagation();
                    const val = el.dataset.val;
                    const idx = input._msSelected.indexOf(val);
                    if (idx > -1) {
                        input._msSelected.splice(idx, 1);
                    } else {
                        input._msSelected.push(val);
                    }
                    
                    if (input._msSelected.length === 0) {
                        input.value = "";
                        input.placeholder = placeholder;
                    } else {
                        const displayList = input._msItems
                            .filter(item => input._msSelected.includes(item.id || item))
                            .map(item => {
                                const rawDisplay = item.title || (typeof item === 'string' ? item : item.id || '');
                                return (rawDisplay || '').replace(/_/g, " ");
                            });
                        input.value = displayList.join(", ");
                    }
                    
                    input.dispatchEvent(new Event('change'));
                    input.dispatchEvent(new Event('input'));
                    input._msRender();
                    if (input._msOnChange) input._msOnChange(input._msSelected);
                });
            });
        };

        input.addEventListener('click', e => {
            e.stopPropagation();
            const isActive = menu.classList.contains('active');
            document.querySelectorAll('.proj-menu').forEach(m => m.classList.remove('active'));
            if (!isActive) {
                menu.classList.add('active');
                input._msRender();
            } else {
                menu.classList.remove('active');
            }
        });
        
        input.clearSelection = () => {
            input._msSelected = [];
            input.value = "";
            input.placeholder = placeholder;
            input._msRender();
        };

        input.getSelectedValues = () => input._msSelected;
        
        document.addEventListener('mousedown', e => {
            if (!menu.contains(e.target) && e.target !== input) {
                menu.classList.remove('active');
            }
        });
    };

    let projAll = [];
    const refreshProjectDropdowns = () => {
        fetch("/api/projects").then(r => r.json()).then(d => {
            const dbProjects = d.projects.map(p => p.name || p.id);
            dbProjects.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base', numeric: true }));
            
            for (let i = sessionCustomProjects.length - 1; i >= 0; i--) {
                if (dbProjects.includes(sessionCustomProjects[i])) {
                    sessionCustomProjects.splice(i, 1);
                }
            }
            
            projAll = [...new Set([...dbProjects, ...sessionCustomProjects])];
            
            const filterInput = document.getElementById("project-filter");
            const filterMenu = document.getElementById("search-proj-menu");
            if (filterInput && filterMenu) {
                mkMultiSelect(filterInput, filterMenu, dbProjects, "All Projects", (selectedProjIds) => {
                    updateDocumentFilter(selectedProjIds);
                });
            }
            
            const uploadProjInput = document.getElementById("upload-project");
            const uploadProjMenu = document.getElementById("upload-proj-menu");
            if (uploadProjInput && uploadProjMenu) {
                mkProj(uploadProjInput, uploadProjMenu, projAll, true);
            }
        });
    };
    refreshProjectDropdowns();

    const updateDocumentFilter = (project_ids) => {
        const docInput = document.getElementById("document-filter");
        const docMenu = document.getElementById("search-doc-menu");
        if (!docInput || !docMenu) return;
        
        if (docInput.clearSelection) docInput.clearSelection();
        
        const projParam = (project_ids && project_ids.length) ? project_ids.join(",") : "";
        fetch(`/api/documents?project=${encodeURIComponent(projParam)}`).then(r => r.json()).then(d => {
            const docs = d.documents || [];
            docs.sort((a, b) => (a.title || "").localeCompare(b.title || "", undefined, { sensitivity: 'base', numeric: true }));
            mkMultiSelect(docInput, docMenu, docs, "All Documents");
        }).catch(() => {});
    };
    
    // Initial Document list fetch (all projects)
    updateDocumentFilter([]);

    // Search and Traceability Submission
    document.getElementById("search-form").addEventListener("submit", e => {
        e.preventDefault();
        const ai = document.getElementById("ai-answer"), cl = document.getElementById("citations-list");
        const q = document.getElementById("query-input").value;
        if (q.trim()) saveHistory(q);
        ai.innerHTML = '<div class="spinner"></div>';
        cl.innerHTML = '<p class="text-muted">Loading...</p>';
        
        const fd = new FormData();
        fd.append("query", q);
        const projEl = document.getElementById("project-filter");
        const docEl = document.getElementById("document-filter");
        const selectedProj = (projEl && projEl.getSelectedValues) ? projEl.getSelectedValues() : [];
        const selectedDocs = (docEl && docEl.getSelectedValues) ? docEl.getSelectedValues() : [];
        
        fd.append("project", selectedProj.join(","));
        fd.append("document", selectedDocs.join(","));
        fd.append("date_from", document.getElementById("date-from").value);
        fd.append("date_to", document.getElementById("date-to").value);
        
        const currentUser = JSON.parse(localStorage.getItem("scl_auth") || "{}");
        fd.append("user", currentUser.name || "Unknown");
        fd.append("user_dept", currentUser.role || "User");
        
        fetch("/api/search", { method: "POST", body: fd }).then(r => r.json()).then(d => {
            window._lastCitations = d.citations || [];
            const cm = {};
            (d.citations || []).forEach((c, i) => cm[c.meeting_id] = i + 1);
            let rpl = t => {
                const placeholders = [];
                t = t.replace(/\[(\d+)\]/g, (match, num) => {
                    const idx = parseInt(num) - 1;
                    const c = (d.citations || [])[idx];
                    if (c) {
                        const cleanText = c.text.replace(/\\n/g, '\n').replace(/\\r/g, '\r');
                        const escapedText = cleanText.replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, '\\n');
                        const html = `<span class="cl" onclick="openViewer('${c.meeting_id}', '${escapedText}')" title="View: ${c.meeting_title}">[${num}]</span>`;
                        const ph = `___PH_${placeholders.length}___`;
                        placeholders.push({ ph, html });
                        return ph;
                    }
                    return match;
                });
                if (d.citations && d.citations.length) {
                    const escapedIds = d.citations.map(c => c.meeting_id.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')).join('|');
                    const regex = new RegExp(`\\b(${escapedIds})\\b`, 'g');
                    t = t.replace(regex, m => {
                        const num = cm[m];
                        const c = (d.citations || [])[num - 1];
                        if (num) {
                            const cleanText = c ? c.text.replace(/\\n/g, '\n').replace(/\\r/g, '\r') : '';
                            const escapedText = cleanText.replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, '\\n');
                            const html = `<span class="cl" onclick="openViewer('${m}', '${escapedText}')" title="View: ${m}">[${num}]</span>`;
                            const ph = `___PH_${placeholders.length}___`;
                            placeholders.push({ ph, html });
                            return ph;
                        }
                        return m;
                    });
                }
                for (let i = placeholders.length - 1; i >= 0; i--) {
                    t = t.replace(placeholders[i].ph, placeholders[i].html);
                }
                return t;
            };
            
            const ex = (t) => {
                const s = d.answer.indexOf(`<${t}>`);
                if (s < 0) return null;
                const a = d.answer.slice(s + t.length + 2);
                const e = a.indexOf(`</${t}>`);
                const n = a.search(/<(?:concise|elaborate)>/);
                const end = e >= 0 ? e : n >= 0 ? Math.min(e < 0 ? 1/0 : e, n) : a.length;
                return a.slice(0, end).trim();
            };
            const conc = ex('concise'), elab = ex('elaborate');
            try {
                parsedC = parseMD(rpl(conc || elab || d.answer));
                parsedE = parseMD(rpl(elab || d.answer));
            } catch (e) {
                parsedC = parsedE = d.answer;
            }
            
            rawC = conc || elab || d.answer;
            rawE = elab || d.answer;
            currentLang = "English";
            translationCache = {
                "English": { concise: parsedC, elaborate: parsedE }
            };
            // ponytail: rpl is already defined as closure above (line 448)
            
            renderSummary = async () => {
                const ai = document.getElementById("ai-answer");
                if (!ai) return;

                if (translationCache[currentLang] && translationCache[currentLang][sumMode]) {
                    const content = translationCache[currentLang][sumMode];
                    ai.innerHTML = `
                        <div class="ai-text">${content}</div>
                        <div style="display:flex;align-items:center;gap:10px;margin-top:14px;">
                            <button class="copy-btn" onclick="copyAI()" style="margin:0;">📋 Copy Response</button>
                            <div style="display:flex;align-items:center;gap:4px;background:var(--border);padding:2px;border-radius:6px;" id="lang-switch">
                                <button class="tb-btn ${currentLang === 'English' ? 'active' : ''}" data-lang="English" style="padding:4px 8px;font-size:11px;border-radius:4px;cursor:pointer;">EN</button>
                                <button class="tb-btn ${currentLang === 'Hindi' ? 'active' : ''}" data-lang="Hindi" style="padding:4px 8px;font-size:11px;border-radius:4px;cursor:pointer;">HI</button>

                            </div>
                        </div>
                    `;
                    renderKatex(ai);
                    renderMermaid(ai);
                    document.querySelectorAll("#summ-tg .tb-btn").forEach(b => b.classList.toggle("active", b.dataset.mode === sumMode));
                    
                    const switchEl = document.getElementById("lang-switch");
                    if (switchEl) {
                        switchEl.querySelectorAll(".tb-btn").forEach(btn => {
                            btn.addEventListener("click", () => {
                                const lang = btn.dataset.lang;
                                if (lang === currentLang) return;
                                currentLang = lang;
                                renderSummary();
                            });
                        });
                    }
                } else {
                    ai.innerHTML = `
                        <div class="ai-text"><p class="text-muted" style="padding:1rem;text-align:center;">Translating summary to ${currentLang}...</p></div>
                        <div style="display:flex;align-items:center;gap:10px;margin-top:14px;">
                            <button class="copy-btn" disabled style="margin:0;opacity:0.5;">📋 Copy Response</button>
                            <div style="display:flex;align-items:center;gap:4px;background:var(--border);padding:2px;border-radius:6px;opacity:0.5;pointer-events:none;">
                                <button class="tb-btn ${currentLang === 'English' ? 'active' : ''}">EN</button>
                                <button class="tb-btn ${currentLang === 'Hindi' ? 'active' : ''}">HI</button>

                            </div>
                        </div>
                    `;
                    try {
                        const currentRaw = (sumMode === 'concise') ? rawC : rawE;
                        const creds = JSON.parse(localStorage.getItem("scl_auth") || "{}");
                        const key = creds.api_key || "";
                        const res = await fetch("/api/translate", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                                "Authorization": `Bearer ${key}`
                            },
                            body: JSON.stringify({ text: currentRaw, target_lang: currentLang })
                        }).then(r => r.json());
                        
                        if (res.status === "success" && res.translated_text) {
                            let parsed = "";
                            try {
                                parsed = parseMD(rpl(res.translated_text));
                            } catch (e) {
                                parsed = res.translated_text;
                            }
                            if (!translationCache[currentLang]) translationCache[currentLang] = {};
                            translationCache[currentLang][sumMode] = parsed;
                            renderSummary();
                        } else {
                            throw new Error("Translation failed.");
                        }
                    } catch(err) {
                        ai.innerHTML = `
                            <div class="ai-text"><p class="text-muted" style="padding:1rem;color:#ff4444;text-align:center;">Translation error: ${err.message}</p></div>
                            <div style="display:flex;align-items:center;gap:10px;margin-top:14px;">
                                <button class="copy-btn" onclick="copyAI()" style="margin:0;">📋 Copy Response</button>
                                <div style="display:flex;align-items:center;gap:4px;background:var(--border);padding:2px;border-radius:6px;" id="lang-switch">
                                    <button class="tb-btn" data-lang="English">EN</button>
                                    <button class="tb-btn" data-lang="Hindi">HI</button>

                                </div>
                            </div>
                        `;
                        const switchEl = document.getElementById("lang-switch");
                        if (switchEl) {
                            switchEl.querySelectorAll(".tb-btn").forEach(btn => {
                                btn.addEventListener("click", () => {
                                    const lang = btn.dataset.lang;
                                    currentLang = lang;
                                    renderSummary();
                                });
                            });
                        }
                    }
                }
            };
            renderSummary();
            document.getElementById("summ-tg").style.display = (conc && elab) ? "flex" : "none";
            cl.innerHTML = d.citations.length ? "" : '<p class="text-muted">No matching citations.</p>';
            
            const currentQuery = document.getElementById("query-input").value;
            d.citations.forEach((c, i) => {
                const ht = highlightKW(c.text, currentQuery);
                const scoreBadge = `<span class="badge" style="background:rgba(56,189,248,0.1); border-color:rgba(56,189,248,0.3); color:#38bdf8; font-weight:600; margin-left:8px; font-size:10px;">Score: ${(c.confidence || 0.00).toFixed(2)}</span>`;
                cl.innerHTML += `<details class="disclosure"><summary><span class="cit-num">[${i + 1}]</span> ${c.meeting_title}${scoreBadge}</summary><div><p><strong>Date:</strong> ${c.date} | <strong>Page:</strong> ${c.page_number || 1} | <strong>Project:</strong> ${c.project_id || 'Unknown'}</p><p style="margin-top:8px">${ht}</p><div style="margin-top:8px;display:flex;gap:6px"><button class="view-doc-btn" data-id="${c.meeting_id}" data-text="${c.text.replace(/"/g, '&quot;')}">View Doc</button><a href="/api/download/${c.meeting_id}" class="dl-btn">↓ Download</a></div></div></details>`;
            });
            try { renderGraph(d.graph || { nodes: [], edges: [] }); } catch (e) {}
            try { renderDecisions((d.graph || {}).decisions || []); } catch (e) {}
            
            const cp = document.getElementById("conflicts-panel");
            const cl2 = document.getElementById("conflicts-list");
            const hasC = d.conflicts && d.conflicts.length > 0;
            if (hasC) {
                cl2.innerHTML = d.conflicts.map(c => `<div class="conflict-item"><h4>⚠ ${c.parameter}</h4>${c.values.map(v => `<div class="val"><span class="doc-title">${v.title}</span><span class="doc-value">${v.value}</span></div>${v.snippet ? `<div class="val-snippet">…${v.snippet}…</div>` : ''}`).join("")}</div>`).join("");
                const bg = document.getElementById("conflicts-badge");
                if (bg) bg.textContent = `⚠ ${d.conflicts.length} Conflicts`;
            }
            if (window.setHasConflicts) window.setHasConflicts(hasC);
            if (window.lucide) window.lucide.createIcons();
        });
    });

    document.getElementById("summ-tg").addEventListener("click", e => {
        const b = e.target.closest(".tb-btn");
        if (!b) return;
        sumMode = b.dataset.mode;
        if (renderSummary) renderSummary();
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

    // File Ingestion Logic
    let fileQueue = [];
    const fmtSize = (b) => {
        for (const u of ['B', 'KB', 'MB', 'GB']) {
            if (Math.abs(b) < 1024) return b.toFixed(1) + ' ' + u;
            b /= 1024;
        }
        return b.toFixed(1) + ' TB';
    };

    const rq = () => {
        const q = document.getElementById("file-queue"), c = document.getElementById("queue-count");
        if (!fileQueue.length) {
            q.innerHTML = '<p class="text-muted" style="font-size:12px">No files selected</p>';
            c.textContent = '';
            return;
        }
        c.textContent = fileQueue.filter(f => f.status !== 'done').length + ' pending';
        
        q.innerHTML = fileQueue.map((f, i) => {
            const ext = f.file.name.split('.').pop().toLowerCase();
            const sizeStr = fmtSize(f.file.size);
            
            let statusIndicator = '';
            if (f.status === 'done') {
                statusIndicator = `<span class="file-status done" style="color: #10b981; font-weight: 600;">✓ Ingested</span>`;
            } else if (f.status === 'duplicate') {
                statusIndicator = `<span class="file-status duplicate" style="color: #f59e0b; font-weight: 600;">⚠ Duplicate</span>`;
            } else if (f.status === 'error') {
                statusIndicator = `<span class="file-status error" style="color: #ef4444; font-weight: 600;">⚠ Failed</span>`;
            } else if (f.status === 'uploading') {
                const progress = f.progress || 0;
                const dashOffset = 56.54 - (progress / 100) * 56.54;
                statusIndicator = `
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div style="position:relative; width:24px; height:24px; display:inline-flex; align-items:center; justify-content:center;">
                            <svg class="progress-ring" width="24" height="24">
                                <circle class="progress-ring__circle" stroke="#222" stroke-width="2.5" fill="transparent" r="9" cx="12" cy="12" />
                                <circle class="progress-ring__circle" stroke="#38bdf8" stroke-width="2.5" fill="transparent" r="9" cx="12" cy="12" stroke-dasharray="56.54" stroke-dashoffset="${dashOffset}" />
                            </svg>
                            <span style="position:absolute; font-size:7px; color:var(--text); font-weight:700;">${progress}%</span>
                        </div>
                        <span class="file-rm cancel-btn" data-idx="${i}" title="Cancel Upload" style="cursor: pointer; font-size: 11px; padding: 2px 6px;">✕</span>
                    </div>`;
            } else {
                statusIndicator = `<span class="file-rm" data-idx="${i}">✕</span>`;
            }
            
            return `<span class="file-item ${f.status}${f.fadeClass ? ' ' + f.fadeClass : ''}" style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; margin-bottom: 4px; background: var(--bg); border: 1px solid var(--border); border-radius: 6px;">
                <span style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;">
                    <span class="file-badge-format ${ext}">${ext}</span>
                    <span class="file-name" title="${f.file.name}" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${f.file.name}</span>
                </span>
                <span style="display: flex; align-items: center; gap: 12px; flex-shrink: 0;">
                    <span class="file-size" style="color: var(--text-muted); font-size: 11px;">${sizeStr}</span>
                    ${statusIndicator}
                </span>
            </span>`;
        }).join('');
    };

    const af = (files) => {
        for (const f of files) fileQueue.push({ file: f, status: 'pending', xhr: null });
        rq();
        document.getElementById("file-input").value = '';
    };

    const dz = document.getElementById("drop-zone"), fi2 = document.getElementById("file-input");
    dz.addEventListener("click", () => fi2.click());
    dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("dragover"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
    dz.addEventListener("drop", e => { e.preventDefault(); dz.classList.remove("dragover"); af(e.dataTransfer.files); });
    fi2.addEventListener("change", () => af(fi2.files));
    
    document.getElementById("file-queue").addEventListener("click", e => {
        const rm = e.target.closest(".file-rm");
        if (rm) {
            const idx = parseInt(rm.dataset.idx);
            const item = fileQueue[idx];
            if (item) {
                if (item.status === 'uploading' && item.xhr) {
                    item.xhr.abort();
                }
                fileQueue.splice(idx, 1);
                rq();
            }
        }
    });

    // Ingest Parallel Uploads
    document.getElementById("upload-form").addEventListener("submit", async e => {
        e.preventDefault();
        const pending = fileQueue.filter(f => f.status === 'pending');
        if (!pending.length) {
            alert("No files to upload. Drag & drop or browse to add files.");
            return;
        }
        const proj = document.getElementById("upload-project").value.trim();
        if (!proj) {
            alert("Please select or create a project before ingesting documents.");
            return;
        }
        const currentUser = JSON.parse(localStorage.getItem("scl_auth") || "{}");
        
        let completedCount = 0;
        const totalPending = pending.length;
        
        // Execute parallel uploads
        await Promise.all(pending.map(async (item) => {
            item.status = 'uploading';
            item.progress = 0;
            rq();
            
            const fd = new FormData();
            fd.append("file", item.file);
            fd.append("project_id", proj);
            fd.append("user", currentUser.name || "Unknown");
            fd.append("user_dept", currentUser.role || "User");
            
            try {
                const d = await new Promise((resolve, reject) => {
                    const xhr = new XMLHttpRequest();
                    item.xhr = xhr; // Store reference so we can abort/cancel
                    
                    xhr.open("POST", "/api/upload");
                    xhr.upload.onprogress = e => {
                        if (e.lengthComputable) {
                            item.progress = Math.round(e.loaded / e.total * 100);
                            rq();
                        }
                    };
                    xhr.onload = () => {
                        if (xhr.status >= 200 && xhr.status < 300) {
                            try {
                                resolve(JSON.parse(xhr.responseText));
                            } catch (err) {
                                reject(xhr.statusText);
                            }
                        } else {
                            reject(xhr.statusText);
                        }
                    };
                    xhr.onerror = () => reject(xhr.statusText);
                    xhr.onabort = () => reject("aborted");
                    xhr.send(fd);
                });
                if (d.status === "duplicate") {
                    item.status = "duplicate";
                } else if (d.status === "success") {
                    item.status = "done";
                    try {
                        refreshProjectDropdowns();
                        loadRegistry();
                    } catch (e) {
                        console.error("Realtime list refresh failed", e);
                    }
                } else {
                    item.status = "error";
                }
                item.docId = d.document_id || "";
            } catch (err) {
                if (err === "aborted") return; // item already deleted by abort handler
                item.status = "error";
            }
            
            completedCount++;
            rq();
            
            if (item.status === "done") {
                // Wait 500ms, then trigger 1-second fade out, then remove
                setTimeout(() => {
                    item.fadeClass = "fade-out";
                    rq();
                    setTimeout(() => {
                        const idx = fileQueue.indexOf(item);
                        if (idx > -1) fileQueue.splice(idx, 1);
                        rq();
                        
                        // Check if all uploads in the queue are completed
                        if (fileQueue.length === 0 || fileQueue.every(f => f.status === 'done' || f.status === 'error' || f.status === 'duplicate')) {
                            showDoneToast();
                        }
                    }, 1000); // 1 sec fade-out duration
                }, 500);
            } else if (item.status === "duplicate") {
                // Wait 1500ms so user can see "Duplicate" status, then trigger 1-second fade out, then remove
                setTimeout(() => {
                    item.fadeClass = "fade-out";
                    rq();
                    setTimeout(() => {
                        const idx = fileQueue.indexOf(item);
                        if (idx > -1) fileQueue.splice(idx, 1);
                        rq();
                        
                        // Check if all uploads in the queue are completed
                        if (fileQueue.length === 0 || fileQueue.every(f => f.status === 'done' || f.status === 'error' || f.status === 'duplicate')) {
                            showDoneToast();
                        }
                    }, 1000); // 1 sec fade-out duration
                }, 1500);
            } else if (item.status === "error") {
                if (fileQueue.every(f => f.status === 'done' || f.status === 'error' || f.status === 'duplicate')) {
                    showDoneToast();
                }
            }
        }));
        
        const showDoneToast = () => {
            const toast = document.getElementById("upload-success-toast");
            if (toast) {
                toast.style.display = "flex";
                setTimeout(() => {
                    toast.style.display = "none";
                }, 2000);
            }
        };
        
        // Auto-refresh registry and projects dropdowns
        refreshProjectDropdowns();
        loadRegistry();
    });

    document.getElementById("citations-list").addEventListener("click", e => {
        const btn = e.target.closest(".view-doc-btn");
        if (btn) openViewer(btn.dataset.id, btn.dataset.text);
    });
    document.getElementById("reg-docs").addEventListener("click", e => {
        const btn = e.target.closest(".view-doc-btn");
        if (btn) openViewer(btn.dataset.id, "");
    });
    
    document.getElementById("viewer-close").addEventListener("click", () => ov.style.display = "none");
    document.getElementById("viewer-download").addEventListener("click", () => {
        if (window._currentDocId) window.open("/api/download/" + window._currentDocId);
    });
    ov.addEventListener("click", e => { if (e.target === ov) ov.style.display = "none"; });
    
    document.getElementById("viewer-ocr").addEventListener("click", () => {
        if (!window._currentDoc) return;
        window._viewerMode = (window._viewerMode === 'original' ? 'ocr' : 'original');
        const ocrBtn = document.getElementById("viewer-ocr");
        if (ocrBtn) {
            ocrBtn.innerText = window._viewerMode === 'ocr' ? "📄 Original" : "👁 OCR";
        }
        renderViewerContent();
    });

    // Project Registry
    const loadRegistry = () => {
        fetch("/api/registry").then(r => r.json()).then(d => {
            const sb = document.getElementById("reg-projects");
            sb.innerHTML = d.projects.length ? "" : '<p class="text-muted">No projects found.</p>';
            d.projects.forEach((p, idx) => {
                const el = document.createElement("div");
                el.className = "reg-project-item";
                el.innerHTML = `<span>${p.project_id.replace(/_/g, " ")}</span><span class="badge">${p.doc_count}</span>`;
                el.addEventListener("click", () => {
                    sb.querySelectorAll(".reg-project-item").forEach(x => x.classList.remove("sel"));
                    el.classList.add("sel");
                    loadProjectDocs(p.project_id);
                    loadActivity(p.project_id);
                });
                sb.appendChild(el);
                if (idx === 0) {
                    el.click();
                }
            });
        });
    };

    const loadProjectDocs = (pid) => {
        const title = document.getElementById("reg-search").value;
        const st = document.getElementById("reg-source").value;
        const df = document.getElementById("reg-from").value;
        const dt = document.getElementById("reg-to").value;
        const sort = document.getElementById("reg-sort").value;
        const qs = new URLSearchParams({ sort, source_type: st, title, date_from: df, date_to: dt });
        
        fetch(`/api/registry/${encodeURIComponent(pid)}/documents?${qs}`).then(r => r.json()).then(d => {
            const mb = document.getElementById("reg-docs");
            mb.innerHTML = d.documents.length ? "" : '<p class="text-muted">No documents found.</p>';
            if (!d.documents.length) return;
            
            mb.innerHTML = '<div class="reg-docs">' + d.documents.map(x => {
                const sz = x.file_size_bytes ? fmtSize(x.file_size_bytes) : "—";
                const q = x.ocr_quality || "auto";
                const qc = q === "high" ? "high" : q === "low" ? "low" : "medium";
                const thumb = x.source_type && ["pdf", "png", "jpg", "jpeg", "tiff", "bmp"].includes(x.source_type) ? `<img src="/api/originals/${x.id}_${x.file_path}" class="reg-thumb" onerror="this.style.display='none'">` : "";
                // created_at is "YYYY-MM-DD HH:MM:SS" — split into date and time parts
                const [dtDate, dtTime] = x.created_at ? x.created_at.split(" ") : ["—", ""];
                return `<div class="reg-doc-item">${thumb}<div class="reg-doc-info"><div class="reg-doc-title">${x.title}</div><div class="reg-doc-meta"><span class="reg-quality ${qc}"></span>Date: ${dtDate || "—"} · Time: ${dtTime || "—"} · Format: ${x.source_type ? x.source_type.toUpperCase() : "?"} · Size: ${sz} · By: ${x.uploaded_by || "Anonymous"}</span></div></div><div class="reg-doc-actions"><button class="view-doc-btn" data-id="${x.id}" data-text="">View</button><a href="/api/download/${x.id}" class="dl-btn">↓</a></div></div>`;
            }).join("") + "</div>";
        });
    };

    const loadActivity = (pid) => {
        fetch(`/api/registry/${encodeURIComponent(pid)}/activity`).then(r => r.json()).then(d => {
            const al = document.getElementById("reg-activity-list");
            al.innerHTML = d.logs.length ? "" : '<p class="text-muted">No activity.</p>';
            al.innerHTML = d.logs.map(l => `<div class="reg-activity-item"><strong>${l.username}</strong> ${l.action_type} · ${l.timestamp} · ${l.details}</div>`).join("");
        });
    };

    ["reg-search", "reg-source", "reg-from", "reg-to", "reg-sort"].forEach(id => {
        document.getElementById(id).addEventListener("input", () => {
            const sel = document.querySelector(".reg-project-item.sel");
            if (sel) {
                const pid = sel.querySelector('span').textContent.trim().replace(/\s+/g, "_");
                loadProjectDocs(pid);
            }
        });
    });

    // Local filter audits
    const auditSearchInput = document.getElementById("audit-search-filter");
    if (auditSearchInput) {
        auditSearchInput.addEventListener("input", e => {
            const query = e.target.value.toLowerCase().trim();
            if (!window._allAudits) return;
            const filtered = window._allAudits.filter(l => {
                return (l.username || "").toLowerCase().includes(query) ||
                       (l.action_type || "").toLowerCase().includes(query) ||
                       (l.details || "").toLowerCase().includes(query) ||
                       (l.timestamp || "").toLowerCase().includes(query);
            });
            renderAudits(filtered);
        });
    }

    if (window.mermaid) mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' });
    renderHistory();
    initCitePreview();

    const Cal = (input, picker) => {
        let d = new Date(), y = d.getFullYear(), m = d.getMonth();
        const days = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

        const render = () => {
            const first = new Date(y, m, 1);
            const start = first.getDay();
            const dim = new Date(y, m + 1, 0).getDate();
            const dpm = new Date(y, m, 0).getDate();
            let h = `<div class="cal-header"><button class="cal-nav" data-d="-1">◀</button><span>${y}-${String(m + 1).padStart(2, '0')}</span><button class="cal-nav" data-d="1">▶</button></div><div class="cal-grid">`;
            days.forEach(day => h += `<div class="cal-dow">${day}</div>`);
            for (let i = start - 1; i >= 0; i--) h += `<div class="cal-day other">${dpm - i}</div>`;
            for (let i = 1; i <= dim; i++) {
                const t = new Date();
                h += `<div class="cal-day${i === t.getDate() && m === t.getMonth() && y === t.getFullYear() ? ' today' : ''}" data-d="${i}">${i}</div>`;
            }
            const tot = start + dim;
            for (let i = 1; i <= (tot % 7 ? 7 - tot % 7 : 0); i++) h += `<div class="cal-day other">${i}</div>`;
            h += "</div>";
            picker.innerHTML = h;

            picker.querySelectorAll(".cal-nav").forEach(n => n.addEventListener("click", e => {
                e.stopPropagation();
                m += parseInt(n.dataset.d);
                if (m < 0) { m = 11; y--; }
                if (m > 11) { m = 0; y++; }
                render();
            }));

            picker.querySelectorAll(".cal-day:not(.other)").forEach(c => c.addEventListener("click", e => {
                e.stopPropagation();
                input.value = `${y}-${String(m + 1).padStart(2, '0')}-${String(c.dataset.d).padStart(2, '0')}`;
                picker.classList.remove("active");
                input.dispatchEvent(new Event("input"));
            }));
        };

        // Open on click — stopPropagation so document listener doesn't immediately close it
        input.addEventListener("click", e => {
            e.stopPropagation();
            if (!picker.classList.contains("active")) {
                picker.classList.add("active");
                render();
            }
        });

        // Close when clicking anywhere outside both the picker and the input
        document.addEventListener("click", e => {
            if (!picker.contains(e.target) && e.target !== input) {
                picker.classList.remove("active");
            }
        });
    };
    document.querySelectorAll(".cal-group").forEach(g => Cal(g.querySelector("input"), g.querySelector(".cal-picker")));

    // Keydown Shortcuts
    document.addEventListener("keydown", e => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            document.getElementById("query-input").focus();
        }
        if (e.key === 'Escape') {
            ov.style.display = "none";
            document.getElementById("ocr-panel").style.display = "none";
            const g = document.getElementById("grid");
            if (g && g.classList.contains("max")) document.getElementById("bk").click();
        }
        if (!e.ctrlKey && !e.metaKey && !e.altKey && document.activeElement.tagName !== 'INPUT') {
            const t = document.querySelectorAll(".nav-btn");
            if (e.key === '1') t[0]?.click();
            if (e.key === '2') t[1]?.click();
            if (e.key === '3') t[2]?.click();
            if (e.key === '4') t[3]?.click();
        }
    });
    if (window.lucide) lucide.createIcons();
});
