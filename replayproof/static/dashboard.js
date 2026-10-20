const icons = {
  grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  layers:'<path d="m12 3 10 5-10 5L2 8z"/><path d="m2 12 10 5 10-5M2 16l10 5 10-5"/>',
  shield:'<path d="M12 3 3.5 6v6c0 4 4 7.5 8.5 9 4.5-1.5 8.5-5 8.5-9V6z"/><path d="m8.5 11.5 2.5 2.5 4.5-5"/>',
  network:'<rect x="8" y="2" width="8" height="6" rx="1"/><rect x="2" y="16" width="7" height="6" rx="1"/><rect x="15" y="16" width="7" height="6" rx="1"/><path d="M12 8v4M5.5 16v-4h13v4"/>',
  code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-16-2 20"/>',
  external:'<path d="M14 3h7v7m0-7L10 14"/><path d="M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/>',
  'arrow-right':'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  'arrow-up-right':'<path d="M6 18 18 6M6 6h12v12"/>',
  refresh:'<path d="M20 7a9 9 0 0 0-15-2L2 8m0-5v5h5m-3 9a9 9 0 0 0 15 2l3-3m0 5v-5h-5"/>',
  play:'<path d="m8 4 12 8-12 8z"/>',
  activity:'<path d="M2 12h4l3-8 6 16 3-8h4"/>',
  chevron:'<path d="m7 10 5 5 5-5"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  plus:'<path d="M12 4v16M4 12h16"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  'check-circle':'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  buffer:'<rect x="4" y="3" width="16" height="6" rx="1"/><rect x="4" y="13" width="16" height="8" rx="1"/><path d="M8 6h.01M8 17h.01m4 0h5"/>',
  candles:'<path d="M6 3v4m0 10v4m6-19v9m0 7v4m6-18v2m0 10v5"/><rect x="4" y="7" width="4" height="10" rx=".5"/><rect x="10" y="11" width="4" height="7" rx=".5"/><rect x="16" y="6" width="4" height="10" rx=".5"/>',
  lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2"/>',
  copy:'<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  download:'<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  menu:'<path d="M3 6h18M3 12h18M3 18h18"/>',
  alert:'<path d="m12 3 10 18H2zM12 9v4m0 4h.01"/>',
};
function icon(name) { return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.activity}</svg>`; }
function hydrateIcons(root = document) { root.querySelectorAll('[data-icon]').forEach(el => {el.innerHTML = icon(el.dataset.icon);}); }
hydrateIcons();
const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const number = value => Number(value || 0).toLocaleString('en-US');
const price = ticks => (Number(ticks) / 10000).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:4});
const utcTime = value => new Date(value).toLocaleTimeString('en-GB', {timeZone:'UTC', hour12:false});
const utcDate = value => new Date(value).toLocaleString('en-GB', {timeZone:'UTC', day:'2-digit', month:'short', year:'numeric',hour:'2-digit',minute:'2-digit'});
const shortId = value => value ? value.slice(0,8) : '—';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const state = {streams:[], stream:null, status:null, events:[], bars:[], runs:[], report:null, view:'overview', chart:'candles', offset:0, nextOffset:null, busy:false, refreshVersion:0, demoRunning:false};

async function api(path, options = {}) {
  const response = await fetch(path, {headers:{'Content-Type':'application/json'}, ...options});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(d => `${d.loc.at(-1)}: ${d.msg}`).join('; ') : data.detail;
    const error = new Error(detail || `Request failed (${response.status})`);
    error.status = response.status; error.data = data; throw error;
  }
  return data;
}
function toast(message, error = false) {
  const el = document.createElement('div'); el.className = `toast${error ? ' error' : ''}`;
  el.innerHTML = `${icon(error ? 'alert' : 'check-circle')}<span>${escapeHTML(message)}</span>`;
  $('toast-container').append(el); setTimeout(() => el.remove(), 5500);
}
function showError(error) { $('error-banner').textContent = error.message || String(error); $('error-banner').hidden = false; }
async function checkHealth() {
  let online = false;
  try { online = (await api('/health/ready')).status === 'ready'; } catch { /* Display the observed unavailable state. */ }
  $('top-health').textContent = online ? 'Database connected' : 'Database unavailable';
  $('side-health').textContent = online ? 'All systems operational' : 'Database unavailable';
  $('db-health').textContent = online ? 'Connected' : 'Unreachable';
  ['top-health-dot','side-health-dot'].forEach(id => $(id).classList.toggle('offline', !online));
}
async function loadStreams(preferredId = null) {
  const data = await api('/v1/streams?limit=100'); state.streams = data.streams;
  const savedId = preferredId || sessionStorage.getItem('replayproof-stream');
  let selected = state.streams.find(s => s.id === savedId);
  if (!selected) selected = state.streams.find(s => s.symbol === 'RPL_USD') || state.streams.find(s => s.symbol === 'SYNTH') || state.streams[0];
  renderStreamOptions();
  if (selected) await selectStream(selected.id);
  else { state.stream = null; state.status = null; state.bars=[]; state.events=[]; state.runs=[]; state.report=null; render(); }
}
async function selectStream(id) {
  const stream = state.streams.find(s => s.id === id);
  if (!stream) return;
  state.stream = stream; state.offset=0; state.report=null;
  sessionStorage.setItem('replayproof-stream',id);
  $('stream-popover').hidden=true; $('stream-select').setAttribute('aria-expanded','false');
  $('current-symbol').textContent=stream.symbol.replaceAll('_',' / ');
  $('stream-id').textContent=stream.id;
  $('stream-id').title=stream.id;
  await refreshStream(); renderStreamOptions();
}
async function refreshStream() {
  if (!state.stream) return;
  const streamId=state.stream.id, version=++state.refreshVersion;
  $('refresh').classList.add('spinning');
  try {
    const status = await api(`/v1/streams/${streamId}/status`);
    let barsRequest=Promise.resolve({bars:[]});
    if (status.first_event_time && status.last_event_time) {
      const end=new Date(status.last_event_time); end.setUTCSeconds(0,0); end.setUTCMinutes(end.getUTCMinutes()+1);
      const first=new Date(status.first_event_time); first.setUTCSeconds(0,0);
      const start=new Date(Math.max(first.getTime(),end.getTime()-31*86400000));
      const params=new URLSearchParams({start:start.toISOString(),end:end.toISOString(),limit:'1000'});
      barsRequest=api(`/v1/streams/${streamId}/bars?${params}`);
    }
    const [bars,events,reports]=await Promise.all([
      barsRequest,
      api(`/v1/streams/${streamId}/events?limit=20&offset=${state.offset}`),
      api(`/v1/streams/${streamId}/reconciliations?limit=20`),
    ]);
    if (version!==state.refreshVersion || state.stream.id!==streamId) return;
    state.status=status; state.bars=bars.bars; state.events=events.events; state.nextOffset=events.next_offset; state.runs=reports.runs;
    if (!state.report || !state.runs.some(r=>r.id===state.report.id)) state.report=state.runs[0] || null;
    else state.report=state.runs.find(r=>r.id===state.report.id);
    $('error-banner').hidden=true;
    $('updated').textContent=`Updated ${new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}`;
    render();
  } catch(error) { if(version===state.refreshVersion) showError(error); }
  finally { if(version===state.refreshVersion) $('refresh').classList.remove('spinning'); }
}
function renderStreamOptions() {
  const query=$('stream-search').value.trim().toLowerCase();
  const streams=state.streams.filter(s=>`${s.symbol} ${s.id}`.toLowerCase().includes(query));
  $('stream-options').innerHTML=streams.length ? streams.map(s=>`<button class="stream-option ${state.stream?.id===s.id?'current':''}" data-stream-id="${escapeHTML(s.id)}"><span><strong>${escapeHTML(s.symbol.replaceAll('_',' / '))}</strong><small>${escapeHTML(shortId(s.id))} · ${escapeHTML(utcDate(s.created_at))} UTC</small></span><span>${number(s.last_applied_seq)} SEQ</span></button>`).join('') : '<p class="panel-empty">No matching recent streams</p>';
}
function render() {
  const s=state.status;
  $('metric-events').textContent=s ? number(s.source_event_count) : '—';
  $('metric-cursor').innerHTML=`${s?number(s.last_applied_seq):'—'}<span class="metric-unit">SEQ</span>`;
  $('metric-buffered').textContent=s?number(s.buffered_count):'—';
  $('metric-conflicts').textContent=s?number(s.conflict_count):'—';
  $('cursor-description').innerHTML=s?`${icon(s.blocked_by_gaps?'lock':'check-circle')}<span>${s.blocked_by_gaps?'Held at the last complete sequence':'Contiguous prefix, fully applied'}</span>`:'Waiting for a feed session';
  $('cursor-description').classList.toggle('warning',!!s?.blocked_by_gaps);
  $('cursor-description').querySelector('svg')?.setAttribute('style','width:11px;height:11px');
  $('buffered-description').textContent=s?.blocked_by_gaps?`${number(s.buffered_count)} stored beyond a missing sequence`:'No events waiting on a gap';
  $('buffered-description').classList.toggle('warning',!!s?.blocked_by_gaps);
  $('metric-buffered').style.color=s?.buffered_count?'var(--purple)':'';
  $('metric-conflicts').style.color=s?.conflict_count?'var(--amber)':'';
  $('ledger-count').textContent=s?number(s.source_event_count):'0';
  renderSequence(); renderChart(); renderEvents(); renderReconciliation();
  $('reconcile-now').disabled=!state.stream || state.busy;
  $('reconcile-history').disabled=!state.stream || state.busy;
}
function renderSequence() {
  const s=state.status;
  $('sequence-cursor').textContent=s?number(s.last_applied_seq):'—';
  $('sequence-high').textContent=s?number(s.max_received_seq):'—';
  const badge=$('sequence-badge'); badge.className=`pill ${s?.blocked_by_gaps?'warning':'positive'}`;
  badge.innerHTML=`${icon(s?.blocked_by_gaps?'alert':'check')}${s?.blocked_by_gaps?'Gap detected':s?.max_received_seq?'In sync':'Awaiting events'}`;
  $('prefix-progress').style.width=s?.max_received_seq?`${100*s.last_applied_seq/s.max_received_seq}%`:'0%';
  const high=s?.max_received_seq||0, start=Math.max(1,high-95);
  $('sequence-window').textContent=high?`${number(start)} – ${number(high)}`:'NO EVENTS';
  let cells='';
  for(let sequence=start;sequence<=high;sequence++) {
    const missing=s.gaps.some(([a,b])=>sequence>=a&&sequence<=b);
    const kind=missing?'gap':sequence>s.last_applied_seq?'buffered':'applied';
    cells+=`<span class="seq-cell ${kind}" title="Sequence ${sequence}: ${missing?'missing within highest received sequence':kind}">${sequence}</span>`;
  }
  $('sequence-grid').innerHTML=cells||'<div class="sequence-placeholder">Your sequence map will appear here.</div>';
  const gap=$('gap-summary'); gap.classList.toggle('warning',!!s?.blocked_by_gaps);
  const ranges=s?.gaps.map(([a,b])=>a===b?String(a):`${a}–${b}`).join(', ');
  gap.innerHTML=`${icon(s?.blocked_by_gaps?'alert':'check-circle')}<div><strong>${s?.blocked_by_gaps?`Missing sequence${s.gaps.length>1?' ranges':''}: ${escapeHTML(ranges)}`:'No gaps within received range'}</strong><p>${s?.blocked_by_gaps?'Buffered events remain unapplied until these gaps are filled.':'Nothing inferred beyond the highest received sequence.'}</p></div>`;
}
const SVG_NS='http://www.w3.org/2000/svg';
function svgElement(name,attrs={},content=null) { const el=document.createElementNS(SVG_NS,name); Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,String(v))); if(content!==null) el.textContent=content; return el; }
let chartGeometry=null;
function renderChart() {
  const svg=$('price-chart'); svg.replaceChildren();
  const bars=state.bars.slice(-60); $('chart-empty').hidden=!!bars.length;
  $('chart-tooltip').hidden=true;
  if(!bars.length){$('projected-price').textContent='—';$('price-change').textContent='No applied trades yet';$('chart-ohlc').innerHTML='<span>O —</span><span>H —</span><span>L —</span><span>C —</span><span>V —</span>';chartGeometry=null;return;}
  const last=bars.at(-1), first=bars[0];
  $('projected-price').textContent=price(last.close);
  const delta=(last.close-first.open)/10000, percent=100*(last.close-first.open)/first.open;
  $('price-change').textContent=`${delta>=0?'+':''}${delta.toFixed(4).replace(/0+$/,'').replace(/\.$/,'')} (${percent>=0?'+':''}${percent.toFixed(2)}%) over visible bars`;
  $('price-change').classList.toggle('down',delta<0);
  setOHLC(last);
  $('chart-range').textContent=`${new Date(last.minute_start).toLocaleDateString('en-GB',{timeZone:'UTC',day:'2-digit',month:'short',year:'numeric'})} · UTC`;
  const left=13,right=730,top=14,bottom=194,volTop=215,volBottom=244;
  const rawMin=Math.min(...bars.map(b=>b.low)),rawMax=Math.max(...bars.map(b=>b.high));
  const pad=Math.max((rawMax-rawMin)*.2,20),min=rawMin-pad,max=rawMax+pad;
  const y=value=>bottom-(value-min)/(max-min)*(bottom-top),step=(right-left)/bars.length;
  for(let i=0;i<5;i++){const yy=top+(bottom-top)*i/4;svg.append(svgElement('line',{x1:left,y1:yy,x2:right,y2:yy,stroke:'#28382d','stroke-width':'.7','stroke-dasharray':'3 5'}));svg.append(svgElement('text',{x:741,y:yy+3,fill:'#668471','font-size':11,'font-family':'Consolas,monospace'},price(max-(max-min)*i/4)));}
  const maxVolume=Math.max(...bars.map(b=>b.volume));
  const linePoints=[];
  bars.forEach((bar,i)=>{
    const x=left+step*(i+.5),positive=bar.close>=bar.open,color=positive?'#9dcdaa':'#cb919b';
    svg.append(svgElement('rect',{x:x-Math.min(step*.32,8),y:volBottom-(bar.volume/maxVolume)*(volBottom-volTop),width:Math.min(step*.64,16),height:(bar.volume/maxVolume)*(volBottom-volTop),rx:1,fill:positive?'#3b5e46':'#584047',opacity:.65}));
    if(state.chart==='candles') {
      svg.append(svgElement('line',{x1:x,y1:y(bar.high),x2:x,y2:y(bar.low),stroke:color,'stroke-width':1}));
      svg.append(svgElement('rect',{x:x-Math.min(step*.28,7),y:Math.min(y(bar.open),y(bar.close)),width:Math.min(step*.56,14),height:Math.max(Math.abs(y(bar.open)-y(bar.close)),1.5),rx:.8,fill:color}));
    }
    linePoints.push([x,y(bar.close)]);
    if(i===0||i===bars.length-1||(bars.length>8&&i%Math.ceil(bars.length/5)===0)) svg.append(svgElement('text',{x,y:262,fill:'#688572','font-size':11,'text-anchor':'middle','font-family':'Consolas,monospace'},utcTime(bar.minute_start).slice(0,5)));
  });
  if(state.chart==='line'){
    const defs=svgElement('defs'),gradient=svgElement('linearGradient',{id:'area-gradient',x1:0,y1:0,x2:0,y2:1});
    gradient.append(svgElement('stop',{offset:'0%','stop-color':'#8fc9a0','stop-opacity':'.17'}),svgElement('stop',{offset:'100%','stop-color':'#8fc9a0','stop-opacity':'0'}));defs.append(gradient);svg.append(defs);
    const path=linePoints.map(([x,yy],i)=>`${i?'L':'M'}${x},${yy}`).join(' ');
    svg.append(svgElement('path',{d:`${path} L${linePoints.at(-1)[0]},${bottom} L${linePoints[0][0]},${bottom} Z`,fill:'url(#area-gradient)'}));
    svg.append(svgElement('path',{d:path,fill:'none',stroke:'#a8dbb5','stroke-width':1.8,'stroke-linejoin':'round'}));
  }
  const lastY=y(last.close);
  svg.append(svgElement('line',{x1:left,y1:lastY,x2:right,y2:lastY,stroke:'#79b389','stroke-width':.8,'stroke-dasharray':'3 4',opacity:.6}));
  svg.append(svgElement('rect',{x:735,y:lastY-9,width:62,height:18,rx:3,fill:'#2d4d37'}));
  svg.append(svgElement('text',{x:766,y:lastY+3,fill:'#b9e4c5','font-size':11,'text-anchor':'middle','font-family':'Consolas,monospace'},price(last.close)));
  svg.append(svgElement('line',{id:'chart-crosshair',x1:0,y1:top,x2:0,y2:volBottom,stroke:'#88ab94','stroke-width':.6,'stroke-dasharray':'3 3',visibility:'hidden'}));
  chartGeometry={bars,left,right,step};
}
function setOHLC(bar){$('chart-ohlc').innerHTML=`<span>O <b>${price(bar.open)}</b></span><span>H <b>${price(bar.high)}</b></span><span>L <b>${price(bar.low)}</b></span><span>C <b>${price(bar.close)}</b></span><span>V <b>${number(bar.volume)}</b></span>`;}
$('price-chart').addEventListener('pointermove',event=>{
  if(!chartGeometry)return;
  const rect=event.currentTarget.getBoundingClientRect(), x=(event.clientX-rect.left)*800/rect.width;
  const {bars,left,right,step}=chartGeometry;
  if(x<left||x>right)return;
  const i=Math.min(bars.length-1,Math.max(0,Math.floor((x-left)/step))),bar=bars[i];
  setOHLC(bar);const cross=$('chart-crosshair');cross.setAttribute('x1',left+step*(i+.5));cross.setAttribute('x2',left+step*(i+.5));cross.setAttribute('visibility','visible');
  const tooltip=$('chart-tooltip');tooltip.hidden=false;tooltip.textContent=`${utcTime(bar.minute_start).slice(0,5)} UTC · ${bar.trade_count} trades · ${number(bar.volume)} volume`;
  tooltip.style.left=`${Math.min(Math.max(event.clientX-rect.left+8,10),Math.max(10,rect.width-210))}px`;
});
$('price-chart').addEventListener('pointerleave',()=>{$('chart-tooltip').hidden=true;$('chart-crosshair')?.setAttribute('visibility','hidden');if(state.bars.length)setOHLC(state.bars.at(-1));});
function eventRow(event,extended=false){return `<tr><td class="seq-number">#${number(event.sequence)}</td><td class="event-source" title="${escapeHTML(event.source_event_id)}">${escapeHTML(event.source_event_id)}</td><td>${escapeHTML(utcTime(event.event_time))}</td><td class="numeric">${price(event.price_ticks)}</td><td class="numeric">${number(event.quantity)}</td><td><span class="event-status ${event.state}">${icon(event.state==='applied'?'check':'buffer')}${event.state==='applied'?'Applied':'Buffered'}</span></td>${extended?`<td class="fingerprint" title="${escapeHTML(event.payload_sha256)}">${escapeHTML(event.payload_sha256.slice(0,14))}…</td>`:''}</tr>`;}
function renderEvents(){
  $('overview-events').innerHTML=state.events.slice(0,7).map(e=>eventRow(e)).join('')||'<tr><td colspan="6" class="empty-cell">No canonical events in this session yet.</td></tr>';
  const query=$('event-filter').value.trim().toLowerCase();
  const filtered=state.events.filter(e=>`${e.sequence} ${e.source_event_id} ${e.state} ${e.payload_sha256}`.toLowerCase().includes(query));
  $('explorer-events').innerHTML=filtered.map(e=>eventRow(e,true)).join('')||'<tr><td colspan="7" class="empty-cell">No matching events on this page.</td></tr>';
  $('event-page-label').textContent=state.events.length?`Records ${number(state.offset+1)}–${number(state.offset+state.events.length)} · newest sequence first`:'No events loaded';
  $('events-prev').disabled=state.offset===0; $('events-next').disabled=state.nextOffset===null;
}
function renderReconciliation(){
  const latest=state.runs[0];
  const card=$('reconcile-state'); card.className=`reconcile-state ${!latest?'neutral':latest.mismatch_count?'warning':''}`;
  const current=latest && state.status && latest.observed_cursor===state.status.last_applied_seq;
  card.innerHTML=`<span class="state-ring">${icon(!latest?'shield':latest.mismatch_count?'alert':'check')}</span><div><strong>${!latest?'No comparison yet':latest.mismatch_count?'Projection mismatch':current?'All buckets match':'Previous snapshot matched'}</strong><p>${!latest?'Run the independent SQL reference check':`Observed at sequence ${number(latest.observed_cursor)}${!current?' · run again for current cursor':''}`}</p></div>`;
  $('reconcile-buckets').textContent=latest?number(latest.expected_count):'—';$('reconcile-mismatches').textContent=latest?number(latest.mismatch_count):'—';
  $('digest-preview').textContent=latest?`${latest.digest.slice(0,14)}…${latest.digest.slice(-8)}`:'Not calculated yet';
  $('digest-preview').title=latest?.digest||'';$('copy-digest').disabled=!latest;
  $('report-list').innerHTML=state.runs.length?state.runs.map(r=>`<button class="report-list-button ${state.report?.id===r.id?'selected':''}" data-report-id="${escapeHTML(r.id)}"><div><strong>Sequence ${number(r.observed_cursor)}</strong><span class="pill ${r.mismatch_count?'warning':'positive'}">${r.mismatch_count?'Mismatch':'Matched'}</span></div><small>${escapeHTML(utcDate(r.created_at))} UTC</small><small><code>${escapeHTML(shortId(r.id))}</code> · ${number(r.expected_count)} minute buckets</small></button>`).join(''):'<p class="panel-empty">Run a reconciliation to create your first evidence record.</p>';
  renderReport();
}
function renderReport(){
  const report=state.report;$('download-report').disabled=!report;
  if(!report){$('report-content').innerHTML='<div class="panel-empty">No report selected. Run a comparison or select a previous check.</div>';return;}
  const mismatch=report.mismatch_count>0;
  const intro=`<div class="report-result ${mismatch?'warning':''}">${icon(mismatch?'alert':'shield')}<div><strong>${mismatch?'The projection differs from the SQL reference.':'The projection matches the SQL reference.'}</strong><p>${mismatch?'Exact mismatches are retained below. Source records remain untouched.':'Every compared minute bucket matches at the observed cursor.'}</p></div></div><div class="report-details"><div><span>Observed cursor</span><strong>${number(report.observed_cursor)}</strong></div><div><span>Expected buckets</span><strong>${number(report.expected_count)}</strong></div><div><span>Bucket mismatches</span><strong>${number(report.mismatch_count)}</strong></div></div><div class="full-digest mono"><span>OBSERVED PROJECTION · SHA-256</span>${escapeHTML(report.digest)}</div>`;
  let diffContent='';
  if(mismatch){const rows=[];for(const diff of report.diffs){for(const field of ['open','high','low','close','volume','trade_count']){const expected=diff.expected?.[field],actual=diff.actual?.[field];if(expected!==actual)rows.push(`<tr><td>${escapeHTML(utcTime(diff.minute_start))}</td><td>${escapeHTML(field)}</td><td>${expected===undefined?'Missing bucket':number(expected)}</td><td class="diff-value">${actual===undefined?'Missing bucket':number(actual)}</td></tr>`);}}diffContent=`<h3 class="diff-heading">Concrete differences${report.diffs_truncated?' (first 100 buckets)':''}</h3><div class="table-scroll"><table class="diff-table"><thead><tr><th>Minute UTC</th><th>Field</th><th>Expected</th><th>Actual</th></tr></thead><tbody>${rows.join('')}</tbody></table></div>`;}
  $('report-content').innerHTML=`${intro}${diffContent}<details class="report-json"><summary>Inspect the persisted JSON report</summary><pre>${escapeHTML(JSON.stringify(report,null,2))}</pre></details>`;
}
const pageInfo={overview:['Overview','Every event. <span>Accounted for.</span>','Sequence-aware ingestion. Verifiable recovery. A little less uncertainty.'],events:['Event explorer','The source. <span>Preserved.</span>','Explore canonical events and their application state, without changing the source.'],reconciliation:['Reconciliation','Evidence, <span>not assumptions.</span>','Compare materialized bars with an independently implemented SQL reference.'],architecture:['Architecture','Simple by design. <span>Strict by contract.</span>','A small architecture with an inspectable, transactional correctness boundary.']};
function route(){const key=location.hash.slice(1)||'overview';state.view=pageInfo[key]?key:'overview';const [label,title,description]=pageInfo[state.view];document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==`view-${state.view}`);document.querySelectorAll('[data-view]').forEach(el=>{el.classList.toggle('active',el.dataset.view===state.view);if(el.dataset.view===state.view)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});$('breadcrumb-name').textContent=label;$('page-title').innerHTML=title;$('page-description').textContent=description;$('sidebar').classList.remove('mobile-open');document.title=`${label} · ReplayProof`;if(state.offset!==0){state.offset=0;refreshStream();}render();}
window.addEventListener('hashchange',route);
$('stream-select').addEventListener('click',()=>{$('stream-popover').hidden=!$('stream-popover').hidden;$('stream-select').setAttribute('aria-expanded',String(!$('stream-popover').hidden));if(!$('stream-popover').hidden)$('stream-search').focus();});
$('stream-search').addEventListener('input',renderStreamOptions);
$('stream-options').addEventListener('click',event=>{const button=event.target.closest('[data-stream-id]');if(button)selectStream(button.dataset.streamId).catch(showError);});
document.addEventListener('click',event=>{if(!event.target.closest('.stream-chooser')){$('stream-popover').hidden=true;$('stream-select').setAttribute('aria-expanded','false');}});
document.addEventListener('keydown',event=>{if(event.key==='Escape'){$('stream-popover').hidden=true;$('stream-select').setAttribute('aria-expanded','false');$('sidebar').classList.remove('mobile-open');}});
$('menu-button').addEventListener('click',()=>$('sidebar').classList.toggle('mobile-open'));
$('close-menu').addEventListener('click',()=>$('sidebar').classList.remove('mobile-open'));
document.querySelectorAll('.nav-item').forEach(el=>el.addEventListener('click',()=>$('sidebar').classList.remove('mobile-open')));
$('refresh').addEventListener('click',async()=>{await Promise.all([refreshStream(),checkHealth()]);});
for(const mode of ['candles','line'])$(`chart-${mode}`).addEventListener('click',()=>{state.chart=mode;['candles','line'].forEach(m=>$(`chart-${m}`).classList.toggle('selected',m===mode));['candles','line'].forEach(m=>$(`chart-${m}`).setAttribute('aria-pressed',String(m===mode)));renderChart();});
$('event-filter').addEventListener('input',renderEvents);
$('events-prev').addEventListener('click',()=>{state.offset=Math.max(0,state.offset-20);refreshStream();});
$('events-next').addEventListener('click',()=>{if(state.nextOffset!==null){state.offset=state.nextOffset;refreshStream();}});
$('report-list').addEventListener('click',event=>{const button=event.target.closest('[data-report-id]');if(button){state.report=state.runs.find(r=>r.id===button.dataset.reportId);renderReconciliation();}});
$('copy-digest').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(state.runs[0].digest);toast('Projection checksum copied.');}catch{toast('Clipboard unavailable. The full checksum is in the report.',true);}});
$('download-report').addEventListener('click',()=>{if(!state.report)return;const blob=new Blob([JSON.stringify(state.report,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`reconciliation-${state.report.id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
async function reconcile(){if(!state.stream||state.busy)return;state.busy=true;render();try{const report=await api(`/v1/streams/${state.stream.id}/reconcile`,{method:'POST'});state.report=report;await refreshStream();toast(report.mismatch_count?`SQL reference found ${report.mismatch_count} mismatched buckets.`:'Reconciled. Every minute bucket matches.',!!report.mismatch_count);}catch(error){showError(error);toast(error.message,true);}finally{state.busy=false;render();}}
$('reconcile-now').addEventListener('click',reconcile);$('reconcile-history').addEventListener('click',reconcile);
$('open-create').addEventListener('click',()=>{$('stream-popover').hidden=true;$('create-dialog').showModal();$('new-symbol').focus();});
$('close-create').addEventListener('click',()=>$('create-dialog').close());
$('create-form').addEventListener('submit',async event=>{event.preventDefault();const button=event.submitter;button.disabled=true;try{const stream=await api('/v1/streams',{method:'POST',body:JSON.stringify({symbol:$('new-symbol').value})});$('create-dialog').close();await loadStreams(stream.id);toast('A new feed session is ready.');}catch(error){toast(error.message,true);}finally{button.disabled=false;}});
function scenarioEvents(){let seed=2027;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};let last=1823000;const base=Date.UTC(2027,0,1,9);return Array.from({length:96},(_,index)=>{last=Math.max(10000,last+Math.round((random()-.44)*5200));const minute=Math.floor(index/4),seconds=Math.floor(random()*56);return{sequence:index+1,source_event_id:`rpl-${String(index+1).padStart(4,'0')}`,event_time:new Date(base+minute*60000+seconds*1000).toISOString(),price_ticks:last,quantity:10+Math.floor(random()*240),schema_version:1};});}
function setStep(index,complete=false){document.querySelectorAll('.demo-steps li').forEach((el,i)=>{el.classList.toggle('active',i===index&&!complete);el.classList.toggle('done',i<index||(i===index&&complete));el.querySelector('.step-result').innerHTML=i<index||(i===index&&complete)?icon('check'):'';});}
function demoMessage(text,error=false){$('demo-message').textContent=text;$('demo-message').classList.toggle('error',error);}
let resumeDemo=null;
$('inspect-gap').addEventListener('click',()=>$('demo-dialog').close());
$('open-demo').addEventListener('click',()=>{if(!state.demoRunning){document.querySelectorAll('.demo-steps li').forEach(el=>{el.classList.remove('active','done');el.querySelector('.step-result').replaceChildren();});demoMessage('Creates a new stream. Existing streams stay intact.');$('start-demo').innerHTML=`${icon('play')}Start live demonstration${icon('arrow-right')}`;}$('demo-dialog').showModal();});
$('start-demo').addEventListener('click',async()=>{
  if(state.demoRunning){if(resumeDemo){const resume=resumeDemo;resumeDemo=null;$('start-demo').disabled=true;$('start-demo').innerHTML=`${icon('refresh')}Recovering and verifying…`;resume();}return;}
  if($('start-demo').dataset.complete==='true'){$('demo-dialog').close();return;}
  state.demoRunning=true;state.busy=true;$('start-demo').disabled=true;$('open-demo').disabled=true;$('stream-select').disabled=true;
  $('start-demo').innerHTML=`${icon('refresh')}Running against PostgreSQL…`;
  const events=scenarioEvents();
  let sid;
  try {
    location.hash='overview';setStep(0);demoMessage('Creating a fresh stream and establishing the first 16 events…');
    const stream=await api('/v1/streams',{method:'POST',body:JSON.stringify({symbol:'RPL_USD'})});sid=stream.id;
    const send=event=>api(`/v1/streams/${sid}/events`,{method:'POST',body:JSON.stringify(event)});
    await loadStreams(sid);
    for(const event of events.slice(0,16))await send(event);
    await refreshStream();setStep(0,true);await sleep(450);
    setStep(1);demoMessage('Sequence 17 is withheld. Receiving 18–96 in small concurrent groups…');
    const future=events.slice(17);
    for(let i=0;i<future.length;i+=6){await Promise.all(future.slice(i,i+6).map(send));if(i%18===0)await refreshStream();}
    await refreshStream();
    if(state.status.last_applied_seq!==16||state.status.buffered_count!==79)throw new Error('The expected gap invariant did not hold. Inspect the stream before continuing.');
    setStep(1,true);demoMessage('Paused at the gap: cursor 16, with 79 later events durably buffered. Inspect the dashboard, then recover sequence 17 to continue.');
    $('inspect-gap').hidden=false;$('start-demo').disabled=false;
    $('start-demo').innerHTML=`${icon('arrow-right')}Recover sequence 17`;
    $('open-demo').disabled=false;$('open-demo').innerHTML=`${icon('play')}Continue recovery${icon('arrow-right')}`;
    await new Promise(resolve=>{resumeDemo=resolve;});
    $('inspect-gap').hidden=true;$('open-demo').disabled=true;
    setStep(2);
    const duplicate=await send(events[15]);if(duplicate.status!=='duplicate')throw new Error('Retry did not deduplicate as expected.');
    let conflictRecorded=false;
    try{await send({...events[15],quantity:events[15].quantity+1});}catch(error){if(error.status===409)conflictRecorded=true;else throw error;}
    if(!conflictRecorded)throw new Error('Divergent payload was not quarantined.');
    await refreshStream();setStep(2,true);demoMessage('Identical retry deduplicated. Divergent retry returned 409 and was audited.');
    await sleep(700);setStep(3);
    await send(events[16]);await refreshStream();
    if(state.status.last_applied_seq!==96||state.status.buffered_count!==0)throw new Error('Gap fill did not recover the complete prefix.');
    const report=await api(`/v1/streams/${sid}/reconcile`,{method:'POST'});
    if(report.mismatch_count!==0)throw new Error('SQL reconciliation detected a mismatch after recovery.');
    state.report=report;await refreshStream();setStep(3,true);
    demoMessage('Recovered through sequence 96. No buffered events. All minute buckets match the SQL reference.');
    $('start-demo').dataset.complete='true';
    $('start-demo').innerHTML=`${icon('check-circle')}View recovered stream${icon('arrow-right')}`;
    toast('96 events recovered. Independent SQL comparison matched.');
    await loadStreams(sid);
  }catch(error){demoMessage(`The demonstration stopped: ${error.message}`,true);$('start-demo').innerHTML=`${icon('refresh')}Try again with a fresh stream`;toast(error.message,true);}
  finally{resumeDemo=null;state.demoRunning=false;state.busy=false;$('start-demo').disabled=false;$('open-demo').disabled=false;$('open-demo').innerHTML=`${icon('play')}Run replay demo${icon('arrow-right')}`;$('stream-select').disabled=false;$('inspect-gap').hidden=true;render();}
});
$('open-demo').addEventListener('click',()=>{if(!state.demoRunning)$('start-demo').dataset.complete='false';});
route();
Promise.all([checkHealth(),loadStreams()]).catch(showError);
setInterval(()=>{if(document.visibilityState==='visible'&&!state.busy){checkHealth();refreshStream();}},12000);
