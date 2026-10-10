/* Local, dependency-free selection of Mapo polygon records; no reprojection. */
(() => {
  "use strict";
  const utf8 = new TextEncoder();
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  const view = bytes => new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const ascii = bytes => new TextDecoder("ascii").decode(bytes).replace(/\0.*$/, "").trim();
  const read = async (file, start, end) => {
    check(Number.isSafeInteger(start) && start >= 0 && end <= file.size && end >= start,
      "파일 색인이 원본 파일 범위를 벗어납니다.");
    const bytes = new Uint8Array(await file.slice(start, end).arrayBuffer());
    check(bytes.length === end - start, "파일을 끝까지 읽지 못했습니다.");
    return bytes;
  };
  function header(bytes, fileSize) {
    check(bytes.length >= 100, "지도 파일의 헤더가 잘렸습니다.");
    const d = view(bytes);
    check(d.getUint32(0, false) === 9994 && d.getUint32(28, true) === 1000,
      "지원하는 Shapefile 형식이 아닙니다.");
    check(d.getUint32(24, false) * 2 === fileSize, "지도 헤더의 파일 크기가 실제 파일과 다릅니다.");
    check(d.getUint32(32, true) === 5, "이 도구는 읍면동 Polygon(유형 5) 경계를 지원합니다.");
    const box = Array.from({length: 4}, (_, i) => d.getFloat64(36 + i * 8, true));
    check(box.every(Number.isFinite) && box[0] <= box[2] && box[1] <= box[3],
      "지도 헤더의 경계 범위가 올바르지 않습니다.");
    return box;
  }
  function polygonBounds(content) {
    check(content.length >= 44, "다각형 레코드가 잘렸습니다.");
    const d = view(content);
    check(d.getUint32(0, true) === 5, "선택한 동에 Polygon이 아닌 레코드가 있습니다.");
    const parts = d.getUint32(36, true), points = d.getUint32(40, true);
    const pointOffset = 44 + 4 * parts;
    check(parts > 0 && points >= parts * 4 && pointOffset + 16 * points === content.length,
      "다각형의 부분·좌표 개수가 파일 길이와 맞지 않습니다.");
    const starts = Array.from({length: parts}, (_, i) => d.getUint32(44 + 4 * i, true));
    check(starts[0] === 0 && starts.every((v, i) => v < points && (!i || v > starts[i-1])),
      "다각형 부분의 색인이 올바르지 않습니다.");
    let xmin = Infinity, ymin = Infinity, xmax = -Infinity, ymax = -Infinity;
    const xy = i => [d.getFloat64(pointOffset + i * 16, true), d.getFloat64(pointOffset + i * 16 + 8, true)];
    for (let i = 0; i < points; i++) {
      const [x,y] = xy(i);
      check(Number.isFinite(x) && Number.isFinite(y), "다각형에 유효하지 않은 좌표가 있습니다.");
      xmin = Math.min(xmin,x); ymin = Math.min(ymin,y); xmax = Math.max(xmax,x); ymax = Math.max(ymax,y);
    }
    starts.forEach((start,i) => {
      const end = (starts[i+1] ?? points) - 1;
      check(end - start >= 3, "다각형의 고리 좌표가 부족합니다.");
      const a = xy(start), b = xy(end);
      check(a[0] === b[0] && a[1] === b[1], "다각형의 고리가 닫혀 있지 않습니다.");
    });
    const box = [xmin,ymin,xmax,ymax];
    check(box.every((v,i) => Math.abs(v - d.getFloat64(4 + i * 8, true)) <= 0.000001),
      "다각형 경계 범위가 실제 좌표와 다릅니다.");
    return box;
  }
  async function extractMapo(inputFiles, options = {}) {
    const district = options.districtCode ?? "11140";
    const expectedRows = options.expectedRows ?? 16;
    const year = options.boundaryYear ?? 2023;
    check(/^[0-9]{5}$/.test(district) && Number.isInteger(year) && year > 1900,
      "지역 코드 또는 자료 연도가 올바르지 않습니다.");
    const files = {};
    for (const f of inputFiles) {
      const match = /^(.*)\.(shp|shx|dbf|prj|cpg)$/i.exec(f.name);
      if (!match) continue;
      const ext = match[2].toLowerCase();
      check(!files[ext], `${ext.toUpperCase()} 파일이 여러 개입니다. 같은 읍면동 자료 한 묶음만 선택해주세요.`);
      files[ext] = f;
    }
    for (const ext of ["shp","shx","dbf","prj"])
      check(files[ext], `${ext.toUpperCase()} 파일이 필요합니다. 압축을 푼 폴더에서 네 파일을 함께 선택해주세요.`);
    const stems = ["shp","shx","dbf","prj"].map(ext => files[ext].name.slice(0,-4).toLowerCase());
    check(new Set(stems).size === 1, "파일 이름 앞부분이 다릅니다. 같은 지도 묶음을 선택해주세요.");
    check(files.dbf.size <= 16 * 1024 * 1024 && files.shx.size <= 16 * 1024 * 1024 && files.prj.size < 1024 * 1024,
      "속성·색인 파일이 예상보다 큽니다. 파일 목록을 확인해주세요.");
    const [shpHeader, shx, dbf, prj] = await Promise.all([
      read(files.shp,0,100), read(files.shx,0,files.shx.size),
      read(files.dbf,0,files.dbf.size), read(files.prj,0,files.prj.size)
    ]);
    header(shpHeader, files.shp.size); const sourceBox = header(shx,files.shx.size);
    check(shpHeader.every((v,i) => (i >= 24 && i < 28) || v === shx[i]),
      "SHP와 SHX 헤더가 다릅니다. 서로 다른 지도 파일일 수 있습니다.");
    check(ascii(prj).includes("PROJCS[") && ascii(prj).includes("UTM_K"),
      "View-T UTM_K 좌표계 설명이 아닙니다. 원본 PRJ를 확인해주세요.");
    check(dbf.length >= 33 && dbf[0] === 3, "지원하는 DBF 형식이 아닙니다.");
    const dv = view(dbf), count = dv.getUint32(4,true), h = dv.getUint16(8,true), rowSize = dv.getUint16(10,true);
    check(h >= 33 && h <= dbf.length && rowSize > 1 && dbf.length >= h + count * rowSize,
      "DBF 레코드가 잘렸거나 헤더가 올바르지 않습니다.");
    check(shx.length === 100 + count * 8, "SHP 색인과 DBF 행 개수가 다릅니다.");
    let pos = 32, fieldOffset = 1, districtField = null; const characterFields = [];
    while (pos < h && dbf[pos] !== 13) {
      check(pos + 32 <= h, "DBF 필드 정의가 잘렸습니다.");
      const name = ascii(dbf.subarray(pos,pos+11)), length = dbf[pos+16];
      check(length > 0, "DBF 필드 길이가 올바르지 않습니다.");
      if (name.toLowerCase() === "sigungu_id") districtField = {offset:fieldOffset,length};
      if (dbf[pos+11] === 67) characterFields.push({offset:fieldOffset,length});
      fieldOffset += length; pos += 32;
    }
    check(pos < h && dbf[pos] === 13 && fieldOffset === rowSize && districtField,
      "DBF에 올바른 sigungu_id 필드가 필요합니다.");
    const sx = view(shx), selected = []; let nextOffset = 50;
    for (let i = 0; i < count; i++) {
      const offset = sx.getUint32(100+i*8,false), words = sx.getUint32(104+i*8,false);
      check(offset === nextOffset && words >= 22 && (offset+4+words)*2 <= files.shp.size,
        "SHP 색인이 끊기거나 원본 파일 범위를 벗어납니다.");
      nextOffset = offset + 4 + words;
      const start = h + i * rowSize;
      check(dbf[start] === 32 || dbf[start] === 42, "DBF 행의 삭제 표시가 올바르지 않습니다.");
      if (dbf[start] === 32 && ascii(dbf.subarray(start+districtField.offset,start+districtField.offset+districtField.length)) === district)
        selected.push({index:i,offset:offset*2,bytes:words*2,start});
    }
    check(nextOffset * 2 === files.shp.size, "SHP 색인이 파일 전체 길이와 맞지 않습니다.");
    check(selected.length > 0, "마포구 코드 11140에 해당하는 동이 없습니다.");
    check(!expectedRows || selected.length === expectedRows,
      `마포구 ${expectedRows}개 동을 예상했지만 ${selected.length}개입니다. 파일을 확인해주세요.`);
    let encoding = "UTF-8";
    try {
      const decoder = new TextDecoder("utf-8",{fatal:true});
      for (const s of selected) for (const f of characterFields) decoder.decode(dbf.subarray(s.start+f.offset,s.start+f.offset+f.length));
    } catch {
      const decoder = new TextDecoder("euc-kr",{fatal:true});
      for (const s of selected) for (const f of characterFields) decoder.decode(dbf.subarray(s.start+f.offset,s.start+f.offset+f.length));
      encoding = "CP949";
    }
    const total = 100 + selected.reduce((sum,s) => sum + 8 + s.bytes,0);
    check(total < 30 * 1024 * 1024, "추출 결과가 30MB를 넘습니다. 더 작은 분할 방법이 필요합니다.");
    const shp = new Uint8Array(total); shp.set(shpHeader);
    const outIndex = new Uint8Array(100 + selected.length * 8); outIndex.set(shpHeader);
    const outDBF = new Uint8Array(h + rowSize * selected.length + 1); outDBF.set(dbf.subarray(0,h));
    view(outDBF).setUint32(4,selected.length,true); outDBF[outDBF.length-1] = 26;
    let cursor = 100, box = [Infinity,Infinity,-Infinity,-Infinity];
    for (let j = 0; j < selected.length; j++) {
      const s = selected[j], record = await read(files.shp,s.offset,s.offset+8+s.bytes), rd = view(record);
      check(rd.getUint32(0,false) === s.index+1 && rd.getUint32(4,false)*2 === s.bytes,
        "SHP 레코드 번호·길이가 SHX와 맞지 않습니다.");
      const bounds = polygonBounds(record.subarray(8));
      check(bounds[0] >= sourceBox[0]-0.000001 && bounds[1] >= sourceBox[1]-0.000001 &&
        bounds[2] <= sourceBox[2]+0.000001 && bounds[3] <= sourceBox[3]+0.000001,
        "선택한 동의 좌표가 원본 지도 범위를 벗어납니다.");
      box = [Math.min(box[0],bounds[0]),Math.min(box[1],bounds[1]),Math.max(box[2],bounds[2]),Math.max(box[3],bounds[3])];
      view(shp).setUint32(cursor,j+1,false); view(shp).setUint32(cursor+4,s.bytes/2,false);
      shp.set(record.subarray(8),cursor+8);
      view(outIndex).setUint32(100+j*8,cursor/2,false); view(outIndex).setUint32(104+j*8,s.bytes/2,false);
      outDBF.set(dbf.subarray(s.start,s.start+rowSize),h+j*rowSize); cursor += 8+s.bytes;
    }
    for (const output of [shp,outIndex]) {
      const d = view(output); d.setUint32(24,output.length/2,false);
      box.forEach((value,i) => d.setFloat64(36+i*8,value,true));
    }
    const prefix = `mapo_boundary_${year}`;
    const metadata = {
      district_name:"서울특별시 마포구", provider_sigungu_id:district,
      boundary_year:year, year_basis:"사용자가 선택한 원본 자료 연도; 파일 헤더로 조사연도를 인증하지 않음",
      selected_records:selected.length, selected_original_record_indices_zero_based:selected.map(s=>s.index),
      original_files:["shp","shx","dbf","prj"].map(ext=>({name:files[ext].name,bytes:files[ext].size})),
      output_shp_bytes:shp.length, output_bbox_native_crs:box, dbf_encoding:encoding,
      geometry_payload_preserved:true, coordinate_transform_applied:false,
      boundary_equivalence_to_2024:"미검증: 코드 일치와 경계 동일성은 별도 확인사항",
      validation_scope:"선택 레코드·색인·속성 정합성, 고리 닫힘·유한 좌표·범위 검사. 다각형 위상 유효성·자료 진위는 별도 검토 필요"
    };
    return {metadata, files:[
      {name:prefix+".shp",bytes:shp},{name:prefix+".shx",bytes:outIndex},
      {name:prefix+".dbf",bytes:outDBF},{name:prefix+".prj",bytes:prj},
      {name:prefix+".cpg",bytes:utf8.encode(encoding)},
      {name:"subset_metadata.json",bytes:utf8.encode(JSON.stringify(metadata,null,2)+"\n")}
    ]};
  }
  const crcTable = Array.from({length:256},(_,i) => {
    let c=i; for(let j=0;j<8;j++) c=(c&1)?0xedb88320^(c>>>1):c>>>1; return c>>>0;
  });
  const crc32 = bytes => { let c=0xffffffff; for(const b of bytes) c=crcTable[(c^b)&255]^(c>>>8); return (c^0xffffffff)>>>0; };
  function makeZip(files) {
    const local=[], central=[]; let offset=0, centralSize=0;
    for(const file of files) {
      const name=utf8.encode(file.name), size=file.bytes.length, crc=crc32(file.bytes);
      check(size < 0xffffffff && name.length < 65536, "ZIP 파일 크기 제한을 넘습니다.");
      const l=new Uint8Array(30+name.length), ld=view(l);
      ld.setUint32(0,0x04034b50,true); ld.setUint16(4,20,true); ld.setUint16(6,0x800,true);
      ld.setUint16(12,33,true); ld.setUint32(14,crc,true); ld.setUint32(18,size,true); ld.setUint32(22,size,true);
      ld.setUint16(26,name.length,true); l.set(name,30); local.push(l,file.bytes);
      const c=new Uint8Array(46+name.length), cd=view(c);
      cd.setUint32(0,0x02014b50,true); cd.setUint16(4,20,true); cd.setUint16(6,20,true); cd.setUint16(8,0x800,true);
      cd.setUint16(14,33,true); cd.setUint32(16,crc,true); cd.setUint32(20,size,true); cd.setUint32(24,size,true);
      cd.setUint16(28,name.length,true); cd.setUint32(42,offset,true); c.set(name,46); central.push(c);
      offset+=l.length+size; centralSize+=c.length;
    }
    const end=new Uint8Array(22), e=view(end);
    e.setUint32(0,0x06054b50,true); e.setUint16(8,files.length,true); e.setUint16(10,files.length,true);
    e.setUint32(12,centralSize,true); e.setUint32(16,offset,true);
    const parts=[...local,...central,end], out=new Uint8Array(offset+centralSize+22); let pos=0;
    for(const p of parts) {out.set(p,pos);pos+=p.length;} return out;
  }
  const api={extractMapo,makeZip};
  if(typeof module !== "undefined" && module.exports) module.exports=api;
  else globalThis.TransitBoundaryHelper=api;
})();
