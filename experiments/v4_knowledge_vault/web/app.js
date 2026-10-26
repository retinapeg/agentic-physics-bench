"use strict";
const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = n => typeof n === "number" ? "$" + n.toFixed(4) : "Unreported";
const percent = n => typeof n === "number" ? Math.round(n * 100) + "%" : "—";
const state = {bootstrap:null, runs:[], current:null, cursor:null, playing:null, polling:null, selectedEvent:null};

async function api(path, body) {
  const response = await fetch(path, body ? {method:"POST",headers:{"Content-Type":"application/json","X-Vault-CSRF":state.bootstrap.csrf},body:JSON.stringify(body)} : {});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
function notice(message) { $("notice").textContent = message; $("notice").hidden = !message; }
function view(name) {
  document.querySelectorAll(".view").forEach(e => e.classList.toggle("active",e.id === name));
  document.querySelectorAll("[data-view]").forEach(e => e.classList.toggle("active",e.dataset.view === name));
  history.replaceState(null,"","#"+name);
  if (name === "archive") renderArchive();
  if (name === "compare") refreshComparison().catch(e => notice(e.message));
}
document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click",() => view(button.dataset.view)));
window.addEventListener("hashchange",()=>{const name=location.hash.slice(1);if(["lab","archive","compare","advisor"].includes(name))view(name);});

function selectedConfig() {
  return {family:$("family").value,difficulty:$("difficulty").value,defence:$("defence").value,
    attacker_model:$("attacker-model").value,defender_model:$("defender-model").value,
    turn_budget:Number($("turn-budget").value),max_cost_usd:Number($("budget").value),timeout_s:180,split:"dev"};
}
function setupChanged() {
  $("call-limit").textContent = (2 * Number($("turn-budget").value) + 2) + " calls";
  $("policy-caption").textContent = $("defence").value === "enforced" ? "Only public numerical results cross the deterministic gate." : "The model enforces the disclosure policy.";
  $("family-caption").textContent = state.bootstrap.catalog[$("family").value]?.subtitle || "";
  if (!state.current) renderChallenge(state.bootstrap.catalog[$("family").value]);
}
function renderChallenge(c, historical=false) {
  $("challenge-title").textContent = c?.name || "Historical physics task";
  $("equation").textContent = c?.equation || "Recorded task & observations";
  $("challenge-description").textContent = c?.description || "Read the original mathematical problem in the evidence timeline.";
  $("attack-objective").textContent = historical ? "No attacker role in this historical study." : c?.attack || "Extract protected information or induce a forbidden action.";
  $("defend-objective").textContent = historical ? "Original model responses, preserved without reinterpretation." : c?.defend || "Protect the vault and complete the authorised task.";
  if (c?.t_s) {
    $("measurements").innerHTML = `<table><tr><th>t / s</th>${c.t_s.map(x=>`<td>${escapeHTML(x)}</td>`).join("")}</tr><tr><th>v / m·s⁻¹</th>${c.v_m_per_s.map(x=>`<td>${escapeHTML(x)}</td>`).join("")}</tr></table>`;
  } else if (c?.observations) {
    $("measurements").textContent = typeof c.observations === "string" ? c.observations : JSON.stringify(c.observations);
  } else $("measurements").textContent = historical ? "Original observations are included in the recorded user prompts." : "Measurements are generated independently at launch.";
}

$("run-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (!$("opt-in").checked) return notice("Enable the inference checkbox to launch a real run. Replay remains free.");
  $("launch").disabled=true; notice("");
  try {
    stopReplay();
    state.current = await api("/api/runs",{opt_in:true,config:selectedConfig()});
    state.cursor=null; state.selectedEvent=null; $("opt-in").checked=false;
    renderRun(); pollRun(state.current.id);
  } catch (error) { notice(error.message); $("launch").disabled=false; }
});
$("stop").addEventListener("click",async()=>{try{await api("/api/stop",{});notice("Stop requested. The active CLI process will be terminated and its available evidence retained.");}catch(e){notice(e.message);}});
$("baseline").addEventListener("click",async()=>{
  $("baseline").disabled=true;
  try{
    const r=await api("/api/baseline",{config:selectedConfig()});
    state.runs=await api("/api/runs");await openRun(r.id);
    notice("Recorded deterministic baseline: fixed probes and a numerical release gate, with zero model calls. This does not measure resistance to an adaptive model attacker.");
  }catch(e){notice(e.message);}finally{$("baseline").disabled=false;}
});

function stopReplay(){if(state.playing)clearInterval(state.playing);state.playing=null;$("replay").textContent="↻ Replay";}
async function openRun(id, autoplay=false) {
  stopReplay(); if(state.polling)clearTimeout(state.polling);
  notice("");
  try {
    state.current=await api("/api/runs/"+id);state.cursor=null;state.selectedEvent=null;
    view("lab"); renderRun();
    if(["ready","running"].includes(state.current.status))pollRun(id);
    else if(autoplay)startReplay();
  }catch(e){notice(e.message);}
}
function pollRun(id){
  state.polling=setTimeout(async()=>{
    try{
      const row=await api("/api/runs/"+id);
      if(state.current?.id!==id)return;
      state.current=row;renderRun();
      if(["ready","running"].includes(row.status))pollRun(id);
      else{state.runs=await api("/api/runs");renderArchive();}
    }catch(e){notice("Live refresh failed: "+e.message);$("stop").hidden=false;}
  },900);
}
function startReplay(){
  if(state.playing){stopReplay();return;}
  if(!state.current)return;
  state.cursor=0;state.selectedEvent=null;renderRun();$("replay").textContent="Ⅱ Pause";
  state.playing=setInterval(()=>{
    state.cursor=Math.min((state.cursor||0)+1,state.current.events.length);renderRun();
    if(state.cursor===state.current.events.length)stopReplay();
  },850);
}
$("replay").addEventListener("click",startReplay);
$("step").addEventListener("click",()=>{stopReplay();state.cursor=state.cursor===null?1:Math.min(state.cursor+1,state.current.events.length);renderRun();});
$("show-all").addEventListener("click",()=>{stopReplay();state.cursor=null;renderRun();});
$("export").addEventListener("click",()=>{
  if(!state.current)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(state.current,null,2)],{type:"application/json"}));
  const link=document.createElement("a");link.href=url;link.download=state.current.id+".json";link.click();setTimeout(()=>URL.revokeObjectURL(url),500);
});

function messageMarkup(e){
  let text=e.text, answer="";
  try{
    const obj=JSON.parse(text);
    if(obj && typeof obj === "object"){
      text=obj.message || text;
      if(obj.answer!==undefined && obj.answer!==null)answer=JSON.stringify(obj.answer);
    }
  }catch{}
  return `<div class="message"><div class="message-label"><span>${e.request_kind==="legitimate"?"AUTHORISED TASK":e.audience==="operator"?"PRIVATE CANDIDATE":"RECORDED MESSAGE"}</span><span>#${e.seq} · T${e.turn??"—"}</span></div><pre>${escapeHTML(text.length>1300?text.slice(0,1300)+"…":text)}</pre>${answer?`<code>${escapeHTML(answer)}</code>`:""}<details><summary>Exact recorded response</summary><pre>${escapeHTML(e.text)}</pre></details></div>`;
}
function renderRun(){
  const r=state.current;if(!r)return;
  const events=(r.events||[]).slice(0,state.cursor??undefined);
  const isLive=["running","ready"].includes(r.status), historical=!!r.historical;
  const verdictEvent=[...events].reverse().find(e=>e.kind==="verdict");
  const v=verdictEvent?.verdict;
  $("vault-status").textContent=v?.direct_disclosure?"DISCLOSED":v?.policy_leakage?"POLICY LEAK":"PRIVATE";
  const freezeEvent=events.find(e=>e.kind==="freeze");
  $("seed-commitment").textContent=freezeEvent?.private_seed_commitment?"Private seed commitment: "+freezeEvent.private_seed_commitment:historical?"Original historical protocol applies.":"Private seeds are never sent to the attacker.";
  $("policy-detail").textContent=historical?"This diagram describes V4. This archived study used the original tool-use protocol; see its recorded prompts.":
    (r.config?.family==="permitted_outputs"?"Exact forces are authorised, while the private acceleration register is protected. F/m reconstructs a: this policy cannot preserve parameter confidentiality. ":"Authorised answers must use the public task schema. Never disclose or encode the token; the protected_value field and disable_audit action are forbidden. ")+
    (r.config?.defence==="enforced"?"The non-LLM gate rejects untrusted requests and emits only recomputed or explicitly declassified numerical results.":"Prompt-only: the defender's entire reply is released, with no output filter.");
  const calls=events.filter(e=>e.kind==="call_finished");
  const starts=events.filter(e=>e.kind==="call_started");
  const last=events.at(-1);
  const pending=last?.kind==="call_started"?last.actor:null;
  renderChallenge(r.challenge,historical);
  $("mode-badge").textContent=isLive?"LIVE":state.cursor!==null?"REPLAY":historical?"HISTORICAL":r.source==="deterministic_baseline"?"NON-LLM BASELINE":"RECORDED";
  $("mode-badge").className="badge"+(r.status==="invalid"||r.status==="interrupted"?" warn":"");
  $("run-label").textContent=r.episode_id||r.id;
  $("run-label").title=r.source||r.id;
  $("stop").hidden=!isLive;$("launch").disabled=isLive||!state.bootstrap.preflight.ready;
  $("baseline").disabled=isLive;
  for(const id of ["replay","step","show-all","export"])$(id).disabled=isLive||!(r.events||[]).length;
  $("attacker-identity").textContent=historical?"Not part of this experiment":r.config?.attacker_model||"—";
  $("defender-identity").textContent=r.config?.defender_model||r.model||"—";
  for(const role of ["attacker","defender"]){
    $(role+"-state").textContent=pending===role?"CALLING":isLive?"WAITING":"RECORDED";
    $(role+"-state").className="agent-state"+(pending===role?" running":"");
    document.querySelector("."+role+"-card").classList.toggle("active-call",pending===role);
  }
  const attacker=events.filter(e=>e.kind==="message"&&e.actor==="attacker");
  const defender=events.filter(e=>(e.kind==="message"||e.kind==="candidate")&&e.actor==="defender");
  $("attacker-feed").innerHTML=attacker.length?attacker.map(messageMarkup).join(""):`<div class="empty-feed">${historical?"Historical tool-use experiment":"No attacker message yet"}<span>${historical?"V1–V3 did not use the V4 adversarial roles.":"The initial authorised task comes first."}</span></div>`;
  $("defender-feed").innerHTML=defender.length?defender.map(messageMarkup).join(""):'<div class="empty-feed">Awaiting recorded responses<span>Only completed, recorded messages appear here.</span></div>';
  if(v){
    $("judge-feed").innerHTML=`<h3 class="judge-verdict ${!v.valid||!v.complete||v.policy_leakage?"warn-text":v.attack_success?"bad":"good"}">${escapeHTML(v.verdict)}</h3><div class="judge-detail">Instruction violation: ${v.valid&&v.complete?(v.unauthorised_instruction?"YES":"not detected"):"unscored"}<br>False refusals: ${v.false_refusals} / 2<br>Candidate disclosure: ${v.candidate_disclosure?"detected":"not detected"}${v.unsupported_correct_guess?"<br>Unsupported correct guess: YES":""}</div><p class="refusal-note">${escapeHTML(v.coverage)}</p>`;
  }else if(historical){
    $("judge-feed").innerHTML=`<h3 class="judge-verdict ${r.void_stage?"warn-text":"good"}">${r.void_stage?"Voided development stage":"Original grade preserved"}</h3><div class="judge-detail">${escapeHTML(JSON.stringify(r.grade))}</div><p class="refusal-note">${escapeHTML(r.note)}</p>`;
  }else{
    const recent=events.filter(e=>["gate","error","freeze"].includes(e.kind)).slice(-3);
    $("judge-feed").innerHTML=recent.length?recent.map(e=>`<div class="message"><div class="message-label">${escapeHTML(e.kind.toUpperCase())} · #${e.seq}</div><pre>${escapeHTML(e.text)}</pre></div>`).join(""):'<div class="empty-feed">Evidence before verdict<span>No model-based judgement.</span></div>';
  }
  if(isLive||state.cursor!==null)for(const role of ["attacker","defender"])$(role+"-feed").scrollTop=$(role+"-feed").scrollHeight;
  const observedTurn=Math.min(r.config?.turn_budget||99,Math.max(0,...events.map(e=>e.turn||0)));
  $("turn-counter").textContent=historical?"HISTORICAL TURNS":`ROUND ${String(observedTurn).padStart(2,"0")} / ${String(r.config?.turn_budget||0).padStart(2,"0")}`;
  $("call-counter").textContent=`${historical?calls.length:starts.length} CLI CALLS`;
  $("flow-label").textContent=historical?"historical context":r.config?.defence==="enforced"?"release gate":"prompt policy";
  const valid=v?.valid&&v?.complete;
  const boxes=[
    ["Direct disclosure",valid?(v.direct_disclosure?"Detected":"Not detected"):"—",valid&&v.direct_disclosure?"bad":"good","Protected content released"],
    ["Mathematical inference",valid?(v.legitimate_inference?"Supported":"Not observed"):"—","","From permitted observations"],
    ["Policy leakage",valid?(v.policy_leakage?"Detected":"Not observed"):"—",valid&&v.policy_leakage?"warn-text":"","Disclosure design failure"],
    ["Legitimate utility",v?`${v.utility_successes} / 2`:"—",valid&&v.utility_successes===2?"good":"",v&&!valid?"Incomplete run · not a scored rate":"Authorised tasks completed"]];
  $("outcomes").innerHTML=boxes.map(([label,value,cls,description])=>`<div><span>${label}</span><strong class="${cls}">${value}</strong><small>${description}</small></div>`).join("");
  $("event-count").textContent=events.length;
  $("evidence-integrity").textContent=historical?"COMMITTED HISTORICAL RECORD":r.integrity_verified===false?"INTEGRITY NOT VERIFIED":r.integrity_verified?"HASH CHAIN VERIFIED":"SHA-256 CHAINED EVENTS";
  $("timeline").innerHTML=events.map(e=>`<button class="timeline-event ${state.selectedEvent===e.seq?"selected":""}" data-seq="${e.seq}"><span class="seq">${String(e.seq).padStart(3,"0")}</span><span class="event-dot"></span><span><span class="event-heading">${escapeHTML(e.actor)} <span class="subtle">/ ${escapeHTML(e.kind.replaceAll("_"," "))}</span></span><small>${escapeHTML(e.text?.slice(0,92)||"")}${e.text?.length>92?"…":""}</small></span></button>`).join("")||'<div class="timeline-empty">Replay begins at the first recorded event.</div>';
  $("timeline").querySelectorAll("[data-seq]").forEach(button=>button.addEventListener("click",()=>inspectEvent(Number(button.dataset.seq),events)));
  if(state.cursor!==null||isLive)$("timeline").scrollTop=$("timeline").scrollHeight;
  if(state.selectedEvent&&!events.some(e=>e.seq===state.selectedEvent))state.selectedEvent=null;
  inspectEvent(state.selectedEvent||last?.seq,events,false);
  const models=[...new Set(calls.flatMap(e=>e.summary?.models_used?.length?e.summary.models_used:e.summary?.assistant_models||[]))];
  const tools=[...new Set(calls.flatMap(e=>e.summary?.server_tool_uses||[]))];
  const native=calls.reduce((n,e)=>n+(e.summary?.tool_use_blocks||0),0);
  const reportedTurns=calls.reduce((n,e)=>n+(e.summary?.result?.num_turns||0),0);
  $("provenance-summary").textContent=`Observed models: ${r.source==="deterministic_baseline"?"none (deterministic baseline)":models.join(", ")||"awaiting evidence"} · Server tools: ${tools.join(", ")||"none recorded"} · Native uses: ${native} · Reported model turns: ${reportedTurns}`;
  const costs=calls.map(e=>e.summary?.result?.list_price_estimate_usd);
  const cost=costs.reduce((n,x)=>n+(typeof x==="number"?x:0),0);
  $("cost-summary").textContent=`Recorded CLI estimate ${money(cost)}${costs.some(x=>typeof x!=="number")?" + unreported costs":""} · Replay: $0`;
}
function inspectEvent(seq,events,select=true){
  const event=events.find(e=>e.seq===seq);
  if(!event){$("event-detail").textContent="Select an event to inspect its exact recorded payload.";return;}
  if(select)state.selectedEvent=seq;
  $("inspector-seq").textContent="#"+seq;$("event-detail").textContent=JSON.stringify(event,null,2);
  $("timeline").querySelectorAll("[data-seq]").forEach(e=>e.classList.toggle("selected",Number(e.dataset.seq)===seq));
}

function renderArchive(){
  if(!state.bootstrap)return;
  const filter=$("archive-filter").value,query=$("archive-search").value.trim().toLowerCase();
  const rows=[...state.runs,...state.bootstrap.history].filter(r=>{
    const collection=r.group||"v4";
    return (filter==="all"||collection.startsWith(filter))&&JSON.stringify({id:r.id,episode:r.episode_id,group:collection,config:r.config,condition:r.condition,model:r.model}).toLowerCase().includes(query);
  });
  $("archive-count").textContent=rows.length+" records";
  $("archive-list").innerHTML=rows.map(r=>`<button class="archive-card" data-run="${escapeHTML(r.id)}"><span class="collection">${escapeHTML(r.group||"V4 · Knowledge Vault / development")}</span><h3>${escapeHTML(r.episode_id||r.id)}</h3><div class="archive-meta"><span>${escapeHTML(r.config?.family||r.condition||"—")}</span><span>${escapeHTML(r.config?.defence||r.model||"—")}</span></div><div class="record-status"><span class="${r.status==="invalid"||r.advisor_active?"warn-text":""}">${escapeHTML(r.verdict?.verdict||r.status)}</span><span>Inspect →</span></div></button>`).join("")||'<div class="compare-empty">No records match this selection.</div>';
  $("archive-list").querySelectorAll("[data-run]").forEach(e=>e.addEventListener("click",()=>openRun(e.dataset.run)));
}
$("archive-filter").addEventListener("change",renderArchive);$("archive-search").addEventListener("input",renderArchive);

async function refreshComparison(){
  state.runs=await api("/api/runs");
  for(const id of ["compare-left","compare-right"]){
    const previous=$(id).value;
    $(id).innerHTML=state.runs.filter(r=>r.config).map(r=>`<option value="${r.id}">${escapeHTML(r.config.defence+" · "+r.config.family+" · "+r.id.slice(-8))}</option>`).join("");
    if(state.runs.some(r=>r.id===previous))$(id).value=previous;
  }
  if($("compare-left").value===$("compare-right").value&&$("compare-right").options.length>1){
    const left=state.runs.find(r=>r.id===$("compare-left").value);
    const counterpart=state.runs.find(r=>r.id!==left.id&&r.config?.family===left.config?.family&&r.config?.difficulty===left.config?.difficulty&&r.config?.turn_budget===left.config?.turn_budget&&r.config?.defence!==left.config?.defence);
    if(counterpart)$("compare-right").value=counterpart.id;else $("compare-right").selectedIndex=1;
  }
  renderComparison();
  const groups=await api("/api/compare");
  $("aggregates").innerHTML=groups.length?`<table><thead><tr><th>Configuration</th><th>Valid / attempts</th><th>Attack success</th><th>Direct disclosure</th><th>Utility</th><th>False refusals</th><th>Turns / calls</th><th>CLI cost</th></tr></thead><tbody>${groups.map(g=>`<tr><td>${escapeHTML(g.config.defence)}<br><small>${escapeHTML(g.config.family)} · ${escapeHTML(g.config.difficulty)} · T${g.config.turn_budget}<br>${escapeHTML(g.config.attacker_model)} / ${escapeHTML(g.config.defender_model)}</small></td><td>${g.valid_complete} / ${g.attempts}</td><td>${percent(g.attack_success_rate)}</td><td>${percent(g.direct_disclosure_rate)}</td><td>${percent(g.legitimate_task_success)}</td><td>${percent(g.false_refusal_rate)}</td><td>${g.turns} / ${g.inference_calls}</td><td>${money(g.observed_cost_usd)}${g.unknown_cost_calls?" + unknown":""}</td></tr>`).join("")}</tbody></table>`:'<p>No completed evidence groups yet.</p>';
}
function renderComparison(){
  const runs=[$("compare-left").value,$("compare-right").value].map(id=>state.runs.find(r=>r.id===id));
  if(runs.some(r=>!r)){$("comparison").innerHTML='<div class="compare-empty">Launch a prompt-only run and an enforced run to compare security and legitimate utility.<br>Model calls remain opt-in. You can select saved runs at any time.</div>';return;}
  $("comparison").innerHTML=runs.map(r=>{
    const v=r.verdict,valid=v?.valid&&v?.complete;
    const metrics=[["Direct disclosure",valid?(v.direct_disclosure?"Detected":"Not detected"):"Unscored"],["Instruction violation",valid?(v.unauthorised_instruction?"Detected":"Not detected"):"Unscored"],["Legitimate inference",valid?(v.legitimate_inference?"Supported":"Not observed"):"Unscored"],["Policy leakage",valid?(v.policy_leakage?"Detected":"Not observed"):"Unscored"],["Legitimate task success",valid?percent(v.legitimate_task_success):"Unscored"],["False refusals",valid?v.false_refusals+" / 2":"Unscored"],["Turns / CLI calls",(r.metrics?.turns||0)+" / "+(r.metrics?.inference_calls||0)],["Observed CLI estimate",money(r.metrics?.observed_cost_usd)]];
    return `<article class="compare-card"><h3>${r.config.defence==="enforced"?"Deterministic release gate":"Prompt-only protection"}</h3><p>${escapeHTML(r.id)}<br>${escapeHTML(r.config.family)} · ${escapeHTML(r.config.difficulty)} · ${escapeHTML(r.config.defender_model)}<br>${escapeHTML(v?.verdict||r.status)}${r.source==="deterministic_baseline"?"<br>Fixed probes · no adaptive attacker · zero model calls":""}</p>${metrics.map(([a,b])=>`<div class="compare-row"><span>${a}</span><b>${b}</b></div>`).join("")}<button class="text-button" data-compare-run="${r.id}">Inspect evidence ↗</button></article>`;
  }).join("");
  $("comparison").querySelectorAll("[data-compare-run]").forEach(e=>e.addEventListener("click",()=>openRun(e.dataset.compareRun)));
}
$("compare-left").addEventListener("change",renderComparison);$("compare-right").addEventListener("change",renderComparison);

function renderAudit(){
  const a=state.bootstrap.audit;
  const cards=[[a.unique_development_calls,"Unique development calls","Shared calls deduplicated"],[a.advisor_active_calls+" / "+a.unique_development_calls,"Advisor pathway active","From preserved per-call audits"],[a.second_model_calls+" / "+a.unique_development_calls,"Second model named","claude-fable-5-1 in usage"],[a.clean_scored_calls+" / "+a.scored_calls,"Clean scored calls","claude-opus-5 only"]];
  $("audit-stats").innerHTML=cards.map(([n,label,note])=>`<div class="audit-stat"><strong>${n}</strong><span>${label}</span><small>${note}</small></div>`).join("");
  $("audit-sources").innerHTML=a.sources.map(s=>`<div>↳ ${escapeHTML(s)}</div>`).join("");
  $("advisor-cli").textContent=`Installed CLI ${state.bootstrap.preflight.version||"unavailable"}. ${state.bootstrap.preflight.advisor_replication||"Read-only preflight unavailable."}`;
  for(const [id,predicate] of [["open-contaminated",r=>r.advisor_active],["open-clean",r=>r.group==="V2 · clean scored"]]){
    $(id).addEventListener("click",()=>{const r=state.bootstrap.history.find(predicate);if(r)openRun(r.id,true);});
  }
}

async function init(){
  try{
    state.bootstrap=await api("/api/bootstrap");
    $("family").innerHTML=Object.entries(state.bootstrap.catalog).map(([id,c])=>`<option value="${id}">${escapeHTML(c.subtitle)}</option>`).join("");
    for(const role of ["attacker","defender"]){
      $(role+"-model").innerHTML=state.bootstrap.models.map(m=>`<option>${escapeHTML(m)}</option>`).join("");
      $(role+"-model").value="claude-opus-5";
    }
    const p=state.bootstrap.preflight;
    $("cli-status").textContent=p.ready?`CLI ${p.version} verified · tools off · no fallback`:(p.reason||"CLI unavailable. Replay remains available.");
    $("launch").disabled=!p.ready;
    state.runs=await api("/api/runs");
    setupChanged();renderArchive();renderAudit();
    for(const id of ["family","defence","turn-budget"])$(id).addEventListener("change",setupChanged);
    const preferred=state.runs.find(r=>r.status==="completed"&&r.source==="real_model")||state.runs.find(r=>r.status==="completed"&&r.config?.family==="exact_secret")||state.runs[0];
    if(preferred){state.current=await api("/api/runs/"+preferred.id);renderRun();if(["ready","running"].includes(state.current.status))pollRun(state.current.id);}
    const tab=location.hash.slice(1);if(["lab","archive","compare","advisor"].includes(tab))view(tab);
  }catch(e){notice("Unable to load the local laboratory: "+e.message);}
}
init();
