"""Tests für Baugruppen-Variantenmix (Anteile, Mengen, Gewichtung)."""

from __future__ import annotations

import pytest

from app.services.assembly_variant_mix import (
    MIX_COMPLETE,
    MIX_INCOMPLETE,
    MIX_OVERFLOW,
    effective_component_jahresmenge,
    lose_from_jahresmenge,
    validate_active_share_sum,
    validate_share_pct,
    variant_jahresmenge,
)


def test_share_pct_bounds():
    assert validate_share_pct(0) == 0.0
    assert validate_share_pct(100) == 100.0
    assert validate_share_pct(20) == 20.0
    with pytest.raises(ValueError, match="unter 0"):
        validate_share_pct(-0.01)
    with pytest.raises(ValueError, match="über 100"):
        validate_share_pct(100.01)
    with pytest.raises(ValueError):
        validate_share_pct(None)


def test_active_share_sum_complete_incomplete_overflow():
    ok = validate_active_share_sum([20, 10, 2, 68])
    assert ok.status == MIX_COMPLETE
    assert ok.is_complete is True
    assert ok.can_compute_full is True

    incomplete = validate_active_share_sum([20, 10, 2])
    assert incomplete.status == MIX_INCOMPLETE
    assert incomplete.missing_pct == pytest.approx(68.0)
    assert "100 %" in incomplete.message
    assert "fehlen" in incomplete.message.lower() or "fehlen" in incomplete.message

    overflow = validate_active_share_sum([60, 50])
    assert overflow.status == MIX_OVERFLOW
    assert overflow.overflow_pct == pytest.approx(10.0)
    assert "überschreiten" in overflow.message


def test_inactive_shares_not_in_caller_list():
    # Inaktive Varianten werden vom Aufrufer ausgeschlossen
    only_active = validate_active_share_sum([100])
    assert only_active.is_complete is True


def test_variant_jahresmenge_example():
    assert variant_jahresmenge(100_000, 20) == 20_000
    assert variant_jahresmenge(100_000, 2) == 2_000
    assert variant_jahresmenge(100_000, 0) == 0


def test_effective_component_quantity_pdc_example():
    # 100k × 20% = 20k Variantenstücke × 4 Halter = 80k
    v001 = variant_jahresmenge(100_000, 20)
    v003 = variant_jahresmenge(100_000, 2)
    q001 = effective_component_jahresmenge(v001, 4)
    q003 = effective_component_jahresmenge(v003, 4)
    assert q001 == pytest.approx(80_000.0)
    assert q003 == pytest.approx(8_000.0)
    assert q001 + q003 == pytest.approx(88_000.0)


def test_component_shares_not_forced_to_100():
    # Mehrere Komponenten in einer Variante – keine Summenprüfung untereinander
    v_qty = variant_jahresmenge(100_000, 20)
    grund = effective_component_jahresmenge(v_qty, 1)
    halter = effective_component_jahresmenge(v_qty, 4)
    radar = effective_component_jahresmenge(v_qty, 1)
    assert grund == pytest.approx(20_000.0)
    assert halter == pytest.approx(80_000.0)
    assert radar == pytest.approx(20_000.0)


def test_weighted_cost_not_unweighted_average():
    # Variante A 80% à 10 €, Variante B 20% à 30 € → gewichtet 14 €, nicht 20 €
    weighted = 10.0 * 0.8 + 30.0 * 0.2
    unweighted = (10.0 + 30.0) / 2.0
    assert weighted == pytest.approx(14.0)
    assert unweighted == pytest.approx(20.0)
    assert weighted != pytest.approx(unweighted)


def test_lose_from_existing_lot_size_only():
    assert lose_from_jahresmenge(88_000, 10_000) == 9
    assert lose_from_jahresmenge(88_000, None) is None
    assert lose_from_jahresmenge(88_000, 0) is None
    assert lose_from_jahresmenge(0, 10_000) == 0


def test_share_sum_tolerance():
    almost = validate_active_share_sum([33.33, 33.33, 33.34])
    assert almost.status == MIX_COMPLETE


def test_empty_mix_status():
    empty = validate_active_share_sum([])
    assert empty.status == "empty"
    assert empty.can_compute_full is False
    assert empty.missing_pct == pytest.approx(100.0)


def test_kaufteil_effective_qty_formula():
    # Projektstück × Anteil/100 × Menge je Variante
    project_qty = 100_000
    share = 20.0
    menge = 2.0
    v_qty = variant_jahresmenge(project_qty, share)
    assert effective_component_jahresmenge(v_qty, menge) == pytest.approx(40_000.0)


def test_variant_share_same_across_years_concept():
    # Anteile sind jahresunabhängig: gleiche Formel für jedes Jahr
    share = 20.0
    for year_qty in (80_000, 100_000, 120_000):
        assert variant_jahresmenge(year_qty, share) == int(round(year_qty * share / 100.0))


def test_no_silent_default_share():
    # Fehlende Anteile werden nicht stillschweigend erfunden (0 ist explizit, None ungültig)
    assert validate_share_pct(0) == 0.0
    with pytest.raises(ValueError):
        validate_share_pct(None)


def test_weighted_family_cost_formula():
    shares = [20.0, 10.0, 70.0]
    costs = [5.0, 8.0, 4.0]
    weighted = sum(c * (s / 100.0) for c, s in zip(costs, shares, strict=True))
    assert weighted == pytest.approx(4.6)
    assert validate_active_share_sum(shares).can_compute_full is True
