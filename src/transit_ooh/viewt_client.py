"""Scoped official View-T requests. No credentials are written or logged."""

import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://viewt.ktdb.go.kr"
ENDPOINTS = {
    "names": "/cong/mobilemap/MobileGetAllZoneName.do",
    "inflow": "/cong/mobilemap/Mobile_InOutMulti_Traffic.do",
    "od": "/cong/mobilemap/Mobile_OD_Traffic.do",
    "vehicle_paths": "/cong/api/mainPath_emd.do",
}


class ViewTHTTPError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(f"View-T HTTP {code}")


class ViewTNoDataError(ValueError):
    def __init__(self, raw):
        self.raw = raw
        super().__init__("View-T returned an empty population result; not zero")


class ViewTClient:
    def __init__(self):
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self.authenticated = False

    def _request(self, path, data=None, timeout=300):
        request = urllib.request.Request(
            BASE + path,
            data=urllib.parse.urlencode(data).encode() if data is not None else None,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": BASE,
                "Referer": BASE + "/cong/map/second_map.do",
            },
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError("View-T response exceeds 16 MiB")
            return raw
        except urllib.error.HTTPError as exc:
            raise ViewTHTTPError(exc.code) from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError("View-T connection failed or timed out") from None

    def authenticate(self, token):
        self.authenticated = False
        if not token:
            raise ValueError("A View-T download token is required")
        self._request("/cong/map/page.do", timeout=30)
        raw = self._request(
            "/cong/map/selectOneToken.do", {"tokenKey": token}, timeout=30
        )
        try:
            status = json.loads(raw).get("tokenKey")
        except (ValueError, AttributeError):
            raise RuntimeError("Unexpected View-T authentication response") from None
        if status != "SUCCESS":
            reason = {"NOTKEY": "not recognized", "ENDDATE": "expired"}.get(
                status, "unexpected response"
            )
            raise RuntimeError("View-T token authentication: " + reason)
        self.authenticated = True

    def fetch(self, kind, parameters):
        if not self.authenticated:
            raise RuntimeError("Authenticate before acquiring data")
        if kind not in ENDPOINTS:
            raise ValueError("Unsupported View-T endpoint")
        for attempt in range(3):
            try:
                raw = self._request(ENDPOINTS[kind], parameters)
                break
            except ViewTHTTPError as exc:
                if exc.code not in {502, 503, 504} or attempt == 2:
                    raise
                time.sleep([5, 15][attempt])
        try:
            payload = json.loads(raw)
        except ValueError:
            raise RuntimeError("View-T did not return JSON") from None
        if not isinstance(payload, dict):
            raise ValueError("Unexpected View-T response")
        if kind in {"inflow", "od"} and payload.get("all") == []:
            raise ViewTNoDataError(raw)
        if kind in {"inflow", "od"} and (
            not isinstance(payload.get("all"), list) or not payload["all"]
        ):
            raise ValueError("No population data or additional access required")
        if kind == "vehicle_paths" and (
            payload.get("STATE") != 200 or not payload.get("RESULT")
        ):
            raise ValueError("No vehicle routes returned")
        if kind == "names" and not isinstance(payload.get("shpMap"), dict):
            raise ValueError("No official zone names returned")
        return raw
