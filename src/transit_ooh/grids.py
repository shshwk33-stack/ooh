"""Metric grid with fixed global origin; exact straight-segment time allocation."""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer


@dataclass(frozen=True)
class Grid:
    crs: str = "EPSG:32652"
    size: float = 200
    offset_x: float = 0
    offset_y: float = 0

    def __post_init__(self):
        c = CRS(self.crs)
        if not c.is_projected or any(a.unit_name != "metre" for a in c.axis_info):
            raise ValueError("Grid CRS must be projected in metres")
        if self.size <= 0:
            raise ValueError("Grid size must be positive")

    def project(self, frame):
        d = frame.copy()
        lon, lat = d.longitude.to_numpy(), d.latitude.to_numpy()
        area = CRS(self.crs).area_of_use
        if (
            area
            and len(d)
            and not (
                (lon >= area.west)
                & (lon <= area.east)
                & (lat >= area.south)
                & (lat <= area.north)
            ).all()
        ):
            raise ValueError(f"Coordinates outside area of use of {self.crs}")
        d["x"], d["y"] = Transformer.from_crs(4326, self.crs, always_xy=True).transform(
            lon, lat
        )
        d["grid_id"] = [self.key(x, y) for x, y in zip(d.x, d.y, strict=False)]
        return d

    def key(self, x, y):
        return f"{int(np.floor((x - self.offset_x) / self.size))}:{int(np.floor((y - self.offset_y) / self.size))}"

    def center(self, key):
        ix, iy = map(int, key.split(":"))
        return (ix + 0.5) * self.size + self.offset_x, (
            iy + 0.5
        ) * self.size + self.offset_y

    def bounds(self, key):
        x, y = self.center(key)
        s = self.size / 2
        return x - s, y - s, x + s, y + s

    def cells(self, keys):
        inv = Transformer.from_crs(self.crs, 4326, always_xy=True)
        rows = []
        for k in sorted(set(keys)):
            x0, y0, x1, y1 = self.bounds(k)
            lon, lat = inv.transform((x0 + x1) / 2, (y0 + y1) / 2)
            xs = [x0, x1, x1, x0, x0]
            ys = [y0, y0, y1, y1, y0]
            lo, la = inv.transform(xs, ys)
            rows.append(
                {
                    "grid_id": k,
                    "longitude": lon,
                    "latitude": lat,
                    "polygon": list(map(list, zip(lo, la, strict=False))),
                }
            )
        return pd.DataFrame(
            rows, columns=["grid_id", "longitude", "latitude", "polygon"]
        )

    def segment_parts(self, x0, y0, x1, y1):
        cuts = [0.0, 1.0]
        for a, b, offset in [(x0, x1, self.offset_x), (y0, y1, self.offset_y)]:
            if abs(b - a) < 1e-10:
                continue
            lo, hi = sorted([a, b])
            first = int(np.floor((lo - offset) / self.size)) + 1
            last = int(np.floor((hi - offset) / self.size))
            cuts.extend(
                (i * self.size + offset - a) / (b - a)
                for i in range(first, last + 1)
                if 0 < (i * self.size + offset - a) / (b - a) < 1
            )
        cuts = sorted(set(cuts))
        out = []
        for a, b in itertools.pairwise(cuts):
            mid = (a + b) / 2
            out.append((self.key(x0 + (x1 - x0) * mid, y0 + (y1 - y0) * mid), b - a))
        return out
