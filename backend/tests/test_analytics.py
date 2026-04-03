import numpy as np
import pytest

from app.services import analytics


def test_ols_beta_perfect_line() -> None:
    x = np.linspace(-1, 1, 50)
    y = 1.5 * x + 3.0
    b = analytics.ols_beta_y_on_x(y, x)
    assert b == pytest.approx(1.5)


def test_historical_var_es_tail() -> None:
    rng = np.random.default_rng(0)
    r = rng.normal(0.001, 0.01, size=500)
    r[:25] -= 0.08
    var_l, es_l = analytics.historical_var_es(r, 0.05)
    assert var_l > 0
    assert es_l >= var_l - 1e-9
