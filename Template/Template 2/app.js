const state={headers:{},user:null,allowedTabs:[],refs:{users:[],items:[],vendors:[],customers:[],warehouses:[],uoms:[],taxes:[],machines:[],requisitions:[],purchaseOrders:[],grns:[],salesOrders:[],challans:[],employees:[],leaveRequests:[],payrollRuns:[]}};
const ID_PREFIX={users:"UID",vendors:"VID",customers:"CID",warehouses:"WID",items:"IID",machines:"MID",employees:"EID"};

const $=id=>document.getElementById(id);
const esc=v=>String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\"/g,"&quot;");
const fmt=(t,id)=>`${ID_PREFIX[t]||"ID"}-${String(id).padStart(4,"0")}`;
const ref=(t,id)=>{const r=(state.refs[t]||[]).find(x=>String(x.id)===String(id));if(!r)return `#${id}`;if(t==="items")return `${fmt("items",r.id)} | ${r.sku} | ${r.name}`;if(t==="machines")return `${fmt("machines",r.id)} - ${r.name}`;if(t==="users")return `${fmt("users",r.id)} - ${r.name}`;if(t==="vendors")return `${fmt("vendors",r.id)} - ${r.name}`;if(t==="customers")return `${fmt("customers",r.id)} - ${r.name}`;if(t==="warehouses")return `${fmt("warehouses",r.id)} - ${r.name}`;if(t==="employees")return `${fmt("employees",r.id)} - ${r.name}`;return r.name||r.code||r.id};
const taxRate=key=>((state.refs.taxes.find(x=>String(x.id)===String(key)||String(x.code)===String(key))||{}).rate||"0");
const itemLabel=i=>`${fmt("items",i.id)} | ${i.sku} | ${i.name} | ${i.category}`;
const SEARCH_SYNONYMS={pr:["purchase requisition","requisition"],requisition:["pr","purchase request"],po:["purchase order"],so:["sales order"],grn:["goods receipt note","goods receipt"],vendor:["supplier","seller"],supplier:["vendor"],customer:["client","buyer"],employee:["staff","worker"],warehouse:["godown","store"],item:["product","material","sku","code"],material:["item","product"],sku:["item","code"],qty:["quantity","amount"],quantity:["qty"],gst:["tax","hsn"],hsn:["tax","gst"],vehicle:["truck","transport"],location:["site","plant"]};
function normalizeSearchText(text){return String(text||"").toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g,"").replace(/[^a-z0-9]+/g," ").trim()}
function tokenizedSearchTerms(text){return normalizeSearchText(text).split(/\s+/).filter(Boolean)}
function expandSearchTerms(tokens){const out=new Set();(tokens||[]).forEach(token=>{if(!token)return;out.add(token);(SEARCH_SYNONYMS[token]||[]).forEach(alias=>tokenizedSearchTerms(alias).forEach(term=>out.add(term)))});return [...out]}
function acronymForText(text){return tokenizedSearchTerms(text).map(part=>part[0]).join("")}
function searchRowMeta(row){if(row._searchMeta)return row._searchMeta;const source=[row.label,row.value,...(row.keywords||[])].filter(Boolean).join(" ");const normalized=normalizeSearchText(source);row._searchMeta={normalized,tokens:tokenizedSearchTerms(normalized),acronym:acronymForText(source),value:normalizeSearchText(row.value),index:Number.isFinite(Number(row.index))?Number(row.index):0};return row._searchMeta}
function scoreSearchRow(query,row){const q=normalizeSearchText(query);if(!q)return 1;const meta=searchRowMeta(row);let score=0;if(meta.value===q||meta.normalized===q)score+=1200;if(meta.value.startsWith(q)||meta.normalized.startsWith(q))score+=720;if(meta.acronym===q)score+=640;else if(meta.acronym.startsWith(q))score+=420;if(meta.normalized.includes(q))score+=320;const terms=expandSearchTerms(tokenizedSearchTerms(q));let matched=0;terms.forEach(term=>{if(!term)return;if(meta.tokens.includes(term)){score+=96;matched+=1;return;}if(meta.tokens.some(token=>token.startsWith(term))){score+=56;matched+=1;return;}if(meta.normalized.includes(term)){score+=24;matched+=1;}});if(matched&&matched===terms.length)score+=180;const compactQ=q.replace(/\s+/g,"");const compactText=meta.normalized.replace(/\s+/g,"");if(!score&&compactQ.length>=3&&compactText.includes(compactQ))score+=90;return score}
function rankSearchRows(query,rows,limit=12){const source=Array.isArray(rows)?rows:[];if(!source.length)return[];if(!normalizeSearchText(query))return source.slice(0,limit);return source.map(row=>({row,score:scoreSearchRow(query,row)})).filter(x=>x.score>0).sort((a,b)=>b.score-a.score||searchRowMeta(a.row).index-searchRowMeta(b.row).index).slice(0,limit).map(x=>x.row)}
function itemSearchRows(items=state.refs.items){return (items||[]).map((item,index)=>({label:itemLabel(item),value:String(item.id),keywords:[fmt("items",item.id),item.sku,item.name,item.category,ref("uoms",item.uomId),item.category==="RAW"?"raw material":"",item.category==="CONSUMABLE"?"consumable supply":"",item.category==="FG"?"finished goods":"",item.category==="WIP"?"work in progress":""],index}))}
const itemId=v=>{const s=String(v||"").trim();if(!s)return"";const h=s.split("|")[0].trim();if(/^IID-\d{4}$/i.test(h))return String(Number(h.split("-")[1]));if(/^\d+$/.test(h))return h;const r=rankSearchRows(s,itemSearchRows(),1)[0];return r?String(r.value||""):""};
const itemCodeName=id=>{const it=(state.refs.items||[]).find(x=>String(x.id)===String(id));if(!it)return `#${id}`;return `${fmt("items",it.id)} | ${it.sku} | ${it.name}`};
const linesSummary=(lines,qtyKey,rateKey)=>{const src=Array.isArray(lines)?lines:[];if(!src.length)return "-";return src.map(l=>`${itemCodeName(l.itemId)} (Qty: ${l[qtyKey]??0}${rateKey?`, Rate: ${l[rateKey]??0}`:""})`).join(" | ")};
const totalQty=(lines,qtyKey)=>{const src=Array.isArray(lines)?lines:[];return src.reduce((s,l)=>s+Number(l[qtyKey]||0),0).toFixed(2)};
const itemMeta=id=>{const it=(state.refs.items||[]).find(x=>String(x.id)===String(id));return{itemCode:it?fmt("items",it.id):`#${id}`,sku:it?.sku||"-",itemName:it?.name||"-"}};
const VIEW_ICON='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8"></circle></svg>';
const CSV_ICON='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zm0 0v5h5M8 14h8M8 10h3M8 18h8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"></path></svg>';
const PDF_ICON='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm7 0v5h5M8.5 15h2a1.5 1.5 0 0 0 0-3h-2zm0 0v3m5-3h2m-2 1.5h1.5m-1.5 1.5h2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"></path></svg>';
const rowActionButton=(label,action,icon)=>`<button type="button" class="ghost-button icon-action-button row-icon-action" data-row-action="${action}" aria-label="${esc(label)}" title="${esc(label)}">${icon}</button>`;
const enhanceTables=()=>window.printCoEnhanceTables?.();

function toast(m,e=false){const el=$("toast");el.textContent=m;el.style.background=e?"#7f1d1d":"#0f172a";el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2200)}
function table(rows,cols){if(!Array.isArray(rows)||!rows.length)return `<div class="table-empty">No records found.</div>`;const h=cols.map(c=>`<th>${esc(c.label)}</th>`).join("")+'<th class="row-actions-head" data-export-ignore="true">Actions</th>';const b=rows.map((r,i)=>{const cells=cols.map(c=>esc((c.format?c.format(r[c.key],r):r[c.key])??"-"));const primary=cells.find(v=>v&&v!=="-")||`Row ${i+1}`;const actions=`<td class="row-actions-cell" data-export-ignore="true"><div class="action-row table-action-row row-table-action-row">${rowActionButton(`${primary} view details`,"view",VIEW_ICON)}${rowActionButton(`${primary} export csv`,"csv",CSV_ICON)}${rowActionButton(`${primary} export pdf`,"pdf",PDF_ICON)}</div></td>`;return `<tr>${cells.map(v=>`<td>${v}</td>`).join("")}${actions}</tr>`}).join("");return `<table class="data-table"><thead><tr>${h}</tr></thead><tbody>${b}</tbody></table>`}
function render(id,rows,cols){if($(id)){$(id).innerHTML=table(rows,cols);enhanceTables()}}

async function api(path,opt={}){const res=await fetch(path,{headers:{"Content-Type":"application/json",...state.headers,...(opt.headers||{})},...opt});const t=await res.text();const d=t?JSON.parse(t):{};if(!res.ok)throw new Error(d.error||"Request failed");return d}
const form=o=>Object.fromEntries(new FormData(o).entries());
function syncAuthCache(){try{if(state.headers&&state.headers["x-user-id"]){sessionStorage.setItem("erpAuthHeaders",JSON.stringify(state.headers));sessionStorage.setItem("erpUser",JSON.stringify(state.user||{}));}else{sessionStorage.removeItem("erpAuthHeaders");sessionStorage.removeItem("erpUser");}}catch{}}

function setSession(u,h){state.user=u;state.headers=h;$("sessionUser").textContent=`${u.name||"Not logged in"}`;closeProfileMenu();syncAuthCache()}
function setAppShellVisible(isVisible){if($("appShell"))$("appShell").style.display=isVisible?"flex":"none";if($("loginPage"))$("loginPage").style.display=isVisible?"none":"block"}
function isRequisitionOnlyRole(role){return ["store","sales","production","logistics","accounts"].includes(String(role||"").toLowerCase())}
function isPrivilegedHrRole(role){return ["admin","hr"].includes(String(role||"").toLowerCase())}
function tabsForRole(role){
 const r=String(role||"").toLowerCase();
 const all=["dashboard","procurement","inventory","sales","production","logistics","accounts","hrmPayroll"];
 if(r==="admin")return all;
 const map={
  purchase:["dashboard","procurement","hrmPayroll"],
  store:["dashboard","inventory","procurement","hrmPayroll"],
  sales:["dashboard","sales","procurement","hrmPayroll"],
  production:["dashboard","production","procurement","hrmPayroll"],
  logistics:["dashboard","logistics","procurement","hrmPayroll"],
  accounts:["dashboard","accounts","procurement","hrmPayroll"],
  hr:["dashboard","hrmPayroll"]
 };
 return map[r]||["dashboard"];
}
function applyProcurementRoleUi(role){
 const limited=isRequisitionOnlyRole(role);
 const show=(id,visible)=>{const el=$(id);const host=el?(el.closest(".card")||el):null;if(host)host.style.display=visible?"":"none"};
 if(!limited){
  ["vendorForm","poForm","approvePoForm","grnForm","loadVendors","loadPurchaseOrders","loadGrns","loadQualityChecks","loadReorders","vendorList","purchaseOrderList","grnList","qualityList","reorderList","loadRequisitions","requisitionList"].forEach(id=>show(id,true));
  return;
 }
 ["vendorForm","poForm","approvePoForm","grnForm","loadVendors","loadPurchaseOrders","loadGrns","loadQualityChecks","loadReorders","vendorList","purchaseOrderList","grnList","qualityList","reorderList","loadRequisitions","requisitionList"].forEach(id=>show(id,false));
}
function applyHrmRoleUi(role){
 const privileged=isPrivilegedHrRole(role);
 const show=(id,visible)=>{const el=$(id);const host=el?(el.closest(".card")||el):null;if(host)host.style.display=visible?"":"none"};
 if(privileged){
  ["employeeForm","attendanceForm","leaveForm","leaveApproveForm","payrollForm","loadEmployees","employeeList","loadAttendance","attendanceList","loadLeaveRequests","leaveList","loadPayrollRuns","payrollList"].forEach(id=>show(id,true));
  return;
 }
 ["employeeForm","attendanceForm","leaveApproveForm","payrollForm","loadEmployees","employeeList","loadAttendance","attendanceList"].forEach(id=>show(id,false));
 ["leaveForm","loadLeaveRequests","leaveList","loadPayrollRuns","payrollList"].forEach(id=>show(id,true));
}
function applyRoleAccess(role){
 state.allowedTabs=tabsForRole(role);
 document.querySelectorAll(".nav-btn").forEach(btn=>{
  const allowed=state.allowedTabs.includes(btn.dataset.target);
  btn.style.display=allowed?"":"none";
  btn.disabled=!allowed;
 });
 document.querySelectorAll(".module").forEach(mod=>{
  const allowed=state.allowedTabs.includes(mod.id);
  mod.style.display=allowed?"":"none";
  mod.classList.remove("active");
 });
 const first=state.allowedTabs[0]||"dashboard";
 const firstBtn=document.querySelector(`.nav-btn[data-target="${first}"]`);
 if(firstBtn)firstBtn.classList.add("active");
 if($(first))$(first).classList.add("active");
 applyProcurementRoleUi(role);
 applyHrmRoleUi(role);
}
function roleDesignation(role){
 const map={admin:"System Administrator",purchase:"Purchase Officer",store:"Store Keeper",sales:"Sales Executive",production:"Production Planner",logistics:"Logistics Coordinator",accounts:"Accounts Officer",hr:"HR Manager",guest:"Guest"};
 return map[String(role||"").toLowerCase()]||role||"User";
}
function renderProfile(){
 if(!$("profileInfo"))return;
 const u=state.user||{};
 const initials=String(u.name||u.email||"U").trim().split(/\s+/).slice(0,2).map(x=>x.charAt(0).toUpperCase()).join("")||"U";
 const role=String(u.role||"guest").toUpperCase();
 $("profileInfo").innerHTML=`
  <section class="profile-summary-card">
   <div class="profile-summary-head">
    <div class="profile-avatar" aria-hidden="true">${esc(initials)}</div>
    <div class="profile-summary-copy">
     <p class="eyebrow">Signed In User</p>
     <h4>${esc(u.name||"Not logged in")}</h4>
     <p class="profile-summary-role">${esc(roleDesignation(u.role))}</p>
    </div>
   </div>
   <div class="profile-meta-grid">
    <article class="profile-meta-item">
     <span>Email</span>
     <strong>${esc(u.email||"-")}</strong>
    </article>
    <article class="profile-meta-item">
     <span>Role</span>
     <strong>${esc(role)}</strong>
    </article>
    <article class="profile-meta-item">
     <span>User ID</span>
     <strong>${esc(u.id?fmt("users",u.id):"-")}</strong>
    </article>
    <article class="profile-meta-item">
     <span>Status</span>
     <strong>${state.headers["x-user-id"]?"Active session":"Signed out"}</strong>
    </article>
   </div>
  </section>`;
}
function closeProfileMenu(){if($("profileMenu"))$("profileMenu").hidden=true}
function logout(){
 state.headers={};
 state.user=null;
 state.allowedTabs=[];
 resetMachineSelections();
 jobMaterialDraft.length=0;
 renderJobMaterialList();
 setSession({name:"Not logged in",role:"guest"},{});
 setAppShellVisible(false);
 closeProfileMenu();
 renderProfile();
 applyRoleAccess("guest");
 const firstNav=document.querySelector('.nav-btn[data-target="dashboard"]');
 if(firstNav){document.querySelectorAll(".nav-btn").forEach(x=>x.classList.remove("active"));firstNav.classList.add("active");}
 document.querySelectorAll(".module").forEach(m=>m.classList.remove("active"));
 if($("dashboard"))$("dashboard").classList.add("active");
 toast("Logged out");
}
function setupClickTracking(){
 if(document.body.dataset.clickTracking==="true")return;
 document.body.dataset.clickTracking="true";
 document.addEventListener("click",e=>{
  if(!state.headers["x-user-id"])return;
  const node=e.target?.closest?.("button,a,input,select,textarea,.nav-btn,.card,.data-table tr,[data-target]");
  if(!node)return;
  const tag=(node.tagName||"").toLowerCase();
  const label=(node.innerText||node.value||node.id||node.name||"").trim().slice(0,140);
  const payload={action:`CLICK_${tag||"node"}`,path:window.location.pathname,uiTarget:node.id||node.name||node.className||tag,details:{label,x:e.clientX,y:e.clientY,ts:new Date().toISOString()}};
  fetch("/api/meta/activity/click",{method:"POST",headers:{"Content-Type":"application/json",...state.headers},body:JSON.stringify(payload),keepalive:true}).catch(()=>{});
 },true);
}
function skuByCat(sku,cat){const p={RAW:"RAW",WIP:"WIP",FG:"FG",CONSUMABLE:"CON"}[cat]||"ITM";const v=String(sku||"").trim().toUpperCase();return v.startsWith(`${p}-`)?v:`${p}-${v}`}

const comboInputs=new WeakMap();
const semanticInputs=new WeakMap();
const semanticLists=new Map();
let semanticObserverBound=false;
function ensureComboInputStyles(){if(document.getElementById("comboInputStyles"))return;const style=document.createElement("style");style.id="comboInputStyles";style.textContent=".combo-native-hidden{position:absolute!important;left:-9999px!important;width:1px!important;height:1px!important;opacity:0!important;pointer-events:none!important}.combo-input{width:100%;margin:0;min-height:40px}";document.head.appendChild(style)}
function ensureSemanticList(id){if($(id))return $(id);const list=document.createElement("datalist");list.id=id;document.body.appendChild(list);return list}
function renderSemanticList(listEl,rows){if(!listEl)return;listEl.innerHTML=(rows||[]).map(row=>`<option value="${esc(row.label)}"></option>`).join("")}
function uniqueSemanticRows(rows){const seen=new Set();return (Array.isArray(rows)?rows:[]).map((row,index)=>({value:row?.value??row?.label??"",label:String(row?.label||"").trim(),keywords:Array.isArray(row?.keywords)?row.keywords:row?.keywords?[row.keywords]:[],index:row?.index??index})).filter(row=>{if(!row.label)return false;const key=`${normalizeSearchText(row.label)}|${normalizeSearchText(row.value||row.label)}`;if(seen.has(key))return false;seen.add(key);return true;})}
function registerSemanticList(id,rows){const clean=uniqueSemanticRows(rows);semanticLists.set(id,clean);renderSemanticList(ensureSemanticList(id),clean.slice(0,12));document.querySelectorAll(`input[list="${id}"]`).forEach(input=>refreshSemanticInput(input));return clean}
function semanticRowsFromValues(values,keywords){return [...new Set((values||[]).map(v=>String(v||"").trim()).filter(Boolean))].map((label,index)=>({label,value:label,keywords,index}))}
function semanticRowsFromEntities(rows,labelFn,keywordsFn){return (rows||[]).map((row,index)=>({label:String(labelFn(row)||"").trim(),value:String(labelFn(row)||"").trim(),keywords:[...(keywordsFn?keywordsFn(row):[])],index})).filter(row=>row.label)}
function refreshSemanticInput(input){const listId=input?.getAttribute?.("list");const rows=semanticLists.get(listId)||[];if(!listId||!rows.length)return;const ranked=rankSearchRows(input.value,rows,12);renderSemanticList(ensureSemanticList(listId),ranked.length?ranked:rows.slice(0,12))}
function attachSemanticInput(input){if(!input||input.readOnly||input.type==="hidden"||input.classList.contains("combo-input"))return;const listId=input.getAttribute("list");if(!listId||!semanticLists.has(listId)||semanticInputs.has(input))return;const refresh=()=>refreshSemanticInput(input);input.addEventListener("focus",refresh);input.addEventListener("input",refresh);semanticInputs.set(input,{refresh});refresh()}
function comboOptions(select){return Array.from(select.options||[]).map((o,idx)=>({value:String(o.value??""),label:String(o.textContent||"").trim(),keywords:[select.name,select.id],index:idx})).filter(o=>o.value!==""&&o.label)}
function comboBestMatch(query,rows){return rankSearchRows(query,rows,1)[0]||null}
function syncComboInput(select){
 if(!select||select.multiple||select.dataset.noCombo==="true")return;
 ensureComboInputStyles();
 let meta=comboInputs.get(select);
 if(!meta){
  const input=document.createElement("input");
  const listId=`combo-list-${select.id||select.name||Math.random().toString(36).slice(2)}`;
  const dl=document.createElement("datalist");
  input.type="search";
  input.className="combo-input";
  input.setAttribute("list",listId);
  input.placeholder=select.dataset.searchPlaceholder||"Search by name, code, ID, or keyword";
  dl.id=listId;
  select.classList.add("combo-native-hidden");
  select.parentNode?.insertBefore(input,select);
  select.parentNode?.insertBefore(dl,select.nextSibling);
  meta={input,dl};
  comboInputs.set(select,meta);

  const refreshInput=()=>{const rows=comboOptions(select);const ranked=rankSearchRows(meta.input.value,rows,12);renderSemanticList(meta.dl,ranked.length?ranked:rows.slice(0,12));return rows};
  const applyInput=()=>{const rows=refreshInput();const best=comboBestMatch(meta.input.value,rows);if(best){select.value=best.value;meta.input.value=best.label;select.dispatchEvent(new Event("change",{bubbles:true}));}};
  input.addEventListener("focus",refreshInput);
  input.addEventListener("input",refreshInput);
  input.addEventListener("change",applyInput);
  input.addEventListener("blur",applyInput);
 }

 const rows=comboOptions(select);
 const current=rows.find(r=>String(r.value)===String(select.value))||null;
 renderSemanticList(meta.dl,current?rankSearchRows(current.label,rows,12):rows.slice(0,12));
 if(current)meta.input.value=current.label;
 else meta.input.value="";
}
function bindSemanticList(selector,listId,rows,placeholder){registerSemanticList(listId,rows);document.querySelectorAll(selector).forEach(input=>{if(!input||input.readOnly||input.type==="hidden")return;input.setAttribute("list",listId);if(placeholder&&!input.placeholder)input.placeholder=placeholder;attachSemanticInput(input)})}
function refreshSemanticFieldLists(){const vendors=state.refs.vendors||[];const customers=state.refs.customers||[];const employees=state.refs.employees||[];const machines=state.refs.machines||[];const taxes=state.refs.taxes||[];const challans=state.refs.challans||[];const leaveRequests=state.refs.leaveRequests||[];bindSemanticList('#vendorForm input[name="name"]',"vendorNameSearchList",semanticRowsFromEntities(vendors,x=>x.name,x=>[fmt("vendors",x.id),x.category,x.gstin,x.phone,"vendor","supplier"]),"Search existing vendor names");bindSemanticList('#vendorForm input[name="gstin"]',"gstinSearchList",semanticRowsFromValues([...vendors.map(x=>x.gstin),...customers.map(x=>x.gstin)],["gstin","tax","registration"]),"Search existing GSTINs");bindSemanticList('input[name="phone"]',"phoneSearchList",semanticRowsFromValues([...vendors.map(x=>x.phone),...customers.map(x=>x.phone)],["phone","mobile","contact"]),"Search existing phone numbers");bindSemanticList('input[name="email"]',"emailSearchList",semanticRowsFromValues([...(state.refs.users||[]).map(x=>x.email),...vendors.map(x=>x.email),...customers.map(x=>x.email)],["email","mail","contact"]),"Search existing email addresses");bindSemanticList('#customerForm input[name="name"]',"customerNameSearchList",semanticRowsFromEntities(customers,x=>x.name,x=>[fmt("customers",x.id),x.gstin,x.phone,"customer","client"]),"Search existing customer names");bindSemanticList('#machineForm input[name="name"]',"machineNameSearchList",semanticRowsFromEntities(machines,x=>x.name,x=>[fmt("machines",x.id),x.type,x.location,"machine","equipment"]),"Search existing machine names");bindSemanticList('#employeeForm input[name="name"]',"employeeNameSearchList",semanticRowsFromEntities(employees,x=>x.name,x=>[fmt("employees",x.id),x.department,x.designation,"employee","staff"]),"Search existing employee names");bindSemanticList('input[name="department"]',"departmentSearchList",semanticRowsFromValues(employees.map(x=>x.department),["department","team","division"]),"Start typing department");bindSemanticList('input[name="designation"]',"designationSearchList",semanticRowsFromValues(employees.map(x=>x.designation),["designation","role","title"]),"Start typing designation");bindSemanticList('input[name="location"]',"locationSearchList",semanticRowsFromValues([...(state.refs.warehouses||[]).map(x=>x.location),...machines.map(x=>x.location)],["location","site","plant"]),"Search by location or site");bindSemanticList('input[name="vehicleNo"]',"vehicleNoSearchList",semanticRowsFromValues(challans.map(x=>x.vehicleNo),["vehicle","truck","transport"]),"Search existing vehicle numbers");bindSemanticList('input[name="code"]',"taxCodeSearchList",taxes.map((x,index)=>({label:x.code,value:x.id,keywords:[x.description,"tax","gst","hsn"],index})),"Search HSN or GST code");bindSemanticList('#taxForm input[name="name"]',"taxDescriptionSearchList",semanticRowsFromEntities(taxes,x=>x.description||x.name||x.code,x=>[x.code,"tax","gst","hsn"]), "Search tax descriptions");bindSemanticList('input[name="reason"]',"reasonSearchList",semanticRowsFromValues(leaveRequests.map(x=>x.reason),["reason","leave","wastage","note"]),"Search previous reasons");bindSemanticList('input[name="remarks"],#jobMaterialRemarks',"remarksSearchList",semanticRowsFromValues([...leaveRequests.map(x=>x.reason),...challans.map(x=>x.transporter)],["remarks","notes","comment"]),"Search previous notes");bindSemanticList('input[name="bankAccount"]',"bankAccountSearchList",semanticRowsFromValues(employees.map(x=>x.bankAccount),["bank","account","salary"]),"Search existing bank accounts");bindSemanticList('input[name="ifsc"]',"ifscSearchList",semanticRowsFromValues(employees.map(x=>x.ifsc),["ifsc","bank","branch"]),"Search existing IFSC codes")}
function applyComboInputs(scope=document){if(scope.matches?.("select"))syncComboInput(scope);scope.querySelectorAll?.("select").forEach(syncComboInput);if(scope.matches?.('input[list]'))attachSemanticInput(scope);scope.querySelectorAll?.('input[list]').forEach(attachSemanticInput)}
function observeSemanticInputs(){if(semanticObserverBound||!document.body)return;const observer=new MutationObserver(mutations=>{mutations.forEach(m=>{m.addedNodes.forEach(node=>{if(!(node instanceof HTMLElement))return;if(node.matches?.("select,input[list]"))applyComboInputs(node);if(node.querySelector?.("select,input[list]"))applyComboInputs(node)})})});observer.observe(document.body,{childList:true,subtree:true});semanticObserverBound=true}

function sel(id,rows,label,valueFn){if(!$(id))return;$(id).innerHTML=`<option value=""></option>`+rows.map(r=>`<option value="${esc(valueFn?valueFn(r):r.id)}">${esc(label(r))}</option>`).join("");$(id).value="";syncComboInput($(id))}
function selMulti(id,rows,label,selected=[]){const el=$(id);if(!el)return;const pick=new Set((selected||[]).map(String));el.innerHTML=rows.map(r=>`<option value="${esc(r.id)}" ${pick.has(String(r.id))?"selected":""}>${esc(label(r))}</option>`).join("")}
function datalist(){registerSemanticList("itemSearchList",itemSearchRows(state.refs.items))}
function grnDatalist(lines=[]){const allowed=new Set((lines||[]).map(l=>String(l.itemId)));registerSemanticList("grnItemSearchList",itemSearchRows(state.refs.items.filter(i=>allowed.has(String(i.id)))))}
const machineSelections={create:[],status:[]};
const jobMaterialDraft=[];
const requisitionDraft=[];
const poDraft=[];
function machineLabelById(id){return ref("machines",id)}
function machineById(id){return (state.refs.machines||[]).find(m=>String(m.id)===String(id))}
function machineCategories(){const cats=[...new Set((state.refs.machines||[]).map(m=>String(m.type||"").trim()).filter(Boolean))];return ["ALL",...cats]}
function syncMachineHidden(key){const id=key==="create"?"jobMachineIds":"jobStatusMachineIds";if($(id))$(id).value=machineSelections[key].join("|")}
function renderMachineList(key){const host=$(key==="create"?"jobMachineList":"jobStatusMachineList");if(!host)return;const rows=machineSelections[key];if(!rows.length){host.innerHTML='<div class="table-empty">No machines selected.</div>';syncMachineHidden(key);enhanceTables();return;}host.innerHTML=`<table class="data-table"><thead><tr><th>Machine ID</th><th>Machine</th><th>Action</th></tr></thead><tbody>${rows.map(mid=>`<tr><td>${esc(fmt("machines",mid))}</td><td>${esc(machineLabelById(mid))}</td><td><button type="button" class="remove-machine-btn" data-machine-key="${esc(key)}" data-machine-id="${esc(mid)}">Remove</button></td></tr>`).join("")}</tbody></table>`;syncMachineHidden(key);enhanceTables()}
function addMachineSelection(key,machineId){const v=String(machineId||"").trim();if(!v)return;if(!machineSelections[key].includes(v))machineSelections[key].push(v);renderMachineList(key)}
function removeMachineSelection(key,machineId){machineSelections[key]=machineSelections[key].filter(x=>String(x)!==String(machineId));renderMachineList(key)}
function resetMachineSelections(){machineSelections.create=[];machineSelections.status=[];renderMachineList("create");renderMachineList("status")}
function syncJobMaterialHidden(){if($("jobMaterialIssues"))$("jobMaterialIssues").value=JSON.stringify(jobMaterialDraft)}
function renderJobMaterialList(){const host=$("jobMaterialList");if(!host)return;if(!jobMaterialDraft.length){host.innerHTML='<div class="table-empty">No materials added.</div>';syncJobMaterialHidden();enhanceTables();return;}host.innerHTML=`<table class="data-table"><thead><tr><th>Item</th><th>Warehouse</th><th>Qty</th><th>Remarks</th><th>Action</th></tr></thead><tbody>${jobMaterialDraft.map((m,i)=>`<tr><td>${esc(ref("items",m.itemId))}</td><td>${esc(ref("warehouses",m.warehouseId))}</td><td>${esc(m.qty)}</td><td>${esc(m.remarks||"")}</td><td><button type="button" class="remove-job-material-btn" data-index="${i}">Remove</button></td></tr>`).join("")}</tbody></table>`;syncJobMaterialHidden();enhanceTables()}
function addJobMaterialLine(){const iid=itemId($("jobMaterialItemSearch")?.value);const wh=$("jobMaterialWarehouseId")?.value;const qty=String($("jobMaterialQty")?.value||"").trim();const remarks=String($("jobMaterialRemarks")?.value||"").trim();if(!iid){toast("Select a valid item",true);return;}if(!wh){toast("Select warehouse",true);return;}if(!Number.isFinite(Number(qty))||Number(qty)<=0){toast("Qty must be positive",true);return;}jobMaterialDraft.push({itemId:iid,warehouseId:wh,qty,remarks});if($("jobMaterialItemSearch"))$("jobMaterialItemSearch").value="";if($("jobMaterialQty"))$("jobMaterialQty").value="";if($("jobMaterialRemarks"))$("jobMaterialRemarks").value="";renderJobMaterialList()}
function removeJobMaterialLine(index){const i=Number(index);if(!Number.isInteger(i)||i<0||i>=jobMaterialDraft.length)return;jobMaterialDraft.splice(i,1);renderJobMaterialList()}
function syncDraftSubmitState(){const prSubmit=$("prForm")?.querySelector?.('button[type="submit"]');if(prSubmit)prSubmit.disabled=!requisitionDraft.length;const poSubmit=$("poForm")?.querySelector?.('button[type="submit"]');if(poSubmit)poSubmit.disabled=!String($("poPrId")?.value||"").trim()||!poDraft.length}
function renderRequisitionDraft(){const host=$("prDraftList");if(!host)return;if(!requisitionDraft.length){host.innerHTML='<div class="table-empty">No items added.</div>';syncDraftSubmitState();enhanceTables();return;}host.innerHTML=`<table class="data-table no-row-actions-table"><thead><tr><th>Item</th><th>Qty</th><th>Action</th></tr></thead><tbody>${requisitionDraft.map((l,i)=>`<tr><td>${esc(ref("items",l.itemId))}</td><td>${esc(l.qty)}</td><td><button type="button" class="remove-pr-line-btn" data-index="${i}">Remove</button></td></tr>`).join("")}</tbody></table>`;syncDraftSubmitState();enhanceTables()}
function renderPoDraft(){const host=$("poDraftList");if(!host)return;const prId=String($("poPrId")?.value||"").trim();if(!prId){host.innerHTML='<div class="table-empty">Select a purchase requisition to load vendor and items.</div>';syncDraftSubmitState();enhanceTables();return;}if(!poDraft.length){host.innerHTML='<div class="table-empty">No items found in the selected purchase requisition.</div>';syncDraftSubmitState();enhanceTables();return;}host.innerHTML=`<table class="data-table no-row-actions-table"><thead><tr><th>Item</th><th>Qty</th><th>Unit Rate</th><th>GST %</th></tr></thead><tbody>${poDraft.map((l,i)=>`<tr><td>${esc(ref("items",l.itemId))}</td><td><span class="draft-fixed-value">${esc(l.qty)}</span></td><td><input type="number" class="po-draft-field-input" data-index="${i}" data-field="unitRate" min="0.01" step="0.01" value="${esc(l.unitRate)}" /></td><td><input type="number" class="po-draft-field-input" data-index="${i}" data-field="taxRate" min="0" step="0.01" value="${esc(l.taxRate)}" /></td></tr>`).join("")}</tbody></table>`;syncDraftSubmitState();enhanceTables()}
function addRequisitionLine(){const f=$("prForm");if(!f)return;const iid=itemId(f.elements.itemSearch?.value);const qty=String(f.elements.qty?.value||"").trim();if(!iid){toast("Select a valid item",true);return;}if(!Number.isFinite(Number(qty))||Number(qty)<=0){toast("Qty must be positive",true);return;}requisitionDraft.push({itemId:iid,qty});if(f.elements.itemSearch)f.elements.itemSearch.value="";if(f.elements.qty)f.elements.qty.value="";renderRequisitionDraft()}
function removeRequisitionLine(index){const i=Number(index);if(!Number.isInteger(i)||i<0||i>=requisitionDraft.length)return;requisitionDraft.splice(i,1);renderRequisitionDraft()}
function updatePoDraftField(index,field,value){const i=Number(index);if(!Number.isInteger(i)||i<0||i>=poDraft.length)return;if(!["unitRate","taxRate"].includes(String(field||"")))return;poDraft[i]={...poDraft[i],[field]:String(value||"").trim()};syncDraftSubmitState()}
function requisitionLabel(pr){const itemCount=Array.isArray(pr?.lines)?pr.lines.length:0;const vendorText=pr?.vendorId?ref("vendors",pr.vendorId):"Vendor pending";return `${pr.prNo} - ${vendorText} (${itemCount} item${itemCount===1?"":"s"})`}
function syncPoFromRequisition(){const prId=String($("poPrId")?.value||"").trim();const vendorHidden=$("poVendorId");const vendorDisplay=$("poVendorText");if(!vendorHidden||!vendorDisplay){poDraft.length=0;renderPoDraft();return;}if(!prId){vendorHidden.value="";vendorDisplay.value="";vendorDisplay.placeholder="Select purchase requisition";poDraft.length=0;renderPoDraft();return;}const pr=(state.refs.requisitions||[]).find(x=>String(x.id)===prId);if(!pr){vendorHidden.value="";vendorDisplay.value="";vendorDisplay.placeholder="Purchase requisition not found";poDraft.length=0;renderPoDraft();return;}vendorHidden.value=String(pr.vendorId||"");vendorDisplay.value=pr.vendorId?ref("vendors",pr.vendorId):"";vendorDisplay.placeholder=pr.vendorId?"":"Vendor not set on requisition";poDraft.length=0;(pr.lines||[]).forEach(line=>{const item=(state.refs.items||[]).find(x=>String(x.id)===String(line.itemId));const taxId=String(item?.gstTaxId||"");poDraft.push({prLineId:line.id,itemId:String(line.itemId),qty:String(line.qty||""),unitRate:String(item?.standardRate||0),taxRate:taxRate(taxId)});});renderPoDraft()}
function filterMachinesForPicker(key){const cat=String((key==="create"?$("jobMachineCategory"): $("jobStatusMachineCategory"))?.value||"ALL");const base=(state.refs.machines||[]).filter(m=>key==="status"||String(m.status||"").toUpperCase()==="ACTIVE");const filtered=cat==="ALL"?base:base.filter(m=>String(m.type||"")===cat);const picker=key==="create"?"jobMachinePicker":"jobStatusMachinePicker";sel(picker,filtered,x=>`${fmt("machines",x.id)} - ${x.name} (${x.type})`)}
function syncPrRequestedByField(){const hidden=$("prRequestedBy");const display=$("prRequestedByDisplay");if(!hidden||!display)return;const user=state.user&&state.user.id&&state.user.id!=="header-user"?state.user:null;if(!user){hidden.value="";display.value="";display.placeholder="Login required";return;}hidden.value=String(user.id);display.value=`${fmt("users",user.id)} - ${user.name||"Current User"}`;}
function syncLeaveEmployeeField(){const hidden=$("leaveEmployeeId");const display=$("leaveEmployeeDisplay");if(!hidden||!display)return;const user=state.user&&state.user.id&&state.user.id!=="header-user"?state.user:null;if(!user){hidden.value="";display.value="";display.placeholder="Login required";return;}const employee=(state.refs.employees||[]).find(x=>String(x.id)===String(user.id));const employeeId=String(employee?.id||user.id);hidden.value=employeeId;display.value=employee?`${fmt("employees",employee.id)} - ${employee.name||user.name||"Current User"}`:`${fmt("users",user.id)} - ${user.name||"Current User"}`;}

function setupNav(){document.querySelectorAll(".nav-btn").forEach(b=>b.addEventListener("click",()=>{if(!state.allowedTabs.includes(b.dataset.target))return;document.querySelectorAll(".nav-btn").forEach(x=>x.classList.remove("active"));document.querySelectorAll(".module").forEach(m=>m.classList.remove("active"));b.classList.add("active");$(b.dataset.target).classList.add("active");if(b.dataset.target==="hrmPayroll"){const jobs=isPrivilegedHrRole(state.user?.role)?[refreshEmployees(),refreshAttendance(),refreshLeaveRequests(),refreshPayrollRuns()]:[refreshEmployees(),refreshLeaveRequests(),refreshPayrollRuns()];Promise.all(jobs).catch(e=>toast(e.message,true));}}))}
function openProfileFromIcon(e){if(e)e.stopPropagation();if(!state.user||!state.headers["x-user-id"])return;const m=$("profileMenu");if(!m)return;renderProfile();m.hidden=!m.hidden}

async function loadRefs(role){
 const safe=async(path,fallback=[])=>{try{return await api(path)}catch{return fallback}};
 const [users,items,vendors,customers,warehouses,uoms,taxes,machines,requisitions,purchaseOrders,grns,salesOrders,challans,employees,leaveRequests,payrollRuns]=await Promise.all([
  safe("/api/users",[]),
  safe("/api/masters/items",[]),
  safe("/api/masters/vendors",[]),
  safe("/api/masters/customers",[]),
  safe("/api/masters/warehouses",[]),
  safe("/api/masters/uoms",[]),
  safe("/api/masters/taxes",[]),
  safe("/api/masters/machines",[]),
  safe("/api/procurement/requisitions",[]),
  safe("/api/procurement/purchase-orders",[]),
  safe("/api/procurement/grns",[]),
  safe("/api/sales/sales-orders",[]),
  safe("/api/logistics/challans",[]),
  safe("/api/hrm-payroll/employees",[]),
  safe("/api/hrm-payroll/leave-requests",[]),
  safe("/api/hrm-payroll/payroll-runs",[]),
 ]);
 state.refs={users,items,vendors,customers,warehouses,uoms,taxes,machines,requisitions,purchaseOrders,grns,salesOrders,challans,employees,leaveRequests,payrollRuns};
 datalist();bindSelectors()
}
function bindSelectors(){
 syncPrRequestedByField();
 syncLeaveEmployeeField();
 sel("prVendorId",state.refs.vendors,x=>`${fmt("vendors",x.id)} - ${x.name}`);
 const currentPrId=String($("poPrId")?.value||"").trim();
 const poReadyRequisitions=(state.refs.requisitions||[]).filter(x=>String(x.status||"").toUpperCase()==="OPEN"&&String(x.vendorId||"").trim());
 sel("poPrId",poReadyRequisitions,x=>requisitionLabel(x));
 if(currentPrId&&poReadyRequisitions.some(x=>String(x.id)===currentPrId)&&$("poPrId"))$("poPrId").value=currentPrId;
 sel("approvePoId",state.refs.purchaseOrders.filter(x=>String(x.approvalStatus||"").toUpperCase()!=="APPROVED"),x=>`${x.poNo} - ${ref("vendors",x.vendorId)}`);
 sel("grnPoId",state.refs.purchaseOrders,x=>`${x.poNo} - ${ref("vendors",x.vendorId)}`);
 sel("grnVendorId",state.refs.vendors,x=>`${fmt("vendors",x.id)} - ${x.name}`);
 sel("grnWarehouseId",state.refs.warehouses,x=>`${fmt("warehouses",x.id)} - ${x.name}`);
 sel("itemUomId",state.refs.uoms,x=>`${x.code} - ${x.name}`);
 sel("itemHsnTaxId",state.refs.taxes,x=>`${x.code} (${x.rate}%)`,x=>x.code);
 sel("issueWarehouseId",state.refs.warehouses,x=>`${fmt("warehouses",x.id)} - ${x.name}`);
 sel("transferFromWarehouseId",state.refs.warehouses,x=>`${fmt("warehouses",x.id)} - ${x.name}`);
 sel("transferToWarehouseId",state.refs.warehouses,x=>`${fmt("warehouses",x.id)} - ${x.name}`);
 sel("wastageWarehouseId",state.refs.warehouses,x=>`${fmt("warehouses",x.id)} - ${x.name}`);
 sel("quoteCustomerId",state.refs.customers,x=>`${fmt("customers",x.id)} - ${x.name}`);
 sel("quoteHsnTaxId",state.refs.taxes,x=>`${x.code} (${x.rate}%)`,x=>x.code);
 sel("soCustomerId",state.refs.customers,x=>`${fmt("customers",x.id)} - ${x.name}`);
 sel("soHsnTaxId",state.refs.taxes,x=>`${x.code} (${x.rate}%)`,x=>x.code);
 sel("challanSoId",state.refs.salesOrders,x=>`${x.soNo} - ${ref("customers",x.customerId)}`);
 const logisticsVendors = state.refs.vendors.filter(x=>String(x.category||"").toUpperCase()==="LOGISTICS");
 const transporterChoices = logisticsVendors.length ? logisticsVendors : state.refs.vendors;
 sel("challanTransporterVendorId",transporterChoices,x=>`${fmt("vendors",x.id)} - ${x.name}${x.category?` (${x.category})`:""}`);
 sel("dispatchTransporterVendorId",transporterChoices,x=>`${fmt("vendors",x.id)} - ${x.name}${x.category?` (${x.category})`:""}`);
 sel("jobSoId",state.refs.salesOrders.filter(x=>["OPEN","RELEASED_TO_PRODUCTION"].includes(String(x.status||"").toUpperCase())),x=>`${x.soNo} - ${ref("customers",x.customerId)} (${x.status})`);
 const cats=machineCategories().map(c=>({id:c,name:c}));
 sel("jobMachineCategory",cats,x=>x.name,x=>x.id);
 sel("jobStatusMachineCategory",cats,x=>x.name,x=>x.id);
 filterMachinesForPicker("create");
 filterMachinesForPicker("status");
 machineSelections.create=machineSelections.create.filter(id=>state.refs.machines.some(m=>String(m.id)===String(id)));
 machineSelections.status=machineSelections.status.filter(id=>state.refs.machines.some(m=>String(m.id)===String(id)));
 renderMachineList("create");renderMachineList("status");
 sel("jobMaterialWarehouseId",state.refs.warehouses,x=>`${fmt("warehouses",x.id)} - ${x.name}`);
 renderJobMaterialList();
 sel("dispatchChallanId",state.refs.challans,x=>`${x.challanNo} - ${x.dispatchStatus}`);
 sel("pinvPoId",state.refs.purchaseOrders,x=>`${x.poNo} - ${ref("vendors",x.vendorId)}`);
 sel("pinvGrnId",state.refs.grns,x=>`${x.grnNo} - ${ref("vendors",x.vendorId)}`);
 sel("sinvSoId",state.refs.salesOrders,x=>`${x.soNo} - ${ref("customers",x.customerId)}`);
 syncPurchaseInvoiceSource();syncSalesInvoiceSource();
 const scopedEmployees=isPrivilegedHrRole(state.user?.role)?state.refs.employees:state.refs.employees.filter(x=>String(x.id)===String(state.user?.id));
sel("attendanceEmployeeId",scopedEmployees,x=>`${fmt("employees",x.id)} - ${x.name}`);
sel("leaveApproveId",state.refs.leaveRequests.filter(x=>String(x.status||"").toUpperCase()==="PENDING"),x=>`${ref("employees",x.employeeId)} (${x.fromDate} to ${x.toDate})`);
 syncLeaveApprovalState();
 syncPoFromRequisition();bindPoLines();showPoDetails();refreshSemanticFieldLists();applyComboInputs();
}
function syncGrnItemByPoLine(){const poId=$("grnPoId")?.value;const lineId=$("grnPoLineId")?.value;const po=state.refs.purchaseOrders.find(x=>String(x.id)===String(poId));const line=(po?.lines||[]).find(l=>String(l.id)===String(lineId));const input=$("grnForm")?.elements?.itemSearch;if(!input)return;if(!line){input.value="";return;}const it=state.refs.items.find(i=>String(i.id)===String(line.itemId));if(it)input.value=itemLabel(it)}
function bindPoLines(){const poId=$("grnPoId")?.value;const po=state.refs.purchaseOrders.find(x=>String(x.id)===String(poId));const lines=po?.lines||[];if(!$("grnPoLineId"))return;$("grnPoLineId").innerHTML=lines.map(l=>`<option value="${esc(l.id)}">${esc(`POL-${String(l.id).padStart(4,"0")} - ${ref("items",l.itemId)} (Qty: ${l.qty}, Rec: ${l.receivedQty})`)}</option>`).join("");grnDatalist(lines);if(po&&$("grnVendorId"))$("grnVendorId").value=String(po.vendorId);syncGrnItemByPoLine()}
function showPoDetails(){const id=$("approvePoId")?.value;const po=state.refs.purchaseOrders.find(x=>String(x.id)===String(id));if(!$("approvePoDetails"))return;if(!po){$("approvePoDetails").innerHTML='<div class="table-empty">Select a PO to view details.</div>';return;}const rows=(po.lines||[]).map(l=>({item:ref("items",l.itemId),qty:l.qty,rate:l.unitRate,received:l.receivedQty}));$("approvePoDetails").innerHTML=table(rows,[{key:"item",label:"Item"},{key:"qty",label:"Qty"},{key:"rate",label:"Unit Rate"},{key:"received",label:"Received"}])}
function syncPurchaseInvoiceSource(){const poId=$("pinvPoId")?.value;const po=state.refs.purchaseOrders.find(x=>String(x.id)===String(poId));const poGrns=state.refs.grns.filter(x=>String(x.poId)===String(poId));sel("pinvGrnId",poGrns,x=>`${x.grnNo} - ${ref("vendors",x.vendorId)}`);const grnId=$("pinvGrnId")?.value;const grn=poGrns.find(x=>String(x.id)===String(grnId))||poGrns[0];if(grn&&$("pinvGrnId"))$("pinvGrnId").value=String(grn.id);if($("pinvVendorText"))$("pinvVendorText").value=po?ref("vendors",po.vendorId):"";if(!$("pinvSourceDetails"))return;if(!po||!grn){$("pinvSourceDetails").innerHTML='<div class="table-empty">Select PO and GRN to preview invoice lines.</div>';return;}const poLines=po.lines||[];const rows=(grn.lines||[]).map(gl=>{const poLine=poLines.find(pl=>String(pl.id)===String(gl.poLineId));const qty=Number(gl.qtyAccepted||0);const rate=Number(poLine?.unitRate||0);const taxRate=Number(poLine?.taxRate||0);const base=(qty*rate);const tax=(base*taxRate/100);return{item:ref("items",gl.itemId),lotNo:gl.lotNo||"-",qty:qty.toFixed(2),unitPrice:rate.toFixed(2),taxRate:taxRate.toFixed(2),taxAmount:tax.toFixed(2),lineTotal:(base+tax).toFixed(2)}}).filter(r=>Number(r.qty)>0);$("pinvSourceDetails").innerHTML=table(rows,[{key:"item",label:"Item"},{key:"lotNo",label:"Lot No"},{key:"qty",label:"Qty (Accepted)"},{key:"unitPrice",label:"Unit Price"},{key:"taxRate",label:"Tax %"},{key:"taxAmount",label:"Tax Amt"},{key:"lineTotal",label:"Line Total"}])}
function syncSalesInvoiceSource(){const soId=$("sinvSoId")?.value;const so=state.refs.salesOrders.find(x=>String(x.id)===String(soId));if($("sinvCustomerText"))$("sinvCustomerText").value=so?ref("customers",so.customerId):"";if(!$("sinvSourceDetails"))return;if(!so){$("sinvSourceDetails").innerHTML='<div class="table-empty">Select SO to preview invoice lines.</div>';return;}const rows=(so.lines||[]).map(l=>{const qty=Number(l.qty||0);const rate=Number(l.unitPrice||0);const taxRate=Number(l.taxRate||0);const base=(qty*rate);const tax=(base*taxRate/100);return{item:ref("items",l.itemId),qty:qty.toFixed(2),unitPrice:rate.toFixed(2),taxRate:taxRate.toFixed(2),taxAmount:tax.toFixed(2),lineTotal:(base+tax).toFixed(2)}});$("sinvSourceDetails").innerHTML=table(rows,[{key:"item",label:"Item"},{key:"qty",label:"Qty"},{key:"unitPrice",label:"Unit Price"},{key:"taxRate",label:"Tax %"},{key:"taxAmount",label:"Tax Amt"},{key:"lineTotal",label:"Line Total"}])}
function syncLeaveApprovalState(){const pending=state.refs.leaveRequests.filter(x=>String(x.status||"").toUpperCase()==="PENDING");const btn=$("leaveApproveForm")?.querySelector?.('button[type="submit"]');if(btn)btn.disabled=!pending.length}

function miniBars(title,data){const e=Object.entries(data||{});if(!e.length)return"";const max=Math.max(...e.map(x=>Number(x[1])||0),1);const bars=e.map(([k,v])=>{const w=Math.max(6,Math.round(((Number(v)||0)/max)*100));return `<div class="mini-bar-row"><span>${esc(k)}</span><div class="mini-bar"><i style="width:${w}%"></i></div><b>${esc(v)}</b></div>`}).join("");return `<div class="card"><h3>${esc(title)}</h3><div class="mini-bars">${bars}</div></div>`}

async function refreshDashboard(){try{if(typeof window.renderProfessionalDashboard==="function"){await window.renderProfessionalDashboard();return;}const [s,p]=await Promise.all([api("/api/reports/dashboard"),api("/api/reports/procurement")]);const cards=Object.entries(s).map(([k,v])=>`<div class="card"><h3>${esc(k.replace(/([A-Z])/g," $1"))}</h3><p>${esc(v)}</p></div>`).join("");$("dashboardCards").innerHTML=cards+miniBars("PO Approval",p.ordersByApprovalStatus)+miniBars("GRN Quality",p.grnQualityStatus)+miniBars("Invoice Match",p.invoiceMatchStatus)}catch(e){toast(e.message,true)}}
async function refreshUsers(){const r=await api("/api/users");state.refs.users=r;render("usersList",r,[{key:"id",label:"User ID",format:v=>fmt("users",v)},{key:"name",label:"Name"},{key:"role",label:"Role"},{key:"email",label:"Email"}])}
async function refreshItems(){const r=await api("/api/masters/items");state.refs.items=r;datalist();render("itemsList",r,[{key:"id",label:"Item ID",format:v=>fmt("items",v)},{key:"sku",label:"Item Code"},{key:"name",label:"Item Name"},{key:"category",label:"Category"},{key:"uomId",label:"UOM",format:v=>ref("uoms",v)},{key:"reorderLevel",label:"Reorder Level"},{key:"standardRate",label:"Std Rate"}])}
async function refreshVendors(){const r=await api("/api/masters/vendors");state.refs.vendors=r;render("vendorList",r,[{key:"id",label:"Vendor ID",format:v=>fmt("vendors",v)},{key:"name",label:"Vendor Name"},{key:"category",label:"Category"},{key:"gstin",label:"GSTIN"},{key:"phone",label:"Phone"}])}
async function refreshCustomers(){const r=await api("/api/masters/customers");state.refs.customers=r;render("customerList",r,[{key:"id",label:"Customer ID",format:v=>fmt("customers",v)},{key:"name",label:"Customer Name"},{key:"creditLimit",label:"Credit Limit"},{key:"outstanding",label:"Outstanding"}])}
async function refreshInventoryMasters(){const [w,u]=await Promise.all([api("/api/masters/warehouses"),api("/api/masters/uoms")]);state.refs.warehouses=w;state.refs.uoms=u;render("warehousesList",w,[{key:"id",label:"Warehouse ID",format:v=>fmt("warehouses",v)},{key:"name",label:"Warehouse"},{key:"location",label:"Location"}]);render("uomList",u,[{key:"id",label:"UOM ID"},{key:"code",label:"Code"},{key:"name",label:"Unit Name"}])}
async function refreshMachines(){const r=await api("/api/masters/machines");state.refs.machines=r;bindSelectors();render("machineList",r,[{key:"id",label:"Machine ID",format:v=>fmt("machines",v)},{key:"name",label:"Machine Name"},{key:"type",label:"Type"},{key:"status",label:"Status"},{key:"maintenanceDate",label:"Next Maintenance"},{key:"maintenanceFrequencyDays",label:"Maint. Freq (Days)"},{key:"location",label:"Location"},{key:"capacityPerHour",label:"Capacity/Hour"}])}
async function refreshTaxes(){const r=await api("/api/masters/taxes");state.refs.taxes=r;render("taxList",r,[{key:"code",label:"HSN Code"},{key:"description",label:"Description"},{key:"rate",label:"Rate %"}])}
async function refreshReorders(){const r=await api("/api/procurement/reorder-alerts");render("reorderList",r,[{key:"id",label:"Alert ID"},{key:"itemId",label:"Item",format:v=>ref("items",v)},{key:"currentQty",label:"Current Qty"},{key:"reorderLevel",label:"Reorder Level"},{key:"status",label:"Status"},{key:"date",label:"Date"}])}
async function refreshRequisitions(){const r=await api("/api/procurement/requisitions");state.refs.requisitions=r;bindSelectors();render("requisitionList",r,[{key:"prNo",label:"Purchase Requisition ID"},{key:"vendorId",label:"Vendor",format:v=>v?ref("vendors",v):"-"},{key:"requestedBy",label:"Requested By",format:v=>ref("users",v)},{key:"lines",label:"Requested Items",format:v=>linesSummary(v,"qty")},{key:"lines",label:"Total Qty",format:v=>totalQty(v,"qty")}])}
async function refreshPurchaseOrders(){const r=await api("/api/procurement/purchase-orders");state.refs.purchaseOrders=r;bindSelectors();render("purchaseOrderList",r,[{key:"poNo",label:"PO No"},{key:"date",label:"Date"},{key:"vendorId",label:"Vendor",format:v=>`${fmt("vendors",v)} - ${ref("vendors",v)}`},{key:"lines",label:"Items (SKU | Name)",format:v=>linesSummary(v,"qty","unitRate")},{key:"lines",label:"Total Qty",format:v=>totalQty(v,"qty")},{key:"approvalStatus",label:"Approval"},{key:"status",label:"Status"},{key:"baseAmount",label:"Base Amount"},{key:"taxAmount",label:"GST Amount"},{key:"totalAmount",label:"Grand Total"}])}
async function refreshGrns(){const r=await api("/api/procurement/grns");state.refs.grns=r;bindSelectors();render("grnList",r,[{key:"grnNo",label:"GRN No"},{key:"date",label:"Date"},{key:"poId",label:"PO",format:v=>(state.refs.purchaseOrders.find(p=>p.id===String(v))||{}).poNo||`#${v}`},{key:"vendorId",label:"Vendor",format:v=>`${fmt("vendors",v)} - ${ref("vendors",v)}`},{key:"warehouseId",label:"Warehouse",format:v=>`${fmt("warehouses",v)} - ${ref("warehouses",v)}`},{key:"qualityStatus",label:"Quality"},{key:"status",label:"Status"}])}
async function refreshQualityChecks(){const r=await api("/api/procurement/grns");const m=r.map(x=>{const l=Array.isArray(x.lines)?x.lines:[];return{grnNo:x.grnNo,date:x.date,qualityStatus:x.qualityStatus,acceptedQty:l.reduce((s,a)=>s+Number(a.qtyAccepted||0),0),rejectedQty:l.reduce((s,a)=>s+Number(a.qtyRejected||0),0),result:x.qualityStatus==="PASS"?"Accepted":x.qualityStatus==="HOLD"?"On Hold":"Rejected"}});render("qualityList",m,[{key:"grnNo",label:"GRN No"},{key:"date",label:"Date"},{key:"qualityStatus",label:"Quality Status"},{key:"acceptedQty",label:"Accepted Qty"},{key:"rejectedQty",label:"Rejected Qty"},{key:"result",label:"Result"}])}
async function refreshStock(){const r=await api("/api/inventory/stock");render("stockList",r,[{key:"itemId",label:"Item",format:v=>ref("items",v)},{key:"warehouseId",label:"Warehouse",format:v=>ref("warehouses",v)},{key:"lotNo",label:"Lot"},{key:"stockType",label:"Stock Type"},{key:"qty",label:"Qty"},{key:"avgRate",label:"Avg Rate"}])}
async function refreshQuotations(){const r=await api("/api/sales/quotations");render("quotationList",r,[{key:"quoteNo",label:"Quote No"},{key:"date",label:"Date"},{key:"customerId",label:"Customer",format:v=>`${fmt("customers",v)} - ${ref("customers",v)}`},{key:"status",label:"Status"},{key:"totalAmount",label:"Total Amount"}])}
async function refreshSalesOrders(){const r=await api("/api/sales/sales-orders");state.refs.salesOrders=r;bindSelectors();render("salesOrderList",r,[{key:"soNo",label:"SO No"},{key:"date",label:"Date"},{key:"customerId",label:"Customer",format:v=>`${fmt("customers",v)} - ${ref("customers",v)}`},{key:"lines",label:"Items (SKU | Name)",format:v=>linesSummary(v,"qty","unitPrice")},{key:"lines",label:"Total Qty",format:v=>totalQty(v,"qty")},{key:"status",label:"Status"},{key:"creditStatus",label:"Credit"},{key:"baseAmount",label:"Base Amount"},{key:"taxAmount",label:"GST Amount"},{key:"totalAmount",label:"Grand Total"}])}
async function refreshJobs(){const r=await api("/api/production/job-cards");sel("jobStatusId",r,x=>`${x.jobNo} - ${x.status}`);render("jobList",r.map(x=>({...x,soNo:(state.refs.salesOrders.find(s=>s.id===String(x.soId))||{}).soNo||x.soId,machines:String(x.machineIds||"").split("|").filter(Boolean).map(mid=>ref("machines",mid)).join(", "),issuedMaterials:(x.materialIssues||[]).map(m=>`${ref("items",m.itemId)} x ${m.qty}`).join(" | ")})),[{key:"jobNo",label:"Job No"},{key:"soNo",label:"Sales Order"},{key:"machines",label:"Machines"},{key:"issuedMaterials",label:"Materials Issued"},{key:"date",label:"Date"},{key:"status",label:"Status"},{key:"currentStep",label:"Current Step"},{key:"routing",label:"Routing"}])}
async function refreshChallans(){const r=await api("/api/logistics/challans");state.refs.challans=r;bindSelectors();render("challanList",r,[{key:"challanNo",label:"Challan No"},{key:"soId",label:"SO",format:v=>(state.refs.salesOrders.find(x=>x.id===String(v))||{}).soNo||`#${v}`},{key:"date",label:"Date"},{key:"transporter",label:"Transporter"},{key:"dispatchStatus",label:"Dispatch Status"},{key:"freightCost",label:"Freight Cost"}])}
async function refreshDispatchDetails(){const r=await api("/api/logistics/challans");render("dispatchList",r.filter(x=>String(x.dispatchStatus||"").toUpperCase()!=="PENDING"),[{key:"challanNo",label:"Challan"},{key:"transporter",label:"Transporter"},{key:"vehicleNo",label:"Vehicle"},{key:"dispatchStatus",label:"Dispatch Status"},{key:"status",label:"Doc Status"},{key:"freightCost",label:"Freight Cost"}])}
async function refreshPurchaseInvoices(){const r=await api("/api/accounts/purchase-invoices");render("purchaseInvoiceList",r,[{key:"invoiceNo",label:"Invoice No"},{key:"poId",label:"PO",format:v=>(state.refs.purchaseOrders.find(x=>x.id===String(v))||{}).poNo||`#${v}`},{key:"grnId",label:"GRN",format:v=>(state.refs.grns.find(x=>x.id===String(v))||{}).grnNo||`#${v}`},{key:"vendorId",label:"Vendor",format:v=>ref("vendors",v)},{key:"lines",label:"Items (Source Lines)",format:v=>linesSummary(v,"qty","unitPrice")},{key:"lines",label:"Total Qty",format:v=>totalQty(v,"qty")},{key:"baseAmount",label:"Base Amount"},{key:"taxAmount",label:"GST Amount"},{key:"totalAmount",label:"Grand Total"},{key:"matchStatus",label:"3-Way Match"},{key:"status",label:"Status"}])}
async function refreshSalesInvoices(){const r=await api("/api/accounts/sales-invoices");render("salesInvoiceList",r,[{key:"invoiceNo",label:"Invoice No"},{key:"soId",label:"SO",format:v=>(state.refs.salesOrders.find(x=>x.id===String(v))||{}).soNo||`#${v}`},{key:"customerId",label:"Customer",format:v=>ref("customers",v)},{key:"lines",label:"Items (Source Lines)",format:v=>linesSummary(v,"qty","unitPrice")},{key:"lines",label:"Total Qty",format:v=>totalQty(v,"qty")},{key:"baseAmount",label:"Base Amount"},{key:"taxAmount",label:"GST Amount"},{key:"totalAmount",label:"Grand Total"},{key:"status",label:"Status"},{key:"receivedAmount",label:"Received"}])}
async function refreshLedger(){const [p,r]=await Promise.all([api("/api/accounts/payables"),api("/api/accounts/receivables")]);const pRows=p.map(x=>({...x,vendor:ref("vendors",x.vendorId)}));const rRows=r.map(x=>({...x,customer:ref("customers",x.customerId)}));$("ledgerList").innerHTML=`<h4 class="table-group-title">Accounts Payable</h4>${table(pRows,[{key:"invoiceId",label:"Invoice ID"},{key:"vendor",label:"Vendor"},{key:"amountDue",label:"Amount Due"},{key:"amountPaid",label:"Amount Paid"},{key:"status",label:"Status"}])}<h4 class="table-group-title" style="margin-top:12px;">Accounts Receivable</h4>${table(rRows,[{key:"invoiceId",label:"Invoice ID"},{key:"customer",label:"Customer"},{key:"amountDue",label:"Amount Due"},{key:"amountReceived",label:"Amount Received"},{key:"status",label:"Status"}])}`}
async function refreshEmployees(){const r=await api("/api/hrm-payroll/employees");state.refs.employees=r;bindSelectors();render("employeeList",r,[{key:"empCode",label:"Emp Code"},{key:"name",label:"Name"},{key:"department",label:"Department"},{key:"designation",label:"Designation"},{key:"joinDate",label:"Join Date"},{key:"baseSalary",label:"Base Salary"},{key:"active",label:"Active"}])}
async function refreshAttendance(){if(!state.refs.employees.length){state.refs.employees=await api("/api/hrm-payroll/employees")}const r=await api("/api/hrm-payroll/attendance");render("attendanceList",r,[{key:"employeeId",label:"Employee",format:v=>ref("employees",v)},{key:"date",label:"Date"},{key:"status",label:"Status"},{key:"workHours",label:"Work Hrs"},{key:"overtimeHours",label:"OT Hrs"},{key:"remarks",label:"Remarks"}])}
async function refreshLeaveRequests(){const r=await api("/api/hrm-payroll/leave-requests");state.refs.leaveRequests=r;bindSelectors();render("leaveList",r,[{key:"employeeId",label:"Employee",format:v=>ref("employees",v)},{key:"fromDate",label:"From"},{key:"toDate",label:"To"},{key:"leaveType",label:"Type"},{key:"status",label:"Status",format:v=>String(v||"").toUpperCase()},{key:"reason",label:"Reason"},{key:"approvedBy",label:"Updated By",format:v=>v?ref("users",v):"-"}])}
async function refreshPayrollRuns(){const r=await api("/api/hrm-payroll/payroll-runs");state.refs.payrollRuns=r;render("payrollList",r,[{key:"runNo",label:"Run No"},{key:"month",label:"Month"},{key:"employeeId",label:"Employee",format:v=>ref("employees",v)},{key:"baseSalary",label:"Base"},{key:"allowance",label:"Allowance"},{key:"deduction",label:"Deduction"},{key:"netPay",label:"Net Pay"},{key:"processedDate",label:"Processed Date"}])}
async function refreshAll(role){
 await loadRefs(role);
 const allowed=tabsForRole(role||state.user?.role);
 const tasks=[];
 if(allowed.includes("dashboard"))tasks.push(refreshDashboard());
 if(allowed.includes("procurement") && !isRequisitionOnlyRole(role||state.user?.role))tasks.push(refreshVendors(),refreshRequisitions(),refreshPurchaseOrders(),refreshGrns(),refreshQualityChecks(),refreshReorders());
 if(allowed.includes("inventory"))tasks.push(refreshItems(),refreshInventoryMasters(),refreshStock());
 if(allowed.includes("sales"))tasks.push(refreshCustomers(),refreshQuotations(),refreshSalesOrders());
 if(allowed.includes("production"))tasks.push(refreshMachines(),refreshJobs());
 if(allowed.includes("logistics"))tasks.push(refreshSalesOrders(),refreshChallans(),refreshDispatchDetails());
 if(allowed.includes("accounts"))tasks.push(refreshTaxes(),refreshPurchaseInvoices(),refreshSalesInvoices(),refreshLedger());
 if(allowed.includes("hrmPayroll"))tasks.push((async()=>{await refreshEmployees();if(isPrivilegedHrRole(role||state.user?.role))await refreshAttendance();await refreshLeaveRequests();await refreshPayrollRuns()})());
 await Promise.all(tasks);
 bindSelectors();
}

function setupForms(){
 $("approvePoId")?.addEventListener("change",showPoDetails);$("grnPoId")?.addEventListener("change",bindPoLines);$("grnPoLineId")?.addEventListener("change",syncGrnItemByPoLine);
 $("pinvPoId")?.addEventListener("change",syncPurchaseInvoiceSource);$("pinvGrnId")?.addEventListener("change",syncPurchaseInvoiceSource);$("sinvSoId")?.addEventListener("change",syncSalesInvoiceSource);
 $("jobMachineCategory")?.addEventListener("change",()=>filterMachinesForPicker("create"));
 $("jobStatusMachineCategory")?.addEventListener("change",()=>filterMachinesForPicker("status"));
 $("addJobMachineBtn")?.addEventListener("click",()=>addMachineSelection("create",$("jobMachinePicker")?.value));
 $("addJobStatusMachineBtn")?.addEventListener("click",()=>addMachineSelection("status",$("jobStatusMachinePicker")?.value));
 $("addJobMaterialBtn")?.addEventListener("click",addJobMaterialLine);
 $("addPrLineBtn")?.addEventListener("click",addRequisitionLine);
 $("poPrId")?.addEventListener("change",syncPoFromRequisition);
 document.addEventListener("click",e=>{const btn=e.target?.closest?.(".remove-machine-btn");if(!btn)return;removeMachineSelection(btn.dataset.machineKey,btn.dataset.machineId);});
 document.addEventListener("click",e=>{const btn=e.target?.closest?.(".remove-job-material-btn");if(!btn)return;removeJobMaterialLine(btn.dataset.index);});
 document.addEventListener("click",e=>{const btn=e.target?.closest?.(".remove-pr-line-btn");if(!btn)return;removeRequisitionLine(btn.dataset.index);});
 document.addEventListener("input",e=>{const input=e.target?.closest?.(".po-draft-field-input");if(!input)return;updatePoDraftField(input.dataset.index,input.dataset.field,input.value);});
 $("jobStatusId")?.addEventListener("change",async e=>{try{const jobs=await api("/api/production/job-cards");const j=jobs.find(x=>String(x.id)===String(e.target.value));if(!j)return;const f=$("jobStatusForm");if(!f)return;if(f.elements.status)f.elements.status.value=j.status||"IN_PROGRESS";if(f.elements.currentStep)f.elements.currentStep.value=j.currentStep||"PRINT";machineSelections.status=String(j.machineIds||"").split("|").filter(Boolean);renderMachineList("status");if(f.elements.remarks&&j.remarks!==undefined)f.elements.remarks.value=j.remarks||"";}catch{}});
 $("loginForm").addEventListener("submit",async e=>{e.preventDefault();try{const r=await fetch("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form(e.target))}).then(x=>x.json());if(!r.user)throw new Error(r.error||"Login failed");setSession(r.user,r.authHeaders);setAppShellVisible(true);applyRoleAccess(r.user.role);renderProfile();await refreshAll(r.user.role);toast("Login successful")}catch(err){toast(err.message,true)}});
 $("logoutBtn")?.addEventListener("click",logout);
 $("itemForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);await api("/api/masters/items",{method:"POST",body:JSON.stringify({...d,sku:skuByCat(d.sku,d.category),active:true})});await refreshItems();bindSelectors();toast("Item created")}catch(err){toast(err.message,true)}});
 $("vendorForm").addEventListener("submit",async e=>{e.preventDefault();try{await api("/api/masters/vendors",{method:"POST",body:JSON.stringify(form(e.target))});await Promise.all([refreshVendors(),refreshLedger()]);bindSelectors();toast("Vendor created")}catch(err){toast(err.message,true)}});
 $("customerForm").addEventListener("submit",async e=>{e.preventDefault();try{await api("/api/masters/customers",{method:"POST",body:JSON.stringify(form(e.target))});await Promise.all([refreshCustomers(),refreshSalesOrders(),refreshLedger()]);bindSelectors();toast("Customer created")}catch(err){toast(err.message,true)}});
 $("prForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);const lines=[...requisitionDraft];if(!lines.length)throw new Error("Add at least one item before creating requisition");const requestedBy=d.requestedBy||String(state.user?.id||"").trim();if(!requestedBy)throw new Error("Login required to create requisition");if(!d.vendorId)throw new Error("Select a vendor");await api("/api/procurement/requisitions",{method:"POST",body:JSON.stringify({requestedBy,vendorId:d.vendorId,lines})});requisitionDraft.length=0;renderRequisitionDraft();e.target.reset();bindSelectors();toast("PR created");await refreshRequisitions()}catch(err){toast(err.message,true)}});
 $("poForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);const lines=poDraft.map(line=>({prLineId:String(line.prLineId||"").trim(),unitRate:String(line.unitRate||"").trim(),taxRate:String(line.taxRate||"").trim()}));if(!d.prId)throw new Error("Select a purchase requisition");if(!d.vendorId)throw new Error("Selected requisition does not have a vendor");if(!lines.length)throw new Error("No requisition items available for purchase order");if(lines.some(line=>!line.prLineId))throw new Error("Each PO line must be linked to a purchase requisition line");if(lines.some(line=>!Number.isFinite(Number(line.unitRate))||Number(line.unitRate)<=0))throw new Error("Each unit rate must be greater than zero");if(lines.some(line=>!Number.isFinite(Number(line.taxRate))||Number(line.taxRate)<0))throw new Error("GST % must be zero or greater");await api("/api/procurement/purchase-orders",{method:"POST",body:JSON.stringify({prId:d.prId,lines})});poDraft.length=0;renderPoDraft();e.target.reset();bindSelectors();toast("PO created");await refreshPurchaseOrders()}catch(err){toast(err.message,true)}});
 $("approvePoForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);await api(`/api/procurement/purchase-orders/${d.poId}/approve`,{method:"POST"});await refreshPurchaseOrders();toast("PO approved")}catch(err){toast(err.message,true)}});
 $("grnForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);const po=state.refs.purchaseOrders.find(x=>String(x.id)===String(d.poId));const poLine=(po?.lines||[]).find(x=>String(x.id)===String(d.poLineId));if(!poLine)throw new Error("Select a valid PO line");const typed=itemId(d.itemSearch);const iid=String(poLine.itemId);if(typed&&String(typed)!==iid)throw new Error("Selected item must match the chosen PO line");await api("/api/procurement/grns",{method:"POST",body:JSON.stringify({poId:d.poId,vendorId:d.vendorId,warehouseId:d.warehouseId,qualityStatus:d.qualityStatus,lines:[{poLineId:d.poLineId,itemId:iid,qtyAccepted:d.qtyAccepted,qtyRejected:d.qtyRejected,lotNo:"AUTO-LOT"}]})});await Promise.all([refreshReorders(),refreshStock(),refreshPurchaseOrders(),refreshGrns(),refreshQualityChecks()]);toast("GRN posted")}catch(err){toast(err.message,true)}});
 $("issueForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target),iid=itemId(d.itemSearch);if(!iid)throw new Error("Select a valid item");await api("/api/inventory/issue",{method:"POST",body:JSON.stringify({itemId:iid,warehouseId:d.warehouseId,qty:d.qty,referenceType:d.purpose,referenceId:`P-${Date.now()}`,remarks:`Purpose: ${d.purpose}`})});await refreshStock();toast("Stock issued")}catch(err){toast(err.message,true)}});
 $("transferForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target),iid=itemId(d.itemSearch);if(!iid)throw new Error("Select a valid item");await api("/api/inventory/transfer",{method:"POST",body:JSON.stringify({...d,itemId:iid})});await refreshStock();toast("Stock transferred")}catch(err){toast(err.message,true)}});
 $("wastageForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target),iid=itemId(d.itemSearch);if(!iid)throw new Error("Select a valid item");await api("/api/inventory/wastage",{method:"POST",body:JSON.stringify({...d,itemId:iid})});await refreshStock();toast("Wastage posted")}catch(err){toast(err.message,true)}});
 $("quotationForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target),iid=itemId(d.itemSearch);if(!iid)throw new Error("Select a valid item");await api("/api/sales/quotations",{method:"POST",body:JSON.stringify({customerId:d.customerId,lines:[{itemId:iid,qty:d.qty,unitPrice:d.unitPrice,taxRate:taxRate(d.hsnTaxId)}]})});await refreshQuotations();toast("Quotation created")}catch(err){toast(err.message,true)}});
 $("salesOrderForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target),iid=itemId(d.itemSearch);if(!iid)throw new Error("Select a valid item");await api("/api/sales/sales-orders",{method:"POST",body:JSON.stringify({customerId:d.customerId,lines:[{itemId:iid,qty:d.qty,unitPrice:d.unitPrice,taxRate:taxRate(d.hsnTaxId)}]})});await refreshSalesOrders();toast("Sales order created")}catch(err){toast(err.message,true)}});
 $("jobCardForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);const machineIds=[...machineSelections.create];if(!machineIds.length)throw new Error("Select at least one machine");await api("/api/production/job-cards",{method:"POST",body:JSON.stringify({...d,machineIds,materialIssues:[...jobMaterialDraft]})});machineSelections.create=[];renderMachineList("create");jobMaterialDraft.length=0;renderJobMaterialList();await refreshJobs();toast("Job card created")}catch(err){toast(err.message,true)}});
 $("jobStatusForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);const machineIds=[...machineSelections.status];await api(`/api/production/job-cards/${d.jobId}/status`,{method:"PATCH",body:JSON.stringify({status:d.status,currentStep:d.currentStep,machineIds:machineIds.length?machineIds:undefined,remarks:d.remarks})});await refreshJobs();toast("Job status updated")}catch(err){toast(err.message,true)}});
 $("machineForm").addEventListener("submit",async e=>{e.preventDefault();try{await api("/api/masters/machines",{method:"POST",body:JSON.stringify({...form(e.target),active:true})});await refreshMachines();toast("Machine created")}catch(err){toast(err.message,true)}});
 $("challanForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);const v=state.refs.vendors.find(x=>String(x.id)===String(d.transporterVendorId));await api("/api/logistics/challans",{method:"POST",body:JSON.stringify({soId:d.soId,transporter:v?v.name:""})});await Promise.all([refreshChallans(),refreshDispatchDetails()]);toast("Delivery challan created")}catch(err){toast(err.message,true)}});
 $("dispatchForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);const v=state.refs.vendors.find(x=>String(x.id)===String(d.transporterVendorId));await api(`/api/logistics/challans/${d.challanId}/dispatch`,{method:"PATCH",body:JSON.stringify({challanId:d.challanId,transporter:v?v.name:"",vehicleNo:d.vehicleNo,freightCost:d.freightCost})});await Promise.all([refreshChallans(),refreshDispatchDetails()]);toast("Dispatch updated")}catch(err){toast(err.message,true)}});
 $("purchaseInvoiceForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);await api("/api/accounts/purchase-invoices",{method:"POST",body:JSON.stringify({poId:d.poId,grnId:d.grnId})});await Promise.all([refreshLedger(),refreshPurchaseInvoices()]);toast("Purchase invoice posted from PO/GRN")}catch(err){toast(err.message,true)}});
 $("salesInvoiceForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);await api("/api/accounts/sales-invoices",{method:"POST",body:JSON.stringify({soId:d.soId})});await Promise.all([refreshLedger(),refreshSalesInvoices()]);toast("Sales invoice posted from SO")}catch(err){toast(err.message,true)}});
 $("taxForm").addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);await api("/api/masters/taxes",{method:"POST",body:JSON.stringify({code:d.code,rate:d.rate,description:d.name,name:d.name})});await refreshTaxes();bindSelectors();toast("HSN code created")}catch(err){toast(err.message,true)}});
 $("employeeForm")?.addEventListener("submit",async e=>{e.preventDefault();try{await api("/api/hrm-payroll/employees",{method:"POST",body:JSON.stringify(form(e.target))});await refreshEmployees();await refreshAttendance();toast("Employee created")}catch(err){toast(err.message,true)}});
 $("attendanceForm")?.addEventListener("submit",async e=>{e.preventDefault();try{await api("/api/hrm-payroll/attendance",{method:"POST",body:JSON.stringify(form(e.target))});await refreshAttendance();toast("Attendance saved")}catch(err){toast(err.message,true)}});
 $("leaveForm")?.addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);const employeeId=d.employeeId||String(state.user?.id||"").trim();if(!employeeId)throw new Error("Login required to create leave request");const body={employeeId,fromDate:d.fromDate,toDate:d.toDate,leaveType:d.leaveType,reason:d.reason};await api("/api/hrm-payroll/leave-requests",{method:"POST",body:JSON.stringify(body)});await refreshLeaveRequests();toast("Leave request created")}catch(err){toast(err.message,true)}});
 $("leaveApproveForm")?.addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);if(!d.leaveId)throw new Error("No pending leave request selected");await api(`/api/hrm-payroll/leave-requests/${d.leaveId}`,{method:"PATCH",body:JSON.stringify({status:String(d.status||"").toUpperCase()})});await refreshLeaveRequests();toast("Leave request updated")}catch(err){toast(err.message,true)}});
 $("payrollForm")?.addEventListener("submit",async e=>{e.preventDefault();try{const d=form(e.target);await api("/api/hrm-payroll/payroll-runs/process",{method:"POST",body:JSON.stringify({month:d.month})});await refreshPayrollRuns();toast("Payroll processed")}catch(err){toast(err.message,true)}});
 [["loadUsers",refreshUsers],["loadVendors",refreshVendors],["loadRequisitions",refreshRequisitions],["loadPurchaseOrders",refreshPurchaseOrders],["loadGrns",refreshGrns],["loadQualityChecks",refreshQualityChecks],["loadReorders",refreshReorders],["loadItems",refreshItems],["loadInventoryMasters",refreshInventoryMasters],["loadStock",refreshStock],["loadCustomers",refreshCustomers],["loadQuotations",refreshQuotations],["loadSalesOrders",refreshSalesOrders],["loadMachines",refreshMachines],["loadJobs",refreshJobs],["loadChallans",refreshChallans],["loadDispatch",refreshDispatchDetails],["loadTaxes",refreshTaxes],["loadPurchaseInvoices",refreshPurchaseInvoices],["loadSalesInvoices",refreshSalesInvoices],["loadLedger",refreshLedger],["loadEmployees",refreshEmployees],["loadAttendance",refreshAttendance],["loadLeaveRequests",refreshLeaveRequests],["loadPayrollRuns",refreshPayrollRuns]].forEach(([id,fn])=>$(id)?.addEventListener("click",()=>fn().catch(e=>toast(e.message,true))));
 renderRequisitionDraft();renderPoDraft();
}

async function init(){setupNav();setupForms();setupClickTracking();try{setSession({name:"Not logged in",role:"guest"},{});applyRoleAccess("guest");setAppShellVisible(false);resetMachineSelections();renderProfile();closeProfileMenu();applyComboInputs();observeSemanticInputs();}catch(e){toast(e.message,true)}}
document.getElementById("topProfileBtn")?.addEventListener("click",openProfileFromIcon);
document.addEventListener("click",e=>{const m=$("profileMenu");const b=$("topProfileBtn");if(!m||m.hidden)return;if(m.contains(e.target)||b?.contains(e.target))return;closeProfileMenu();});
init();
