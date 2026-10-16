"""Prospective, frozen A/B/C evaluation against independent manual counts.

This module never invents field observations or tunes weights on evaluation
outcomes. Integrity hashes detect accidental changes; they are not signatures or
proof that a user-declared field count was independently collected.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

SCHEMA = "transit_ooh_prospective_field_v1"
MODELS = {"A": "static_score", "B": "mobility_score", "C": "integrated_score"}


def _csv(frame):
    return frame.to_csv(index=False).encode("utf-8-sig")


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def freeze_campaign(
    scores, metadata, dates, start_time="12:00", duration_minutes=15, alpha=0.5
):
    """Return a ZIP with a frozen protocol and a score-blind collection sheet.

    All candidates receive one equal-duration session at the same local time on
    every date. A different observation design needs a separate analysis design.
    This strict balanced pilot avoids silently treating missing sessions as zero.
    """
    required = {"grid_id", "static_score", "mobility_score", "longitude", "latitude"}
    if not required <= set(scores) or scores[list(required)].isna().any().any():
        raise ValueError("Require complete candidate IDs, coordinates and A/B scores")
    d = scores[sorted(required)].copy()
    d["grid_id"] = d.grid_id.astype(str).str.strip()
    if d.grid_id.duplicated().any() or d.grid_id.eq("").any() or len(d) < 10:
        raise ValueError(
            "Require at least 10 unique mapped candidates; this is not a power guarantee"
        )
    for c in ["static_score", "mobility_score"]:
        v = pd.to_numeric(d[c], errors="raise")
        if not np.isfinite(v).all() or not v.between(0, 1).all():
            raise ValueError("Frozen component scores must be finite [0,1]")
        d[c] = v
    if not d.longitude.between(124, 132).all() or not d.latitude.between(33, 39).all():
        raise ValueError("Reviewed observation-site coordinates in Korea required")
    if not np.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("Weight must be within [0,1]")
    required_meta = {
        "spatial_support_id",
        "training_end_date",
        "prediction_source",
        "prediction_observation_type",
        "input_sha256",
        "target",
        "site_mapping_review",
        "independence_plan",
    }
    if required_meta - metadata.keys() or any(not metadata[k] for k in required_meta):
        raise ValueError(
            "Complete study, mapping and independent-observation metadata required"
        )
    if metadata["prediction_observation_type"] not in {
        "public_observed",
        "estimated",
        "mixed_observed_estimated",
    }:
        raise ValueError(
            "Synthetic predictions cannot become a real field-validation campaign"
        )
    if metadata["target"] not in {
        "manual_vehicle_passages",
        "manual_pedestrian_passages",
    }:
        raise ValueError(
            "Choose independent manual vehicle or pedestrian passages, not ad impressions"
        )
    if len(metadata["input_sha256"]) != 64 or any(
        c not in "0123456789abcdef" for c in metadata["input_sha256"]
    ):
        raise ValueError("Input artifact SHA256 required")
    days = sorted(set(str(pd.Timestamp(x).date()) for x in dates))
    if len(days) != len(dates) or len(days) < 5:
        raise ValueError(
            "At least five distinct planned dates required; this is not a power guarantee"
        )
    if (
        pd.Timestamp(metadata["training_end_date"]).date()
        >= pd.Timestamp(days[0]).date()
    ):
        raise ValueError("Evaluation dates must be after all model input dates")
    if (
        isinstance(duration_minutes, bool)
        or not isinstance(duration_minutes, int)
        or not 1 <= duration_minutes <= 120
    ):
        raise ValueError("Session duration must be 1..120 integer minutes")
    try:
        clock = datetime.strptime(start_time, "%H:%M")
    except (ValueError, TypeError) as exc:
        raise ValueError("Local start_time must be HH:MM") from exc
    if (
        start_time != clock.strftime("%H:%M")
        or clock.hour * 60 + clock.minute + duration_minutes > 1440
    ):
        raise ValueError("Session must fit within one local calendar date")
    frozen = datetime.now(UTC)
    if pd.Timestamp(f"{days[0]} {start_time}", tz="Asia/Seoul") <= frozen:
        raise ValueError("Prospective sessions must start after protocol freezing")
    d = d.sort_values("grid_id").reset_index(drop=True)
    d["integrated_score"] = alpha * d.mobility_score + (1 - alpha) * d.static_score
    schedule = pd.DataFrame(
        [
            {
                "grid_id": row.grid_id,
                "longitude": row.longitude,
                "latitude": row.latitude,
                "date": date,
                "start_time": start_time,
                "duration_minutes": duration_minutes,
            }
            for date in days
            for row in d.itertuples()
        ]
    )
    template = schedule.assign(count="", observer_id="", conditions="")
    files = {
        "predictions.csv": _csv(d),
        "schedule.csv": _csv(schedule),
        "observations_BLIND.csv": _csv(template),
    }
    protocol = {
        "schema": SCHEMA,
        "frozen_at_utc": frozen.isoformat(),
        "metadata": metadata,
        "alpha": alpha,
        "timezone": "Asia/Seoul",
        "dates": days,
        "candidate_count": len(d),
        "start_time": start_time,
        "duration_minutes": duration_minutes,
        "predictions_sha256": _hash(files["predictions.csv"]),
        "schedule_sha256": _hash(files["schedule.csv"]),
        "primary_comparison": "C_minus_A_Spearman",
        "secondary_comparisons": ["B_minus_A", "C_minus_B"],
        "top_k": [5, 10],
        "tie_policy": "grid_id_lexical",
        "provenance_verification": "user_declared_not_independently_authenticated",
        "generalization": "specified_sites_dates_timeband_and_manual_passage_target_only",
    }
    files["protocol.json"] = json.dumps(protocol, ensure_ascii=False, indent=2).encode()
    files["README.txt"] = (
        "현장 관측자는 observations_BLIND.csv만 사용합니다. 모델 점수는 공유하지 마세요.\n"
        "count는 해당 시간의 직접 통과 계수입니다. 결측은 빈칸, 실제 0회만 0으로 적습니다.\n"
        "observer_id는 가명, conditions에는 날씨/행사/공사 등만 기록합니다.\n"
        "동일 세션을 중복 관측한 자료는 별도 관측자 일치도 검토용이며 여기에 합산하지 않습니다.\n"
        "여러 후보를 같은 시간에 관측하는 균형 설계입니다. 필요한 인력/시간을 먼저 확보하세요.\n"
        "프로토콜·입력 해시는 변경 감지용이며 독립 수집의 인증이나 공인 사전등록이 아닙니다.\n"
        "모델·가중치를 결과에 맞춰 바꾸면 새 캠페인으로 등록해야 합니다.\n"
    ).encode()
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def read_campaign(data):
    with ZipFile(BytesIO(data)) as archive:
        required = {"protocol.json", "predictions.csv", "schedule.csv"}
        if not required <= set(archive.namelist()) or len(archive.namelist()) != len(
            set(archive.namelist())
        ):
            raise ValueError("Missing or duplicate campaign members")
        if sum(info.file_size for info in archive.infolist()) > 16 * 1024 * 1024:
            raise ValueError("Campaign exceeds 16 MiB limit")
        protocol = json.loads(archive.read("protocol.json"))
        if protocol.get("schema") != SCHEMA:
            raise ValueError("Unknown field protocol")
        tables = {}
        for name in ["predictions", "schedule"]:
            raw = archive.read(name + ".csv")
            if _hash(raw) != protocol[name + "_sha256"]:
                raise ValueError("Frozen campaign checksum mismatch")
            tables[name] = pd.read_csv(BytesIO(raw), dtype={"grid_id": str})
    p, schedule = tables["predictions"], tables["schedule"]
    if (
        protocol.get("timezone") != "Asia/Seoul"
        or protocol.get("top_k") != [5, 10]
        or not 0 <= protocol["alpha"] <= 1
        or protocol["metadata"]["prediction_observation_type"]
        not in {"public_observed", "estimated", "mixed_observed_estimated"}
        or protocol["metadata"]["target"]
        not in {"manual_vehicle_passages", "manual_pedestrian_passages"}
    ):
        raise ValueError("Invalid frozen scope, targets or weight")
    days = protocol["dates"]
    if (
        len(days) < 5
        or days != sorted(set(days))
        or any(str(pd.Timestamp(day).date()) != day for day in days)
        or pd.Timestamp(protocol["metadata"]["training_end_date"]).date()
        >= pd.Timestamp(days[0]).date()
        or pd.Timestamp(protocol["frozen_at_utc"]).tzinfo is None
    ):
        raise ValueError("Invalid prospective dates")
    duration = protocol["duration_minutes"]
    if (
        isinstance(duration, bool)
        or not isinstance(duration, int)
        or not 1 <= duration <= 120
    ):
        raise ValueError("Invalid frozen duration")
    clock = datetime.strptime(protocol["start_time"], "%H:%M")
    if clock.hour * 60 + clock.minute + duration > 1440:
        raise ValueError("Session crosses a calendar date")
    if p.isna().any().any() or schedule.isna().any().any():
        raise ValueError("Incomplete frozen files")
    scores = p[list(MODELS.values())].to_numpy(dtype=float)
    if not np.isfinite(scores).all() or (scores < 0).any() or (scores > 1).any():
        raise ValueError("Invalid frozen scores")
    if (
        not schedule.start_time.eq(protocol["start_time"]).all()
        or not schedule.duration_minutes.eq(duration).all()
        or not p.longitude.between(124, 132).all()
        or not p.latitude.between(33, 39).all()
    ):
        raise ValueError("Invalid frozen schedule or coordinates")
    if (
        p.grid_id.duplicated().any()
        or len(p) != protocol["candidate_count"]
        or len(p) < 10
    ):
        raise ValueError("Invalid frozen candidate universe")
    expected = {(d, z) for d in protocol["dates"] for z in p.grid_id}
    if (
        len(expected) != len(schedule)
        or set(zip(schedule.date, schedule.grid_id, strict=True)) != expected
    ):
        raise ValueError("Invalid balanced schedule")
    if not np.allclose(
        p.integrated_score,
        protocol["alpha"] * p.mobility_score + (1 - protocol["alpha"]) * p.static_score,
    ):
        raise ValueError("Frozen integrated predictions differ from declared weight")
    return protocol, p, schedule


def _rho(score, outcome):
    if len(np.unique(score)) < 2 or len(np.unique(outcome)) < 2:
        return np.nan
    return float(spearmanr(score, outcome).statistic)


def evaluate_campaign(campaign, observations, replicates=1000, seed=42):
    """Compare frozen models; bootstrap all models on identical sampled units.

    Day-only draws condition on the fixed sites. Crossed site/date draws explore
    site and date sampling variation (no guarantee of population representativeness).
    Top-K capture is the fraction of manual passage rates at selected sites, not
    unique people reached. No p-values or automatic 'improvement' label are issued.
    """
    protocol, predictions, schedule = read_campaign(campaign)
    if (
        isinstance(replicates, bool)
        or not isinstance(replicates, int)
        or not 100 <= replicates <= 10000
    ):
        raise ValueError("Use 100..10000 bootstrap replicates")
    columns = [
        "grid_id",
        "date",
        "start_time",
        "duration_minutes",
        "count",
        "observer_id",
    ]
    if not set(columns) <= set(observations):
        raise ValueError("Missing manual observation fields")
    o = observations[columns].copy()
    if (
        o.isna().any().any()
        or len(o) != len(schedule)
        or o.duplicated(["grid_id", "date"]).any()
    ):
        raise ValueError(
            "Complete unique planned sessions required; missing is not zero"
        )
    for col in ["grid_id", "date", "observer_id", "start_time"]:
        o[col] = o[col].astype(str).str.strip()
        if o[col].eq("").any():
            raise ValueError("Empty session identifiers")
    for col in ["count", "duration_minutes"]:
        if o[col].map(lambda x: isinstance(x, (bool, np.bool_))).any():
            raise ValueError("Boolean counts/durations invalid")
        o[col] = pd.to_numeric(o[col], errors="raise")
        if (
            not np.isfinite(o[col]).all()
            or (o[col] < 0).any()
            or (o[col] % 1 != 0).any()
        ):
            raise ValueError("Nonnegative integer observed counts/durations required")
    merged = schedule.merge(
        o,
        on=["grid_id", "date"],
        suffixes=("_plan", ""),
        validate="one_to_one",
        how="outer",
        indicator=True,
    )
    if (
        not merged._merge.eq("both").all()
        or not merged.start_time.eq(merged.start_time_plan).all()
        or not merged.duration_minutes.eq(merged.duration_minutes_plan).all()
    ):
        raise ValueError("Observed sessions differ from the frozen schedule")
    end = pd.Timestamp(
        f"{max(protocol['dates'])} {protocol['start_time']}", tz="Asia/Seoul"
    ) + pd.Timedelta(minutes=protocol["duration_minutes"])
    start = pd.Timestamp(
        f"{min(protocol['dates'])} {protocol['start_time']}", tz="Asia/Seoul"
    )
    if pd.Timestamp(protocol["frozen_at_utc"]) >= start or end > datetime.now(UTC):
        raise ValueError(
            "Cannot evaluate uncompleted or retrospectively frozen sessions"
        )
    ids = predictions.grid_id.tolist()
    o["rate_per_hour"] = o["count"] * 60 / o.duration_minutes
    panel = (
        o.pivot(index="date", columns="grid_id", values="rate_per_hour")
        .loc[protocol["dates"], ids]
        .to_numpy()
    )
    mean = panel.mean(axis=0)
    values = predictions[list(MODELS.values())].to_numpy()
    estimates, resamples, draws = [], [], []
    for j, model in enumerate(MODELS):
        selected = np.lexsort((np.array(ids), -values[:, j]))
        for k in protocol["top_k"]:
            selected_ids = selected[:k]
            cutoff = values[selected_ids[-1], j]
            tied = np.flatnonzero(values[:, j] == cutoff)
            strict = np.flatnonzero(values[:, j] > cutoff)
            places = k - len(strict)
            total = mean.sum()
            estimates.append(
                {
                    "model": model,
                    "spearman": _rho(values[:, j], mean),
                    "top_k": k,
                    "capture_share": float(mean[selected_ids].sum() / total)
                    if total
                    else np.nan,
                    "capture_tie_lower": float(
                        (mean[strict].sum() + np.sort(mean[tied])[:places].sum())
                        / total
                    )
                    if total
                    else np.nan,
                    "capture_tie_upper": float(
                        (mean[strict].sum() + np.sort(mean[tied])[-places:].sum())
                        / total
                    )
                    if total
                    else np.nan,
                    "candidates": len(ids),
                    "dates": len(panel),
                }
            )
    rng = np.random.default_rng(seed)
    for rep in range(replicates):
        day_idx = rng.choice(len(panel), len(panel), replace=True)
        site_idx = rng.choice(len(ids), len(ids), replace=True)
        outcome = panel[day_idx].mean(axis=0)
        draws.append(
            {
                "replicate": rep,
                "day_indices": ";".join(map(str, day_idx)),
                "site_indices": ";".join(map(str, site_idx)),
            }
        )
        for method, idx in [
            ("paired_days_fixed_sites", np.arange(len(ids))),
            ("crossed_sites_and_days", site_idx),
        ]:
            rho = [_rho(values[idx, j], outcome[idx]) for j in range(3)]
            for label, x, y in [
                ("C_minus_A", 2, 0),
                ("B_minus_A", 1, 0),
                ("C_minus_B", 2, 1),
            ]:
                resamples.append(
                    {
                        "replicate": rep,
                        "method": method,
                        "comparison": label,
                        "delta_spearman": rho[x] - rho[y],
                    }
                )
    samples = pd.DataFrame(resamples)
    summaries = []
    base_rhos = [_rho(values[:, j], mean) for j in range(3)]
    for (method, comparison), group in samples.groupby(["method", "comparison"]):
        v = group.delta_spearman.dropna()
        x, y = {"C_minus_A": (2, 0), "B_minus_A": (1, 0), "C_minus_B": (2, 1)}[
            comparison
        ]
        summaries.append(
            {
                "method": method,
                "comparison": comparison,
                "estimate": base_rhos[x] - base_rhos[y],
                "p025": float(v.quantile(0.025))
                if len(v) >= 0.9 * replicates
                else np.nan,
                "p975": float(v.quantile(0.975))
                if len(v) >= 0.9 * replicates
                else np.nan,
                "valid_replicates": len(v),
                "replicates": replicates,
                "scope": "conditional_pilot_percentile_interval_not_advertising_effect",
            }
        )
    return {
        "model_metrics": pd.DataFrame(estimates),
        "paired_differences": pd.DataFrame(summaries),
        "bootstrap_samples": samples,
        "bootstrap_draws": pd.DataFrame(draws),
        "candidate_outcomes": pd.DataFrame(
            {"grid_id": ids, "manual_mean_passages_per_hour": mean}
        ),
        "audit": {
            "schema": SCHEMA,
            "campaign_sha256": _hash(campaign),
            "observations_sha256": _hash(_csv(o)),
            "seed": seed,
            "replicates": replicates,
            "alpha": protocol["alpha"],
            "target": protocol["metadata"]["target"],
            "status": "user_declared_manual_counts_evaluated",
            "source_authentication": "not_independently_verified",
            "limitations": [
                "small_pilot_no_power_guarantee",
                "no_seasonal_generalization",
                "no_advertising_attention_outcome",
                "no_automatic_performance_improvement_claim",
                "date_and_site_exchangeability_assumed_no_spatial_or_serial_correlation_correction",
            ],
        },
    }
