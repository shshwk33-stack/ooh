"""Capture the running application, preserving its synthetic-data warning."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "deliverables/capstone3/assets"
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/chromium", headless=True,
        args=["--no-sandbox", "--enable-unsafe-swiftshader", "--use-angle=swiftshader"])
    page = browser.new_page(viewport={"width":1740,"height":960}, device_scale_factor=1.5)
    page.goto("http://127.0.0.1:8503", wait_until="domcontentloaded")
    page.get_by_text("분석 후보", exact=True).wait_for(timeout=60000)
    basemap = page.get_by_label("온라인 배경지도 (CARTO / OSM)", exact=True)
    basemap.focus()
    basemap.press("Space")
    page.wait_for_timeout(2000)
    assert not basemap.is_checked()
    assert page.get_by_test_id("stException").count() == 0
    page.screenshot(path=str(OUT / "dashboard_viewport.png"))
    # Exercise the actual weight control and wait for the resulting metric.
    slider = page.get_by_test_id("stSlider").filter(has_text="Mobility 가중치 (%)").get_by_role("slider")
    slider.focus()
    slider.press("Home")
    for _ in range(60):
        slider.press("ArrowRight")
    page.get_by_text("60 : 40", exact=True).wait_for(timeout=60000)
    assert page.get_by_test_id("stException").count() == 0
    page.screenshot(path=str(OUT / "dashboard_weight60.png"))
    result={"app_url":"http://127.0.0.1:8503", "input":"synthetic demo", "browser":"system Chromium via Playwright", "default_weight":"50:50", "changed_weight":"60:40", "result_metric_updated":True, "streamlit_exceptions":0, "basemap":"disabled for offline screenshot; coordinates and synthetic layers retained"}
    (OUT / "dashboard_capture_evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),encoding="utf-8")
    browser.close()
print("Actual browser capture and 50:50 to 60:40 control check passed.")
