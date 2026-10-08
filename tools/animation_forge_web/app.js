/* Pose images are pure evaluations; playback only selects integer visual ticks. */
'use strict';
const $ = id => document.getElementById(id);
const clone = value => JSON.parse(JSON.stringify(value));
let project, example, token, library = [], frames = {}, diagnostics = {}, images = new Map();
let groundY = 584, autoplay = false;
let tick = 0, exposureIndex = 0, playing = false, startTime = 0, startTick = 0;
let comparisonTick = 0;
let generation = 0, debounce, dirty = false, undo = [], redo = [], ready = false;
let lastSaved = '';
let projectRevision = 0, loadRequest = 0;
const total = () => project.exposures.reduce((n, e) => n + e.duration_ticks, 0);
const selectedPose = () => project.poses.find(p => p.id === project.exposures[exposureIndex].pose_id);
const startOf = index => project.exposures.slice(0, index).reduce((n, e) => n + e.duration_ticks, 0);
// Opening exposures play once. Repeat only the section after loop_start.
function playbackTick(absolute, exposures, policy, loopStart = 0) {
  const length = exposures.reduce((n,e)=>n+e.duration_ticks,0);
  if(policy !== 'cycle') return Math.min(absolute,length-1);
  const entry = exposures.slice(0,loopStart).reduce((n,e)=>n+e.duration_ticks,0);
  return absolute < length ? absolute : entry + (absolute-entry) % (length-entry);
}

function status(message, error = false) { $('status').textContent = message; $('status').classList.toggle('error', error); }
async function api(path, data, retried = false) {
  const requestToken=token;
  const response = await fetch('/api/' + path, {method:'POST', headers:{'Content-Type':'application/json','X-Forge-Token':requestToken}, body:JSON.stringify(data)});
  const result = await response.json();
  if(response.status===403 && !retried){
    const bootstrap=await fetch('/api/bootstrap').then(r=>r.json());
    if(bootstrap.token && bootstrap.token!==requestToken){token=bootstrap.token;return api(path,data,true);}
  }
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function remember() { autoplay=false; undo.push(clone(project)); if (undo.length > 60) undo.shift(); redo = []; markDirty(); }
function markDirty() { projectRevision++; dirty = true; $('dirty').textContent = 'Unsaved changes'; updateUndo(); }
function updateUndo() { $('undo').disabled = undo.length === 0; $('redo').disabled = redo.length === 0; }
function stop() { playing = false; $('play').textContent = 'Play'; }
function poseIndexAt(t) {
  let cursor = 0;
  for (let i = 0; i < project.exposures.length; i++) { cursor += project.exposures[i].duration_ticks; if (t < cursor) return i; }
  return project.exposures.length - 1;
}
function selectExposure(index) { autoplay=false; stop(); exposureIndex = index; tick = startOf(index); comparisonTick=tick; refreshControls(); draw(); }
function seek(t, absolute = t) {
  tick = Math.max(0, Math.min(total() - 1, Math.floor(t)));
  comparisonTick = Math.max(0, Math.floor(absolute));
  const index = poseIndexAt(tick);
  if (index !== exposureIndex) { exposureIndex = index; refreshControls(); }
  draw();
}
function fillSaved(files, selected = '') {
  $('saved').replaceChildren();
  if (!files.length) $('saved').add(new Option('No saved revisions yet', ''));
  for (const file of files) $('saved').add(new Option(file, file));
  if (selected) $('saved').value = selected;
  $('open').disabled = !files.length;
}
function refreshProject() {
  $('name').value = project.name;
  $('loop').value = project.loop_policy;
  $('pose').replaceChildren();
  project.exposures.forEach((e,i) => $('pose').add(new Option(project.poses.find(p=>p.id===e.pose_id).label + ' · ' + e.pose_id, String(i))));
  $('source').textContent = project.source.kind === 'authored' ? 'Original authored keys · no captured FPS' : project.source.description;
  const isWalk=project.schema==='other-animation-forge.walk.v1';
  $('study-title').textContent=isWalk?'WALK · EDITABLE MOTION':'REACH · AUTHORED KEYS';
  $('study-scope').textContent=isWalk?'Local reference study · unreviewed':'Original pose study · unreviewed';
  $('animation').value=isWalk?'walk':'reach';
  groundY=isWalk?567:584;
  refreshTimeline(); refreshControls(); updateUndo();
}
function refreshTimeline() {
  $('timeline').replaceChildren();
  project.exposures.forEach((e, i) => {
    const button = document.createElement('button'); button.style.flex = project.exposures.length>12?'0 0 82px':String(e.duration_ticks);
    const label = document.createElement('span'); label.textContent = project.poses.find(p=>p.id===e.pose_id).label;
    const sub = document.createElement('small'); sub.textContent = `${e.duration_ticks} ticks · ${startOf(i)}–${startOf(i)+e.duration_ticks-1}`;
    if(i===project.loop_start){button.classList.toggle('loop-start',true);button.title='Loop starts here; earlier exposures play once';}
    button.append(label,sub); button.onclick = () => selectExposure(i); $('timeline').append(button);
  });
  $('scrub').max = String(total()-1);
  const baselineTotal = project.baseline.exposures.reduce((n,e)=>n+e.duration_ticks,0);
  const entry=project.loop_start?startOf(project.loop_start):0;
  $('duration').textContent = `${total()} ticks / ${(total()/60).toFixed(3)} s · baseline ${baselineTotal} ticks`+(entry?` · ${entry}-tick entry, ${total()-entry}-tick loop`:'');
}
const axisNames = ['X · forward (cm)', 'Y · depth (cm)', 'Z · height (cm)'];
axisNames.forEach((name,axis) => {
  const row = document.createElement('div'); row.className = 'axis';
  const label = document.createElement('label'); label.textContent = name;
  const slider = document.createElement('input'); slider.type='range'; slider.id='axis-'+axis; slider.min=axis===2?'-30':'-180'; slider.max=axis===2?'220':'180'; slider.step='0.5'; slider.setAttribute('aria-label',name);
  const number = document.createElement('input'); number.type='number'; number.id='number-'+axis; number.min=slider.min; number.max=slider.max; number.step='0.5'; number.setAttribute('aria-label',name+' exact');
  label.append(slider); row.append(label,number); $('axes').append(row);
  function change(value) {
    const v = Number(value); if (!Number.isFinite(v) || v < Number(slider.min) || v > Number(slider.max)) { refreshControls(); return; }
    if(v === selectedPose().controls[$('target').value][axis]) return;
    stop(); remember(); selectedPose().controls[$('target').value][axis] = v;
    slider.value = number.value = String(v); scheduleRender();
  }
  slider.onchange = () => change(slider.value);
  slider.oninput = () => { number.value=slider.value; };
  number.onchange = () => change(number.value);
  number.oninput = () => { if(number.value!=='' && Number(number.value)>=Number(slider.min) && Number(number.value)<=Number(slider.max))change(number.value); };
});
function refreshControls() {
  const pose = selectedPose(), target = $('target').value;
  $('pose').value = String(exposureIndex);
  $('hold').value = String(project.exposures[exposureIndex].duration_ticks);
  pose.controls[target].forEach((v,i)=>{$('axis-'+i).value=String(v);$('number-'+i).value=String(Math.round(v*1000)/1000);});
  const wrist = target.startsWith('right') ? 'right_wrist' : 'left_wrist';
  $('wrist-control').hidden = !target.endsWith('hand');
  $('wrist').value = String(pose.controls[wrist]); $('wrist-value').textContent=pose.controls[wrist]+'°';
  $('pose-caption').textContent = pose.label + ' · ' + pose.id;
  const messages = diagnostics[pose.id] || [];
  $('diagnostics').textContent = messages.length ? messages.map(m=>typeof m==='string'?m:m.message||JSON.stringify(m)).join(' · ') : 'Pose controls affect this key only. Hands and contact remain unverified.';
}
function paint(canvas, image) {
  const ctx=canvas.getContext('2d'); ctx.fillStyle='#E6E6E6';ctx.fillRect(0,0,640,640);
  ctx.strokeStyle='#b2bbc0';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(25,groundY+.5);ctx.lineTo(615,groundY+.5);ctx.stroke();
  if(image) ctx.drawImage(image,0,0);
}
function draw() {
  const pair = frames[selectedPose().id];
  let baselineId=selectedPose().id;
  if($('compare').value==='timing'){
    const time=playbackTick(comparisonTick,project.baseline.exposures,project.loop_policy,project.baseline.loop_start||0);
    let cursor=0;for(const e of project.baseline.exposures){cursor+=e.duration_ticks;if(time<cursor){baselineId=e.pose_id;break;}}
  }
  const baselinePair=frames[baselineId];
  $('baseline-caption').textContent=($('compare').value==='timing'?'Original timing · ':'Same pose · ')+baselineId;
  paint($('before'), baselinePair && images.get(baselinePair.baseline)); paint($('after'), pair && images.get(pair.current));
  $('scrub').value = String(tick);$('clock').textContent=`Tick ${tick} / ${total()-1} · ${selectedPose().id}`;
  [...$('timeline').children].forEach((b,i)=>b.classList.toggle('active',i===exposureIndex));
}
function scheduleRender() { clearTimeout(debounce); ready=false; stop(); generation++; debounce=setTimeout(render,180); }
async function render() {
  const current = ++generation; ready=false; stop(); $('play').disabled=true; status('Rendering pose changes…');
  try {
    const result = await api('preview', {project:clone(project),facing:$('facing').value});
    const urls = new Set(Object.values(result.frames).flatMap(pair=>Object.values(pair)));
    const loaded = new Map();
    await Promise.all([...urls].map(url=>new Promise((resolve,reject)=>{
      if(images.has(url)){loaded.set(url,images.get(url));return resolve();}
      const img=new Image(); img.onload=()=>{loaded.set(url,img);resolve();};img.onerror=()=>reject(new Error('Could not load rendered pose')); img.src=url;
    })));
    if(current !== generation) return;
    frames=result.frames;diagnostics=result.diagnostics;images=loaded;ready=true;groundY=result.ground_y||groundY;
    refreshControls();draw();status('Ready · poses render locally; visual holds do not change geometry.');
    if(autoplay){autoplay=false;$('play').onclick();}
  } catch(error) {if(current === generation){status(error.message,true);}}
  finally {if(current === generation) $('play').disabled=!ready;}
}
function install(p, label, playOnReady = false) {
  if(project) {undo.push(clone(project)); if(undo.length>60)undo.shift();} redo=[];
  clearTimeout(debounce); generation++; projectRevision++; stop();project=clone(p);autoplay=playOnReady;tick=0;comparisonTick=0;exposureIndex=0;dirty=false;frames={};diagnostics={};
  $('dirty').textContent=label;refreshProject();draw();render();
}
$('pose').onchange=()=>selectExposure(Number($('pose').value));
$('target').onchange=refreshControls;
for(const id of ['axes','wrist','hold','target']){ $(id).addEventListener('pointerdown',stop);$(id).addEventListener('focusin',stop); }
$('wrist').oninput=()=>{$('wrist-value').textContent=$('wrist').value+'°';};
$('wrist').onchange=()=>{stop();remember();selectedPose().controls[$('target').value.startsWith('right')?'right_wrist':'left_wrist']=Number($('wrist').value);scheduleRender();};
$('hold').oninput=()=>{
  const value=Number($('hold').value); if(!Number.isInteger(value)||value<1||value>600 || value===project.exposures[exposureIndex].duration_ticks)return;
  stop();remember();project.exposures[exposureIndex].duration_ticks=value;tick=startOf(exposureIndex);comparisonTick=tick;refreshTimeline();draw();status('Visual hold updated. Geometry is unchanged.');
};
$('hold').onchange=refreshControls;
$('name').oninput=()=>{const name=$('name').value.trim();if(name&&name!==project.name){remember();project.name=name;}};
$('name').onchange=()=>{$('name').value=project.name;};
$('loop').onchange=()=>{stop();remember();project.loop_policy=$('loop').value;};
$('facing').onchange=render;
$('compare').onchange=draw;
$('speed').onchange=()=>{startTime=performance.now();startTick=comparisonTick;};
$('scrub').oninput=()=>{stop();seek(Number($('scrub').value));};
$('step').onclick=()=>{stop();seek(playbackTick(tick+1,project.exposures,project.loop_policy,project.loop_start||0));};$('step-back').onclick=()=>{stop();seek(tick-1);};
$('reset').onclick=()=>{stop();seek(0);};
$('play').onclick=()=>{if(playing){stop();return;}if(!ready)return;if(project.loop_policy==='oneshot'&&tick===total()-1)seek(0);playing=true;startTime=performance.now();startTick=comparisonTick;$('play').textContent='Pause';};
function animate(now) {
  if(playing){const absolute=startTick+Math.floor((now-startTime)*60*Number($('speed').value)/1000);const t=playbackTick(absolute,project.exposures,project.loop_policy,project.loop_start||0);if(project.loop_policy!=='cycle'&&absolute>=total())stop();seek(t,absolute);}
  requestAnimationFrame(animate);
}
$('restore').onclick=()=>{stop();remember();const pose=selectedPose();pose.controls=clone(project.baseline.poses.find(p=>p.id===pose.id).controls);refreshControls();render();};
$('undo').onclick=()=>{if(!undo.length)return;stop();redo.push(clone(project));project=undo.pop();markDirty();tick=Math.min(tick,total()-1);exposureIndex=poseIndexAt(tick);refreshProject();render();};
$('redo').onclick=()=>{if(!redo.length)return;stop();undo.push(clone(project));project=redo.pop();markDirty();tick=Math.min(tick,total()-1);exposureIndex=poseIndexAt(tick);refreshProject();render();};
$('save').onclick=async()=>{try{const snapshot=clone(project);const result=await api('save',{project:snapshot});lastSaved=result.file;fillSaved(result.projects,result.file);if(JSON.stringify(project)===JSON.stringify(snapshot)){dirty=false;$('dirty').textContent='Saved revision';}$('save-status').textContent='Saved '+result.file;status('Saved a new local revision. Existing revisions are preserved.');}catch(e){status(e.message,true);}};
$('open').onclick=async()=>{const revision=projectRevision,request=++loadRequest,file=$('saved').value;try{const r=await api('load',{file});if(revision!==projectRevision||request!==loadRequest){status('Project changed while loading. Reopen again when ready.');return;}install(r.project,'Reopened revision');$('save-status').textContent='Reopened '+file;}catch(e){status(e.message,true);}};
$('example').onclick=()=>install(example,'Known-good example');
$('load-animation').onclick=()=>{const item=library.find(item=>item.id===$('animation').value);if(item)install(item.project,'Local animation · ready to edit',true);};
$('download').onclick=()=>{const blob=new Blob([JSON.stringify(project,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='animation.forge.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('import').onchange=async()=>{const revision=projectRevision,request=++loadRequest;try{const file=$('import').files[0];if(!file)return;if(file.size>1_000_000)throw new Error('Project must be at most 1 MB');const p=JSON.parse(await file.text());await api('validate',{project:p});if(revision!==projectRevision||request!==loadRequest){status('Project changed while importing. Import again when ready.');return;}install(p,'Imported · save a revision');markDirty();}catch(e){status(e.message,true);}finally{$('import').value='';}};
$('export').onclick=async()=>{const b=$('export');b.disabled=true;status('Exporting transparent poses and the review handoff…');try{const result=await api('export',{project:clone(project)});const link=document.createElement('a');link.href=result.url;link.target='_blank';link.textContent='Open exported review ↗';const detail=document.createElement('p');detail.textContent=result.directory;$('export-result').replaceChildren(link,detail);status('Export complete · transparent PNGs, editable project and exact visual timing.');}catch(e){status(e.message,true);}finally{b.disabled=false;}};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
async function boot(){try{const r=await fetch('/api/bootstrap').then(r=>r.json());token=r.token;example=r.example||r.project;library=r.library||[{id:'reach',title:'Reach · four authored poses',project:example}];$('animation').replaceChildren();for(const item of library)$('animation').add(new Option(item.title,item.id));if(r.editable_walk&&!r.editable_walk.available)$('animation-hint').textContent='Walk unavailable: '+r.editable_walk.error;fillSaved(r.projects);install(r.project,'Local animation · ready to edit',r.project.schema==='other-animation-forge.walk.v1');requestAnimationFrame(animate);}catch(e){status(e.message,true);}}
boot();
