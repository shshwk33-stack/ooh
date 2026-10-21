"""Reproduce an acquired-data, fieldwork-free, reduced-model decision study."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pyogrio
from matplotlib import font_manager
from scipy.stats import spearmanr

from transit_ooh.decision import weight_audit
from transit_ooh.io import sha256, write_json
from transit_ooh.public_decision import (
    compare_portfolios,
    nominal_scores,
    portfolio_metrics,
    solve_portfolio,
    top_indices,
)
from transit_ooh.public_sources import (
    build_candidate_features,
    common_reported_sectors,
    evaluate_public_outcomes,
    read_seoul_zip,
)
from transit_ooh.viewt_roads import load_context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--network", required=True, help="Original 2024 Seoul Level 5.5 ZIP"
    )
    parser.add_argument("--output", default="reports/public_decision")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(args.output)
    tables, figures = out / "tables", out / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(exist_ok=True)
    raw = root / "data/raw/seoul_commercial"
    context, _ = load_context(root / "data/processed/viewt_official_roads")
    network = pyogrio.read_dataframe(
        "/vsizip/" + str(Path(args.network).resolve()), read_geometry=False
    )
    names_path = root / "data/raw/viewt_population/zone_names_2024.json"
    names = json.loads(names_path.read_text())["shpMap"]
    stores = read_seoul_zip(raw / "stores_2024.zip")
    features, coverage, store_coverage, links = build_candidate_features(
        stores, names, context.table, network, context.metadata, sha256(args.network)
    )
    # Existing acquired 2024 provider display points, not inferred delivery stops.
    label_source = root / "deliverables/viewt_actual/dong_inflow_2024_weekdays.csv"
    labels = pd.read_csv(label_source, dtype={"destination_id": str})
    labels = labels.rename(columns={"destination_id": "grid_id"})
    if labels.grid_id.duplicated().any() or not set(features.grid_id) <= set(
        labels.grid_id
    ):
        raise ValueError("Incomplete or duplicated acquired map label support")
    checked = features[["grid_id", "name"]].merge(
        labels[["grid_id", "name"]],
        on="grid_id",
        suffixes=("_input", "_map"),
        validate="one_to_one",
    )
    if not checked.name_input.eq(checked.name_map).all():
        raise ValueError("Provider map label names disagree with locked candidates")
    features = (
        features.merge(
            labels[["grid_id", "longitude", "latitude"]],
            on="grid_id",
            validate="one_to_one",
        )
        .sort_values("grid_id")
        .reset_index(drop=True)
    )

    def save(frame, name):
        frame.to_csv(tables / (name + ".csv"), index=False, encoding="utf-8-sig")

    save(features, "candidate_features")
    save(coverage, "coverage_and_crosswalk")
    save(store_coverage, "reported_store_sector_coverage")
    private = root / "data/processed/public_decision"
    private.mkdir(parents=True, exist_ok=True)
    links.to_csv(private / "provider_link_dong_mapping.csv", index=False)
    studies = [
        compare_portfolios(features, k, low, high)
        for k in [3, 5, 10]
        for low, high in [(0.0, 1.0), (0.3, 0.7)]
    ]
    primary = studies[2]
    comparison = pd.concat([s["comparison"] for s in studies], ignore_index=True)
    save(comparison, "portfolio_comparison")
    f, design, matrix, solved = (
        primary[x] for x in ["features", "design", "matrix", "solver"]
    )
    design["scenario_id"] = np.arange(len(design))
    save(design, "scenario_design")
    save(
        pd.DataFrame(matrix, columns=f.grid_id).assign(
            scenario_id=np.arange(len(matrix))
        ),
        "scenario_scores",
    )
    nominal = nominal_scores(f)
    save(nominal.merge(f[["grid_id", "name"]], on="grid_id"), "nominal_scores")
    for name, frame in weight_audit(nominal).items():
        save(frame, "nominal_" + name)
    sensitivity = []
    for alpha in np.linspace(0, 1, 21):
        scores = nominal_scores(f, float(alpha)).integrated_score
        for k in [5, 10]:
            sensitivity.append(
                {
                    "alpha": alpha,
                    "k": k,
                    "spearman_vs_50": spearmanr(
                        nominal.integrated_score, scores
                    ).statistic,
                    "top_k_overlap": len(
                        set(top_indices(scores, k))
                        & set(top_indices(nominal.integrated_score, k))
                    )
                    / k,
                }
            )
    save(pd.DataFrame(sensitivity), "weight_sensitivity")

    cv = []
    for quarter in [20241, 20242, 20243, 20244]:
        test = design.stock.eq(f"stores_{quarter}")
        train = ~design.stock.isin([f"stores_{quarter}", "stores_mean"])
        fit = solve_portfolio(matrix[train], 5)
        train_f = f.copy()
        train_f["stores_mean"] = f[
            [f"stores_{q}" for q in [20241, 20242, 20243, 20244] if q != quarter]
        ].mean(axis=1)
        ns = nominal_scores(train_f)
        selections = {
            "A_stores": top_indices(ns.static_score, 5),
            "B_vehicle_context": top_indices(ns.mobility_score, 5),
            "C50_reduced": top_indices(ns.integrated_score, 5),
            "C60_reduced": top_indices(
                nominal_scores(train_f, 0.6).integrated_score, 5
            ),
            "R_minimax": fit["selected"],
        }
        for model, chosen in selections.items():
            cv.append(
                {
                    "held_out_quarter": quarter,
                    "model": model,
                    "selected_ids": ";".join(f.iloc[chosen].grid_id),
                    **portfolio_metrics(matrix[test], chosen),
                }
            )
    save(pd.DataFrame(cv), "held_out_quarter_specification")
    family_cv = []
    for family in ["road", "normalization"]:
        for omitted in sorted(design[family].unique()):
            test = design[family].eq(omitted)
            fit = solve_portfolio(matrix[~test], 5)
            choices = {**primary["selections"], "R_minimax": fit["selected"]}
            for model, chosen in choices.items():
                family_cv.append(
                    {
                        "held_out_family": family,
                        "held_out_definition": omitted,
                        "model": model,
                        "selected_ids": ";".join(f.iloc[chosen].grid_id),
                        **portfolio_metrics(matrix[test], chosen),
                    }
                )
    save(pd.DataFrame(family_cv), "held_out_definition_specification")

    bounds = f[["grid_id", "name"]].copy()
    for column, indices in [
        ("selected", solved["selected"]),
        ("in_any_optimum", solved["possible"]),
        ("in_every_optimum", solved["necessary"]),
    ]:
        bounds[column] = bounds.index.isin(indices)
    save(bounds, "optimal_set_ties")
    alternatives = {
        f"R_optimum_{i + 1}": chosen
        for i, chosen in enumerate(solved["optimal_combinations"])
    }
    optimal_table = pd.DataFrame(
        [
            {
                "model": name,
                "selected_ids": ";".join(f.iloc[chosen].grid_id),
                "selected_names": ";".join(f.iloc[chosen]["name"]),
                **portfolio_metrics(matrix, chosen),
            }
            for name, chosen in alternatives.items()
        ]
    )
    save(optimal_table, "all_optimal_sets")

    # Quantify the price of robustness rather than presenting R as universally best.
    nominal_oracle = nominal.integrated_score.iloc[
        top_indices(nominal.integrated_score, 5)
    ].mean()
    price = []
    for model, chosen in {**primary["selections"], **alternatives}.items():
        utility = float(nominal.integrated_score.iloc[chosen].mean())
        price.append(
            {
                "model": model,
                "nominal_mean_utility": utility,
                "nominal_loss_vs_C50": float(nominal_oracle - utility),
                **portfolio_metrics(matrix, chosen),
            }
        )
    price = pd.DataFrame(price)
    save(price, "price_of_robustness")
    portfolios = pd.DataFrame(
        {
            "nominal_mean_utility": nominal.integrated_score.to_numpy()[
                solved["all_combinations"]
            ].mean(axis=1),
            "worst_regret": solved["all_worst_regrets"],
        }
    )
    best = np.inf
    frontier = np.zeros(len(portfolios), dtype=bool)
    for j in np.lexsort((portfolios.worst_regret, -portfolios.nominal_mean_utility)):
        if portfolios.worst_regret.iloc[j] < best - 1e-12:
            frontier[j] = True
            best = portfolios.worst_regret.iloc[j]
    portfolios["pareto_representative"] = frontier
    portfolios["selected_ids"] = [
        ";".join(f.iloc[c].grid_id) for c in solved["all_combinations"]
    ]
    save(portfolios, "all_portfolios_tradeoff")

    lock = {
        "locked_at_utc": datetime.now(UTC).isoformat(),
        "status": "retrospective_reproduction_prior_2025_preliminary_outcomes_known",
        "protocol_sha256": sha256(root / "docs/PUBLIC_DATA_RESEARCH_PROTOCOL.md"),
        "features_sha256": sha256(tables / "candidate_features.csv"),
        "scores_sha256": sha256(tables / "nominal_scores.csv"),
        "selection_sha256": sha256(tables / "portfolio_comparison.csv"),
        "all_optima_sha256": sha256(tables / "all_optimal_sets.csv"),
        "outcomes_not_passed_to_solver": True,
        "external_preregistration": False,
    }
    write_json(out / "prediction_lock.json", lock)
    sales = read_seoul_zip(raw / "sales_2025.zip")
    score_vectors = {
        "A_stores": nominal.static_score,
        "B_vehicle_context": nominal.mobility_score,
        "C50_reduced": nominal.integrated_score,
        "C60_reduced": nominal_scores(f, 0.6).integrated_score,
    }
    outcome, outcome_values = evaluate_public_outcomes(
        sales, f, score_vectors, primary["selections"]
    )
    save(outcome, "external_context_association")
    save(outcome_values, "reported_transaction_context")
    alternate_outcome, _ = evaluate_public_outcomes(sales, f, {}, alternatives)
    save(alternate_outcome, "external_context_all_optima")
    common = common_reported_sectors(sales, f)
    save(pd.DataFrame({"sector": common}), "common_transaction_sectors")
    if common:
        common_outcome, _ = evaluate_public_outcomes(
            sales[sales["서비스_업종_코드"].isin(common)],
            f,
            score_vectors,
            {**primary["selections"], **alternatives},
        )
        save(common_outcome, "external_context_common_sectors")

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font.exists():
        font_manager.fontManager.addfont(font)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update(
        {
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 10,
        }
    )

    def figure(fig, name, note):
        fig.get_layout_engine().set(rect=(0, 0.11, 1, 0.89))
        fig.text(0.015, 0.015, note, fontsize=8, color="#476071")
        for extension in ["png", "svg"]:
            path = figures / f"{name}.{extension}"
            fig.savefig(path, dpi=170, bbox_inches="tight")
            if extension == "svg":
                path.write_text(
                    "\n".join(line.rstrip() for line in path.read_text().splitlines())
                    + "\n"
                )
        plt.close(fig)

    selected = solved["selected"]
    fig, ax = plt.subplots(figsize=(10, 6), layout="constrained")
    ax.scatter(nominal.static_score, nominal.mobility_score, s=80, color="#15869a")
    for i, row in f.iterrows():
        offset = {"용강동": (-32, -18), "공덕동": (8, 4), "성산2동": (-20, 12)}.get(
            row["name"], (4, 6)
        )
        ax.annotate(
            row["name"],
            (nominal.static_score.iloc[i], nominal.mobility_score.iloc[i]),
            xytext=offset,
            textcoords="offset points",
            fontsize=8,
        )
    ax.scatter(
        nominal.static_score.iloc[selected],
        nominal.mobility_score.iloc[selected],
        s=190,
        facecolors="none",
        edgecolors="#e98236",
        linewidths=2,
        label="강건 선택 5곳 · 동점 중 코드순 조합",
    )
    ax.set(
        xlabel="2024년 분기 평균 전체 점포 · 정규화",
        ylabel="2024년 일반도로 차량 맥락 · 정규화",
        title="서로 다른 입지 관점 · 실제 공개자료",
    )
    ax.legend()
    figure(
        fig,
        "ACQUIRED_candidate_tradeoff",
        "서울시 OA-22172 / KTDB View-T 2024 · 점포 재고와 연평균 교통 맥락 · 광고 노출 점수가 아님",
    )

    view = primary["comparison"]
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    ax.bar(view.model, view.worst_regret, color=["#8192a5"] * 4 + ["#13889b"])
    for i, value in enumerate(view.worst_regret):
        ax.text(i, value + 0.004, f"{value:.3f}", ha="center")
    ax.set(
        ylabel="최선 K집합 대비 평균 점수 손실",
        title="선택 5곳의 최악후회 · 작을수록 강건",
    )
    figure(
        fig,
        "ACQUIRED_worst_regret",
        "정의한 시나리오 목적의 비교이며 실제 광고효과 개선율이 아님 · 0~100% 전체 가중치 범위",
    )

    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    ax.scatter(
        portfolios.nominal_mean_utility,
        portfolios.worst_regret,
        s=12,
        color="#c4d5df",
        alpha=0.6,
        label="가능한 3,003개 조합",
    )
    pf = portfolios[frontier].sort_values("nominal_mean_utility")
    ax.plot(
        pf.nominal_mean_utility,
        pf.worst_regret,
        color="#1b8a97",
        label="명목 점수–최악후회 경계",
    )
    for model, color in [("C50_reduced", "#e88934"), ("R_minimax", "#142f50")]:
        row = price[price.model.eq(model)].iloc[0]
        ax.scatter(
            row.nominal_mean_utility, row.worst_regret, color=color, s=80, label=model
        )
    ax.set(
        xlabel="기본 50:50에서 선택 집합의 평균 점수 · 클수록 좋음",
        ylabel="가정 전체의 최악후회 · 작을수록 좋음",
        title="강건성의 대가 · 기본 점수와 선택 위험의 균형",
    )
    ax.legend(fontsize=8)
    figure(
        fig,
        "ACQUIRED_price_of_robustness",
        "정규화된 의사결정 효용의 교환관계 · 운영비/수익/광고손실액을 측정한 값이 아님",
    )

    fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
    for model, group in outcome.groupby("model", sort=False):
        ax.plot(
            group.quarter.astype(str),
            group.selected_transaction_share,
            marker="o",
            label=model,
        )
    ax.set(
        xlabel="2025년 분기",
        ylabel="선택 5개 동의 보고 거래 건수 비중",
        title="선택 결과와 외부 거래 맥락 · 회고적·탐색적 비교",
    )
    ax.legend(ncol=2, fontsize=8)
    figure(
        fig,
        "ACQUIRED_external_tradeoff",
        "서울시 OA-22175 카드사 기반 추정 자료 · 광고성과 정답 아님 · 과거 예비값 인지, 외부 사전등록 아님",
    )

    fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
    for model, group in pd.DataFrame(cv).groupby("model", sort=False):
        ax.plot(
            group.held_out_quarter.astype(str),
            group.worst_regret,
            marker="o",
            label=model,
        )
    ax.set(
        xlabel="선정에서 제외한 점포 분기",
        ylabel="제외 분기에서의 최악후회",
        title="분기를 하나씩 제외한 자료 명세 검사",
    )
    ax.legend(ncol=2, fontsize=8)
    figure(
        fig,
        "ACQUIRED_held_out_specification",
        "학습에서 제외 분기와 이를 포함하는 연평균도 제거 · 독립 미래 성능이나 Bootstrap 신뢰구간이 아님",
    )

    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    ax.scatter(f.longitude, f.latitude, s=80, color="#8fa5bb", label="비교 가능한 후보")
    ax.scatter(
        f.iloc[selected].longitude,
        f.iloc[selected].latitude,
        s=220,
        color="#13889b",
        label="강건 선택 · 동점 중 코드순 조합",
    )
    for _, row in f.iterrows():
        ax.annotate(
            row["name"],
            (row.longitude, row.latitude),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set(xlabel="경도", ylabel="위도", title="선택한 후보 행정동 · 기관 지도 표시점")
    ax.set_aspect(1 / np.cos(np.deg2rad(37.56)))
    ax.legend(loc="lower left", fontsize=8)
    figure(
        fig,
        "ACQUIRED_selected_dongs",
        "점은 행정동 표시용 좌표이며 배송 거점/정차 위치가 아님 · 보유 도로 맥락 없는 동은 제외",
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "study_type": "acquired_aggregate_reduced_model_decision_study",
        "field_observation_required": False,
        "year_inputs": 2024,
        "year_external_context": 2025,
        "mapo_dongs": len(coverage),
        "eligible_dongs": len(f),
        "excluded": coverage.loc[
            ~coverage.eligible, ["grid_id", "name", "reason"]
        ].to_dict("records"),
        "network_links_matched": len(links),
        "network_length_match": True,
        "commercial_mapo_sector_rows": int(store_coverage.reported_industries.sum()),
        "scenario_endpoint_rows": len(design),
        "unique_score_vectors": len(np.unique(matrix.round(12), axis=0)),
        "primary_k": 5,
        "combinations_evaluated": solved["combinations_evaluated"],
        "optimal_sets": solved["optimal_sets"],
        "primary_comparison": view.to_dict("records"),
        "all_optimal_sets": optimal_table.to_dict("records"),
        "primary_external_context": outcome[outcome.primary].to_dict("records"),
        "common_transaction_industries": len(common),
        "reported_transaction_sector_range": [
            int(outcome_values.reported_industries.min()),
            int(outcome_values.reported_industries.max()),
        ],
        "price_of_robustness": price.to_dict("records"),
        "new_2026_file_holdout": "not_run_no_2026_file_in_reviewed_official_listing; separate_API_not_verified",
        "prior_2025_preliminary_outcomes_known": True,
        "external_preregistration": False,
        "full_population_vehicle_model": "not_run_weekday_definition_unresolved",
        "sources": {
            "stores": {
                "page": "https://data.seoul.go.kr/dataList/OA-22172/S/1/datasetView.do",
                "sha256": sha256(raw / "stores_2024.zip"),
            },
            "sales": {
                "page": "https://data.seoul.go.kr/dataList/OA-22175/S/1/datasetView.do",
                "sha256": sha256(raw / "sales_2025.zip"),
            },
            "network_sha256": sha256(args.network),
            "road_metadata_sha256": sha256(
                root / "data/processed/viewt_official_roads/metadata.json"
            ),
            "provider_names_sha256": sha256(names_path),
            "map_display_points_sha256": sha256(label_source),
        },
        "limitations": [
            "No advertising exposure/effect observations",
            "One district; 15 eligible aggregate candidates",
            "Retrospective current releases and known preliminary 2025 outcomes; not prospective prediction",
            "Provider nominal link-to-dong assignment, not precise clipped allocation",
            "Reported industry coverage varies; missing rows not zero",
            "Estimated transactions are commercial context, not independent ad ground truth",
            "Regret improvements conditional on assumed utility/scenarios",
            "Population excluded until weekday alignment is established",
            "No route/time/cost/capacity/visibility constraints",
        ],
    }
    summary = json.loads(pd.Series(summary).to_json(force_ascii=False))
    summary["code_sha256"] = {
        str(p.relative_to(root)): sha256(p)
        for p in [
            Path(__file__).resolve(),
            root / "src/transit_ooh/public_decision.py",
            root / "src/transit_ooh/public_sources.py",
        ]
    }
    summary["artifacts_sha256"] = {
        str(p.relative_to(out)): sha256(p)
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.name != "summary.json"
    }
    write_json(out / "summary.json", summary)
    print(
        json.dumps(
            {
                key: summary[key]
                for key in [
                    "eligible_dongs",
                    "excluded",
                    "combinations_evaluated",
                    "optimal_sets",
                    "primary_comparison",
                    "price_of_robustness",
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
