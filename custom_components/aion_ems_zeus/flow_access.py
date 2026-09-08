"""Canonical read helpers for the Energy Flow snapshot.

``EnergyFlowEngine.refresh()`` publishes exactly one live power calculation per
cycle. Every power value lives under ``summary()["flows"][<field>]`` as a
``{"w": ..., "kw": ...}`` payload, and ``battery_soc_percent`` is a bare number
in the same section.

Reading ``summary()[<field>]`` (top level) or ``summary()["flows"][<field>_w]``
(flat suffix) returns ``None`` for every field. Several engines did exactly that
and then coerced the result to ``0.0``, so their pages rendered a confident
"0 W" instead of the measured value. These helpers are the only supported way
to read the snapshot: they accept either the full summary or the ``flows``
section, tolerate the legacy key spellings, and return ``None`` -- never a
fabricated zero -- when a value is genuinely unavailable.
"""

from __future__ import annotations

from typing import Any

# Canonical field -> legacy spellings that older callers used. The canonical
# name is always tried first so a correct snapshot never depends on an alias.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "solar_power": ("solar_power_w", "solar_w", "pv_power_w"),
    "wind_power": ("wind_power_w",),
    "generator_power": ("generator_power_w",),
    "house_power": ("house_power_w", "home_power_w", "home_w", "load_power_w"),
    "grid_import_power": ("grid_import_power_w", "grid_import_w", "import_power_w"),
    "grid_export_power": ("grid_export_power_w", "grid_export_w", "export_power_w"),
    "grid_power": ("grid_power_w",),
    "net_grid_power": ("net_grid_power_w",),
    "battery_power": ("battery_power_w",),
    "net_battery_power": ("net_battery_power_w",),
    "battery_charge_power": ("battery_charge_power_w",),
    "battery_discharge_power": ("battery_discharge_power_w",),
    "ev_power": ("ev_power_w",),
    "heat_pump_power": ("heat_pump_power_w",),
    "water_heater_power": ("water_heater_power_w",),
}


def flow_section(summary: Any) -> dict[str, Any]:
    """Return the ``flows`` section from a full snapshot or a flows dict."""
    if not isinstance(summary, dict):
        return {}
    flows = summary.get("flows")
    if isinstance(flows, dict):
        return flows
    # Already the flows section (or an unrelated dict, which simply yields None
    # for every canonical field below).
    return summary


def _coerce(value: Any) -> float | None:
    if isinstance(value, dict):
        if value.get("w") is not None:
            return _coerce(value.get("w"))
        if value.get("kw") is not None:
            kw = _coerce(value.get("kw"))
            return kw * 1000.0 if kw is not None else None
        return _coerce(value.get("value"))
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # reject NaN


def flow_w(summary: Any, field: str, default: float | None = None) -> float | None:
    """Return one canonical power value in W, or ``default`` when unavailable.

    ``default`` stays ``None`` on purpose: an unmapped or unavailable source is
    not 0 W, and publishing it as 0 W is what made several pages disagree with
    the Energy Flow snapshot.
    """
    flows = flow_section(summary)
    if not flows:
        return default
    for key in (field, *FIELD_ALIASES.get(field, ())):
        value = _coerce(flows.get(key))
        if value is not None:
            return value
    return default


def flow_soc(summary: Any, default: float | None = None) -> float | None:
    """Return battery state of charge in percent, or ``default``."""
    flows = flow_section(summary)
    value = _coerce(flows.get("battery_soc_percent"))
    if value is None:
        value = _coerce(flows.get("battery_soc"))
    return value if value is not None else default


def flow_values(summary: Any, default: float | None = None) -> dict[str, float | None]:
    """Return the canonical live power context every consumer should share.

    Keys use the flat ``*_w`` naming that engine payloads and the frontend
    already expect, so callers publish one vocabulary for live power.
    """
    flows = flow_section(summary)
    return {
        "solar_w": flow_w(flows, "solar_power", default),
        "home_w": flow_w(flows, "house_power", default),
        "grid_import_w": flow_w(flows, "grid_import_power", default),
        "grid_export_w": flow_w(flows, "grid_export_power", default),
        "net_grid_w": flow_w(flows, "net_grid_power", default),
        "battery_charge_w": flow_w(flows, "battery_charge_power", default),
        "battery_discharge_w": flow_w(flows, "battery_discharge_power", default),
        "net_battery_w": flow_w(flows, "net_battery_power", default),
        "battery_soc_percent": flow_soc(flows, default),
    }


__all__ = [
    "FIELD_ALIASES",
    "flow_section",
    "flow_soc",
    "flow_values",
    "flow_w",
]
