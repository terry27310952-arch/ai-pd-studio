param(
  [string]$Target = ""
)

$ErrorActionPreference = 'Stop'

function Find-TargetHtml {
  param([string]$Hint)
  if ($Hint) {
    if (Test-Path $Hint -PathType Leaf) { return (Resolve-Path $Hint).Path }
    if (Test-Path $Hint -PathType Container) {
      $p = Join-Path $Hint 'OPEN_DIRECT.html'
      if (Test-Path $p) { return (Resolve-Path $p).Path }
    }
  }

  $direct = Join-Path (Get-Location) 'OPEN_DIRECT.html'
  if (Test-Path $direct) { return (Resolve-Path $direct).Path }

  $preferred = Get-ChildItem -Path (Get-Location) -Filter OPEN_DIRECT.html -File -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match 'v4_3_ULTRALITE_24FPS|ICT11' } |
    Select-Object -First 1
  if ($preferred) { return $preferred.FullName }

  $any = Get-ChildItem -Path (Get-Location) -Filter OPEN_DIRECT.html -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($any) { return $any.FullName }
  throw 'OPEN_DIRECT.html not found. Put this patch in the extracted v4.3 folder and run again.'
}

$htmlPath = Find-TargetHtml $Target
$dir = Split-Path -Parent $htmlPath
$backup = Join-Path $dir ('OPEN_DIRECT.v43.backup.' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.html')
Copy-Item $htmlPath $backup -Force

$h = Get-Content -Raw -Encoding UTF8 $htmlPath

# Title
$h = $h.Replace('ICT11 UltraLite AI Market Film v4.3','ICT11 Smooth Native AI Market Film v4.4 STABLE')

# Native browser video FPS + CSS GPU motion, not JS stepped motion.
$h = [regex]::Replace($h, '\.realBroll\{[^}]*\}', '.realBroll{position:absolute;inset:-2%;width:104%;height:104%;object-fit:cover;opacity:0;will-change:opacity,transform;transition:opacity .20s ease-out,transform var(--moveDur,8s) linear;transform-origin:center center;backface-visibility:hidden}')
$h = $h.Replace('preload="metadata"></video><video id="brollB" class="realBroll" muted playsinline preload="metadata"','preload="auto"></video><video id="brollB" class="realBroll" muted playsinline preload="auto"')
$h = $h.Replace('opacity:.014;background-image:','opacity:0;background-image:')
$h = $h.Replace('text-shadow:0 3px 16px rgba(0,0,0,.92)','text-shadow:0 2px 8px rgba(0,0,0,.80)')

# State variables: remove artificial 24/12fps gating variables.
$h = $h.Replace("let lastVisualTs=0,lastAiScene=-1,lastAiFrame=-1,lastBrollMotion=-1,lastUiTs=0;","let lastAiScene=-1,lastAiFrame=-1,lastUiTs=0;")

$configure = @'
function configureVideo(v,idx){
  const slot=BROLL_SLOTS[idx],src=BROLL_SOURCES[slot.source];
  v.dataset.slot=String(idx);v.dataset.sourceId=src.id;v.src=src.url;v.muted=true;v.playsInline=true;v.loop=false;v.preload='auto';
  v.style.objectPosition='50% 50%';
  v.style.setProperty('--moveDur',Math.max(1.5,slot.e-slot.s)+'s');
  v.style.transition='opacity .20s ease-out, transform '+Math.max(1.5,slot.e-slot.s)+'s linear';
  v.style.transform='scale('+slot.zoom+') translate3d('+slot.pan+'%,0,0)';
  v.onloadedmetadata=()=>{if(Number(v.dataset.slot)!==idx)return;v.playbackRate=fitRate(v,slot);try{v.currentTime=Math.min(slot.offset,Math.max(.05,(v.duration||1)-.2))}catch(e){}};
  v.load()
}
'@
$h = [regex]::Replace($h, 'function configureVideo\(v,idx\)\{.*?(?=function releaseVideo)', $configure, [System.Text.RegularExpressions.RegexOptions]::Singleline)

$release = @'
function releaseVideo(v){
  try{if(!v.paused)v.pause()}catch(e){}
  v.oncanplay=null;v.onloadedmetadata=null;v.onerror=null;v.style.opacity='0';
  v.removeAttribute('src');try{v.load()}catch(e){};v.dataset.slot='';v.dataset.sourceId=''
}
'@
$h = [regex]::Replace($h, 'function releaseVideo\(v\)\{.*?(?=function prepareNext)', $release, [System.Text.RegularExpressions.RegexOptions]::Singleline)

$prepare = @'
function prepareNext(idx){
  const n=idx+1;if(n<0||n>=BROLL_SLOTS.length||n===nextPrepared)return;
  const standby=vids[1-activeVid];
  if(Number(standby.dataset.slot)!==n){releaseVideo(standby);configureVideo(standby,n)}
  standby.style.opacity='0';nextPrepared=n
}
'@
$h = [regex]::Replace($h, 'function prepareNext\(idx\)\{.*?(?=function activate)', $prepare, [System.Text.RegularExpressions.RegexOptions]::Singleline)

$activate = @'
function activate(idx,t){
  if(idx<0||idx===activeSlot)return;
  const slot=BROLL_SLOTS[idx],old=vids[activeVid],ni=1-activeVid,next=vids[ni],token=++serial;
  activeSlot=idx;nextPrepared=-1;
  if(Number(next.dataset.slot)!==idx){releaseVideo(next);configureVideo(next,idx)}
  const show=()=>{
    if(token!==serial||activeSlot!==idx)return;
    const rate=fitRate(next,slot);next.playbackRate=rate;
    try{next.currentTime=Math.min(slot.offset+Math.max(0,t-slot.s)*rate,Math.max(.05,(next.duration||1)-.12))}catch(e){}
    next.style.transition='none';
    next.style.transform='scale('+slot.zoom+') translate3d('+slot.pan+'%,0,0)';
    next.style.opacity='1';void next.offsetWidth;
    next.style.transition='opacity .20s ease-out, transform '+Math.max(1.5,slot.e-slot.s)+'s linear';
    next.style.transform='scale('+(slot.zoom+.018)+') translate3d('+(-slot.pan*.25)+'%,0,0)';
    old.style.opacity='0';activeVid=ni;
    if(!audio.paused)next.play().catch(()=>{});
    if(lastFxSlot!==idx){lastFxSlot=idx;fireFx(slot.fx)}
    setTimeout(()=>{if(old!==next)releaseVideo(old);prepareNext(idx)},280)
  };
  if(next.readyState>=3)show();else next.oncanplay=show;
  next.onerror=()=>{if(token!==serial)return;old.style.opacity='1';next.style.opacity='0'}
}
'@
$h = [regex]::Replace($h, 'function activate\(idx,t\)\{.*?(?=function clearCanvas)', $activate, [System.Text.RegularExpressions.RegexOptions]::Singleline)

# AI scenes are lightweight 960x540; 30fps is enough without visible stepping.
$h = $h.Replace('frame=Math.floor((t-s.s)*12)','frame=Math.floor((t-s.s)*30)')

$sync = @'
function syncVisual(t){
  const ai=renderAI(t);
  if(ai){brollStage.style.opacity='0';for(const v of vids)if(!v.paused)v.pause();return}
  brollStage.style.opacity='1';
  const idx=slotAt(t);if(idx<0)return;
  if(idx!==activeSlot)activate(idx,t);
  const v=vids[activeVid];
  if(v&&Number(v.dataset.slot)===idx&&v.readyState>=2&&!audio.paused&&v.paused)v.play().catch(()=>{});
  if(nextPrepared!==idx+1)prepareNext(idx)
}
'@
$h = [regex]::Replace($h, 'function syncVisual\(t\)\{.*?(?=function tick)', $sync, [System.Text.RegularExpressions.RegexOptions]::Singleline)

$tick = @'
function tick(ts){
  const t=audio.currentTime||0;
  syncVisual(t);renderSub(t);
  if(loaded&&ts-lastUiTs>180){
    lastUiTs=ts;const d=audio.duration||D,pp=d?100*t/d:0;
    progress.value=Math.round(pp*10);progress.style.setProperty('--p',pp+'%');
    timeEl.textContent=fmt(t)+' / '+fmt(d);playBtn.textContent=audio.paused?'▶':'❚❚'
  }
  requestAnimationFrame(tick)
}
'@
$h = [regex]::Replace($h, 'function tick\(ts\)\{.*?(?=function init\(\))', $tick, [System.Text.RegularExpressions.RegexOptions]::Singleline)

$h = $h.Replace("audio.addEventListener('seeking',()=>{activeSlot=-1;syncVisual(audio.currentTime||0)})","audio.addEventListener('seeking',()=>{activeSlot=-1;nextPrepared=-1;syncVisual(audio.currentTime||0)})")

# Guard against a failed patch leaving old frame limit code behind.
if ($h -match 'ts-lastVisualTs<41' -or $h -match 'lastBrollMotion') {
  throw 'Patch verification failed: old frame limiter still exists.'
}
if ($h -notmatch "v\.preload='auto'" -or $h -notmatch 'next\.readyState>=3') {
  throw 'Patch verification failed: smooth preload engine was not installed.'
}

Set-Content -Path $htmlPath -Value $h -Encoding UTF8

Write-Host ''
Write-Host 'ICT11 v4.4 STABLE patch complete.' -ForegroundColor Green
Write-Host ('Patched: ' + $htmlPath)
Write-Host ('Backup : ' + $backup)
Write-Host 'Launching player...'

Start-Process $htmlPath
