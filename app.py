from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

WORK = Path(__file__).resolve().parents[1]
ROOT = WORK.parent
SRC = WORK / "src"
VENDOR = WORK / "vendor"
for p in (str(SRC), str(VENDOR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import engine

st.set_page_config(page_title="Rane Materials Decision Engine", page_icon="⚙️", layout="wide")

SERIES_LABELS = {
    "copper": "Copper",
    "nickel": "Nickel",
    "aluminium": "Aluminium",
    "phenolic_resin": "Resin price proxy",
    "natural_rubber": "Natural rubber",
    "steel_hr": "Steel HR coil",
    "steel_cr": "Steel CR coil",
    "global_40ft_freight": "Global 40 ft freight",
}
SHOCK_CONTROL_KEYS = {m: f"shock_{m}" for m in engine.INPUTS}


def _apply_preset() -> None:
    assumptions = engine.load_assumptions()
    selected = st.session_state.get("preset_choice", "Base case")
    preset = engine.scenario_from_preset(selected, assumptions=assumptions)
    for material, key in SHOCK_CONTROL_KEYS.items():
        st.session_state[key] = float(preset["material_price_shocks_pct"][material])
    for name in ("freight_change_pct", "fx_change_pct", "tariff_change_pct", "demand_change_pct", "oem_pass_through_pct", "lead_time_delay_days"):
        st.session_state[name] = float(preset[name])


def _initialise_controls() -> None:
    if "preset_choice" not in st.session_state:
        st.session_state["preset_choice"] = "Base case"
    initial = engine.scenario_from_preset(st.session_state["preset_choice"])
    for material, key in SHOCK_CONTROL_KEYS.items():
        st.session_state.setdefault(key, float(initial["material_price_shocks_pct"][material]))
    for name in ("freight_change_pct", "fx_change_pct", "tariff_change_pct", "demand_change_pct", "oem_pass_through_pct", "lead_time_delay_days"):
        st.session_state.setdefault(name, float(initial[name]))


def _assumption_overrides(df: pd.DataFrame) -> dict[str, Any]:
    return {str(row["key"]): engine._parse_value(row["value"]) for _, row in df.iterrows()}


def _money(value: float, digits: int = 2) -> str:
    return f"₹{value:,.{digits}f} Cr"


def _scenario_inputs() -> dict[str, Any]:
    return {
        "material_price_shocks_pct": {m: float(st.session_state[SHOCK_CONTROL_KEYS[m]]) for m in engine.INPUTS},
        "freight_change_pct": float(st.session_state["freight_change_pct"]),
        "fx_change_pct": float(st.session_state["fx_change_pct"]),
        "tariff_change_pct": float(st.session_state["tariff_change_pct"]),
        "demand_change_pct": float(st.session_state["demand_change_pct"]),
        "oem_pass_through_pct": float(st.session_state["oem_pass_through_pct"]),
        "lead_time_delay_days": float(st.session_state["lead_time_delay_days"]),
    }


_initialise_controls()

st.title("Rane Materials Management Decision Engine")
st.caption("Offline decision model · slider changes recalculate the full cost, inventory, EBITDA/PAT and action chain immediately.")

with st.sidebar:
    st.header("Live scenario controls")
    st.selectbox("Preset", list(engine.PRESETS), key="preset_choice", on_change=_apply_preset)
    st.caption("You can adjust each shock below independently. No Apply button is needed.")
    with st.expander("Material price shocks", expanded=True):
        shock_labels = {
            "copper": "Copper", "nickel": "Nickel", "aluminium": "Aluminium",
            "phenolic_resin": "Resin proxy", "natural_rubber": "Natural rubber",
            "steel_hr": "Steel HR", "steel_cr": "Steel CR",
        }
        for material in engine.INPUTS:
            st.slider(shock_labels[material] + " shock (%)", -50.0, 200.0, key=SHOCK_CONTROL_KEYS[material], step=1.0)
    with st.expander("Freight, FX, tariff and demand", expanded=True):
        st.slider("40 ft freight change (%)", -80.0, 400.0, key="freight_change_pct", step=1.0,
                  help="+300% represents a 4× rate.")
        st.slider("INR depreciation / appreciation (%)", -30.0, 50.0, key="fx_change_pct", step=1.0)
        st.slider("Tariff change (percentage points)", -10.0, 50.0, key="tariff_change_pct", step=0.5)
        st.slider("Demand change (%)", -50.0, 30.0, key="demand_change_pct", step=1.0)
    with st.expander("Commercial and lead-time controls", expanded=True):
        st.slider("OEM cost pass-through (%)", 0.0, 100.0, key="oem_pass_through_pct", step=1.0)
        st.slider("Additional lead-time delay (days)", 0.0, 90.0, key="lead_time_delay_days", step=1.0)

    with st.expander("Assumptions register", expanded=False):
        st.caption("Values marked illustrative are placeholders, not Rane actuals. Edits recalculate live; Save writes them to the CSV register.")
        register = pd.read_csv(engine.write_default_assumptions(), dtype={"category": str, "key": str, "value": str, "unit": str, "source_or_rationale": str, "editable": str})
        edited_register = st.data_editor(
            register,
            key="assumption_editor",
            hide_index=True,
            height=360,
            width="stretch",
            disabled=["category", "key", "unit", "source_or_rationale", "editable"],
            column_config={
                "value": st.column_config.TextColumn("Value", help="Edit a numeric value or text assumption."),
                "source_or_rationale": st.column_config.TextColumn("Source / rationale", width="large"),
            },
        )
        save_assumptions = st.button("Save assumptions", key="save_assumptions", width="stretch")

edited_values = _assumption_overrides(edited_register)
assumptions = engine.load_assumptions(overrides=edited_values)
scenario = engine.scenario_from_preset(st.session_state["preset_choice"], _scenario_inputs(), assumptions)

try:
    result = engine.calculate_scenario(scenario, assumptions)
except Exception as exc:
    st.error(f"The current assumption edit is invalid, so the saved register is being used. Details: {exc}")
    assumptions = engine.load_assumptions()
    scenario = engine.scenario_from_preset(st.session_state["preset_choice"], _scenario_inputs(), assumptions)
    result = engine.calculate_scenario(scenario, assumptions)
    save_assumptions = False

if save_assumptions:
    try:
        engine._shares(assumptions)
        result = engine.calculate_scenario(scenario, assumptions)
        edited_register.to_csv(engine.ASSUMPTIONS_FILE, index=False, encoding="utf-8-sig")
        st.sidebar.success("Assumptions saved. The current scenario is using the edited values.")
    except Exception as exc:
        st.sidebar.error(f"Assumptions were not saved: {exc}")

tabs = st.tabs([
    "M1 · Forecasts", "M2 · What-if simulator", "M3 · Cost and earnings chain",
    "M4 · Containers and inventory", "M5 · Recommended actions",
])

# M1: forecast display with a transparent scenario overlay.
with tabs[0]:
    st.subheader("Price and freight forecasts")
    st.caption("Forecasts are cached from the Phase 2 engine. The active material/freight shock is overlaid live; bands widen with horizon.")
    forecast_file = WORK / "outputs" / "forecast_paths.csv"
    method_file = WORK / "outputs" / "method_justification.csv"
    if not forecast_file.exists() or not method_file.exists():
        st.warning("Run Phase 2 once to create forecast outputs.")
    else:
        paths = pd.read_csv(forecast_file, parse_dates=["forecast_date"])
        methods = pd.read_csv(method_file)
        selected = st.selectbox("Forecast series", list(SERIES_LABELS), format_func=lambda x: SERIES_LABELS[x], key="forecast_series")
        data = paths[paths["series"] == selected].sort_values("forecast_date").copy()
        overlay = float(scenario["freight_change_pct"]) if selected == "global_40ft_freight" else float(scenario["material_price_shocks_pct"].get(selected, 0.0))
        multiplier = 1.0 + overlay / 100.0
        for col in ("forecast_median", "lower_80", "upper_80", "lower_95", "upper_95"):
            data[col] = pd.to_numeric(data[col], errors="coerce") * multiplier
        chart = data.set_index("forecast_date")[["forecast_median", "lower_80", "upper_80"]]
        chart = chart.rename(columns={"forecast_median": "Median", "lower_80": "80% lower", "upper_80": "80% upper"})
        st.line_chart(chart, height=300)
        summary = pd.read_csv(WORK / "outputs" / "forecast_summary.csv")
        summary = summary[summary.series == selected].copy()
        for col in ("forecast_median", "lower_80", "upper_80", "lower_95", "upper_95"):
            summary[col] = pd.to_numeric(summary[col], errors="coerce") * multiplier
        st.dataframe(summary[["horizon_months", "forecast_date", "forecast_median", "lower_80", "upper_80", "lower_95", "upper_95", "unit"]], hide_index=True, width="stretch")
        method = methods[methods.series == selected]
        if not method.empty:
            m = method.iloc[0]
            st.info(f"Method: {m['selected_method']} · Confidence: {m['confidence']} · Rolling-origin MAPE: {m['mean_mape_pct']:.2f}%" if pd.notna(m["mean_mape_pct"]) else f"Method: {m['selected_method']} · Confidence: {m['confidence']}")
            st.caption(str(m["selection_basis"]))
        if selected == "phenolic_resin":
            st.warning("The supplied resin price series is generic and is not confirmed as the exact phenolic formulation.")
        if selected == "natural_rubber":
            st.warning("Annual data ends at FY2024–25. The monthly display interpolates the one-year forecast from that source date.")
        if selected == "global_40ft_freight":
            st.warning("Source dates were reconstructed between stated endpoints; the locations of two missing weekly observations are unknown.")

# M2: all scenario values and cost bridge update on every rerun.
with tabs[1]:
    st.subheader("What-if scenario simulator")
    st.write(f"Active preset: **{scenario['preset']}** · all controls are live.")
    m = result["metrics"]
    cols = st.columns(4)
    cols[0].metric("Gross cost shock", _money(m["gross_total_cost_shock_cr"]))
    cols[1].metric("OEM recovery", _money(m["oem_recovery_cr"]))
    cols[2].metric("EBITDA after shock", _money(m["ebitda_after_cr"]), delta=_money(m["ebitda_change_vs_baseline_cr"]))
    cols[3].metric("PAT after tax", _money(m["pat_after_cr"]), delta=_money(m["pat_change_after_tax_cr"]))
    bridge = pd.DataFrame([
        {"Cost bridge": "Material price / FX / tariff", "Impact (₹ Cr)": m["gross_material_cost_shock_cr"]},
        {"Cost bridge": "Ocean freight", "Impact (₹ Cr)": m["gross_freight_cost_shock_cr"]},
        {"Cost bridge": "Total gross shock", "Impact (₹ Cr)": m["gross_total_cost_shock_cr"]},
        {"Cost bridge": "OEM recovery", "Impact (₹ Cr)": -m["oem_recovery_cr"]},
        {"Cost bridge": "Net unpassed cost", "Impact (₹ Cr)": m["net_unpassed_cost_shock_cr"]},
    ])
    st.bar_chart(bridge.set_index("Cost bridge"), horizontal=True)
    input_risk = pd.DataFrame(result["landed_costs"])[["input", "delta_vs_volume_adjusted_baseline_cr"]].copy()
    input_risk = input_risk.rename(columns={"input": "Input", "delta_vs_volume_adjusted_baseline_cr": "Annual cost at risk (₹ Cr)"})
    st.markdown("#### ₹ at risk by input")
    st.bar_chart(input_risk.set_index("Input"), horizontal=True)
    pat_hit = float(assumptions["baseline_pat_cr"]) - float(m["pat_after_cr"])
    if pat_hit > 0:
        pat_buffer_days = float(assumptions["baseline_pat_cr"]) / pat_hit * 365.0
        buffer_label = f"{pat_buffer_days:,.0f} days"
    else:
        buffer_label = "No depletion at this run-rate"
    st.metric("Run-rate days to consume PAT buffer", buffer_label,
              help="Illustrative annualized scenario PAT loss divided into the baseline PAT buffer. This is a pacing indicator, not a cash forecast.")
    st.dataframe(pd.DataFrame([{
        "Revenue after demand and OEM recovery (₹ Cr)": m["revenue_after_cr"],
        "Raw material spend (₹ Cr)": m["raw_material_cost_scenario_cr"],
        "Ocean freight spend (₹ Cr)": m["ocean_freight_cost_scenario_cr"],
        "Pass-through (%)": m["oem_pass_through_pct"], "Tax assumption (%)": m["tax_rate_assumption_pct"],
        "EBITDA margin after scenario (%)": m["ebitda_margin_after_pct"],
    }]), hide_index=True, width="stretch")

# M3: landed cost, line cost by division, EBITDA/PAT calculation chain.
with tabs[2]:
    st.subheader("Live cost and earnings chain")
    st.caption("Latest source price per input is combined with the active FX, tariff and freight controls. Annual material mix allocations are editable assumptions.")
    m = result["metrics"]
    k = st.columns(4)
    k[0].metric("Landed material cost change", f"{(m['raw_material_cost_scenario_cr'] / float(assumptions['baseline_raw_material_spend_cr']) - 1.0) * 100:.1f}%")
    k[1].metric("EBITDA", _money(m["ebitda_after_cr"]), delta=_money(m["ebitda_change_vs_baseline_cr"]))
    k[2].metric("PAT", _money(m["pat_after_cr"]), delta=_money(m["pat_change_after_tax_cr"]))
    k[3].metric("EBITDA margin", f"{m['ebitda_margin_after_pct']:.2f}%")
    st.markdown("#### Landed cost per tonne")
    landed = pd.DataFrame(result["landed_costs"])
    st.dataframe(landed[["input", "source_date", "source_price", "source_unit", "price_basis_per_tonne", "base_landed_cost_inr_per_tonne", "scenario_landed_cost_inr_per_tonne", "landed_cost_change_pct"]], hide_index=True, width="stretch")
    st.markdown("#### Annual line cost by division")
    line = pd.DataFrame(result["line_costs"])
    st.dataframe(line, hide_index=True, width="stretch")
    st.caption("PAT uses a simplified marginal tax effect on the change in EBITDA. It is calibrated to the official handout baseline; it is not a full income statement forecast.")

# M4: container economics and working inventory runway.
with tabs[3]:
    st.subheader("Container and inventory model")
    c = result["container"]
    inv = pd.DataFrame(result["inventory"])
    k = st.columns(4)
    k[0].metric("Annual containers (modelled)", f"{c['scenario_annual_containers_modelled']:,.0f}")
    k[1].metric("Payload utilization", f"{c['payload_utilization_pct']:.0f}%", help=f"Assumed {c['loaded_payload_tonnes_per_container']:.1f} loaded tonnes per container.")
    k[2].metric("Ocean freight per loaded tonne", f"₹{c['freight_cost_inr_per_loaded_tonne']:,.0f}")
    k[3].metric("Annual ocean freight spend", _money(c["annual_ocean_freight_spend_cr_scenario"]))
    k2 = st.columns(2)
    k2[0].metric("Reorder alerts", str(int(inv.reorder_alert.sum())))
    k2[1].metric("Stock-out alerts", str(int(inv.stockout_alert.sum())))
    st.dataframe(inv, hide_index=True, width="stretch")
    st.caption("Inventory days, supplier lead times and container payload are assumptions because those records were not supplied.")

# M5: formula-driven candidate actions, ranked for the active scenario.
with tabs[4]:
    st.subheader("Prescriptive action matrix")
    st.caption("Actions re-rank as the scenario changes. Each is evaluated on its own; benefits are not stacked. Working-capital release is displayed separately from EBITDA-equivalent net result.")
    actions = pd.DataFrame(result["actions"])
    st.dataframe(actions[["rank", "action", "annual_cost_cr", "annual_benefit_cr", "net_result_cr", "scenario_ebitda_before_action_cr", "ebitda_after_if_action_cr", "scenario_pat_before_action_cr", "pat_after_if_action_cr", "working_capital_release_cr"]], hide_index=True, width="stretch")
    selected_action = st.selectbox("Action details", actions.action.tolist(), key="selected_action")
    row = actions[actions.action == selected_action].iloc[0]
    col1, col2, col3 = st.columns(3)
    col1.metric("Cost", _money(row.annual_cost_cr))
    col2.metric("Benefit", _money(row.annual_benefit_cr))
    col3.metric("Net result", _money(row.net_result_cr))
    before_after = pd.DataFrame({"Before": [row.scenario_ebitda_before_action_cr, row.scenario_pat_before_action_cr],
                                 "After this action": [row.ebitda_after_if_action_cr, row.pat_after_if_action_cr]}, index=["EBITDA (₹ Cr)", "PAT (₹ Cr)"])
    st.bar_chart(before_after, horizontal=True)
    st.write("**Functions affected:** " + str(row.functions_affected))
    st.write("**Suppliers affected:** " + str(row.suppliers_affected))
    st.caption(str(row.formula_note))
    st.caption("Every action value comes from the current engine inputs and assumptions register. Placeholder supplier groups and cost rates are labeled assumptions.")

with st.expander("Model reference and limits"):
    st.json(result["context"])
    st.caption("Offline mode: all forecasts and market history are read from local CSV files. The app makes no external data calls and requires no login.")

