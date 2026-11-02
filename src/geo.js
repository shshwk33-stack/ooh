import { locations } from './research.js';
export function inside(p, ring) { let result=false; for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])result=!result;}return result; }
export function makeRoads(ring){
 const features=[];const dx=.00083,dy=.00069;
 const node=(i,j)=>{const x=126.86+i*dx,y=37.525+j*dy;return[x+Math.sin(j*.11)*.0013+Math.sin(j*.43)*.00012,y+Math.sin(i*.12)*.00085]};
 for(let i=0;i<135;i++)for(let j=0;j<104;j++){const a=node(i,j);if(!inside(a,ring))continue;for(const [di,dj] of [[1,0],[0,1]]){const b=node(i+di,j+dj);if(!inside(b,ring))continue;const major=di?j%12===0:i%13===0;const traffic=major?3300+(i*7+j*11)%1000:300+(i*73+j*127+(di?400:0))%2800;features.push({type:'Feature',properties:{id:`MP-${i}-${j}-${di}`,traffic,major,name:major?'마포 간선 구간':'마포 생활도로 구간'},geometry:{type:'LineString',coordinates:[a,b]}})}}
 return{type:'FeatureCollection',features};
}
export const trafficColor=v=>v==null?'#52646a':v>=3000?'#ffde89':v>=1900?'#f5ab57':v>=900?'#e247a1':'#633e9b';
export const hexColors=['#db5d48','#ee8050','#f2a85b','#f5ca6b','#e8dc7e','#c9d877','#8fc86a','#57b478','#2f9e75'];
export function fieldValue(lon,lat,rows){let weighted=0,total=0,nearest=rows[0],distance=Infinity;for(const c of rows){const[cy,cx]=locations[c.id];const d=Math.hypot((cx-lon)*.79,cy-lat);const influence=Math.exp(-(d*d)/.00013);weighted+=influence*c.score;total+=influence;if(d<distance){distance=d;nearest=c}}const proximity=Math.exp(-distance*distance/.00032);return{value:Math.min(.99,(total?weighted/total:0)*proximity),nearest};}
export function makeHexagons(ring,rows){const cells=[];const r=.0008;let n=0;for(let col=0;col<83;col++){const lon=126.865+col*r*1.5;for(let row=0;row<70;row++){const lat=37.53+row*r*1.37+(col%2)*r*.685;if(!inside([lon,lat],ring))continue;const{value,nearest}=fieldValue(lon,lat,rows);const vertices=Array.from({length:6},(_,i)=>{const a=i*Math.PI/3;return[lon+r*.98*Math.cos(a),lat+r*.79*.98*Math.sin(a)]});cells.push({id:`H-${String(n++).padStart(4,'0')}`,lon,lat,value,nearest,vertices});}}return cells;}
