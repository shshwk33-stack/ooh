"""Verify local browser extraction with independent GIS readers and synthetic files."""
import json
import struct
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon, box

root = Path(__file__).resolve().parents[1]
wkt = (
    'PROJCS["ITRF_2000_UTM_K",GEOGCS["GCS_ITRF_2000",'
    'DATUM["D_ITRF_2000",SPHEROID["GRS_1980",6378137,298.257222101]],'
    'PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",1000000],'
    'PARAMETER["False_Northing",2000000],PARAMETER["Central_Meridian",127.5],'
    'PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",38],UNIT["Meter",1]]'
)
with tempfile.TemporaryDirectory(prefix="boundary_helper_") as tmp:
    folder = Path(tmp)
    hole = Polygon(
        [(940000, 1940000), (940000, 1940020), (940020, 1940020), (940020, 1940000)],
        holes=[[(940005, 1940005), (940015, 1940005), (940015, 1940015), (940005, 1940015)]],
    )
    islands = MultiPolygon([box(940030, 1940030, 940040, 1940040), box(940050, 1940050, 940060, 1940060)])
    original = gpd.GeoDataFrame(
        {"zone_id": ["11010530", "11140610", "11130510", "11140710", "11140720"],
         "name": ["검사용A", "검사용고리", "검사용B", "검사용다중", "삭제검사용"],
         "sigungu_id": [11010, 11140, 11130, 11140, 11140]},
        geometry=[box(939000, 1939000, 939010, 1939010), hole,
                  box(941000, 1941000, 941010, 1941010), islands,
                  box(940070, 1940070, 940080, 1940080)], crs=wkt,
    )
    original.to_file(folder / "fixture.shp", driver="ESRI Shapefile", encoding="UTF-8")
    # Test source row deletion without changing SHX record positions.
    dbf_path = folder / "fixture.dbf"
    dbf = bytearray(dbf_path.read_bytes())
    header, row = struct.unpack_from("<HH", dbf, 8)
    dbf[header + 4 * row] = ord("*")
    dbf_path.write_bytes(dbf)
    with ZipFile(root / "deliverables/Mapo_boundary_helper.zip") as package:
        assert package.testzip() is None
        assert set(package.namelist()) == {"Mapo_boundary_helper.html", "사용방법.txt"}
        html = package.read("Mapo_boundary_helper.html")
        assert b"/*__BOUNDARY_CORE__*/" not in html
        assert b"connect-src 'none'" in html
        (folder / "helper.html").write_bytes(html)
    subprocess.run(["node", str(root / "tools/boundary_helper/check_core.cjs"), str(folder)], check=True)
    with ZipFile(folder / "roundtrip.zip") as result:
        assert result.testzip() is None
        result.extractall(folder / "output")
        metadata = json.loads(result.read("subset_metadata.json"))
    output = gpd.read_file(folder / "output/mapo_boundary_2023.shp", encoding="UTF-8")
    source = gpd.read_file(folder / "fixture.shp", encoding="UTF-8")
    expected = source[source.sigungu_id == 11140].reset_index(drop=True)
    assert len(output) == 2
    assert output.zone_id.tolist() == expected.zone_id.tolist()
    assert output.name.tolist() == expected.name.tolist()
    assert output.sigungu_id.tolist() == expected.sigungu_id.tolist()
    assert output.crs.equals(source.crs)
    assert all(a.equals_exact(b, tolerance=0) for a, b in zip(output.geometry, expected.geometry, strict=True))
    assert output.geometry.is_valid.all()
    assert metadata["boundary_equivalence_to_2024"].startswith("미검증")
    assert len(output.geometry.iloc[0].interiors) == 1
    assert output.geometry.iloc[1].geom_type == "MultiPolygon"
    # Independent binary check: selected geometry and complete DBF row bytes preserved.
    source_shp = (folder / "fixture.shp").read_bytes()
    source_shx = (folder / "fixture.shx").read_bytes()
    target_shp = (folder / "output/mapo_boundary_2023.shp").read_bytes()
    target_shx = (folder / "output/mapo_boundary_2023.shx").read_bytes()
    target_dbf = (folder / "output/mapo_boundary_2023.dbf").read_bytes()
    for j, i in enumerate([1, 3]):
        src_offset, src_words = struct.unpack_from(">II", source_shx, 100 + 8 * i)
        dst_offset, dst_words = struct.unpack_from(">II", target_shx, 100 + 8 * j)
        assert src_words == dst_words
        assert source_shp[src_offset*2+8:(src_offset+4+src_words)*2] == target_shp[dst_offset*2+8:(dst_offset+4+dst_words)*2]
        assert dbf[header+i*row:header+(i+1)*row] == target_dbf[header+j*row:header+(j+1)*row]
    checks = json.loads((folder / "javascript_checks.json").read_text())
    print(json.dumps({**checks, "gis_roundtrip": "passed; exact native coordinates, holes, multipart and Korean attributes preserved",
                      "selected_geometry_and_dbf_bytes": "exact match", "real_uploaded_polygon_payload_tested": False}, ensure_ascii=False, indent=2))
