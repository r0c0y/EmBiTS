document.addEventListener("DOMContentLoaded", () => {
    const us=document.getElementById("user-selector"), ud=document.getElementById("user-dept-display"), ov=document.getElementById("viewer-overlay");
    let sumMode='elaborate', parsedC='', parsedE='';
    document.querySelectorAll(".nav-btn").forEach(b=>b.addEventListener("click",()=>{
        document.querySelectorAll(".nav-btn,.tab-content").forEach(e=>e.classList.remove("active"));
        b.classList.add("active"); document.getElementById(b.dataset.tab).classList.add("active");
        document.getElementById("tab-title").textContent=b.textContent.replace(/[▲🔍📋🛡️]/g,"").trim();
        const subs={"search-tab":"Query SCL meeting records.","upload-tab":"Upload documents to the knowledge base.","registry-tab":"View all indexed documents.","audit-tab":"Security and compliance audit trail."};
        document.getElementById("tab-subtitle").textContent=subs[b.dataset.tab]||"";
        if(b.dataset.tab==="audit-tab") loadAudits();
    }));
    us.addEventListener("change",()=>ud.textContent="Dept: "+us.options[us.selectedIndex].dataset.dept);
    fetch("/api/projects").then(r=>r.json()).then(d=>{
        const ls=document.getElementById("upload-lot"), tb=document.querySelector("#registry-table tbody");
        ls.innerHTML=""; tb.innerHTML="";
        d.lots.forEach(l=>{ls.innerHTML+=`<option value="${l.id}">${l.name}</option>`;tb.innerHTML+=`<tr><td>SCL-555</td><td>${l.id}</td><td>${l.date}</td><td><span class="badge">Active</span></td></tr>`});
    });
    document.getElementById("search-form").addEventListener("submit",e=>{
        e.preventDefault(); const ai=document.getElementById("ai-answer"), cl=document.getElementById("citations-list");
        const q=document.getElementById("query-input").value; if(q.trim())saveHistory(q);
        ai.innerHTML='<div class="spinner"></div>'; cl.innerHTML='<p class="text-muted">Loading...</p>';
        const fd=new FormData(); fd.append("query",q);
        fd.append("department",document.getElementById("dept-filter").value);
        fd.append("user",us.value); fd.append("user_dept",us.options[us.selectedIndex].dataset.dept);
        fetch("/api/search",{method:"POST",body:fd}).then(r=>r.json()).then(d=>{
            window._lastCitations=d.citations||[]; const cm={};
            (d.citations||[]).forEach((c,i)=>cm[c.meeting_id]=i+1);
            const rpl=t=>t.replace(/\b(SCL-555-[A-Z0-9]+-[A-Z0-9]+)\b/g,m=>cm[m]?`<span class="cl" onclick="fetchDoc('${m}')" title="View: ${m}">[${cm[m]}]</span>`:m);
            const ex=(t)=>{const s=d.answer.indexOf(`<${t}>`);if(s<0)return null;
            const a=d.answer.slice(s+t.length+2);const e=a.indexOf(`</${t}>`);const n=a.search(/<(?:concise|elaborate)>/);
            const end=e>=0?e:n>=0?Math.min(e<0?1/0:e,n):a.length;return a.slice(0,end).trim()};
            const conc=ex('concise'), elab=ex('elaborate');
            try{parsedC=parseMD(rpl(conc||elab||d.answer));parsedE=parseMD(rpl(elab||d.answer))}catch(e){parsedC=parsedE=d.answer}
            const render=()=>{ai.innerHTML=`<div class="ai-text">${sumMode==='concise'?parsedC:parsedE}</div><button class="copy-btn" onclick="copyAI()">📋 Copy Response</button>`;renderKatex(ai);renderMermaid(ai);document.querySelectorAll("#summ-tg .tb-btn").forEach(b=>b.classList.toggle("active",b.dataset.mode===sumMode))};
            render(); document.getElementById("summ-tg").style.display=(conc&&elab)?"flex":"none";
            cl.innerHTML=d.citations.length?"":'<p class="text-muted">No matching citations.</p>';
            const q=document.getElementById("query-input").value;
            d.citations.forEach((c,i)=>{const ht=highlightKW(c.text,q);cl.innerHTML+=`<details class="disclosure"><summary><span class="cit-num">[${i+1}]</span> ${c.meeting_title}</summary><div><p><strong>Date:</strong>${c.date}|<strong>Dept:</strong>${c.department}</p><p style="margin-top:8px">${ht}</p><div style="margin-top:8px;display:flex;gap:6px"><button class="view-doc-btn" data-id="${c.meeting_id}" data-text="${c.text.replace(/"/g,'&quot;')}">View Doc</button><a href="/api/download/${c.meeting_id}" class="dl-btn">↓ Download</a></div></div></details>`});
            try{renderGraph(d.graph||{nodes:[],edges:[]})}catch(e){}
            try{renderDecisions((d.graph||{}).decisions||[])}catch(e){}
            const cp=document.getElementById("conflicts-panel"),cl2=document.getElementById("conflicts-list");
            const hasC=d.conflicts&&d.conflicts.length>0;
            if(hasC){cl2.innerHTML=d.conflicts.map(c=>`<div class="conflict-item"><h4>⚠ ${c.parameter}</h4>${c.values.map(v=>`<div class="val"><span class="doc-title">${v.title}</span><span class="doc-value">${v.value}</span></div>${v.snippet?`<div class="val-snippet">…${v.snippet}…</div>`:''}`).join("")}</div>`).join("");const bg=document.getElementById("conflicts-badge");if(bg)bg.textContent=`⚠ ${d.conflicts.length} Conflicts`}
            if(window.setHasConflicts)window.setHasConflicts(hasC);
            if(window.lucide) window.lucide.createIcons();
        });
    });
    document.getElementById("summ-tg").addEventListener("click",e=>{
        const b=e.target.closest(".tb-btn"); if(!b) return;
        sumMode=b.dataset.mode; const ai=document.getElementById("ai-answer");
        ai.innerHTML=`<div class="ai-text">${sumMode==='concise'?parsedC:parsedE}</div><button class="copy-btn" onclick="copyAI()">📋 Copy Response</button>`;renderKatex(ai);renderMermaid(ai);
        document.querySelectorAll("#summ-tg .tb-btn").forEach(b2=>b2.classList.toggle("active",b2.dataset.mode===sumMode));
    });
    const initTheme=()=>{
        const tb=document.getElementById("theme-btn"); if(!tb) return;
        const st=(dark)=>{document.documentElement.classList.toggle("light",!dark);tb.textContent=dark?'🌙':'☀️';localStorage.setItem('scl-theme',dark?'dark':'light')};
        if(localStorage.getItem('scl-theme')==='light') st(false);
        tb.addEventListener("click",()=>st(document.documentElement.classList.contains("light")));
    }; initTheme();
    let fileQueue=[];
    const rq=()=>{const q=document.getElementById("file-queue"),c=document.getElementById("queue-count");
    if(!fileQueue.length){q.innerHTML='<p class="text-muted" style="font-size:12px">No files selected</p>';c.textContent='';return}
    c.textContent=fileQueue.filter(f=>f.status!=='done').length+' pending';
    q.innerHTML=fileQueue.map((f,i)=>`<span class="file-item ${f.status}${f.fadeClass?' '+f.fadeClass:''}"><span class="file-icon">${f.status==='done'?'✓':f.status==='error'?'⚠':f.status==='uploading'?'⏳':'📄'}</span><span class="file-name">${f.file.name}</span>${f.status==='done'?'<span class="file-status">'+f.docId+'</span>':f.status==='pending'?'<span class="file-rm" data-idx="'+i+'">✕</span>':''}</span>`).join('')};
    const af=(files)=>{for(const f of files)fileQueue.push({file:f,status:'pending'});rq();document.getElementById("file-input").value=''};
    const dz=document.getElementById("drop-zone"),fi2=document.getElementById("file-input");
    dz.addEventListener("click",()=>fi2.click());dz.addEventListener("dragover",e=>{e.preventDefault();dz.classList.add("dragover")});
    dz.addEventListener("dragleave",()=>dz.classList.remove("dragover"));
    dz.addEventListener("drop",e=>{e.preventDefault();dz.classList.remove("dragover");af(e.dataTransfer.files)});
    fi2.addEventListener("change",()=>af(fi2.files));
    document.getElementById("file-queue").addEventListener("click",e=>{const rm=e.target.closest(".file-rm");if(rm){fileQueue.splice(parseInt(rm.dataset.idx),1);rq()}});
    document.getElementById("upload-form").addEventListener("submit",async e=>{
        e.preventDefault();const pending=fileQueue.filter(f=>f.status==='pending');if(!pending.length){alert("No files to upload. Drag & drop or browse to add files.");return}
        const lot=document.getElementById("upload-lot").value;
        for(const item of pending){item.status='uploading';rq();
        const fd=new FormData();fd.append("file",item.file);fd.append("lot_id",lot);
        fd.append("user",us.value);fd.append("user_dept",us.options[us.selectedIndex].dataset.dept);
        try{const r=await fetch("/api/upload",{method:"POST",body:fd});const d=await r.json();
        item.status=d.status==="success"?"done":"error";item.docId=d.document_id||""}catch(err){item.status="error"}
        rq();
        if(item.status==="done"){setTimeout(()=>{item.fadeClass="fade-out";rq();
        setTimeout(()=>{const idx=fileQueue.indexOf(item);if(idx>-1)fileQueue.splice(idx,1);rq()},300)},1414)}}});
    document.getElementById("citations-list").addEventListener("click",e=>{const btn=e.target.closest(".view-doc-btn");if(btn) openViewer(btn.dataset.id,btn.dataset.text)});
    document.getElementById("viewer-close").addEventListener("click",()=>ov.style.display="none");
    document.getElementById("viewer-download").addEventListener("click",()=>{if(window._currentDocId)window.open("/api/download/"+window._currentDocId)});
    ov.addEventListener("click",e=>{if(e.target===ov)ov.style.display="none"});
    const vb=document.getElementById("btn-verify-ledger"); if(vb) vb.addEventListener("click",()=>verifyLedger(vb));
    if(window.lucide) window.lucide.createIcons();
    if(window.mermaid) mermaid.initialize({startOnLoad:false,theme:'default',securityLevel:'loose'});
    renderHistory(); initCitePreview();
    document.addEventListener("keydown",e=>{
        if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();document.getElementById("query-input").focus()}
        if(e.key==='Escape'){ov.style.display="none";const g=document.getElementById("grid");if(g.classList.contains("max"))document.getElementById("bk").click()}
        if(!e.ctrlKey&&!e.metaKey&&!e.altKey&&document.activeElement.tagName!=='INPUT'){const t=document.querySelectorAll(".nav-btn");
        if(e.key==='1')t[0]?.click();if(e.key==='2')t[1]?.click();if(e.key==='3')t[2]?.click();if(e.key==='4')t[3]?.click()}
    });
});
