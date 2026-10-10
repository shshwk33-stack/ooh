/* Run with the fixture prepared by check_boundary_helper.py. */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const {extractMapo,makeZip}=require('./core.js');
const dir=process.argv[2];
const files=['shp','shx','dbf','prj'].map(ext=>new File([fs.readFileSync(path.join(dir,'fixture.'+ext))],'fixture.'+ext));
const options={expectedRows:2};
const replace=(ext,change)=>files.map(f=>f.name.endsWith('.'+ext)?change(f):f);
const rejects=async(list,pattern)=>assert.rejects(()=>extractMapo(list,options),pattern);
(async()=>{
  let checks=0;
  const result=await extractMapo(files,options);
  assert.equal(result.metadata.selected_records,2);
  assert.deepEqual(result.metadata.selected_original_record_indices_zero_based,[1,3]);
  fs.writeFileSync(path.join(dir,'roundtrip.zip'),makeZip(result.files));checks++;
  await rejects(files.filter(f=>!f.name.endsWith('.prj')),/PRJ/);checks++;
  await rejects(replace('prj',f=>new File(['GEOGCS["WGS84"]'],f.name)),/UTM_K/);checks++;
  await rejects(replace('dbf',f=>new File([fs.readFileSync(path.join(dir,f.name))],'different.dbf')),/앞부분/);checks++;
  const dbf=fs.readFileSync(path.join(dir,'fixture.dbf')); const badCount=Buffer.from(dbf);badCount.writeUInt32LE(6,4);
  await rejects(replace('dbf',f=>new File([badCount],f.name)),/잘렸|개수/);checks++;
  const shx=fs.readFileSync(path.join(dir,'fixture.shx'));const wrongOffset=Buffer.from(shx);wrongOffset.writeUInt32BE(51,100);
  await rejects(replace('shx',f=>new File([wrongOffset],f.name)),/색인/);checks++;
  const shp=fs.readFileSync(path.join(dir,'fixture.shp'));const wrongHeader=Buffer.from(shp);wrongHeader.writeUInt32BE(9995,0);
  await rejects(replace('shp',f=>new File([wrongHeader],f.name)),/형식/);checks++;
  const offset=shx.readUInt32BE(108)*2;const badRecord=Buffer.from(shp);badRecord.writeUInt32BE(999,offset);
  await rejects(replace('shp',f=>new File([badRecord],f.name)),/레코드/);checks++;
  const badPoint=Buffer.from(shp);const parts=badPoint.readUInt32LE(offset+8+36);badPoint.writeDoubleLE(NaN,offset+8+44+4*parts);
  await rejects(replace('shp',f=>new File([badPoint],f.name)),/좌표/);checks++;
  await assert.rejects(()=>extractMapo(files),/16개/);checks++;
  const badBounds=Buffer.from(shp);badBounds.writeDoubleLE(1,offset+8+4);
  await rejects(replace('shp',f=>new File([badBounds],f.name)),/범위/);checks++;
  // Simulate a 120MB source: an unselected large record is never loaded.
  const payload=shp.subarray(offset+8,offset+8+shx.readUInt32BE(112)*2);
  const skippedWords=60*1024*1024;
  const secondOffset=50+4+skippedWords;
  const record=Buffer.alloc(8+payload.length);record.writeUInt32BE(2,0);record.writeUInt32BE(payload.length/2,4);payload.copy(record,8);
  const largeSize=secondOffset*2+record.length;
  const largeHeader=Buffer.from(shp.subarray(0,100));largeHeader.writeUInt32BE(largeSize/2,24);
  const largeIndex=Buffer.alloc(116);largeHeader.copy(largeIndex);largeIndex.writeUInt32BE(58,24);
  largeIndex.writeUInt32BE(50,100);largeIndex.writeUInt32BE(skippedWords,104);
  largeIndex.writeUInt32BE(secondOffset,108);largeIndex.writeUInt32BE(payload.length/2,112);
  const h=dbf.readUInt16LE(8), row=dbf.readUInt16LE(10);
  const twoRows=Buffer.alloc(h+2*row+1);dbf.copy(twoRows,0,0,h);twoRows.writeUInt32LE(2,4);
  dbf.copy(twoRows,h,h,h+row);dbf.copy(twoRows,h+row,h+row,h+2*row);twoRows[twoRows.length-1]=26;
  const reads=[];
  const virtual={name:'fixture.shp',size:largeSize,slice(start,end){
    reads.push([start,end]);
    if(start===0&&end===100)return new Blob([largeHeader]);
    if(start===secondOffset*2&&end===largeSize)return new Blob([record]);
    throw new Error('Unexpected large source read');
  }};
  const virtualFiles=[virtual,new File([largeIndex],'fixture.shx'),new File([twoRows],'fixture.dbf'),files[3]];
  const small=await extractMapo(virtualFiles,{expectedRows:1});
  assert.equal(small.metadata.selected_records,1);
  assert.equal(reads.length,2);assert.ok(reads.reduce((n,[s,e])=>n+e-s,0)<10000);checks++;
  // Execute both generated inline scripts with DOM event stubs.
  const html=fs.readFileSync(path.join(dir,'helper.html'),'utf8');
  const elements=Object.fromEntries(['files','create','status','download'].map(id=>[id,{style:{},handlers:{},addEventListener(event,fn){this.handlers[event]=fn;}}]));
  const context=vm.createContext({TextEncoder,TextDecoder,Uint8Array,DataView,Blob,File,Set,Math,Array,Number,String,Error,Infinity,
    document:{getElementById:id=>elements[id]},URL:{createObjectURL:()=> 'blob:fixture',revokeObjectURL:()=>{}}});
  for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(match[1],context);
  // Wrong expected coverage should display an error and re-enable controls.
  elements.files.files=files;elements.files.handlers.change();await elements.create.handlers.click();
  assert.match(elements.status.textContent,/16개/);assert.equal(elements.create.disabled,false);checks++;
  // Allow synthetic fixture coverage only in the test VM, preserving production default 16.
  const original=context.TransitBoundaryHelper.extractMapo;
  context.TransitBoundaryHelper.extractMapo=list=>original(list,{expectedRows:2});
  await elements.create.handlers.click();
  assert.equal(elements.download.style.display,'block');assert.equal(elements.download.href,'blob:fixture');
  assert.match(elements.status.textContent,/2개 동 추출 완료/);checks++;
  fs.writeFileSync(path.join(dir,'javascript_checks.json'),JSON.stringify({checks_passed:checks,large_source_bytes:largeSize,large_source_bytes_read:reads.reduce((n,[s,e])=>n+e-s,0),dom_smoke:'Node DOM stubs; not a browser screenshot'},null,2));
  console.log(`Boundary helper: ${checks} JavaScript checks passed.`);
})().catch(error=>{console.error(error);process.exitCode=1;});
