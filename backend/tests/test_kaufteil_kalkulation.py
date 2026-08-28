"""Kaufteilkalkulation inkl. SG&A."""

from __future__ import annotations

import pytest

from app.services.central_markup_rates import CentralMarkupRates
from app.services.kaufteil_kalkulation import KaufteilKalkulationError, berechne_kaufteil_kosten


def _rates(**kw) -> CentralMarkupRates:
    defaults = dict(
        mgk_kaufteil_selbst_pct=3.0,
        mgk_kaufteil_oem_pct=5.0,
        fgk_pct=22.0,
        vvgk_pct=10.0,
        gewinn_pct=15.0,
        skonto_pct=0.0,
        handling_oem_kaufteil_pct=6.0,
    )
    defaults.update(kw)
    return CentralMarkupRates(**defaults)


def test_selbstnominiert_mgk_und_sga():
    detail = berechne_kaufteil_kosten(0.10, "selbstnominiert", _rates())
    assert float(detail.mgk_satz_pct) == pytest.approx(3)
    assert float(detail.mgk_je_stueck) == pytest.approx(0.003)
    assert float(detail.oem_handling_je_stueck) == pytest.approx(0)
    assert detail.sga_quelle == "standard"
    assert float(detail.sga_satz_pct) == pytest.approx(10)
    assert float(detail.sga_je_stueck) == pytest.approx(0.0103)
    assert float(detail.kosten_inkl_overheads_je_stueck) == pytest.approx(0.1133)


def test_oem_mgk_handling_und_sga():
    detail = berechne_kaufteil_kosten(1.0, "oem_nominiert", _rates())
    assert float(detail.mgk_je_stueck) == pytest.approx(0.05)
    assert float(detail.oem_handling_je_stueck) == pytest.approx(0.06)
    assert float(detail.sga_je_stueck) == pytest.approx(0.111)


def test_sga_manueller_override():
    detail = berechne_kaufteil_kosten(
        1.0,
        "selbstnominiert",
        _rates(),
        sga_override_aktiv=True,
        sga_satz_manuell=8.0,
    )
    assert detail.sga_quelle == "manuell"
    assert float(detail.sga_satz_pct) == pytest.approx(8)


def test_fehlende_nominierung():
    with pytest.raises(KaufteilKalkulationError, match="Nominierung"):
        berechne_kaufteil_kosten(1.0, None, _rates())


def test_oem_handling_nicht_bei_selbst():
    detail = berechne_kaufteil_kosten(1.0, "selbstnominiert", _rates())
    assert detail.oem_handling_je_stueck == 0
