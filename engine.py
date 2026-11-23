from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "clean"
OUT = ROOT / "outputs"
ASSUMPTIONS_FILE = CLEAN / "assumptions_register.csv"
INPUTS = ["copper", "nickel", "aluminium", "phenolic_resin", "natural_rubber", "steel_hr", "steel_cr"]
DIVISIONS = ["steering_gear", "braking", "engine_valves", "light_metal_castings"]

MIXES = {
    "steering_gear": {"copper": 0.08, "nickel": 0.04, "aluminium": 0.06, "phenolic_resin": 0.07, "natural_rubber": 0.03, "steel_hr": 0.35, "steel_cr": 0.37},
    "braking": {"copper": 0.03, "nickel": 0.01, "aluminium": 0.05, "phenolic_resin": 0.25, "natural_rubber": 0.25, "steel_hr": 0.22, "steel_cr": 0.19},
    "engine_valves": {"copper": 0.06, "nickel": 0.04, "aluminium": 0.08, "phenolic_resin": 0.03, "natural_rubber": 0.02, "steel_hr": 0.45, "steel_cr": 0.32},
    "light_metal_castings": {"copper": 0.01, "nickel": 0.02, "aluminium": 0.70, "phenolic_resin": 0.02, "natural_rubber": 0.01, "steel_hr": 0.14, "steel_cr": 0.10},
}
DIVISION_SPEND = {"steering_gear": 0.35, "braking": 0.20, "engine_valves": 0.20, "light_metal_castings": 0.25}

SUPPLIERS = {
    "copper": "Assumed imported copper supplier pool",
    "nickel": "Assumed imported nickel supplier pool",
    "aluminium": "Assumed aluminium ingot/foundry supplier pool",
    "phenolic_resin": "Assumed phenolic resin supplier pool; proxy price source",
    "natural_rubber": "Assumed Indian natural rubber supplier pool",
    "steel_hr": "Assumed domestic HR coil mill pool",
    "steel_cr": "Assumed domestic CR coil mill pool",
}


def _default_register_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(key: str, value: Any, unit: str, rationale: str, category: str = "model") -> None:
        rows.append({"category": category, "key": key, "value": value, "unit": unit, "source_or_rationale": rationale, "editable": "TRUE"})

    add("baseline_revenue_cr", 3421.0, "INR crore/year", "Official hackathon handout FY25 modelled baseline", "baseline")
    add("baseline_ebitda_cr", 297.7, "INR crore/year", "Official handout FY25 modelled baseline", "baseline")
    add("baseline_pat_cr", 37.6, "INR crore/year", "Official handout FY25 modelled baseline", "baseline")
    add("baseline_raw_material_spend_cr", 1223.0, "INR crore/year", "Official handout; seven inputs combined", "baseline")
    add("default_oem_pass_through_pct", 50.0, "%", "Official handout; editable scenario control", "baseline")
    add("baseline_ocean_freight_spend_cr", 25.0, "INR crore/year", "Official handout; modelled inbound ocean spend", "baseline")
    add("baseline_freight_usd_per_container", 2172.0, "USD per 40-foot container", "Official handout value dated 19 Mar 2026; also last value in freight file", "baseline")
    add("baseline_freight_reference_date", "2026-03-19", "date", "Official handout anchor; freight source dates reconstructed", "baseline")
    add("baseline_fx_inr_per_usd", 94.675, "INR per USD", "Latest cleaned RBI/interbank close, 30 Jun 2026; 134 days older than latest price driver", "baseline")
    add("baseline_fx_reference_date", "2026-06-30", "date", "Latest FX observation in supplied file", "baseline")
    add("marginal_tax_rate_pct", 25.0, "%", "Simplified marginal tax assumption from handout guidance", "baseline")
    add("inventory_carry_rate_pct", 18.0, "% per year", "Illustrative annual carrying cost; no company input supplied", "inventory")
    add("current_stock_cover_days_default", 30.0, "days", "Illustrative starting cover; no inventory data supplied", "inventory")
    add("safety_stock_days_default", 15.0, "days", "Illustrative buffer; no safety-stock data supplied", "inventory")
    add("container_payload_tonnes", 24.0, "tonnes/container", "Illustrative payload capacity; no lane/container data supplied", "logistics")
    add("payload_utilization_pct", 85.0, "% of payload", "Illustrative utilization; no container loading data supplied", "logistics")
    add("inland_freight_inr_per_tonne", 2500.0, "INR/tonne", "Illustrative inland + handling transport allowance", "logistics")
    add("handling_insurance_pct", 1.5, "% of material value", "Illustrative handling/insurance allowance", "logistics")
    add("division_share.steering_gear", 35.0, "% of raw spend", "Illustrative allocation; no division spend mix supplied", "division")
    add("division_share.braking", 20.0, "% of raw spend", "Illustrative allocation; no division spend mix supplied", "division")
    add("division_share.engine_valves", 20.0, "% of raw spend", "Illustrative allocation; no division spend mix supplied", "division")
    add("division_share.light_metal_castings", 25.0, "% of raw spend", "Illustrative allocation; no division spend mix supplied", "division")
    for division, mix in MIXES.items():
        for material, share in mix.items():
            add(f"mix.{division}.{material}", share * 100.0, "% of division raw spend", "Illustrative engineering mix; not actual Rane BOM", "division_mix")
    imports = {"copper": 80, "nickel": 95, "aluminium": 70, "phenolic_resin": 75, "natural_rubber": 10, "steel_hr": 10, "steel_cr": 10}
    duties = {"copper": 5, "nickel": 5, "aluminium": 5, "phenolic_resin": 7.5, "natural_rubber": 0, "steel_hr": 7.5, "steel_cr": 7.5}
    leads = {"copper": 60, "nickel": 75, "aluminium": 55, "phenolic_resin": 45, "natural_rubber": 30, "steel_hr": 30, "steel_cr": 30}
    for material in INPUTS:
        add(f"import_share.{material}", imports[material], "%", "Illustrative sourcing split; no supplier/procurement file supplied", "sourcing")
        add(f"duty_rate.{material}", duties[material], "% ad valorem", "Illustrative baseline duty; verify actual HS code and origin", "sourcing")
        add(f"lead_time_days.{material}", leads[material], "days", "Illustrative supplier lead time; no supplier master supplied", "inventory")
        add(f"stock_cover_days.{material}", 30, "days", "Illustrative on-hand cover; no inventory file supplied", "inventory")
        add(f"safety_stock_days.{material}", 15, "days", "Illustrative buffer; editable", "inventory")
        add(f"supplier.{material}", SUPPLIERS[material], "supplier group", "Placeholder group label; actual suppliers not supplied", "sourcing")
    action_assumptions = {
        "forward_buy_share_pct": (25, "% of annual material volume", "Illustrative eligible forward-buy share"),
        "forward_buy_cover_days": (60, "days", "Illustrative forward-buy cover window"),
        "hedge_share_pct": (50, "% of exposed imported spend", "Illustrative hedge ratio"),
        "hedge_premium_pct": (1, "% of hedged notional", "Illustrative annual hedge cost"),
        "contract_share_pct": (35, "% of annual spend", "Illustrative contract-locked share"),
        "contract_premium_pct": (1.5, "% of locked spend", "Illustrative supplier contract premium"),
        "alternate_share_pct": (20, "% of imported spend", "Illustrative qualified alternate share"),
        "alternate_premium_pct": (2, "% of shifted spend", "Illustrative alternate sourcing premium"),
        "alternate_qualification_cost_cr": (0.2, "INR crore", "Illustrative one-time qualification cost"),
        "stock_topup_days": (15, "days", "Illustrative safety-stock increase"),
        "downtime_cost_cr_per_day": (1.5, "INR crore/day", "Illustrative contribution/line disruption proxy; not company actual"),
        "air_freight_share_pct": (10, "% of inbound volume expedited", "Illustrative emergency air share"),
        "air_vs_ocean_cost_multiple": (10, "times ocean freight cost", "Illustrative air premium multiple"),
        "air_days_saved": (18, "days", "Illustrative air transit-time reduction"),
        "reroute_share_pct": (30, "% of inbound volume rerouted", "Illustrative rerouted volume share"),
        "reroute_surcharge_pct": (25, "% of rerouted ocean freight", "Illustrative reroute surcharge"),
        "reroute_days_saved": (12, "days", "Illustrative reroute lead-time reduction"),
        "oem_target_pass_through_pct": (80, "%", "Illustrative negotiated target; not contractual fact"),
        "oem_concession_pct": (0.25, "% of revenue", "Illustrative commercial concession to secure recovery"),
        "resequence_days_saved": (6, "days", "Illustrative production re-sequencing benefit"),
        "resequence_setup_cost_cr": (0.15, "INR crore", "Illustrative setup/scrap cost"),
        "demand_cut_pct": (5, "% of remaining volume", "Illustrative additional demand-based cut"),
    }
    for key, (value, unit, why) in action_assumptions.items():
        add(key, value, unit, why, "action")
    return rows


def write_default_assumptions(path: Path = ASSUMPTIONS_FILE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(_default_register_rows()).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _parse_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    v = value.strip()
    try:
        return float(v)
    except ValueError:
        return v


def load_assumptions(path: Path = ASSUMPTIONS_FILE, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    write_default_assumptions(path)
    df = pd.read_csv(path, dtype={"key": str, "value": str})
    result = {row.key: _parse_value(row.value) for row in df.itertuples()}
    if overrides:
        result.update(overrides)
    return result


PRESETS: dict[str, dict[str, Any]] = {
    "Base case": {},
    "Red Sea / Hormuz crisis": {"freight_change_pct": 300.0, "fx_change_pct": 3.0, "lead_time_delay_days": 30.0},
    "Metal shock": {"material_price_shocks_pct": {"copper": 20.0, "nickel": 25.0, "aluminium": 15.0, "phenolic_resin": 5.0, "natural_rubber": 5.0, "steel_hr": 20.0, "steel_cr": 20.0}},
    "Tariff and FX escalation": {"fx_change_pct": 10.0, "tariff_change_pct": 10.0},
    "Demand recession": {"demand_change_pct": -15.0, "freight_change_pct": -20.0,
                         "material_price_shocks_pct": {m: -5.0 for m in INPUTS}},
}


def scenario_from_preset(name: str = "Base case", overrides: dict[str, Any] | None = None,
                         assumptions: dict[str, Any] | None = None) -> dict[str, Any]:
    if name not in PRESETS:
        raise KeyError(f"Unknown preset {name!r}; choose from {list(PRESETS)}")
    a = assumptions or load_assumptions()
    scenario: dict[str, Any] = {
        "preset": name,
        "material_price_shocks_pct": {m: 0.0 for m in INPUTS},
        "freight_change_pct": 0.0,
        "fx_change_pct": 0.0,
        "tariff_change_pct": 0.0,
        "demand_change_pct": 0.0,
        "oem_pass_through_pct": float(a["default_oem_pass_through_pct"]),
        "lead_time_delay_days": 0.0,
    }
    preset = PRESETS[name]
    scenario.update({k: v for k, v in preset.items() if k != "material_price_shocks_pct"})
    if "material_price_shocks_pct" in preset:
        scenario["material_price_shocks_pct"].update(preset["material_price_shocks_pct"])
    if overrides:
        for key, value in overrides.items():
            if key == "material_price_shocks_pct":
                scenario[key].update(value)
            else:
                scenario[key] = value
    for material in INPUTS:
        scenario["material_price_shocks_pct"].setdefault(material, 0.0)
    _validate_scenario(scenario)
    return scenario


def _validate_scenario(s: dict[str, Any]) -> None:
    for key in ("freight_change_pct", "fx_change_pct", "demand_change_pct"):
        if float(s[key]) <= -100:
            raise ValueError(f"{key} must be greater than -100%")
    if not 0 <= float(s["oem_pass_through_pct"]) <= 100:
        raise ValueError("oem_pass_through_pct must be between 0 and 100")
    if float(s["lead_time_delay_days"]) < 0:
        raise ValueError("lead_time_delay_days cannot be negative")
    if float(s["tariff_change_pct"]) <= -100:
        raise ValueError("tariff_change_pct must be greater than -100%")
    for material, shock in s["material_price_shocks_pct"].items():
        if float(shock) <= -100:
            raise ValueError(f"{material} price shock must be greater than -100%")


def _latest_prices(clean_dir: Path) -> tuple[dict[str, dict[str, Any]], float, str]:
    specs = {
        "copper": ("copper_monthly.csv", "price_usd_per_tonne", "USD/t"),
        "nickel": ("nickel_monthly.csv", "price_usd_per_tonne", "USD/t"),
        "aluminium": ("aluminium_monthly.csv", "cash_settlement_usd_per_tonne", "USD/t"),
        "phenolic_resin": ("resin_irregular.csv", "price_usd_per_kg", "USD/kg"),
        "natural_rubber": ("natural_rubber_annual.csv", "price_rs_per_tonne", "INR/t"),
        "steel_hr": ("steel_monthly.csv", "hr_coil_2_5mm_rs_t", "INR/t"),
        "steel_cr": ("steel_monthly.csv", "cr_coil_0_63mm_rs_t", "INR/t"),
    }
    prices: dict[str, dict[str, Any]] = {}
    for name, (file, col, currency) in specs.items():
        df = pd.read_csv(clean_dir / file)
        date_col = "fiscal_year_end" if name == "natural_rubber" else "date"
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col, col]).sort_values(date_col)
        last = df.iloc[-1]
        source_value = float(last[col])
        value = source_value
        if name == "phenolic_resin":
            value *= 1000.0  # USD/kg -> USD/t
        prices[name] = {"raw_price": value, "source_price": source_value, "source_unit": currency,
                        "date": pd.Timestamp(last[date_col]).date().isoformat()}
    fx = pd.read_csv(clean_dir / "fx_daily.csv")
    fx["date"] = pd.to_datetime(fx["date"], errors="coerce")
    fx["close_inr_per_usd"] = pd.to_numeric(fx["close_inr_per_usd"], errors="coerce")
    fx = fx.dropna(subset=["date", "close_inr_per_usd"]).sort_values("date")
    return prices, float(fx.iloc[-1].close_inr_per_usd), pd.Timestamp(fx.iloc[-1].date).date().isoformat()


def _shares(a: dict[str, Any]) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    division_spend = {d: float(a[f"division_share.{d}"]) / 100.0 for d in DIVISIONS}
    if abs(sum(division_spend.values()) - 1.0) > 1e-6:
        raise ValueError("Division spend shares must sum to 100% in assumptions_register.csv")
    mix = {d: {m: float(a[f"mix.{d}.{m}"]) / 100.0 for m in INPUTS} for d in DIVISIONS}
    for d in DIVISIONS:
        if abs(sum(mix[d].values()) - 1.0) > 1e-6:
            raise ValueError(f"Material mix for {d} must sum to 100%")
    return division_spend, mix


def calculate_scenario(scenario: dict[str, Any] | None = None, assumptions: dict[str, Any] | None = None,
                       clean_dir: Path = CLEAN) -> dict[str, Any]:
    a = assumptions or load_assumptions()
    s = scenario_from_preset(scenario.get("preset", "Base case"), scenario, a) if scenario else scenario_from_preset("Base case", assumptions=a)
    _validate_scenario(s)
    prices, observed_fx, fx_date = _latest_prices(clean_dir)
    fx_base = float(a["baseline_fx_inr_per_usd"])
    fx_scenario = fx_base * (1.0 + float(s["fx_change_pct"]) / 100.0)
    freight_base = float(a["baseline_freight_usd_per_container"])
    freight_scenario = freight_base * (1.0 + float(s["freight_change_pct"]) / 100.0)
    payload = float(a["container_payload_tonnes"]) * float(a["payload_utilization_pct"]) / 100.0
    if payload <= 0:
        raise ValueError("Container payload after utilization must be positive")
    freight_inr_tonne_base = freight_base * fx_base / payload
    freight_inr_tonne_scenario = freight_scenario * fx_scenario / payload
    raw_spend = float(a["baseline_raw_material_spend_cr"])
    demand_factor = 1.0 + float(s["demand_change_pct"]) / 100.0
    pass_through = float(s["oem_pass_through_pct"]) / 100.0
    tariff = float(s["tariff_change_pct"]) / 100.0
    fx_change = float(s["fx_change_pct"]) / 100.0
    freight_change = float(s["freight_change_pct"]) / 100.0
    division_spend, mix = _shares(a)

    input_spend: dict[str, float] = {m: 0.0 for m in INPUTS}
    for d in DIVISIONS:
        for m in INPUTS:
            input_spend[m] += raw_spend * division_spend[d] * mix[d][m]

    input_rows: list[dict[str, Any]] = []
    unit_cost_factor: dict[str, float] = {}
    imported_shock_cr = 0.0
    material_delta_cr = 0.0
    for m in INPUTS:
        imp = float(a[f"import_share.{m}"]) / 100.0
        duty = float(a[f"duty_rate.{m}"]) / 100.0
        price_shock = float(s["material_price_shocks_pct"].get(m, 0.0)) / 100.0
        base_price = prices[m]["raw_price"]
        usd_based = prices[m]["source_unit"].startswith("USD")
        base_fob_inr = base_price * fx_base if usd_based else base_price
        scenario_fx_factor = 1.0 + imp * fx_change
        base_duty_factor = 1.0 + imp * duty
        scenario_duty_factor = 1.0 + imp * (duty + tariff)
        factor = (1.0 + price_shock) * scenario_fx_factor * scenario_duty_factor / base_duty_factor
        unit_cost_factor[m] = factor
        shock_cr = input_spend[m] * demand_factor * (factor - 1.0)
        material_delta_cr += shock_cr
        # A conservative estimate of exposed import shock for hedge/alternate sourcing actions.
        imported_factor = max(0.0, (1.0 + price_shock) * (1.0 + fx_change) * (1.0 + duty + tariff) / (1.0 + duty) - 1.0)
        imported_shock_cr += input_spend[m] * demand_factor * imp * imported_factor

        scenario_fob_inr = base_fob_inr * (1.0 + price_shock) * scenario_fx_factor
        base_duty_cr = base_fob_inr * imp * duty
        scenario_duty_cr = scenario_fob_inr * imp * (duty + tariff)
        base_ocean_inr_t = imp * freight_inr_tonne_base
        scenario_ocean_inr_t = imp * freight_inr_tonne_scenario
        inland = float(a["inland_freight_inr_per_tonne"])
        handling_rate = float(a["handling_insurance_pct"]) / 100.0
        base_landed = base_fob_inr + base_duty_cr + base_ocean_inr_t + inland
        scenario_landed = scenario_fob_inr + scenario_duty_cr + scenario_ocean_inr_t + inland
        base_landed *= 1.0 + handling_rate
        scenario_landed *= 1.0 + handling_rate
        input_rows.append({
            "input": m, "supplier_group_assumption": a[f"supplier.{m}"], "source_date": prices[m]["date"],
            "source_price": prices[m]["source_price"], "source_unit": prices[m]["source_unit"],
            "price_basis_per_tonne": prices[m]["raw_price"],
            "baseline_spend_share_pct": input_spend[m] / raw_spend * 100.0,
            "scenario_price_shock_pct": float(s["material_price_shocks_pct"].get(m, 0.0)),
            "import_share_assumption_pct": imp * 100.0, "duty_rate_assumption_pct": duty * 100.0,
            "material_cost_factor": factor,
            "base_landed_cost_inr_per_tonne": base_landed,
            "scenario_landed_cost_inr_per_tonne": scenario_landed,
            "landed_cost_change_pct": (scenario_landed / base_landed - 1.0) * 100.0,
            "baseline_material_cost_cr": input_spend[m] * demand_factor,
            "scenario_material_cost_cr": input_spend[m] * demand_factor * factor,
            "delta_vs_volume_adjusted_baseline_cr": shock_cr,
            "lead_time_days_assumption": float(a[f"lead_time_days.{m}"]),
            "stock_cover_days_assumption": float(a[f"stock_cover_days.{m}"]),
            "safety_stock_days_assumption": float(a[f"safety_stock_days.{m}"]),
        })

    baseline_freight = float(a["baseline_ocean_freight_spend_cr"]) * demand_factor
    scenario_freight = baseline_freight * (1.0 + freight_change) * (fx_scenario / fx_base)
    freight_delta_cr = scenario_freight - baseline_freight
    gross_shock_cr = material_delta_cr + freight_delta_cr
    oem_recovery_cr = gross_shock_cr * pass_through
    ebitda_baseline_demand = float(a["baseline_ebitda_cr"]) * demand_factor
    ebitda_after = ebitda_baseline_demand - gross_shock_cr * (1.0 - pass_through)
    ebitda_delta = ebitda_after - float(a["baseline_ebitda_cr"])
    tax = float(a["marginal_tax_rate_pct"]) / 100.0
    pat_after = float(a["baseline_pat_cr"]) + ebitda_delta * (1.0 - tax)
    revenue_after = float(a["baseline_revenue_cr"]) * demand_factor + oem_recovery_cr

    line_rows: list[dict[str, Any]] = []
    for d in DIVISIONS:
        base_line = raw_spend * division_spend[d]
        base_scaled = base_line * demand_factor
        scenario_line = base_line * demand_factor * sum(mix[d][m] * unit_cost_factor[m] for m in INPUTS)
        base_freight_line = float(a["baseline_ocean_freight_spend_cr"]) * division_spend[d]
        scaled_freight_line = base_freight_line * demand_factor
        scenario_freight_line = scenario_freight * division_spend[d]
        line_rows.append({"division": d, "raw_spend_allocation_pct_assumption": division_spend[d] * 100.0,
                          "baseline_raw_material_cost_cr": base_line, "volume_adjusted_raw_material_cost_cr": base_scaled,
                          "scenario_raw_material_cost_cr": scenario_line, "baseline_ocean_freight_cost_cr": base_freight_line,
                          "volume_adjusted_ocean_freight_cost_cr": scaled_freight_line, "scenario_ocean_freight_cost_cr": scenario_freight_line,
                          "scenario_total_landed_cost_cr": scenario_line + scenario_freight_line,
                          "delta_vs_volume_adjusted_baseline_cr": scenario_line + scenario_freight_line - base_scaled - scaled_freight_line})

    lead_delay = float(s["lead_time_delay_days"])
    inventory_rows = []
    total_daily_spend = raw_spend / 365.0
    for row in input_rows:
        m = row["input"]
        cover = float(row["stock_cover_days_assumption"]) / demand_factor
        lead = float(row["lead_time_days_assumption"]) + lead_delay
        safety = float(row["safety_stock_days_assumption"])
        reorder_threshold = lead + safety
        inventory_rows.append({
            "input": m, "stock_cover_days_scenario": cover, "supplier_lead_time_days": lead,
            "safety_stock_days": safety, "days_cover_after_lead_time": cover - lead,
            "reorder_point_days": reorder_threshold, "reorder_alert": cover < reorder_threshold,
            "stockout_alert": cover < lead,
            "estimated_daily_consumption_cr": input_spend[m] * demand_factor / 365.0,
            "estimated_inventory_value_cr": input_spend[m] * demand_factor * cover / 365.0,
        })

    freight_rate_local = freight_scenario * fx_scenario
    containers_base = float(a["baseline_ocean_freight_spend_cr"]) * 10_000_000.0 / (freight_base * fx_base)
    containers_scenario = containers_base * demand_factor
    container = {
        "baseline_freight_usd_per_40ft_container": freight_base,
        "scenario_freight_usd_per_40ft_container": freight_scenario,
        "scenario_fx_inr_per_usd": fx_scenario,
        "payload_capacity_tonnes": float(a["container_payload_tonnes"]),
        "payload_utilization_pct": float(a["payload_utilization_pct"]),
        "loaded_payload_tonnes_per_container": payload,
        "freight_cost_inr_per_container": freight_rate_local,
        "freight_cost_inr_per_loaded_tonne": freight_rate_local / payload,
        "baseline_annual_containers_modelled": containers_base,
        "scenario_annual_containers_modelled": containers_scenario,
        "scenario_annual_inbound_tonnage_modelled": containers_scenario * payload,
        "annual_ocean_freight_spend_cr_scenario": scenario_freight,
        "baseline_freight_anchor": a["baseline_freight_reference_date"],
        "fx_anchor": a["baseline_fx_reference_date"],
    }

    latest_price_date = max(pd.Timestamp(x["date"]) for x in prices.values())
    context = {"scenario": s, "assumption_source": str(ASSUMPTIONS_FILE), "observed_fx_latest_inr_per_usd": observed_fx,
               "observed_fx_latest_date": fx_date, "fx_reference_mismatch_days": (pd.Timestamp(fx_date) - pd.Timestamp(a["baseline_fx_reference_date"])).days,
               "latest_material_price_date": latest_price_date.date().isoformat(),
               "fx_to_latest_material_price_gap_days": (latest_price_date - pd.Timestamp(a["baseline_fx_reference_date"])).days,
               "baseline_reference": "Handout raw spend retained; input price shocks apply relative to latest observed price per input; freight anchored to 19 Mar 2026; FX anchored to 30 Jun 2026."}
    metrics = {
        "revenue_after_cr": revenue_after, "revenue_change_vs_baseline_cr": revenue_after - float(a["baseline_revenue_cr"]),
        "gross_material_cost_shock_cr": material_delta_cr, "gross_freight_cost_shock_cr": freight_delta_cr,
        "gross_total_cost_shock_cr": gross_shock_cr, "oem_recovery_cr": oem_recovery_cr,
        "net_unpassed_cost_shock_cr": gross_shock_cr - oem_recovery_cr,
        "ebitda_baseline_cr": float(a["baseline_ebitda_cr"]), "ebitda_after_cr": ebitda_after,
        "ebitda_change_vs_baseline_cr": ebitda_delta, "ebitda_margin_after_pct": ebitda_after / revenue_after * 100.0 if revenue_after else 0.0,
        "pat_baseline_cr": float(a["baseline_pat_cr"]), "pat_after_cr": pat_after,
        "pat_change_after_tax_cr": pat_after - float(a["baseline_pat_cr"]), "tax_rate_assumption_pct": float(a["marginal_tax_rate_pct"]),
        "oem_pass_through_pct": pass_through * 100.0,
        "raw_material_cost_scenario_cr": sum(x["scenario_material_cost_cr"] for x in input_rows),
        "ocean_freight_cost_scenario_cr": scenario_freight,
        "scenario_operating_cost_proxy_cr": sum(x["scenario_material_cost_cr"] for x in input_rows) + scenario_freight,
    }
    actions = _action_matrix(a, s, metrics, input_rows, inventory_rows, container, input_spend, imported_shock_cr, demand_factor)
    return {"context": context, "metrics": metrics, "landed_costs": input_rows, "line_costs": line_rows,
            "inventory": inventory_rows, "container": container, "actions": actions}


def _action_matrix(a: dict[str, Any], s: dict[str, Any], metrics: dict[str, Any], input_rows: list[dict[str, Any]],
                   inventory_rows: list[dict[str, Any]], container: dict[str, Any], input_spend: dict[str, float],
                   imported_shock_cr: float, demand_factor: float) -> list[dict[str, Any]]:
    raw_spend = float(a["baseline_raw_material_spend_cr"])
    positive_material_delta = max(0.0, float(metrics["gross_material_cost_shock_cr"]))
    positive_total_shock = max(0.0, float(metrics["gross_total_cost_shock_cr"]))
    delay = float(s["lead_time_delay_days"])
    cover_gap = max((float(r["supplier_lead_time_days"]) + float(r["safety_stock_days"]) - float(r["stock_cover_days_scenario"])) for r in inventory_rows)
    at_risk_days = max(0.0, cover_gap)
    downtime = float(a["downtime_cost_cr_per_day"])
    action_defs: list[dict[str, Any]] = []

    locked_share = min(float(a["forward_buy_share_pct"]) / 100.0, float(a["forward_buy_cover_days"]) / 365.0)
    fb_benefit = positive_material_delta * locked_share
    fb_cost = raw_spend * locked_share * float(a["inventory_carry_rate_pct"]) / 100.0 * float(a["forward_buy_cover_days"]) / 365.0
    action_defs.append({"action": "Forward-buy selected inputs", "cost": fb_cost, "benefit": fb_benefit,
        "wc_release": 0.0, "functions": "MMD; Finance; Logistics; suppliers", "suppliers": "; ".join(sorted(set(str(r["supplier_group_assumption"]) for r in input_rows))),
        "formula": "Benefit = positive material shock × min(forward-buy share, cover days/365); cost = financed purchased value × carrying rate × cover days/365."})

    hedge_share = float(a["hedge_share_pct"]) / 100.0
    hedge_benefit = max(0.0, imported_shock_cr) * hedge_share
    imported_baseline = sum(float(r["baseline_material_cost_cr"]) * float(r["import_share_assumption_pct"]) / 100.0 for r in input_rows)
    hedge_cost = imported_baseline * hedge_share * float(a["hedge_premium_pct"]) / 100.0
    action_defs.append({"action": "LME / FX hedge", "cost": hedge_cost, "benefit": hedge_benefit,
        "wc_release": 0.0, "functions": "MMD; Finance; Procurement; suppliers", "suppliers": "Copper, nickel, aluminium and resin supplier groups (assumed)",
        "formula": "Benefit = positive imported-price/FX/tariff shock × hedge share; cost = imported baseline spend × hedge share × hedge premium."})

    contract_share = float(a["contract_share_pct"]) / 100.0
    contract_benefit = positive_material_delta * contract_share
    contract_cost = raw_spend * contract_share * float(a["contract_premium_pct"]) / 100.0
    action_defs.append({"action": "Increase spot-to-contract mix", "cost": contract_cost, "benefit": contract_benefit,
        "wc_release": 0.0, "functions": "MMD; Finance; Procurement; suppliers", "suppliers": "All seven assumed supplier groups",
        "formula": "Benefit = positive material shock × locked share; cost = annual raw spend × locked share × contract premium."})

    alt_share = float(a["alternate_share_pct"]) / 100.0
    alt_benefit = max(0.0, imported_shock_cr) * alt_share
    alt_cost = imported_baseline * alt_share * float(a["alternate_premium_pct"]) / 100.0 + float(a["alternate_qualification_cost_cr"])
    action_defs.append({"action": "Qualify alternate / domestic suppliers", "cost": alt_cost, "benefit": alt_benefit,
        "wc_release": 0.0, "functions": "MMD; Quality; Production; Finance; suppliers", "suppliers": "Illustrative alternate supplier pool by imported input",
        "formula": "Benefit = positive imported cost shock × alternate share; cost = imported baseline spend × share × premium + qualification cost."})

    topup = float(a["stock_topup_days"])
    saved_gap_days = min(topup, at_risk_days)
    stock_cost = raw_spend * topup / 365.0 * float(a["inventory_carry_rate_pct"]) / 100.0
    stock_benefit = saved_gap_days * downtime
    action_defs.append({"action": "Raise safety stock", "cost": stock_cost, "benefit": stock_benefit,
        "wc_release": -raw_spend * topup / 365.0, "functions": "MMD; Finance; Production; Quality; suppliers",
        "suppliers": "All supplier groups for inputs below reorder thresholds",
        "formula": "Benefit = min(stock top-up days, days below lead-time-plus-safety threshold) × downtime proxy/day; cost = added inventory × annual carrying rate."})

    air_share = float(a["air_freight_share_pct"]) / 100.0
    air_cost = float(container["annual_ocean_freight_spend_cr_scenario"]) * air_share * max(0.0, float(a["air_vs_ocean_cost_multiple"]) - 1.0)
    air_benefit = min(delay, float(a["air_days_saved"]), at_risk_days) * downtime
    action_defs.append({"action": "Air-freight critical material", "cost": air_cost, "benefit": air_benefit,
        "wc_release": 0.0, "functions": "MMD; Logistics; Production; Finance; suppliers",
        "suppliers": "Supplier groups causing line-critical shortages",
        "formula": "Cost = scenario ocean spend × expedited share × (air/ocean multiple − 1); benefit = delay days avoided × downtime proxy/day, capped by modeled exposure."})

    reroute_share = float(a["reroute_share_pct"]) / 100.0
    reroute_cost = float(container["annual_ocean_freight_spend_cr_scenario"]) * reroute_share * float(a["reroute_surcharge_pct"]) / 100.0
    reroute_benefit = min(delay, float(a["reroute_days_saved"]), at_risk_days) * downtime
    action_defs.append({"action": "Reroute around chokepoint", "cost": reroute_cost, "benefit": reroute_benefit,
        "wc_release": 0.0, "functions": "MMD; Logistics; Sales; Production; suppliers",
        "suppliers": "Ocean carriers and affected imported input supplier groups",
        "formula": "Cost = scenario ocean spend × rerouted share × surcharge; benefit = delay days avoided × downtime proxy/day, capped by modeled exposure."})

    current_pass = float(s["oem_pass_through_pct"])
    target_pass = max(current_pass, float(a["oem_target_pass_through_pct"]))
    oem_benefit = positive_total_shock * (target_pass - current_pass) / 100.0
    oem_cost = float(a["baseline_revenue_cr"]) * float(a["oem_concession_pct"]) / 100.0
    action_defs.append({"action": "Renegotiate OEM price recovery", "cost": oem_cost, "benefit": oem_benefit,
        "wc_release": 0.0, "functions": "Sales; Finance; MMD; OEM customers",
        "suppliers": "OEM customers; no raw-material supplier change",
        "formula": "Benefit = positive gross input shock × incremental pass-through to target; cost = revenue × illustrative concession rate."})

    seq_days = min(delay, float(a["resequence_days_saved"]), at_risk_days)
    seq_benefit = seq_days * downtime
    seq_cost = float(a["resequence_setup_cost_cr"])
    action_defs.append({"action": "Re-sequence production", "cost": seq_cost, "benefit": seq_benefit,
        "wc_release": 0.0, "functions": "Production; MMD; HR; Quality; Sales",
        "suppliers": "Supplier groups tied to constrained inputs",
        "formula": "Benefit = days of modeled shortage avoided × downtime proxy/day; cost = setup/scrap allowance."})

    cut = float(a["demand_cut_pct"]) / 100.0
    demand_cut_cost = float(a["baseline_ebitda_cr"]) * demand_factor * cut
    wc_release = raw_spend * demand_factor * cut * float(a["current_stock_cover_days_default"]) / 365.0
    action_defs.append({"action": "Demand-based production cuts", "cost": demand_cut_cost, "benefit": 0.0,
        "wc_release": wc_release, "functions": "Sales; Production; MMD; HR; Finance",
        "suppliers": "All supplier groups; purchase call-offs reduced",
        "formula": "Cost = EBITDA contribution lost at baseline margin; working-capital release = raw spend × cut share × stock-cover days/365 (shown separately)."})

    before_ebitda = float(metrics["ebitda_after_cr"])
    before_pat = float(metrics["pat_after_cr"])
    rows = []
    for action in action_defs:
        cost, benefit = float(action["cost"]), float(action["benefit"])
        net = benefit - cost
        after_ebitda = before_ebitda + net
        tax_factor = 1.0 - float(a["marginal_tax_rate_pct"]) / 100.0
        rows.append({
            "action": action["action"], "annual_cost_cr": cost, "annual_benefit_cr": benefit, "net_result_cr": net,
            "scenario_ebitda_before_action_cr": before_ebitda, "ebitda_after_if_action_cr": after_ebitda,
            "scenario_pat_before_action_cr": before_pat, "pat_after_if_action_cr": before_pat + net * tax_factor,
            "working_capital_release_cr": float(action["wc_release"]), "functions_affected": action["functions"],
            "suppliers_affected": action["suppliers"], "formula_note": action["formula"],
            "ranking_basis": "Single-action annual EBITDA-equivalent net result; working-capital release reported separately; actions are not stacked.",
        })
    rows.sort(key=lambda r: r["net_result_cr"], reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def calculate_scenario_from_preset(name: str = "Base case", overrides: dict[str, Any] | None = None,
                                   assumption_overrides: dict[str, Any] | None = None,
                                   clean_dir: Path = CLEAN) -> dict[str, Any]:
    a = load_assumptions(overrides=assumption_overrides)
    s = scenario_from_preset(name, overrides, a)
    return calculate_scenario(s, a, clean_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scenario cost, inventory, container and action engine.")
    parser.add_argument("--preset", default="Base case", choices=list(PRESETS))
    parser.add_argument("--assumptions", type=Path, default=ASSUMPTIONS_FILE)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    a = load_assumptions(args.assumptions)
    result = calculate_scenario(scenario_from_preset(args.preset, assumptions=a), a)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(result["landed_costs"]).to_csv(args.output_dir / "landed_costs.csv", index=False)
    pd.DataFrame(result["line_costs"]).to_csv(args.output_dir / "line_costs_by_division.csv", index=False)
    pd.DataFrame(result["inventory"]).to_csv(args.output_dir / "inventory_runway.csv", index=False)
    pd.DataFrame([result["container"]]).to_csv(args.output_dir / "container_model.csv", index=False)
    pd.DataFrame(result["actions"]).to_csv(args.output_dir / "action_matrix.csv", index=False)
    pd.DataFrame([result["metrics"]]).to_csv(args.output_dir / "scenario_metrics.csv", index=False)
    (args.output_dir / "scenario_run_summary.json").write_text(json.dumps({"context": result["context"], "metrics": result["metrics"]}, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"preset": args.preset, "assumptions_register": str(args.assumptions), "metrics": result["metrics"],
                      "inventory_alerts": sum(r["reorder_alert"] for r in result["inventory"]),
                      "stockout_alerts": sum(r["stockout_alert"] for r in result["inventory"]),
                      "actions": len(result["actions"]), "output_dir": str(args.output_dir)}, indent=2, default=str))


if __name__ == "__main__":
    main()
