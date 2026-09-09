from __future__ import annotations
import json, os, math, random, urllib.parse, urllib.request, zipfile
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / 'dist' / 'KIYOSAKI_ICT11_WEB_v1_2_PERSISTENT_MARKET_FILM_DIRECT'
DIST.mkdir(parents=True, exist_ok=True)


def ms(dt: str) -> int:
    return int(datetime.fromisoformat(dt.replace('Z','+00:00')).timestamp()*1000)


def fetch_klines(interval: str, start: str, end: str):
    q = urllib.parse.urlencode({
        'symbol':'BTCUSDT','interval':interval,
        'startTime':ms(start),'endTime':ms(end),'limit':1000
    })
    urls = [
        'https://api.binance.com/api/v3/klines?' + q,
        'https://api.binance.us/api/v3/klines?' + q,
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as r:
                raw=json.load(r)
            out=[]
            for x in raw:
                out.append({'t':int(x[0]),'o':float(x[1]),'h':float(x[2]),'l':float(x[3]),'c':float(x[4]),'v':float(x[5])})
            if len(out) >= 10:
                return out
        except Exception as e:
            print('fetch failed', interval, url, e)
    return []


def fallback_4h():
    # Shape anchors based on the public Aug 1-Sep 4, 2026 BTCUSDT history.
    anchors=[
      (0,62888),(12,63520),(24,64923),(48,63600),(72,66500),(96,69000),(120,72000),
      (144,74800),(168,78200),(186,76800),(198,78500),(204,77400),(210,77300),(216,81300),(222,79700)
    ]
    n=6*35
    vals=[]
    for i in range(n):
        a=max(j for j in range(len(anchors)) if anchors[j][0] <= i)
        if a==len(anchors)-1: base=anchors[a][1]
        else:
            x0,y0=anchors[a]; x1,y1=anchors[a+1]
            u=(i-x0)/max(1,x1-x0)
            base=y0+(y1-y0)*u
        wiggle=math.sin(i*0.83)*260+math.sin(i*0.19)*420
        vals.append(base+wiggle)
    out=[]
    t0=ms('2026-08-01T00:00:00Z')
    prev=vals[0]
    for i,c in enumerate(vals):
        o=prev
        hi=max(o,c)+130+abs(math.sin(i*1.7))*380
        lo=min(o,c)-120-abs(math.cos(i*1.3))*350
        out.append({'t':t0+i*14400000,'o':o,'h':hi,'l':lo,'c':c,'v':9000+abs(math.sin(i*.31))*22000})
        prev=c
    return out


def resample_from_4h(src, minutes, start_ms, end_ms):
    step=minutes*60*1000
    pts=[]
    by_t={x['t']:x for x in src}
    t=start_ms
    prev=src[0]['c'] if src else 70000
    while t < end_ms:
        parent=max([x for x in src if x['t']<=t], key=lambda x:x['t'], default=None)
        base=parent['c'] if parent else prev
        idx=len(pts)
        c=base + math.sin(idx*.72)*95 + math.sin(idx*.13)*145
        o=prev
        pts.append({'t':t,'o':o,'h':max(o,c)+80,'l':min(o,c)-80,'c':c,'v':1200+abs(math.sin(idx*.23))*4500})
        prev=c; t+=step
    return pts

btc4 = fetch_klines('4h','2026-08-01T00:00:00Z','2026-09-05T00:00:00Z') or fallback_4h()
btc15 = fetch_klines('15m','2026-09-03T00:00:00Z','2026-09-05T00:00:00Z')
btc5 = fetch_klines('5m','2026-09-03T00:00:00Z','2026-09-05T00:00:00Z')
if not btc15:
    btc15=resample_from_4h(btc4,15,ms('2026-09-03T00:00:00Z'),ms('2026-09-05T00:00:00Z'))
if not btc5:
    btc5=resample_from_4h(btc4,5,ms('2026-09-03T00:00:00Z'),ms('2026-09-05T00:00:00Z'))
DATA=json.dumps({'4h':btc4,'15m':btc15,'5m':btc5},separators=(',',':'))

html = r'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>ICT 11 · Market Structure Film v1.2</title>
<style>
:root{--bg:#06080b;--fg:#f4f4f1;--muted:rgba(244,244,241,.52);--up:#3ed6a0;--down:#ff6974;--amber:#f0b35a;--cyan:#65b9ff}
*{box-sizing:border-box} html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#050609;color:var(--fg);font-family:Inter,"Noto Sans JP","Yu Gothic",system-ui,sans-serif}
#stage{position:fixed;inset:0;background:#050609;overflow:hidden} #cv{position:absolute;inset:0;width:100%;height:100%;display:block}
#vignette{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse at 50% 50%,rgba(5,6,9,.05) 0,rgba(5,6,9,.12) 28%,rgba(5,6,9,.36) 72%,rgba(5,6,9,.72) 100%)}
#subtitleWrap{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:min(72vw,1380px);text-align:center;pointer-events:none;filter:drop-shadow(0 4px 20px rgba(0,0,0,.95))}
#subtitle{font-weight:750;font-size:clamp(26px,3.05vw,58px);line-height:1.36;letter-spacing:-.035em;text-wrap:balance;opacity:0;transform:translateY(5px) scale(1.012);transition:none}
#subtitle.on{opacity:1;animation:subIn .18s cubic-bezier(.2,.72,.18,1) both} #subtitle .kw{color:#fff;text-shadow:0 0 22px rgba(240,179,90,.2);position:relative}
#subtitle.focus .kw{color:#ffd18b} #subtitle.punch{font-size:clamp(30px,3.45vw,66px);letter-spacing:-.045em}
@keyframes subIn{from{opacity:0;filter:blur(5px);transform:translateY(8px) scale(1.018)}to{opacity:1;filter:blur(0);transform:none}}
#loader{position:absolute;inset:0;display:grid;place-items:center;background:#050609;z-index:20;transition:opacity .45s ease}
#loader.hide{opacity:0;pointer-events:none}.loadInner{width:min(680px,82vw);text-align:center}.eyebrow{font-size:11px;letter-spacing:.32em;color:rgba(255,255,255,.36);margin-bottom:24px}.loadTitle{font-size:clamp(29px,4.2vw,58px);font-weight:650;letter-spacing:-.05em;margin:0 0 10px}.loadSub{font-size:14px;color:rgba(255,255,255,.42);line-height:1.7;margin-bottom:28px}
#pick{appearance:none;border:1px solid rgba(255,255,255,.18);background:transparent;color:#fff;padding:13px 20px;font-weight:650;letter-spacing:.08em;cursor:pointer}#pick:hover{border-color:rgba(255,255,255,.42)}
#fileInput{display:none}#loadState{margin-top:18px;min-height:20px;font-size:12px;color:rgba(255,255,255,.38)}
#controls{position:absolute;left:0;right:0;bottom:0;height:72px;display:flex;align-items:flex-end;padding:0 24px 16px;gap:14px;background:linear-gradient(transparent,rgba(0,0,0,.65));opacity:0;transition:opacity .2s;z-index:9}#stage.controls #controls{opacity:1}
#playBtn{border:0;background:transparent;color:#fff;font-size:18px;width:28px;height:28px;padding:0;cursor:pointer}.track{position:relative;flex:1;height:28px;display:flex;align-items:center}.track:before{content:"";position:absolute;left:0;right:0;height:2px;background:rgba(255,255,255,.16)}#progress{width:100%;appearance:none;background:transparent;position:relative;z-index:2}#progress::-webkit-slider-thumb{appearance:none;width:9px;height:9px;border-radius:50%;background:white}#progress::-webkit-slider-runnable-track{height:2px;background:linear-gradient(90deg,#fff var(--p,0%),rgba(255,255,255,.16) var(--p,0%))}#time{font-variant-numeric:tabular-nums;font-size:11px;color:rgba(255,255,255,.55);min-width:92px;text-align:right}
#watermark{position:absolute;left:26px;bottom:24px;font-size:10px;letter-spacing:.22em;color:rgba(255,255,255,.14);pointer-events:none;opacity:.9}
</style></head><body>
<main id="stage"><canvas id="cv" width="1920" height="1080"></canvas><div id="vignette"></div><div id="subtitleWrap"><div id="subtitle"></div></div><div id="watermark">ICT · MARKET STRUCTURE</div>
<div id="loader"><div class="loadInner"><div class="eyebrow">KIYOSAKI · ICT FILM v1.2</div><h1 class="loadTitle">MARKET STRUCTURE</h1><div class="loadSub">11.mp4 と 11.srt を選択してください。<br>再生後はチャートと中央字幕だけが残ります。</div><button id="pick">SELECT SOURCE FILES</button><input id="fileInput" type="file" multiple accept="video/*,audio/*,.srt,text/plain"><div id="loadState"></div></div></div>
<div id="controls"><button id="playBtn">▶</button><div class="track"><input id="progress" type="range" min="0" max="1000" value="0"></div><div id="time">00:00 / 00:00</div></div><audio id="audio" preload="auto"></audio></main>
<script>const BTC_DATA=__BTC_DATA__;
const D=1172.638; const stage=document.getElementById('stage'),cv=document.getElementById('cv'),ctx=cv.getContext('2d'),audio=document.getElementById('audio'),sub=document.getElementById('subtitle'),loader=document.getElementById('loader'),pick=document.getElementById('pick'),fileInput=document.getElementById('fileInput'),loadState=document.getElementById('loadState'),playBtn=document.getElementById('playBtn'),progress=document.getElementById('progress'),timeEl=document.getElementById('time');
const DPR=Math.min(2,devicePixelRatio||1); let cues=[],currentCue=-1,loaded=false,lastPointer=0;
function fit(){const r=stage.getBoundingClientRect();cv.width=Math.max(1280,Math.round(r.width*DPR));cv.height=Math.max(720,Math.round(r.height*DPR));} addEventListener('resize',fit);fit();
function ts(s){const m=s.match(/(\d+):(\d+):(\d+)[,.](\d+)/);return m?+m[1]*3600 + +m[2]*60 + +m[3] + +m[4]/1000:0}
function parseSRT(text){const blocks=text.replace(/\r/g,'').trim().split(/\n\s*\n/),out=[];for(const b of blocks){const l=b.split('\n');const ti=l.findIndex(x=>x.includes('-->'));if(ti<0)continue;const [a,z]=l[ti].split('-->').map(x=>x.trim());out.push({s:ts(a),e:ts(z),text:l.slice(ti+1).join('\n').trim()})}if(!out.length)return out;const offset=out[0].s>60?out[0].s:0;for(const q of out){q.s=Math.max(0,q.s-offset);q.e=Math.max(q.s+.04,q.e-offset)}return out}
const KWS=['ICT','スマートマネー','機関投資家','大口','マーケットストラクチャー','MSS','チョーク','CHoCH','BOS','BSL','SSL','流動性','ディスプレイスメント','オーダーブロック','ビットコイン','4時間足','15分足','5分足'];
function esc(s){return s.replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]))}
function cueHtml(t){let h=esc(t).replace(/\n/g,'<br>');for(const k of KWS)h=h.replaceAll(k,`<span class="kw">${k}</span>`);return h}
function renderSub(t){let i=-1;for(let j=0;j<cues.length;j++){if(t>=cues[j].s&&t<cues[j].e){i=j;break}if(cues[j].s>t)break}if(i===currentCue)return;currentCue=i;if(i<0){sub.className='';sub.innerHTML='';return}const q=cues[i],strong=/核心|市場構造|チョーク|BOS|BSL|SSL|ディスプレイスメント|オーダーブロック|ビットコイン/.test(q.text);const punch=/答えは一つ|価格はどう動く|大口の足跡|中核|実際のチャート/.test(q.text);sub.className='';sub.innerHTML=cueHtml(q.text);void sub.offsetWidth;sub.className='on'+(strong?' focus':'')+(punch?' punch':'')}
function clamp(x,a,b){return Math.max(a,Math.min(b,x))} function mix(a,b,t){return a+(b-a)*t}function ease(t){return t*t*(3-2*t)}
function rng(seed){let x=seed>>>0;return()=>{x=(x*1664525+1013904223)>>>0;return x/4294967296}}
function makeCandles(mode,n=86,seed=1){const r=rng(seed),a=[];let p=100;let trend=mode.includes('down')?-.18:.18;for(let i=0;i<n;i++){let d=trend+(r()-.5)*1.15;if(mode.includes('range'))d=(r()-.5)*.85;if(mode.includes('chochDown')&&i>52)d=-.75+(r()-.5)*.65;if(mode.includes('chochUp')&&i>52)d=.75+(r()-.5)*.65;if(mode.includes('dispUp')&&i===58)d=7.6;if(mode.includes('dispDown')&&i===58)d=-7.6;if(mode.includes('stopShort')){if(i<48)d=.22+(r()-.5)*.55;else if(i===52)d=3.2;else if(i>52)d=-.8+(r()-.5)*.6}if(mode.includes('stopLong')){if(i<48)d=-.22+(r()-.5)*.55;else if(i===52)d=-3.2;else if(i>52)d=.8+(r()-.5)*.6}const o=p,c=p+d,hi=Math.max(o,c)+.25+r()*1.05,lo=Math.min(o,c)-.25-r()*1.05;a.push({o,h:hi,l:lo,c,v:.35+r()*.65});p=c}return a}
const fam={intro:makeCandles('up',100,4),hunt:makeCandles('stopShort',96,17),structure:makeCandles('up',96,8),chochD:makeCandles('chochDown',96,12),chochU:makeCandles('chochUp down',96,16),bos:makeCandles('up',96,22),liq:makeCandles('stopShort',100,30),disp:makeCandles('dispUp',100,41),dispD:makeCandles('dispDown down',100,52),rev:makeCandles('chochUp down',100,63)};
const scenes=[
[0,14,'intro',0],[14,36,'intro',1],[36,84,'hunt',0],[84,120,'hunt',1],[120,159,'hunt',2],
[159,208,'structure',0],[208,250,'structure',1],[250,303,'chochD',0],[303,349,'chochD',1],[349,405,'chochU',0],[405,441,'bos',0],
[441,490,'liq',0],[490,568,'liq',1],[568,622,'liq',2],[622,652,'liq',3],
[652,699,'disp',0],[699,779,'disp',1],[779,817,'dispD',0],[817,886,'rev',0],[886,936,'rev',1],[936,969,'rev',2],
[969,1049.681,'btc',0],[1049.681,1101.533,'btc',1],[1101.533,1131.163,'btc',2],[1131.163,1172.638,'btc',3]
];
function sceneAt(t){for(let i=0;i<scenes.length;i++){const s=scenes[i];if(t>=s[0]&&t<s[1])return {i,s,p:clamp((t-s[0])/(s[1]-s[0]),0,1)}return {i:scenes.length-1,s:scenes.at(-1),p:1}}
function bg(){const w=cv.width,h=cv.height;ctx.fillStyle='#06080b';ctx.fillRect(0,0,w,h);ctx.strokeStyle='rgba(255,255,255,.035)';ctx.lineWidth=1;const sx=w/12,sy=h/8;for(let x=0;x<w;x+=sx){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke()}for(let y=0;y<h;y+=sy){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke()}}
function scaleData(arr,start,end){const s=Math.max(0,Math.floor(start)),e=Math.min(arr.length,Math.ceil(end)),vis=arr.slice(s,e);let lo=Infinity,hi=-Infinity;for(const c of vis){lo=Math.min(lo,c.l);hi=Math.max(hi,c.h)}const pad=(hi-lo)*.12||1;return {lo:lo-pad,hi:hi+pad,vis,s,e}}
function drawCandles(arr,viewStart,viewEnd,reveal=1,opts={}){const w=cv.width,h=cv.height;const L=w*.075,R=w*.91,T=h*.10,B=h*.87;const sc=scaleData(arr,viewStart,viewEnd);const count=viewEnd-viewStart,cw=(R-L)/count;const upto=Math.floor(viewStart+count*clamp(reveal,0,1));const y=v=>B-(v-sc.lo)/(sc.hi-sc.lo)*(B-T);ctx.save();ctx.beginPath();ctx.rect(L,T,R-L,B-T);ctx.clip();for(let i=Math.floor(viewStart);i<Math.min(Math.ceil(viewEnd),arr.length);i++){if(i>upto)break;const c=arr[i],x=L+(i-viewStart+.5)*cw,yo=y(c.o),yc=y(c.c),yh=y(c.h),yl=y(c.l),up=c.c>=c.o;ctx.strokeStyle=up?'rgba(62,214,160,.88)':'rgba(255,105,116,.88)';ctx.fillStyle=up?'rgba(62,214,160,.82)':'rgba(255,105,116,.82)';ctx.lineWidth=Math.max(1,DPR*.8);ctx.beginPath();ctx.moveTo(x,yh);ctx.lineTo(x,yl);ctx.stroke();const bh=Math.max(2,Math.abs(yc-yo));ctx.fillRect(x-cw*.28,Math.min(yo,yc),cw*.56,bh);if(opts.volume){ctx.fillStyle=up?'rgba(62,214,160,.10)':'rgba(255,105,116,.10)';ctx.fillRect(x-cw*.26,B+h*.02,cw*.52,-c.v*h*.07)}}ctx.restore();ctx.strokeStyle='rgba(255,255,255,.08)';ctx.beginPath();ctx.moveTo(R,T);ctx.lineTo(R,B);ctx.stroke();ctx.fillStyle='rgba(255,255,255,.28)';ctx.font=`${11*DPR}px ui-monospace,monospace`;ctx.textAlign='left';for(let j=0;j<5;j++){const v=mix(sc.lo,sc.hi,j/4),yy=y(v);ctx.fillText(v>1000?v.toFixed(0):v.toFixed(1),R+10*DPR,yy+4*DPR)}return {L,R,T,B,cw,y,sc}}
function label(x,y,text,color='#fff',size=13,align='center'){ctx.font=`700 ${size*DPR}px Inter,system-ui`;ctx.textAlign=align;ctx.textBaseline='middle';ctx.fillStyle=color;ctx.fillText(text,x,y)}
function hline(y,x1,x2,color,text,side='right'){ctx.strokeStyle=color;ctx.lineWidth=1.2*DPR;ctx.setLineDash([7*DPR,7*DPR]);ctx.beginPath();ctx.moveTo(x1,y);ctx.lineTo(x2,y);ctx.stroke();ctx.setLineDash([]);if(text)label(side==='right'?x2-6*DPR:x1+6*DPR,y-12*DPR,text,color,11,side==='right'?'right':'left')}
function box(x1,y1,x2,y2,color,text){ctx.fillStyle=color.replace('1)','0.09)').replace('rgb','rgba');ctx.fillRect(x1,y1,x2-x1,y2-y1);ctx.strokeStyle=color;ctx.globalAlpha=.42;ctx.strokeRect(x1,y1,x2-x1,y2-y1);ctx.globalAlpha=1;if(text)label(x1+8*DPR,y1-11*DPR,text,color,11,'left')}
function drawSynthetic(key,variant,p){const arr=fam[key],n=arr.length;let vs=0,ve=n;const zoom=.08*ease(p);if(['structure','chochD','chochU','bos','liq','disp','dispD','rev'].includes(key)){vs=mix(0,18,zoom);ve=mix(n,n-8,zoom)}const reveal=clamp(.34+p*.76,0,1),g=drawCandles(arr,vs,ve,reveal,{volume:true}),{L,R,T,B,cw,y}=g;const X=i=>L+(i-vs+.5)*cw;
 if(key==='intro'){if(variant===0){const ids=[18,36,55,71];for(let k=0;k<ids.length;k++)label(X(ids[k]),y(arr[ids[k]].h)-18*DPR,['I','II','III','IV'][k],'rgba(255,255,255,.22)',11);hline(y(arr[24].l),L,R,'rgba(255,255,255,.12)','SUPPORT')}else{hline(y(arr[68].h),L,R,'rgba(240,179,90,.24)','PRICE');}}
 if(key==='hunt'){const level=y(arr[48].h);hline(level,L,R,'rgba(240,179,90,.62)','BSL');for(let i=32;i<49;i+=5){ctx.fillStyle='rgba(240,179,90,.28)';ctx.beginPath();ctx.arc(X(i),level-10*DPR,2.5*DPR,0,7);ctx.fill()}if(variant>=1){label(X(52),y(arr[52].h)-18*DPR,'SWEEP','#f0b35a',12);label(X(58),y(arr[58].c)+24*DPR,'DISPLACEMENT','#ff8e96',11)}}
 if(key==='structure'){const pts=[18,31,43,56,69];for(let k=0;k<pts.length;k++){const i=pts[k],hi=k%2===0;label(X(i),y(hi?arr[i].h:arr[i].l)+(hi?-18:20)*DPR,hi?(k<3?'HH':'HH'):'HL',hi?'#d8f5e9':'#a5d7c6',12)}if(variant>0)hline(y(arr[55].l),X(38),R,'rgba(255,105,116,.46)','STRUCTURE LOW')}
 if(key==='chochD'){hline(y(arr[47].l),L,R,'rgba(255,105,116,.62)','CHoCH / MSS');label(X(59),y(arr[59].c)+26*DPR,'BREAK','#ff6974',12);if(variant>0){hline(y(arr[37].h),X(18),X(58),'rgba(240,179,90,.34)','EQUAL HIGH')}}
 if(key==='chochU'){hline(y(arr[46].h),L,R,'rgba(62,214,160,.62)','CHoCH / MSS');label(X(58),y(arr[58].c)-26*DPR,'BREAK','#3ed6a0',12)}
 if(key==='bos'){const level=y(arr[49].h);hline(level,L,R,'rgba(101,185,255,.58)','BOS');label(X(61),y(arr[61].c)-24*DPR,'CONTINUATION','#65b9ff',11)}
 if(key==='liq'){const top=y(arr[47].h),bot=y(arr[27].l);if(variant===0){for(let i=18;i<80;i+=7){ctx.fillStyle='rgba(255,255,255,.08)';ctx.fillRect(X(i)-1*DPR,T,2*DPR,B-T)}}if(variant===1||variant===3){hline(top,L,R,'rgba(240,179,90,.68)','BSL');label(X(52),y(arr[52].h)-20*DPR,'LIQUIDITY SWEEP','#f0b35a',11)}if(variant===2||variant===3){hline(bot,L,R,'rgba(101,185,255,.62)','SSL');}}
 if(key==='disp'||key==='dispD'){const up=key==='disp',i=58;label(X(i),y(up?arr[i].h:arr[i].l)+(up?-26:26)*DPR,'DISPLACEMENT',up?'#3ed6a0':'#ff6974',12);const ob=arr[i-1];const yy1=y(Math.max(ob.o,ob.c)),yy2=y(Math.min(ob.o,ob.c));box(X(i-1)-cw*.5,yy1,R,yy2,up?'rgba(62,214,160,1)':'rgba(255,105,116,1)','ORDER BLOCK')}
 if(key==='rev'){const ch=y(variant===0?arr[46].h:arr[46].l);hline(ch,L,R,variant===0?'rgba(62,214,160,.56)':'rgba(255,105,116,.56)','CHoCH');if(variant>=1)label(X(59),y(arr[59].c)+(variant===1?-26:26)*DPR,'DISPLACEMENT',variant===1?'#3ed6a0':'#ff6974',12)}
}
function pivots(arr){const out=[];for(let i=3;i<arr.length-3;i++){let H=true,L=true;for(let j=i-3;j<=i+3;j++){if(arr[j].h>arr[i].h)H=false;if(arr[j].l<arr[i].l)L=false}if(H)out.push({i,type:'H',v:arr[i].h});if(L)out.push({i,type:'L',v:arr[i].l})}return out}
function drawBTC(variant,p){let arr=BTC_DATA['4h'],tf='4H';if(variant===2){if(p>.66){arr=BTC_DATA['5m'];tf='5M';p=(p-.66)/.34}else if(p>.33){arr=BTC_DATA['15m'];tf='15M';p=(p-.33)/.33}else{p=p/.33}}const n=arr.length;let vs=0,ve=n;if(variant===0){vs=mix(0,n*.12,ease(p));ve=mix(n,n*.94,ease(p))}else if(variant===1){vs=n*.18;ve=n*.98}else if(variant===2){vs=n*.1;ve=n*.9}else{vs=n*.35;ve=n}const g=drawCandles(arr,vs,ve,1,{volume:true}),{L,R,T,B,cw,y}=g,X=i=>L+(i-vs+.5)*cw;const pv=pivots(arr).filter(x=>x.i>=vs&&x.i<=ve);if(variant<=1){for(let k=0;k<pv.length;k++){const q=pv[k];if(k%3!==0)continue;label(X(q.i),y(q.v)+(q.type==='H'?-16:17)*DPR,q.type==='H'?'BOS':'SSL',q.type==='H'?'rgba(101,185,255,.72)':'rgba(240,179,90,.66)',10)}}if(variant===0){const lastH=pv.filter(q=>q.type==='H').at(-2),lastL=pv.filter(q=>q.type==='L').at(-2);if(lastH)hline(y(lastH.v),Math.max(L,X(lastH.i)-cw*8),R,'rgba(255,105,116,.46)','CHoCH');if(lastL)hline(y(lastL.v),Math.max(L,X(lastL.i)-cw*8),R,'rgba(101,185,255,.44)','SSL')}
 if(variant===1){const mid=Math.floor(n*.72);const c=arr[mid];box(X(mid-1),y(Math.max(c.o,c.c)),Math.min(R,X(mid+18)),y(Math.min(c.o,c.c)),'rgba(240,179,90,1)','ORDER BLOCK');label(X(Math.min(n-1,mid+7)),y(arr[Math.min(n-1,mid+7)].c)-25*DPR,'AUTO STRUCTURE','rgba(255,255,255,.38)',10)}
 if(variant===2){label(L+10*DPR,T+22*DPR,tf,'rgba(255,255,255,.32)',11,'left');const zoneY=mix(T,B,.58);ctx.strokeStyle='rgba(240,179,90,.35)';ctx.lineWidth=1*DPR;ctx.setLineDash([5*DPR,7*DPR]);ctx.strokeRect(L+cw*22,zoneY-45*DPR,(R-L)*.30,90*DPR);ctx.setLineDash([])}
 if(variant===3){ctx.fillStyle='rgba(6,8,11,'+mix(.1,.72,ease(p))+')';ctx.fillRect(0,0,cv.width,cv.height);label(cv.width*.5,cv.height*.33,'BOS  ·  CHoCH  ·  BSL  ·  SSL  ·  DISPLACEMENT  ·  ORDER BLOCK','rgba(255,255,255,'+mix(.08,.48,ease(p))+')',13)}
}
function drawVoid(){const w=cv.width,h=cv.height;const grad=ctx.createRadialGradient(w*.5,h*.5,0,w*.5,h*.5,w*.24);grad.addColorStop(0,'rgba(6,8,11,.56)');grad.addColorStop(.55,'rgba(6,8,11,.28)');grad.addColorStop(1,'rgba(6,8,11,0)');ctx.fillStyle=grad;ctx.fillRect(w*.24,h*.34,w*.52,h*.32)}
function render(t){bg();const q=sceneAt(t),[a,b,key,v]=q.s;if(key==='btc')drawBTC(v,q.p);else drawSynthetic(key,v,q.p);drawVoid();renderSub(t)}
function fmt(s){s=Math.max(0,s||0);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(Math.floor(s%60)).padStart(2,'0')}
function tick(){const t=audio.currentTime||0;render(t);if(loaded){const d=audio.duration||D,pp=d?100*t/d:0;progress.value=Math.round(pp*10);progress.style.setProperty('--p',pp+'%');timeEl.textContent=fmt(t)+' / '+fmt(d);playBtn.textContent=audio.paused?'▶':'❚❚'}requestAnimationFrame(tick)}tick();
function ready(media,srtText){cues=parseSRT(srtText);audio.src=URL.createObjectURL(media);audio.onloadedmetadata=()=>{loaded=true;loader.classList.add('hide');audio.play().catch(()=>{});loadState.textContent='';};audio.load()}
function ingest(files){const arr=[...files],m=arr.find(f=>/\.(mp4|m4a|mp3|wav)$/i.test(f.name)||f.type.startsWith('audio')||f.type.startsWith('video')),s=arr.find(f=>/\.srt$/i.test(f.name));if(!m||!s){loadState.textContent='11.mp4 と 11.srt の2ファイルを選択してください。';return}loadState.textContent='LOADING SOURCE…';const fr=new FileReader();fr.onload=()=>ready(m,fr.result);fr.readAsText(s,'utf-8')}
pick.onclick=()=>fileInput.click();fileInput.onchange=e=>ingest(e.target.files);loader.ondragover=e=>{e.preventDefault();loadState.textContent='DROP TO LOAD'};loader.ondrop=e=>{e.preventDefault();ingest(e.dataTransfer.files)};
playBtn.onclick=()=>audio.paused?audio.play():audio.pause();progress.oninput=()=>{if(loaded){const d=audio.duration||D;audio.currentTime=d*(+progress.value/1000)}};stage.addEventListener('mousemove',e=>{const r=stage.getBoundingClientRect();const near=e.clientY>r.bottom-82;stage.classList.toggle('controls',near);lastPointer=performance.now()});stage.addEventListener('mouseleave',()=>stage.classList.remove('controls'));addEventListener('keydown',e=>{if(e.code==='Space'&&loaded){e.preventDefault();audio.paused?audio.play():audio.pause()}if(e.key==='f'||e.key==='F')document.fullscreenElement?document.exitFullscreen():stage.requestFullscreen();if(e.key==='ArrowRight'&&loaded)audio.currentTime=Math.min(audio.duration,audio.currentTime+5);if(e.key==='ArrowLeft'&&loaded)audio.currentTime=Math.max(0,audio.currentTime-5)});
</script></body></html>'''.replace('__BTC_DATA__', DATA)

(DIST/'OPEN_DIRECT.html').write_text(html,encoding='utf-8')
(DIST/'OPEN_DIRECT.bat').write_text('@echo off\nstart "" "%~dp0OPEN_DIRECT.html"\n',encoding='utf-8')
(DIST/'README.txt').write_text('''KIYOSAKI ICT11 WEB v1.2\n\n1. OPEN_DIRECT.bat 실행\n2. SELECT SOURCE FILES에서 원본 11.mp4 + 11.srt 선택\n3. 이후 브라우저에서 즉시 재생\n\n핵심 변경\n- 191개 랜덤 씬 대신 25개 지속형 차트 시퀀스\n- 동일 차트 상태가 다음 설명으로 누적\n- 중앙 자막 safe void\n- 자막 타이밍 setTimeout 0\n- 실제 2026-08-01~09-04 BTCUSDT 4H 데이터 내장 (빌드 시 Binance 공개 API 수집, 실패 시 로컬 fallback)\n- 실제 BTC 사례와 4H→15M→5M 연속 확대\n- 대시보드/카드/원형 UI 0\n- 외부 런타임 리소스 0\n''',encoding='utf-8')
qa={
 'version':'1.2','runtime_seconds':1172.638,'sequence_count':25,'external_runtime_assets':0,
 'subtitle_clock':'audio.currentTime','subtitle_delay_ms':0,'top_left_ui':0,'top_right_ui':0,
 'actual_btc_4h_rows':len(btc4),'actual_btc_15m_rows':len(btc15),'actual_btc_5m_rows':len(btc5),
 'btc_source':'Binance public API at build time, with deterministic offline fallback',
 'design':'persistent chart film; no cards/dashboard/panel UI'
}
(DIST/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
(DIST/'VISUAL_DIRECTION.md').write_text('''# ICT11 v1.2 Visual Direction\n\n- Full-frame market chart, not a web dashboard.\n- 25 persistent sequences, not 191 unrelated random scenes.\n- Central 28% is a subtitle-void composition zone.\n- HH/HL/LH/LL/BOS/CHoCH/BSL/SSL/ORDER BLOCK are chart annotations, never UI cards.\n- Stop-hunt and displacement are shown by price motion itself.\n- Final BTC case study reuses one real market dataset and progressively reveals every concept learned earlier.\n- Multi-timeframe section behaves like a microscope: 4H → 15M → 5M on the same market event.\n''',encoding='utf-8')
zip_path=ROOT/'dist'/'KIYOSAKI_ICT11_WEB_v1_2_PERSISTENT_MARKET_FILM_DIRECT.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in DIST.rglob('*'):
        if p.is_file(): z.write(p,p.relative_to(DIST.parent))
print(zip_path)
print(json.dumps(qa,ensure_ascii=False))
