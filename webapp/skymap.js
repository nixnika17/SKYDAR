/* First-person sky map: you stand on the ground and look up. Drag to look around, tap a star (or any spot) to see what changes there.
   Everything is drawn locally from stars.js - no external servers needed. */
const SkyMap=(()=>{
 const M=SkyMath,R=M.R,$=id=>document.getElementById(id);
 let cv,ctx,gc,gx,W=0,H=0,dpr=1,Rp=300,running=false,inited=false,B=M.basis(180,35);
 let lat=50,lon=30,locOK=false,tOff=0;           // generic fallback until the browser gives the real location
 let az0=180,alt0=35,fov=100,TARGETS=[],cb={},sel=null,anim=null,done=new Set(),nowL=0,EVS=[],deep=[],used=[],maglim=4.5,catState="loading",gyroOn=false,gotOri=false,smooth=null,gyroOff=[];
 const EC={moving:"#ff5d73",variable:"#ffb347",transient:"#5ee6ff",asteroid:"#d0d6e8",release:"#9b7bff"},EI={moving:"🏃",variable:"💥",transient:"✨",asteroid:"☄️",release:"📡"};
 const opt={lines:true,names:true,xray:false};
 const stars=STARS.map(r=>({name:r[0],ra:M.hms(r[1]),dec:M.dms(r[2]),mag:r[3],con:r[4]})),BY={},CC={};
 stars.forEach(s=>BY[s.name]=s);
 const named=[...stars].sort((a,b)=>a.mag-b.mag);
 for(const [c,segs] of Object.entries({...CONS,...ASTER})){let x=0,y=0,z=0,n=0;new Set(segs.flat()).forEach(k=>{const s=BY[k];if(!s)return;const a=s.ra*R,d=s.dec*R;x+=Math.cos(d)*Math.cos(a);y+=Math.cos(d)*Math.sin(a);z+=Math.sin(d);n++});
  if(n)CC[c]={ra:M.norm(Math.atan2(y,x)/R),dec:Math.atan2(z,Math.hypot(x,y))/R,dashed:c in ASTER}}
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 const now=()=>Date.now()+tOff*3600e3;

 // ---------- persistence / score ----------
 try{JSON.parse(localStorage.getItem("skydar_done")||"[]").forEach(i=>done.add(i))}catch(e){}
 function score(){const el=$("score");if(el)el.textContent=`⭐ ${done.size}/${TARGETS.length||5}`}
 function toast(t){const el=$("toast");if(!el)return;el.textContent=t;el.hidden=false;clearTimeout(toast._t);toast._t=setTimeout(()=>el.hidden=true,3800)}
 function complete(id){if(!id||done.has(id))return;done.add(id);try{localStorage.setItem("skydar_done",JSON.stringify([...done]))}catch(e){}
  const t=TARGETS.find(x=>x.id===id);score();toast(`🎉 Mission complete: ${t?t.mission:id}!  ⭐ ${done.size}/${TARGETS.length}`);renderMissions()}

 // ---------- location & time ----------
 function setLoc(la,lo,ok){lat=clamp(la,-89.9,89.9);lon=lo;locOK=ok;if(ok&&cb.onLoc)cb.onLoc();$("tg-loc").textContent=`📍 ${Math.abs(lat).toFixed(1)}°${lat>=0?"N":"S"} ${Math.abs(lon).toFixed(1)}°${lon>=0?"E":"W"}${ok?"":" (set yours)"}`}
 function manualLoc(){const t=prompt("Your latitude, longitude in degrees (e.g. 50.45, 30.52):",`${lat.toFixed(2)}, ${lon.toFixed(2)}`);if(!t)return;
  const m=t.match(/-?\d+(\.\d+)?/g);if(m&&m.length>=2&&Math.abs(+m[0])<=90&&Math.abs(+m[1])<=180)setLoc(+m[0],+m[1],true);else toast("Could not read that - use two numbers like 50.45, 30.52")}
 function locate(){if(!navigator.geolocation)return manualLoc();
  navigator.geolocation.getCurrentPosition(p=>{setLoc(p.coords.latitude,p.coords.longitude,true);toast("Sky set for your location 📍")},()=>manualLoc(),{timeout:8000,maximumAge:3600e3})}

 // ---------- layout ----------
 function resize(){const w=cv.clientWidth,h=cv.clientHeight;if(!w||!h)return false;dpr=Math.min(window.devicePixelRatio||1,2);
  if(w!==W||h!==H||cv.width!==Math.round(w*dpr)){W=w;H=h;cv.width=Math.round(w*dpr);cv.height=Math.round(h*dpr)}return true}
 const P=v=>M.proj(v,B,Rp,W/2,H/2);
 const hv=(ra,dec)=>M.toHor(ra,dec,nowL,lat);

 // ---------- drawing ----------
 function backdrop(){const gw=Math.ceil(W/6),gh=Math.ceil(H/6);if(gc.width!==gw||gc.height!==gh){gc.width=gw;gc.height=gh}
  const img=gx.createImageData(gw,gh),d=img.data;let i=0;
  for(let j=0;j<gh;j++)for(let k=0;k<gw;k++){const v=M.unproj((k+.5)*W/gw,(j+.5)*H/gh,B,Rp,W/2,H/2),alt=Math.asin(clamp(v[2],-1,1))/R;
   const glow=Math.pow(1-Math.min(Math.max(alt,0)/70,1),3);let r=5+glow*36,g=9+glow*48,b=26+glow*74;
   if(alt<0){const f=opt.xray?.4:1;r=r*(1-f)+10*f;g=g*(1-f)+32*f;b=b*(1-f)+24*f}
   d[i++]=r;d[i++]=g;d[i++]=b;d[i++]=255}
  gx.putImageData(img,0,0);ctx.imageSmoothingEnabled=true;ctx.drawImage(gc,0,0,W,H)}
 function nameLabel(t,x,y){ctx.font="12px system-ui";const w=ctx.measureText(t).width,r=[x-2,y-12,x+w+2,y+3];
  for(const u of used)if(r[0]<u[2]&&r[2]>u[0]&&r[1]<u[3]&&r[3]>u[1])return;used.push(r);label(t,x,y,"rgba(220,232,255,.8)",12)}
 const hidden=v=>v[2]<0&&!opt.xray, dim=v=>v[2]<0?.35:1;
 function label(t,x,y,col,size,al){ctx.font=`${size||12}px system-ui`;ctx.textAlign=al||"left";ctx.fillStyle=col||"rgba(220,232,255,.85)";ctx.fillText(t,x,y)}
 function frame(t){
  nowL=M.lst(now(),lon);B=M.basis(az0,alt0);Rp=(Math.min(W,H)/2)/(2*Math.tan(fov*R/4));
  ctx.setTransform(dpr,0,0,dpr,0,0);used.length=0;backdrop();
  stars.forEach(s=>{s.v=hv(s.ra,s.dec);s.p=P(s.v)});
  for(const s of deep){s.v=hv(s.ra,s.dec);s.p=P(s.v)}
  // lines
  const seg=(set,dash)=>{ctx.setLineDash(dash?[5,5]:[]);ctx.lineWidth=1;
   for(const segs of Object.values(set))for(const [a,b] of segs){const A=BY[a],Bs=BY[b];if(!A.p||!Bs.p||hidden(A.v)||hidden(Bs.v))continue;
    ctx.strokeStyle=dash?"rgba(255,209,102,.38)":"rgba(120,170,255,.30)";ctx.globalAlpha=Math.min(dim(A.v),dim(Bs.v));ctx.beginPath();ctx.moveTo(A.p[0],A.p[1]);ctx.lineTo(Bs.p[0],Bs.p[1]);ctx.stroke()}
   ctx.globalAlpha=1;ctx.setLineDash([])};
  if(opt.lines){seg(CONS,false);seg(ASTER,true)}
  // stars
  const zoomK=(100/clamp(fov,40,140))**.25;
  const star=s=>{if(s.mag>maglim||!s.p||hidden(s.v))return;const r=Math.max(.9,4.4-0.85*s.mag)*zoomK,tw=.88+.12*Math.sin(t/500+s.ra),col=(s.name&&TINT[s.name])||"#eaf0ff";
   ctx.globalAlpha=dim(s.v)*tw*(s.mag>3.5?clamp(1.2-(s.mag-3.5)*.15,.5,1):1);ctx.fillStyle=col;
   if(s.mag<3.5){ctx.shadowColor=col;ctx.shadowBlur=s.mag<2.5?r*2.6:r}else ctx.shadowBlur=0;ctx.beginPath();ctx.arc(s.p[0],s.p[1],r,0,7);ctx.fill()};
  for(const s of stars)star(s);for(const s of deep)star(s);
  ctx.shadowBlur=0;ctx.globalAlpha=1;
  // names
  if(opt.names){const lim=fov>95?1.9:fov>60?2.4:fov>35?3.1:9;for(const s of named){if(!s.p||hidden(s.v)||s.mag>lim||s.mag>maglim||s.p[0]<-20||s.p[0]>W+20||s.p[1]<-10||s.p[1]>H+10)continue;
   ctx.globalAlpha=dim(s.v);nameLabel(s.name,s.p[0]+8,s.p[1]-6);ctx.globalAlpha=1}
   if(fov<=115)for(const [c,o] of Object.entries(CC)){const v=hv(o.ra,o.dec),p=P(v);if(!p||hidden(v))continue;ctx.globalAlpha=dim(v)*.7;label(c.toUpperCase(),p[0],p[1]+30,o.dashed?"rgba(255,209,102,.8)":"rgba(140,180,255,.75)",10,"center");ctx.globalAlpha=1}}
  // horizon + compass
  ctx.strokeStyle="rgba(120,200,160,.5)";ctx.lineWidth=1.5;ctx.beginPath();let pen=false;
  for(let a=0;a<=360;a+=3){const p=P([Math.cos(a*R),Math.sin(a*R),0]);if(!p){pen=false;continue}pen?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]);pen=true}ctx.stroke();
  [["N",0],["NE",45],["E",90],["SE",135],["S",180],["SW",225],["W",270],["NW",315]].forEach(([n,a])=>{const p=P([Math.cos(a*R),Math.sin(a*R),0]);if(!p||p[0]<0||p[0]>W||p[1]<0||p[1]>H)return;
   label(n,p[0],p[1]+(opt.xray?-8:18),n==="N"?"#ff8a8a":"rgba(200,255,225,.9)",n.length===1?18:12,"center")});
  // missions
  TARGETS.forEach(q=>{const v=hv(q.ra,q.dec),p=P(v);q._v=v;q._p=p;if(!p||hidden(v)||p[0]<-30||p[0]>W+30||p[1]<-30||p[1]>H+30)return;
   const ok=done.has(q.id),pulse=(Math.sin(t/350)+1)/2;ctx.globalAlpha=dim(v);ctx.strokeStyle=ok?"#5df2a0":"#ffd166";ctx.lineWidth=2;
   ctx.beginPath();ctx.arc(p[0],p[1],13+pulse*5,0,7);ctx.stroke();ctx.globalAlpha=dim(v)*(.35-pulse*.25);ctx.beginPath();ctx.arc(p[0],p[1],22+pulse*10,0,7);ctx.stroke();
   ctx.globalAlpha=dim(v);ctx.fillStyle=ok?"#5df2a0":"#ffd166";ctx.font="14px system-ui";ctx.textAlign="center";ctx.fillText(ok?"✓":"★",p[0],p[1]+5);
   label(q.mission,p[0],p[1]-22,ok?"#5df2a0":"#ffd166",12,"center");ctx.globalAlpha=1});
  // event beacons: live changes found in the telescope data
  EVS.forEach(e=>{const v=hv(e.ra,e.dec),p=P(v);e._v=v;e._p=p;if(!p||hidden(v)||p[0]<-30||p[0]>W+30||p[1]<-30||p[1]>H+30)return;
   const col=EC[e.kind]||"#fff",ph=((t/45)+e.ra*3)%36;ctx.globalAlpha=dim(v)*(1-ph/36);ctx.strokeStyle=col;ctx.lineWidth=2;ctx.beginPath();ctx.arc(p[0],p[1],6+ph,0,7);ctx.stroke();
   ctx.globalAlpha=dim(v);ctx.fillStyle=col;ctx.shadowColor=col;ctx.shadowBlur=14;ctx.beginPath();ctx.arc(p[0],p[1],5,0,7);ctx.fill();ctx.shadowBlur=0;
   if(fov<80||(sel&&sel.event===e))label(`${EI[e.kind]||""} ${e.title}`.slice(0,38),p[0],p[1]+28,col,11,"center");ctx.globalAlpha=1});
  // selection
  if(sel){const p=P(hv(sel.ra,sel.dec));if(p){ctx.strokeStyle="#5ee6ff";ctx.lineWidth=2;ctx.beginPath();ctx.arc(p[0],p[1],16,0,7);ctx.stroke();
   [[1,0],[-1,0],[0,1],[0,-1]].forEach(([a,b])=>{ctx.beginPath();ctx.moveTo(p[0]+a*20,p[1]+b*20);ctx.lineTo(p[0]+a*28,p[1]+b*28);ctx.stroke()})}}
  // fly animation
  if(anim){const k=clamp((performance.now()-anim.t0)/anim.dur,0,1),e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2;az0=M.norm(anim.a0+anim.da*e);alt0=anim.h0+(anim.h1-anim.h0)*e;fov=anim.f0+(anim.f1-anim.f0)*e;if(k>=1)anim=null}
 }
 function loop(t){if(!running)return;
  try{if(resize())frame(t)}catch(e){console.error("SkyMap render error:",e);const h=$("sk-hint");if(h){h.hidden=false;h.textContent="Sky map error: "+e.message}}
  requestAnimationFrame(loop)}

 // ---------- selection / info card ----------
 function nearestStar(ra,dec){let b=null,bd=1e9;for(const s of stars){const d=M.sep(ra,dec,s.ra,s.dec);if(d<bd){bd=d;b=s}}return [b,bd]}
 function select(o){sel=o;showInfo(o)}
 function showInfo(o){const aa=M.altaz(hv(o.ra,o.dec)),card=$("sk-info"),up=aa.alt>0;
  const where=up?`Right now it is ${Math.round(aa.alt)}° above your horizon, toward the ${M.dir8(aa.az)}.`:`Right now it is below your horizon (the Earth is in the way) - tick “See through ground” to look at it anyway.`;
  let title,sub="",fact="",btn="🔭 See what changes here",fovOpen=0.15,mission=null;
  if(o.event){const e=o.event;title=`${EI[e.kind]||"🔭"} ${e.title}`;sub=`${e.demo?"🧪 DEMO · ":""}${e.target_name||""}`;fact=e.text+(e.vis?`<br><br>🔭 ${e.vis}`:"");btn="🎞 Watch the time-lapse";fovOpen=e.field?e.field[2]:0.15}
  else if(o.quest){title=`🎯 ${o.quest.mission}`;sub=`Target: ${o.quest.name}`;fact=`${o.quest.story}<br><br><b>Your task:</b> ${o.quest.look}`;btn="▶ Start mission";fovOpen=o.quest.fov;mission=o.quest.id}
  else if(o.star){title=o.star.name||"A star";sub=`${o.star.con?`Star in ${o.star.con} · `:""}brightness ${o.star.mag.toFixed(1)} magnitude (lower = brighter)`;fact=(o.star.name?FACTS[o.star.name]:"Visible to the naked eye only under a fairly dark sky.")||"";if(o.star.mag<2)fact+=(fact?" ":"")+"Very bright stars look like big blobs in a telescope. Try a spot right next to it!"}
  else{const [s,d]=nearestStar(o.ra,o.dec);title="A spot in the sky";sub=d<8?`Near ${s.name} (${d.toFixed(1)}° away)`:"Somewhere out there";fact="Every patch of sky holds thousands of faint objects. Let's see if anything there moves or changes."}
  card.innerHTML=`<button class="x" id="sk-x" aria-label="Close">✕</button><b style="font-size:17px">${title}</b><div class="legend">${sub}</div>${fact?`<p style="margin:8px 0">${fact}</p>`:""}<div class="legend" id="sk-when" style="margin-top:6px"></div><div class="legend" style="font-size:12px;margin-top:6px">${where}<br>RA ${o.ra.toFixed(3)}° · Dec ${o.dec.toFixed(3)}°</div><button class="btn pri" id="sk-go" style="width:100%;margin-top:10px">${btn}</button>`;
  card.hidden=false;$("sk-x").onclick=()=>{card.hidden=true;sel=null};
  const open=o.event&&o.event.field?{ra:o.event.field[0],dec:o.event.field[1]}:o;
  $("sk-go").onclick=()=>cb.onOpen&&cb.onOpen({ra:open.ra,dec:open.dec,fov:fovOpen,mission,name:title});
  if(cb.visibility)cb.visibility(o.ra,o.dec).then(t=>{const el=$("sk-when");if(el&&sel===o)el.innerHTML=t})}

 // ---------- missions sheet ----------
 function renderMissions(){const el=$("sk-missions");if(!el)return;
  el.innerHTML=`<button class="x" id="sk-mx" aria-label="Close">✕</button><b style="font-size:17px">🎯 Missions</b><div class="legend" style="margin:4px 0 8px">Five real targets for NASA's SPHEREx telescope. Fly to one, start the mission, then press ▶ to find what moves or flickers. ⭐ ${done.size}/${TARGETS.length}</div>`+
   TARGETS.map(t=>`<div class="find" data-id="${t.id}" style="margin:6px 0"><div class="ic">${done.has(t.id)?"✅":t.emoji}</div><div style="flex:1"><b>${t.mission}</b><small>${t.name}</small></div></div>`).join("");
  el.querySelectorAll(".find").forEach(d=>d.onclick=()=>{const t=TARGETS.find(x=>x.id===d.dataset.id);el.hidden=true;flyTo(t.ra,t.dec);select({ra:t.ra,dec:t.dec,quest:t})});
  $("sk-mx").onclick=()=>el.hidden=true}

 // ---------- camera ----------
 function flyTo(ra,dec){const aa=M.altaz(M.toHor(ra,dec,M.lst(now(),lon),lat));
  if(aa.alt<0&&!opt.xray){setXray(true);toast("That target is below your horizon right now, so the ground is see-through.")}
  anim={t0:performance.now(),dur:900,a0:az0,da:((aa.az-az0+540)%360)-180,h0:alt0,h1:clamp(aa.alt,-80,85),f0:fov,f1:Math.min(fov,70)}}
 function setXray(on){opt.xray=on;$("tg-xray").classList.toggle("on",on)}
 function darkText(){const n=stars.filter(s=>s.mag<=maglim).length+deep.filter(s=>s.mag<=maglim).length,e=$("sk-dark-n");
  if(e)e.textContent=catState==="ok"?`${n.toLocaleString()} stars`:catState==="loading"?`${n} stars…`:`${n} stars (full catalogue missing)`}
 function setDark(m){maglim=m;try{localStorage.setItem("skydar_dark",String(m))}catch(e){}darkText()}
 // ---------- gyroscope: hold the phone up like a window onto the sky ----------
 function onOri(a,b,g){if(!gyroOn||a==null||b==null||g==null||isNaN(a+b+g))return;gotOri=true;const o=M.oriToAzAlt(a,b,g);
  if(!smooth)smooth={az:o.az,alt:o.alt};else{smooth.az=M.norm(smooth.az+(((o.az-smooth.az+540)%360)-180)*.25);smooth.alt+=(o.alt-smooth.alt)*.25}
  az0=smooth.az;alt0=clamp(smooth.alt,-89,89);anim=null;hint()}
 function gyroBtn(){const b=$("tg-gyro");if(b){b.classList.toggle("on",gyroOn);b.textContent=`🧭 Gyroscope: ${gyroOn?"on":"off"}`}}
 async function setGyro(on){
  if(!on){gyroOn=false;gyroOff.forEach(f=>{try{f()}catch(e){}});gyroOff=[];smooth=null;gyroBtn();return false}
  try{if(typeof DeviceOrientationEvent!=="undefined"&&DeviceOrientationEvent.requestPermission){const r=await DeviceOrientationEvent.requestPermission();if(r!=="granted"){toast("Motion access was denied. Allow it in the browser settings.");return false}}}catch(e){}
  gyroOn=true;gotOri=false;smooth=null;
  const abs="ondeviceorientationabsolute" in window,ev=abs?"deviceorientationabsolute":"deviceorientation";
  const h=e=>onOri(e.webkitCompassHeading!=null?360-e.webkitCompassHeading:e.alpha,e.beta,e.gamma);   // iOS gives the compass heading separately
  window.addEventListener(ev,h,true);gyroOff.push(()=>window.removeEventListener(ev,h,true));
  const T=window.Telegram&&window.Telegram.WebApp;   // Telegram's own sensor API (radians) for Mini Apps
  if(T&&T.DeviceOrientation&&T.DeviceOrientation.start){try{const O=T.DeviceOrientation,k=180/Math.PI,th=()=>onOri(O.alpha*k,O.beta*k,O.gamma*k);
   T.onEvent("deviceOrientationChanged",th);O.start({refresh_rate:60,need_absolute:true});gyroOff.push(()=>{try{T.offEvent("deviceOrientationChanged",th);O.stop()}catch(e){}})}catch(e){}}
  gyroBtn();toast("Hold the phone up like a window and move it around the sky 🧭");
  setTimeout(()=>{if(gyroOn&&!gotOri){setGyro(false);toast("No motion-sensor data here. Inside Telegram try 🌐 Open in browser, or allow motion sensors for this site.")}},3500);
  return true}
 function hint(){const h=$("sk-hint");if(h)h.hidden=true}

 // ---------- input ----------
 function bind(){
  const ptrs=new Map();let g=null,pinch=0;
  cv.addEventListener("pointerdown",e=>{cv.setPointerCapture(e.pointerId);ptrs.set(e.pointerId,{x:e.clientX,y:e.clientY});anim=null;
   g={x:e.clientX,y:e.clientY,t:Date.now(),moved:false};if(ptrs.size===2){const [a,b]=[...ptrs.values()];pinch=Math.hypot(a.x-b.x,a.y-b.y);g.moved=true}});
  cv.addEventListener("pointermove",e=>{const p=ptrs.get(e.pointerId);if(!p)return;const dx=e.clientX-p.x,dy=e.clientY-p.y;p.x=e.clientX;p.y=e.clientY;
   if(ptrs.size===1){if(Math.hypot(e.clientX-g.x,e.clientY-g.y)>6)g.moved=true;if(g.moved&&!gyroOn){const dpp=fov/Math.min(W,H);az0=M.norm(az0-dx*dpp/Math.max(.35,Math.cos(alt0*R)));alt0=clamp(alt0+dy*dpp,-89,89);hint()}}
   else if(ptrs.size===2){const [a,b]=[...ptrs.values()],d=Math.hypot(a.x-b.x,a.y-b.y);if(pinch>0)fov=clamp(fov*pinch/d,12,140);pinch=d;hint()}});
  const up=e=>{if(!ptrs.has(e.pointerId))return;const was=ptrs.size;ptrs.delete(e.pointerId);
   if(was===1&&g&&!g.moved&&Date.now()-g.t<600){const r=cv.getBoundingClientRect();tap(e.clientX-r.left,e.clientY-r.top)}if(ptrs.size<2)pinch=0};
  cv.addEventListener("pointerup",up);cv.addEventListener("pointercancel",up);
  cv.addEventListener("wheel",e=>{e.preventDefault();fov=clamp(fov*Math.exp(e.deltaY*.0012),12,140);hint()},{passive:false});
  $("tg-lines").onclick=e=>{opt.lines=!opt.lines;e.currentTarget.classList.toggle("on",opt.lines)};
  $("tg-names").onclick=e=>{opt.names=!opt.names;e.currentTarget.classList.toggle("on",opt.names)};
  $("tg-xray").onclick=()=>setXray(!opt.xray);
  $("tg-loc").onclick=locate;
  $("tg-gyro").onclick=()=>setGyro(!gyroOn);gyroBtn();
  try{const m=parseFloat(localStorage.getItem("skydar_dark"));if(m>0){maglim=m;$("sk-dark").value=String(m)}}catch(e){}
  $("sk-dark").onchange=e=>setDark(+e.target.value);darkText();
  $("tg-ev").onclick=()=>cb.onEvents&&cb.onEvents();
  $("tg-miss").onclick=()=>{renderMissions();$("sk-missions").hidden=!$("sk-missions").hidden};
  $("tm").oninput=e=>{tOff=+e.target.value;$("tm-l").textContent=tOff===0?"now":`${tOff>0?"+":""}${tOff} h`};
  $("tm-l").onclick=()=>{tOff=0;$("tm").value=0;$("tm-l").textContent="now"};
  window.addEventListener("resize",()=>{if(running)resize()})}
 function tap(x,y){hint();let best=null,bd=1e9;
  for(const e of EVS){if(!e._p||hidden(e._v))continue;const d=Math.hypot(e._p[0]-x,e._p[1]-y);if(d<30&&d<bd){bd=d;best={ra:e.ra,dec:e.dec,event:e}}}
  if(!best)for(const q of TARGETS){if(!q._p||hidden(q._v))continue;const d=Math.hypot(q._p[0]-x,q._p[1]-y);if(d<28&&d<bd){bd=d;best={ra:q.ra,dec:q.dec,quest:q}}}
  if(!best){bd=1e9;for(const s of stars.concat(deep)){if(s.mag>maglim||!s.p||hidden(s.v))continue;const d=Math.hypot(s.p[0]-x,s.p[1]-y),thr=14+Math.max(0,(2.5-s.mag)*3);if(d<thr&&d<bd){bd=d;best={ra:s.ra,dec:s.dec,star:s}}}}
  if(!best){const v=M.unproj(x,y,B,Rp,W/2,H/2);if(v[2]<0&&!opt.xray){toast("That is the ground 🌱 - look up!");return}const e=M.toEq(v,nowL,lat);best={ra:e.ra,dec:e.dec}}
  select(best)}

 return {
  init(o){TARGETS=o.targets||[];cb=o;if(inited){score();return}inited=true;cv=$("skycv");ctx=cv.getContext("2d");gc=document.createElement("canvas");gx=gc.getContext("2d");
   bind();score();setLoc(lat,lon,false);
   if(navigator.geolocation)navigator.geolocation.getCurrentPosition(p=>setLoc(p.coords.latitude,p.coords.longitude,true),()=>{},{timeout:8000,maximumAge:3600e3});},
  resume(){if(running)return;running=true;requestAnimationFrame(loop)},
  pause(){running=false},
  complete,flyTo,locate,isDone:id=>done.has(id),
  getLoc:()=>({lat,lon,ok:locOK}),
  getView:()=>({az:az0,alt:alt0,fov,gyro:gyroOn}),setGyro,
  setCatalog(list){deep=[];catState=list&&list.length?"ok":"missing";
   for(const [ra,dec,mag] of list||[]){let dup=false;
    for(const s of stars){if(Math.abs(dec-s.dec)<.1){let dr=Math.abs(ra-s.ra);dr=Math.min(dr,360-dr)*Math.cos(dec*R);if(dr<.1){dup=true;break}}}
    if(!dup)deep.push({ra,dec,mag,name:null,con:null})}
   darkText()},
  setEvents(list){EVS=(list||[]).filter(e=>e.ra!=null);const b=$("tg-ev");if(b)b.textContent=`🔔 Events (${(list||[]).length})`},
  selectEvent(e){select({ra:e.ra,dec:e.dec,event:e})}
 };
})();
window.SkyMap=SkyMap;
