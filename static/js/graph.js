function renderGraph(graph) {
    const container = document.getElementById("cy-container");
    if (!container) return;
    container.innerHTML = "";
    const nodes = graph.nodes || [], edges = graph.edges || [];
    if (!nodes.length) {
        container.innerHTML = '<p class="text-muted" style="padding:1rem;text-align:center">No decision trail available.</p>';
        return;
    }
    const cy = cytoscape({
        container, elements: [
            ...nodes.map(n => ({
                group:'nodes', data:{id:n.id,label:(n.title||'').length>18?n.title.substr(0,16)+'…':n.title,dept:n.department||'',highlight:n.highlight||false}
            })),
            ...edges.map(e => ({
                group:'edges', data:{id:e.source+'-'+e.target,source:e.source,target:e.target,type:e.type||'',rationale:e.rationale||''}
            }))
        ],
        style: [
            {selector:'node', style:{'shape':'round-rectangle','width':140,'height':50,'background-color':'#0a0a0a','border-width':2,'border-color':'#333','content':'data(label)','text-valign':'center','text-halign':'center','color':'#fff','font-family':"'Outfit',sans-serif",'font-size':'10px','font-weight':'bold','text-wrap':'wrap','text-max-width':120,'transition-property':'opacity','transition-duration':'0.2s'}},
            {selector:'node[?highlight]', style:{'border-width':3,'border-color':'#00e5ff'}},
            {selector:'node[dept*="Design"]', style:{'border-color':'#38bdf8'}},
            {selector:'node[dept*="Fab"]', style:{'border-color':'#10b981'}},
            {selector:'node[dept*="Pack"]', style:{'border-color':'#c084fc'}},
            {selector:'node[dept*="Quality"]', style:{'border-color':'#f59e0b'}},
            {selector:'edge', style:{'width':2,'line-color':'#555','target-arrow-color':'#555','target-arrow-shape':'triangle','curve-style':'bezier','transition-property':'opacity','transition-duration':'0.2s'}},
            {selector:'edge[type="triggered_by"]', style:{'line-color':'#f43f5e','line-style':'dashed','target-arrow-color':'#f43f5e'}},
            {selector:'.faded', style:{'opacity':0.15}},
            {selector:'.highlighted', style:{'border-width':3,'border-color':'#00e5ff'}}
        ],
        layout:{name:'cose', animate:false, fit:true, padding:30},
        zoomingEnabled:true, userZoomingEnabled:true, panningEnabled:true, userPanningEnabled:true
    });
    cy.on('mouseover','node', function(evt) {
        const n=evt.target; cy.elements().addClass('faded'); n.removeClass('faded');
        n.connectedEdges().forEach(e => { e.removeClass('faded'); e.connectedNodes().forEach(n2 => { if(n2.id()!==n.id()) n2.removeClass('faded'); }); });
    });
    cy.on('mouseout','node', function() { cy.elements().removeClass('faded'); });
    cy.on('tap','node', function(evt) {
        const n=evt.target, id=n.id(); cy.nodes().removeClass('highlighted'); n.addClass('highlighted');
        const matched=(window._lastCitations||[]).find(c=>c.meeting_id===id);
        matched?openViewer(matched.meeting_id,matched.text):fetchDoc(id);
        const idx=(window._lastCitations||[]).findIndex(c=>c.meeting_id===id);
        if(idx>=0){const el=document.querySelectorAll('.disclosure')[idx];if(el){el.open=true;el.scrollIntoView({behavior:'smooth',block:'center'})}}
    });
    cy.on('tap', function(evt) { if(evt.target===cy) cy.nodes().removeClass('highlighted'); });
    cy.on('mouseover','edge', function(evt) { const r=evt.target.data('rationale'); if(r) container.title='Rationale: '+r; });
    cy.on('mouseout','edge', function() { container.title=''; });
    window.cy = cy;
}

function fetchDoc(id) {
    fetch('/api/document/'+id).then(r=>r.json()).then(d=>{openViewer(d.id,d.transcript_text||'');}).catch(()=>{});
}
