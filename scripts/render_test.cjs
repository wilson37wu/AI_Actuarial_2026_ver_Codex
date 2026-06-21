const fs=require('fs');const {JSDOM}=require('jsdom');
const html=fs.readFileSync(process.argv[2],'utf8');
let errs=[];
const dom=new JSDOM(html,{runScripts:"dangerously",beforeParse(w){w.onerror=(m)=>errs.push(String(m));}});
const w=dom.window; w.addEventListener('error',e=>errs.push(String(e.error||e.message)));
setTimeout(()=>{const doc=w.document;
  const gov=[...doc.querySelectorAll('.tab')].find(t=>t.textContent.trim()==='Governance');
  if(gov)gov.onclick();
  const v=doc.getElementById('view-gov'); const text=v?v.textContent:'';
  console.log("CHECKS",JSON.stringify({
    govTab:!!gov, gateTitle:text.includes('Deployment-gate checklist'),
    gatesRendered:v?v.querySelectorAll('.gate').length:0, clearedText:/12 \/ 12 cleared/.test(text),
    rrTable:!!doc.getElementById('rrTable'), statusFilter:!!doc.getElementById('rrStatus'),
    ratingFilter:!!doc.getElementById('rrRating'), riskRows:v?v.querySelectorAll('#rrTable tr.clk').length:0,
    timeline:!!(v&&v.querySelector('.timeline')), timelineItems:v?v.querySelectorAll('.tl').length:0,
    integrityOK:/integrity OK/.test(text), digestsVerified:/28\/28 digests verified/.test(text), mr011:text.includes('MR-011')}));
  const selR=doc.getElementById('rrRating'); selR.value='HIGH'; selR.onchange();
  console.log("rating=HIGH rows:",v.querySelectorAll('#rrTable tr.clk').length);
  const first=v.querySelector('#rrTable tr.clk'); if(first)first.onclick();
  const det=v.querySelector('tr.det'); console.log("detail visible:",det?det.style.display:'n/a');
  console.log("JS_ERRORS",errs.length,errs.slice(0,3)); process.exit(0);
},250);
