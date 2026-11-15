/* SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer. */
/* Pure sky maths (no DOM): sidereal time, equatorial <-> horizontal, stereographic projection. */
const SkyMath=(()=>{
 const R=Math.PI/180, norm=a=>((a%360)+360)%360;
 const jd=ms=>ms/86400000+2440587.5;
 const lst=(ms,lon)=>norm(280.46061837+360.98564736629*(jd(ms)-2451545.0)+lon);   // local sidereal time, degrees
 // equatorial (deg) -> horizontal unit vector [north, east, up]
 const toHor=(ra,dec,L,lat)=>{const H=(L-ra)*R,d=dec*R,p=lat*R,cd=Math.cos(d),sd=Math.sin(d);
  return [sd*Math.cos(p)-cd*Math.cos(H)*Math.sin(p), -cd*Math.sin(H), sd*Math.sin(p)+cd*Math.cos(H)*Math.cos(p)]};
 const toEq=(v,L,lat)=>{const p=lat*R,Z=v[0]*Math.cos(p)+v[2]*Math.sin(p),X=v[2]*Math.cos(p)-v[0]*Math.sin(p);
  return {ra:norm(L-Math.atan2(-v[1],X)/R),dec:Math.asin(Math.max(-1,Math.min(1,Z)))/R}};
 const altaz=v=>({alt:Math.asin(Math.max(-1,Math.min(1,v[2])))/R,az:norm(Math.atan2(v[1],v[0])/R)});
 const hms=s=>{const [h,m=0,x=0]=s.trim().split(/\s+/).map(Number);return (h+m/60+x/3600)*15};
 const dms=s=>{const t=s.trim(),neg=t[0]==="-",[d,m=0,x=0]=t.replace(/^[+-]/,"").split(/\s+/).map(Number),v=d+m/60+x/3600;return neg?-v:v};
 const dir8=az=>["N","NE","E","SE","S","SW","W","NW"][Math.round(norm(az)/45)%8];
 const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
 const basis=(az0,alt0)=>{const a=az0*R,e=alt0*R,ca=Math.cos(a),sa=Math.sin(a),ce=Math.cos(e),se=Math.sin(e);
  return {f:[ce*ca,ce*sa,se],r:[-sa,ca,0],u:[-se*ca,-se*sa,ce]}};   // forward, right, up
 const proj=(v,B,Rp,cx,cy)=>{const d=dot(v,B.f);if(d<-0.97)return null;const k=2/(1+d);return [cx+dot(v,B.r)*k*Rp,cy-dot(v,B.u)*k*Rp,d]};
 const unproj=(px,py,B,Rp,cx,cy)=>{const X=(px-cx)/Rp,Y=(cy-py)/Rp,q=X*X+Y*Y,d=(4-q)/(4+q),s=(1+d)/2;
  return [0,1,2].map(i=>d*B.f[i]+s*(X*B.r[i]+Y*B.u[i]))};
 const sep=(r1,d1,r2,d2)=>{const a=toHor(r1,d1,0,0),b=toHor(r2,d2,0,0);return Math.acos(Math.max(-1,Math.min(1,dot(a,b))))/R};
 // W3C DeviceOrientation (alpha,beta,gamma in degrees) -> direction the BACK of the phone points at (like looking through a window)
 const oriToAzAlt=(a,b,g)=>{const A=a*R,B=b*R,G=g*R,cA=Math.cos(A),sA=Math.sin(A),cB=Math.cos(B),sB=Math.sin(B),cG=Math.cos(G),sG=Math.sin(G),
  east=-(cA*sG+sA*sB*cG),north=-(sA*sG-cA*sB*cG),up=-cB*cG;return {az:norm(Math.atan2(east,north)/R),alt:Math.asin(Math.max(-1,Math.min(1,up)))/R}};
 return {oriToAzAlt,R,norm,lst,toHor,toEq,altaz,hms,dms,dir8,dot,basis,proj,unproj,sep};
})();
