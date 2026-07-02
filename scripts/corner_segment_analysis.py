"""
Standalone corner-segment analysis using FastF1.

Given a session, a driver, and a corner number, this automatically finds the
corner's data segment (start -> apex -> end) by:

  1. Using FastF1's official circuit info to get the corner's approximate
     apex distance (a starting hint, not the final answer).
  2. Searching a window of telemetry around that distance for the actual
     local speed minimum (the true apex point, which can be offset from the
     official marker by tens of metres).
  3. Walking outward from the apex in both directions until speed stops
     falling (going backward) / stops rising (going forward) -- i.e. the
     nearest local speed maxima flanking the dip. Those maxima are the
     corner's entry and exit boundaries.

From that detected segment it computes entry speed, minimum (apex) speed,
exit speed, and time spent in the corner.

Usage:
    python -m scripts.corner_segment_analysis
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.f1_data import enable_cache, load_session


@dataclass(frozen=True)
class CornerSegment:
    driver: str
    corner_number: int
    entry_distance_m: float
    apex_distance_m: float
    exit_distance_m: float
    entry_speed_kmh: float
    apex_speed_kmh: float
    exit_speed_kmh: float
    corner_time_s: float
    entry_index: int
    apex_index: int
    exit_index: int


def _smooth(series: pd.Series, window: int = 5) -> np.ndarray:
    """Light rolling-mean smoothing so telemetry noise doesn't create false
    local maxima/minima when walking the speed trace."""
    return series.rolling(window=window, center=True, min_periods=1).mean().to_numpy()


def find_corner_segment(
    distance: np.ndarray,
    speed_kmh: np.ndarray,
    apex_hint_distance_m: float,
    search_radius_m: float = 150.0,
    smoothing_window: int = 5,
) -> tuple[int, int, int]:
    """
    Detect a corner's (entry_index, apex_index, exit_index) purely from the
    speed/distance trace, using apex_hint_distance_m only to narrow the
    search window (it does not have to be exact).

    Returns indices into the original (unsmoothed) arrays.
    """
    if len(distance) != len(speed_kmh):
        raise ValueError("distance and speed_kmh must be the same length")

    smoothed = _smooth(pd.Series(speed_kmh), window=smoothing_window)

    lo = apex_hint_distance_m - search_radius_m
    hi = apex_hint_distance_m + search_radius_m
    window_idxs = np.where((distance >= lo) & (distance <= hi))[0]
    if len(window_idxs) == 0:
        raise ValueError(
            f"No telemetry samples within {search_radius_m}m of distance={apex_hint_distance_m}m"
        )

    apex_idx = window_idxs[int(np.argmin(smoothed[window_idxs]))]

    # Walk backward from the apex to the nearest local speed maximum (entry).
    entry_idx = apex_idx
    while entry_idx > 0 and smoothed[entry_idx - 1] >= smoothed[entry_idx]:
        entry_idx -= 1

    # Walk forward from the apex to the nearest local speed maximum (exit).
    exit_idx = apex_idx
    n = len(smoothed)
    while exit_idx < n - 1 and smoothed[exit_idx + 1] >= smoothed[exit_idx]:
        exit_idx += 1

    return entry_idx, apex_idx, exit_idx


def analyse_driver_corner(session, driver_code: str, corner_number: int, search_radius_m: float = 150.0) -> CornerSegment:
    corners = session.get_circuit_info().corners
    corner_row = corners[corners["Number"] == corner_number]
    if corner_row.empty:
        raise ValueError(f"Corner {corner_number} not found in circuit info")
    apex_hint_distance_m = float(corner_row.iloc[0]["Distance"])

    lap = session.laps.pick_drivers(driver_code).pick_fastest()
    telemetry = lap.get_telemetry()

    distance = telemetry["Distance"].to_numpy()
    speed_kmh = telemetry["Speed"].to_numpy()
    time = telemetry["Time"]  # Timedelta series, relative to lap start

    entry_idx, apex_idx, exit_idx = find_corner_segment(
        distance, speed_kmh, apex_hint_distance_m, search_radius_m=search_radius_m
    )

    corner_time_s = (time.iloc[exit_idx] - time.iloc[entry_idx]).total_seconds()

    return CornerSegment(
        driver=driver_code,
        corner_number=corner_number,
        entry_distance_m=float(distance[entry_idx]),
        apex_distance_m=float(distance[apex_idx]),
        exit_distance_m=float(distance[exit_idx]),
        entry_speed_kmh=float(speed_kmh[entry_idx]),
        apex_speed_kmh=float(speed_kmh[apex_idx]),
        exit_speed_kmh=float(speed_kmh[exit_idx]),
        corner_time_s=corner_time_s,
        entry_index=int(entry_idx),
        apex_index=int(apex_idx),
        exit_index=int(exit_idx),
    )


def main():
    enable_cache()

    session = load_session(2025, "Monaco", session_type="R")

    corner_number = 6  # Grand Hotel / Fairmont Hairpin
    drivers = ["LEC", "NOR"]

    print(f"{session.event['EventName']} {session.event.get('EventDate')} - Turn {corner_number} (Hairpin)\n")

    for code in drivers:
        segment = analyse_driver_corner(session, code, corner_number)
        print(f"== {code} ==")
        print(f"  Segment (distance): {segment.entry_distance_m:.0f}m -> {segment.apex_distance_m:.0f}m -> {segment.exit_distance_m:.0f}m")
        print(f"  Segment (index):    {segment.entry_index} -> {segment.apex_index} -> {segment.exit_index}")
        print(f"  Entry speed:   {segment.entry_speed_kmh:.1f} km/h")
        print(f"  Apex speed:    {segment.apex_speed_kmh:.1f} km/h")
        print(f"  Exit speed:    {segment.exit_speed_kmh:.1f} km/h")
        print(f"  Corner time:   {segment.corner_time_s:.2f} s")
        print()


if __name__ == "__main__":
    main()
