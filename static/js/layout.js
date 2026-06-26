function initLayout() {
    const g=document.getElementById("grid"),rp=document.getElementById("rp");
    const gd=document.getElementById("gd"),rs=document.getElementById("rs");
    const bk=document.getElementById("bk"),mt=document.getElementById("mt");
    const leftP=document.querySelector('.panel[data-panel="summary"]');
    const gC=document.querySelector('.panel[data-panel="timeline"]');
    const cC=document.querySelector('.panel[data-panel="citations"]');
    const cp=document.getElementById("conflicts-panel");
    const badge=document.getElementById("conflicts-badge");
    let showSum=true,showTim=true,showCit=true,hasConflicts=false,showConf=false;
    const cyR=()=>{if(window.cy)setTimeout(()=>{window.cy.resize();window.cy.fit()},50)};
    const u=()=>{
        leftP.style.display=showSum?"flex":"none";
        rp.style.display=(showTim||showCit||showConf)?"grid":"none";
        gC.style.display=showTim?"flex":"none";
        cC.style.display=showCit&&!showConf?"flex":"none";
        if(cp)cp.style.display=showConf&&hasConflicts?"flex":"none";
        if(badge)badge.style.display=hasConflicts&&!showConf?"inline":"none";
        gd.style.display=(showSum&&(showTim||showCit||showConf))?"flex":"none";
        rs.style.display=(showTim&&(showCit||showConf))?"flex":"none";
        g.style.gridTemplateColumns=(showSum&&(showTim||showCit||showConf))?"1.6fr auto 1fr":"1fr";
        rp.style.gridTemplateRows="1fr auto 1fr";
        document.querySelectorAll("#mt .ta").forEach(b=>{const p=b.dataset.panel;b.classList.toggle("active",p==="summary"?showSum:p==="timeline"?showTim:showCit&&!showConf)});
        setTimeout(cyR,50);
    };
    const maxG=(card)=>{
        g.classList.add("max");bk.classList.add("active");mt.style.display="flex";
        showSum=card===leftP;showTim=card===gC;showCit=card===cC;showConf=false;
        document.querySelectorAll(".mx").forEach(m=>m.textContent="✕");u();
    };
    const minG=()=>{
        g.classList.remove("max");bk.classList.remove("active");mt.style.display="none";
        showSum=true;showTim=true;showCit=true;showConf=false;
        document.querySelectorAll(".mx").forEach(m=>m.textContent="⛶");
        [leftP,rp,gC,cC,gd,rs].forEach(el=>{if(el)el.style.removeProperty("display")});
        g.style.gridTemplateColumns="";rp.style.gridTemplateRows="1fr auto 1fr";u();
    };
    window.toggleConflicts=()=>{showConf=!showConf;if(showConf)showCit=false;u()};
    if(badge)badge.addEventListener("click",()=>{showConf=!showConf;if(showConf)showCit=false;u()});
    const cc=document.getElementById("conflicts-close");
    if(cc)cc.addEventListener("click",()=>{showConf=false;u()});
    bk.addEventListener("click",minG);
    document.querySelectorAll(".mx").forEach(b=>b.addEventListener("click",e=>{
        e.stopPropagation();const card=b.closest(".panel");
        if(g.classList.contains("max")){
            if(card===leftP)showSum=false;else if(card===gC)showTim=false;else if(card===cC)showCit=false;
            (!showSum&&!showTim&&!showCit)?minG():u();
        }else maxG(card);
    }));
    document.querySelectorAll("#mt .ta").forEach(b=>b.addEventListener("click",()=>{
        if(!g.classList.contains("max"))return;
        const p=b.dataset.panel;
        if(p==="summary")showSum=!showSum;else if(p==="timeline")showTim=!showTim;
        else if(p==="citations"){showCit=!showCit;if(showCit)showConf=false}
        (!showSum&&!showTim&&!showCit)?minG():u();
    }));
    let drag=null;
    gd.addEventListener("mousedown",e=>{drag="g";e.preventDefault();document.body.style.cursor="col-resize";document.body.style.userSelect="none"});
    rs.addEventListener("mousedown",e=>{drag="r";e.preventDefault();document.body.style.cursor="row-resize";document.body.style.userSelect="none"});
    document.addEventListener("mousemove",e=>{
        if(!drag)return;const gr=g.getBoundingClientRect();
        if(drag==="g"){let lw=e.clientX-gr.left-3,rw=gr.right-e.clientX-3;lw=Math.max(200,Math.min(lw,gr.width-200));g.style.gridTemplateColumns=`${(lw/gr.width)*100}% auto ${(gr.width-lw-6)/gr.width*100}%`}
        else if(drag==="r"){const rr=rp.getBoundingClientRect();let th=e.clientY-rr.top-3,bh=rr.bottom-e.clientY-3;th=Math.max(100,Math.min(th,rr.height-100));rp.style.gridTemplateRows=`${(th/rr.height)*100}% auto ${(rr.height-th-6)/rr.height*100}%`}
        cyR();
    });
    document.addEventListener("mouseup",()=>{if(drag){drag=null;document.body.style.cursor="";document.body.style.userSelect="";cyR()}});
    rp.style.display="grid";rp.style.gridTemplateRows="1fr auto 1fr";
    window.setHasConflicts=(v)=>{hasConflicts=v;showConf=false;u()};
}
document.addEventListener("DOMContentLoaded",initLayout);
