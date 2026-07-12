const renderBarChart=(title,body)=>{
    const rows=body.trim().split('\n').map(l=>{const m=l.match(/^(.+?)\s*[:=\-]\s*(\d+\.?\d*)/);return m?{label:m[1].trim(),value:parseFloat(m[2])}:null}).filter(Boolean);
    if(!rows.length)return'';const w=440,h=rows.length*32+44,mx=Math.max(...rows.map(r=>r.value));
    const bars=rows.map((r,i)=>{const y=i*32+36,bw=Math.max(8,(r.value/mx)*(w-160));
        return`<text x="8" y="${y+14}" fill="currentColor" font-size="11" font-family="Outfit,sans-serif" opacity=".6">${r.label}</text><rect x="140" y="${y}" width="${bw}" height="22" rx="4" fill="#38bdf8"/><text x="${148+bw}" y="${y+15}" fill="currentColor" font-size="11" font-family="Outfit,sans-serif" font-weight="600">${r.value}</text>`}).join('');
    return`<div class="chart-wrap"><svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">${title?`<text x="8" y="20" fill="currentColor" font-size="13" font-weight="600" font-family="Outfit,sans-serif">${title}</text>`:''}${bars}</svg></div>`};
const parseMD=(t)=>{try{t=t.replace(/```svg\n([\s\S]*?)\n```/g,(_,s)=>s);t=t.replace(/\[CHART:([^\]]*)\]([\s\S]*?)\[\/CHART\]/g,(_,title,body)=>renderBarChart(title,body));t=t.replace(/\$\$([\s\S]*?)\$\$/g,'<div class="math">$1</div>');t=t.replace(/\$([^\n$]+)\$/g,'<span class="math">$1</span>');t=t.replace(/```mermaid[^\n]*\n([\s\S]*?)\n```/g,'<pre class="mermaid">$1</pre>');return marked.parse(t)}catch(e){return t||''}};
const renderKatex=(el)=>el.querySelectorAll('.math').forEach(m=>{try{katex.render(m.textContent,m,{throwOnError:false,displayMode:m.tagName==='DIV'})}catch(e){}});
const renderMermaid=(el)=>{try{mermaid.run({nodes:el.querySelectorAll('.mermaid')})}catch(e){}};
const highlightKW=(text,query)=>{const t=query.toLowerCase().split(/\s+/).filter(t=>t.length>2);if(!t.length)return text;const e=t.map(t=>t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));return text.replace(new RegExp('('+e.join('|')+')','gi'),'<mark class="kw">$1</mark>')};
const loadAudits=()=>{
    fetch("/api/audit_logs").then(r=>r.json()).then(d=>{
        window._allAudits = d.logs || [];
        renderAudits(window._allAudits);
    });
};
const renderAudits=(logs)=>{
    const tb=document.querySelector("#audit-table tbody");
    if (!tb) return;
    tb.innerHTML=logs.length?"":"<tr><td colspan='4' class='text-muted'>No audits found.</td></tr>";
    logs.forEach(l=>{
        tb.innerHTML+=`<tr>
            <td>${new Date(l.timestamp).toLocaleString()}</td>
            <td>${l.username}</td>
            <td><span class="badge">${l.action_type}</span></td>
            <td>${l.details}</td>
        </tr>`;
    });
};
const openViewer=(id,searchText)=>{
    const show=(d)=>{
        window._currentDocId=d.id;
        window._currentDoc = d;
        window._currentDocSearchText = searchText;
        window._viewerMode = 'original';
        window._viewerCurrentPage = 0;
        window._currentDocPages = [];
        
        document.getElementById("viewer-title").innerText=`[${d.id}] ${d.title}`;
        document.getElementById("viewer-snippet-text").innerHTML=highlightKW(parseMD(searchText || ""), window._currentDocSearchText || "");
        document.getElementById("viewer-meta-dept").innerText="Project: "+(d.project_id||"Unknown");
        document.getElementById("viewer-meta-date").innerText="Date: "+d.date;
        
        const ocrBtn = document.getElementById("viewer-ocr");
        if (ocrBtn) ocrBtn.innerText = "👁 OCR";
        
        renderViewerContent();
        document.getElementById("viewer-overlay").style.display="flex";
        
        fetch(`/api/ocr/${d.id}`).then(r=>r.json()).then(res=>{
            if(res && res.pages) {
                window._currentDocPages = res.pages;
                if (window._viewerMode === 'ocr') {
                    renderViewerContent();
                }
            }
        }).catch(()=>{});
    };
    fetch("/api/document/"+id).then(r=>r.json()).then(show).catch(()=>{})
};

window.zoomImg = (delta) => {
    if (window._imgZoom === undefined) window._imgZoom = 1.0;
    if (delta === 0) {
        window._imgZoom = 1.0;
    } else {
        window._imgZoom = Math.max(0.2, Math.min(4.0, window._imgZoom + delta));
    }
    const img = document.getElementById("viewer-img");
    if (img) {
        img.style.transform = `scale(${window._imgZoom})`;
    }
};

window.prevOCRPage = () => {
    if (window._viewerCurrentPage > 0) {
        window._viewerCurrentPage--;
        renderViewerContent();
    }
};

window.nextOCRPage = () => {
    const pages = window._currentDocPages || [];
    if (window._viewerCurrentPage < pages.length - 1) {
        window._viewerCurrentPage++;
        renderViewerContent();
    }
};

const renderViewerContent = () => {
    const d = window._currentDoc;
    if (!d) return;
    const contentContainer = document.getElementById("viewer-full-text");
    if (!contentContainer) return;
    
    const fileExt = (d.source_type || d.file_path || d.title || "").split('.').pop().toLowerCase();
    const escapeHTML = (str) => (str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    
    if (window._viewerMode === 'ocr') {
        const pages = window._currentDocPages || [];
        const hasPages = pages.length > 0;
        
        let currentText = d.transcript_text || "";
        let paginatorHTML = '';
        
        if (hasPages) {
            const pageIndex = Math.min(window._viewerCurrentPage, pages.length - 1);
            const page = pages[pageIndex];
            if (page) {
                currentText = page.markdown || page.text || "";
            }
            if (pages.length > 1) {
                paginatorHTML = `
                    <div class="ocr-paginator" style="display:flex; align-items:center; justify-content:center; gap:16px; padding:10px; background:var(--bg); border:1px solid var(--border); border-radius:6px; margin-top:8px; width: 100%; box-sizing: border-box; flex-shrink: 0;">
                        <button class="view-doc-btn" style="padding:4px 10px; font-size:12px; margin:0;" onclick="window.prevOCRPage()">◀ Prev</button>
                        <span style="font-size:13px; font-weight:600; color:var(--text);" id="ocr-page-info">${pageIndex + 1} / ${pages.length}</span>
                        <button class="view-doc-btn" style="padding:4px 10px; font-size:12px; margin:0;" onclick="window.nextOCRPage()">Next ▶</button>
                    </div>
                `;
            }
        }
        
        contentContainer.innerHTML = `
            <div style="display: flex; flex-direction: column; overflow: hidden; height: 100%; width: 100%; box-sizing: border-box;">
                <div style="flex: 1; overflow-y: auto; padding: 20px; box-sizing: border-box; background: #0c101d;">
                    <!-- A4 Premium Paper Layout Container -->
                    <div class="ocr-paper-page" style="
                        background: #ffffff;
                        color: #1f2937;
                        border: 1px solid #e5e7eb;
                        border-radius: 8px;
                        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
                        max-width: 800px;
                        margin: 10px auto;
                        padding: 40px 50px;
                        box-sizing: border-box;
                        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        font-size: 15px;
                        line-height: 1.7;
                        text-align: left;
                    ">
                        <!-- Custom CSS overrides specifically for paper layout content -->
                        <style>
                            .ocr-paper-page h1, .ocr-paper-page h2, .ocr-paper-page h3, .ocr-paper-page h4 {
                                color: #111827 !important;
                                font-weight: 700;
                                margin-top: 24px;
                                margin-bottom: 12px;
                                border-bottom: 1px solid #e5e7eb;
                                padding-bottom: 6px;
                            }
                            .ocr-paper-page h1 { font-size: 24px; }
                            .ocr-paper-page h2 { font-size: 20px; }
                            .ocr-paper-page h3 { font-size: 16px; }
                            .ocr-paper-page p {
                                margin-bottom: 16px;
                                color: #374151 !important;
                            }
                            .ocr-paper-page ul, .ocr-paper-page ol {
                                margin-bottom: 16px;
                                padding-left: 24px;
                                color: #374151 !important;
                            }
                            .ocr-paper-page li {
                                margin-bottom: 6px;
                            }
                            .ocr-paper-page table {
                                width: 100% !important;
                                border-collapse: collapse !important;
                                margin: 20px 0 !important;
                                font-size: 13px !important;
                                background: #f9fafb !important;
                                border: 1px solid #d1d5db !important;
                            }
                            .ocr-paper-page th, .ocr-paper-page td {
                                padding: 10px 14px !important;
                                border: 1px solid #d1d5db !important;
                                color: #1f2937 !important;
                            }
                            .ocr-paper-page th {
                                background: #f3f4f6 !important;
                                font-weight: 600 !important;
                                color: #111827 !important;
                            }
                            .ocr-paper-page pre {
                                background: #f3f4f6 !important;
                                border: 1px solid #e5e7eb !important;
                                padding: 14px !important;
                                border-radius: 6px !important;
                                overflow-x: auto !important;
                                color: #1f2937 !important;
                            }
                            .ocr-paper-page code {
                                font-family: monospace !important;
                                font-size: 13px !important;
                                color: #d97706 !important;
                                background: #f3f4f6 !important;
                                padding: 2px 4px !important;
                                border-radius: 4px !important;
                            }
                            .ocr-paper-page blockquote {
                                border-left: 4px solid #3b82f6 !important;
                                padding-left: 16px !important;
                                margin: 16px 0 !important;
                                color: #4b5563 !important;
                                font-style: italic !important;
                            }
                            /* Keep highlighted keyword readable on white paper */
                            .ocr-paper-page .match {
                                background: #fef08a !important;
                                color: #000000 !important;
                                border-radius: 2px !important;
                                padding: 0 2px !important;
                            }
                        </style>
                        ${highlightKW(parseMD(currentText), window._currentDocSearchText || "")}
                    </div>
                </div>
                ${paginatorHTML}
            </div>
        `;
        renderKatex(contentContainer);
        renderMermaid(contentContainer);
    } else {
        if (fileExt === 'pdf' || fileExt === 'docx' || fileExt === 'txt') {
            contentContainer.innerHTML = `<iframe src="/api/preview/${d.id}" style="width:100%; height:100%; border:none; border-radius:6px; background:#fff;"></iframe>`;
        } else if (['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'].includes(fileExt)) {
            contentContainer.innerHTML = `
                <div id="viewer-img-wrapper" style="width:100%; height:100%; overflow:hidden; border:1px solid var(--border); border-radius:8px; background:#111; cursor:zoom-in; position:relative; user-select:none;">
                    <div style="position:absolute;top:10px;right:10px;z-index:10;background:rgba(0,0,0,.55);color:#fff;font-size:10px;padding:3px 8px;border-radius:4px;pointer-events:none;opacity:.8;">Click to zoom · Move to pan</div>
                    <img id="viewer-img" src="/api/preview/${d.id}"
                         style="width:100%; height:100%; object-fit:contain; transform:scale(1); transform-origin:50% 50%; transition:transform .25s cubic-bezier(.4,0,.2,1), transform-origin 0s;" />
                </div>
            `;
            setTimeout(() => {
                const wrap = document.getElementById("viewer-img-wrapper");
                const img  = document.getElementById("viewer-img");
                if (!wrap || !img) return;
                let zoomed = false;
                const SCALE = 3;

                wrap.addEventListener("click", () => {
                    zoomed = !zoomed;
                    img.style.transform  = zoomed ? `scale(${SCALE})` : "scale(1)";
                    wrap.style.cursor    = zoomed ? "zoom-out" : "zoom-in";
                });

                wrap.addEventListener("mousemove", e => {
                    if (!zoomed) return;
                    const r = wrap.getBoundingClientRect();
                    const ox = ((e.clientX - r.left) / r.width  * 100).toFixed(2);
                    const oy = ((e.clientY - r.top)  / r.height * 100).toFixed(2);
                    img.style.transformOrigin = `${ox}% ${oy}%`;
                });

                wrap.addEventListener("mouseleave", () => {
                    if (zoomed) { img.style.transformOrigin = "50% 50%"; }
                });
            }, 50);
        } else if (['txt', 'csv', 'md', 'json', 'xml'].includes(fileExt)) {
            contentContainer.innerHTML = `<pre style="white-space:pre-wrap; font-family:monospace; background:var(--bg); border:1px solid var(--border); padding:16px; border-radius:6px; height:100%; overflow-y:auto; margin:0;"><code>${highlightKW(escapeHTML(d.transcript_text), window._currentDocSearchText || "")}</code></pre>`;
        } else {
            contentContainer.innerHTML = `
                <div style="background:var(--bg); border:1px solid var(--border); border-radius:8px; padding:16px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between; gap:12px;">
                    <div style="display:flex; align-items:center; gap:12px;">
                        <span style="font-size:32px;">📄</span>
                        <div>
                            <strong style="display:block; font-size:14px; color:var(--text); word-break:break-all;">${d.file_path || d.title}</strong>
                            <span style="font-size:11px; color:var(--text-muted); display:block; margin-top:2px;">Format: ${fileExt.toUpperCase()} (${d.file_size_bytes?`${(d.file_size_bytes/1024).toFixed(1)} KB`:'—'})</span>
                        </div>
                    </div>
                    <button class="view-doc-btn" style="padding:8px 16px; font-size:12px; margin:0;" onclick="window.open('/api/download/${d.id}')">Download Original</button>
                </div>
                <div style="font-size:13px; line-height:1.6; height:360px; overflow-y:auto; background:var(--bg); border:1px solid var(--border); padding:16px; border-radius:6px;">
                    <h4 style="margin-bottom:8px; font-size:12px; color:var(--text-muted); text-transform:uppercase;">Extracted Text Transcript:</h4>
                    <p style="white-space:pre-wrap; margin:0; font-family:monospace; color:var(--text);">${d.transcript_text || ''}</p>
                </div>
            `;
        }
    }
};
const renderDecisions=(decisions)=>{const c=document.getElementById("decisions-list");if(!c)return;if(!decisions||!decisions.length){c.innerHTML='';return}c.innerHTML=decisions.map(d=>`<div class="decision-item ${d.status.toLowerCase()}"><span class="dec-status">${d.status==='Approved'?'✓':d.status==='Failed'?'✗':'⚠'}</span><div class="dec-body"><span class="dec-title">${d.summary}</span><span class="dec-meta">${d.type} · ${d.meeting_title}</span></div></div>`).join('')};
window.copyAI=()=>{const el=document.querySelector("#ai-answer .ai-text");if(!el)return;navigator.clipboard.writeText(el.innerText).then(()=>{const b=document.querySelector(".copy-btn");if(b){b.textContent="✓ Copied!";setTimeout(()=>b.textContent="📋 Copy Response",1500)}}).catch(()=>{})};
const getHistoryKey=()=>{
    try {
        const auth = JSON.parse(localStorage.getItem("scl_auth"));
        if (auth && auth.email) return `scl-history-${auth.email}`;
    } catch(e) {}
    return 'scl-history-anonymous';
};
window.loadHistory=()=>{try{return JSON.parse(localStorage.getItem(getHistoryKey()))||[]}catch(e){return[]}};
window.saveHistory=(q)=>{const h=loadHistory().filter(x=>x!==q);h.unshift(q);localStorage.setItem(getHistoryKey(),JSON.stringify(h.slice(0,5)));renderHistory()};
window.renderHistory=()=>{const c=document.getElementById("history-chips");if(!c)return;const h=loadHistory();c.innerHTML=h.map(q=>`<button class="history-chip" onclick="runSearch('${q.replace(/'/g,"\\'")}')">${q}</button>`).join("")};
window.runSearch=(q)=>{document.getElementById("query-input").value=q;document.getElementById("search-form").requestSubmit()};
window.initCitePreview=()=>{const tip=document.getElementById("cit-tooltip");if(!tip)return;
document.addEventListener("mouseover",e=>{const cl=e.target.closest(".cl");if(!cl||!window._lastCitations)return;const i=parseInt(cl.textContent.match(/\d+/))-1;const c=window._lastCitations[i];if(!c)return;
const cleanText = c.text.replace(/\\n/g, ' ').replace(/\\r/g, ' ').replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
const previewSnippet = cleanText.length > 160 ? cleanText.substring(0, 160) + '...' : cleanText;
tip.innerHTML=`<strong>${c.meeting_title}</strong><span>${previewSnippet}</span>`;tip.style.display="flex";const r=cl.getBoundingClientRect();tip.style.left=r.left+"px";tip.style.top=(r.bottom+8)+"px"});
document.addEventListener("mouseout",e=>{if(e.target.closest(".cl"))tip.style.display="none"})};
