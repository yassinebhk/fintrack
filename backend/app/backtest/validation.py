"""Métricas de validación robustas al sobreajuste (overfitting).

Implementa la metodología de Marcos López de Prado para corregir el sesgo
de selección bajo "multiple testing":

- Probabilistic Sharpe Ratio (PSR): probabilidad de que el Sharpe verdadero
  supere un benchmark, ajustada por skew y kurtosis de los retornos.
- Deflated Sharpe Ratio (DSR): PSR donde el benchmark deja de ser 0 y pasa a
  ser el Sharpe máximo *esperado por azar* tras probar N estrategias.
- Walk-forward purgado + embargo: evaluación out-of-sample con un hueco de
  purga y un embargo para evitar la fuga de información (leakage) entre el
  tramo de entrenamiento y el de test.

Referencias:
- Bailey & López de Prado (2014), "The Deflated Sharpe Ratio: Correcting for
  Selection Bias, Backtest Overfitting and Non-Normality".
- López de Prado (2018), "Advances in Financial Machine Learning", cap. 7
  (Cross-Validation in Finance).

Todas las funciones de probabilidad son puras y deterministas (sin LLM): toman
arrays/escalares y devuelven una probabilidad en [0, 1].
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
from loguru import logger
from scipy.stats import norm

# Frecuencia de muestreo por defecto: retornos diarios → 252 sesiones/año.
TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Momentos de la serie de retornos
# ---------------------------------------------------------------------------

def _returns_stats(returns: np.ndarray) -> tuple[int, float, float, float]:
    """Devuelve (n, sharpe_por_periodo, skew, kurtosis_no_excess).

    El Sharpe se calcula *por periodo* (sin anualizar) porque las fórmulas de
    PSR/DSR de López de Prado operan sobre el Sharpe a la misma frecuencia que
    los retornos. La kurtosis es la de Pearson (normal = 3), no la "excess".
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = r.size
    if n < 2:
        return n, 0.0, 0.0, 3.0

    mean = r.mean()
    std = r.std(ddof=1)
    if std == 0:
        return n, 0.0, 0.0, 3.0

    sharpe = mean / std
    # Skew y kurtosis poblacionales (consistentes con la derivación del paper).
    z = (r - mean) / r.std(ddof=0)
    skew = float(np.mean(z**3))
    kurt = float(np.mean(z**4))  # kurtosis de Pearson (3.0 si es normal)
    return n, float(sharpe), skew, kurt


# ---------------------------------------------------------------------------
# Probabilistic Sharpe Ratio (PSR)
# ---------------------------------------------------------------------------

def probabilistic_sharpe_ratio(
    sharpe: float,
    n: int,
    skew: float,
    kurt: float,
    benchmark_sharpe: float = 0.0,
) -> float:
    """PSR: P(Sharpe_verdadero > benchmark_sharpe).

    Fórmula (Bailey & López de Prado, 2014), con el Sharpe y el benchmark
    expresados a la misma frecuencia que los retornos:

        PSR(SR*) = Φ( (SR - SR*) * sqrt(n - 1)
                       / sqrt(1 - skew*SR + (kurt - 1)/4 * SR^2) )

    donde Φ es la CDF normal estándar, `n` el nº de observaciones, `skew` la
    asimetría y `kurt` la kurtosis de Pearson (normal = 3). El denominador es la
    desviación típica del estimador del Sharpe ajustada por no-normalidad.

    Devuelve una probabilidad en [0, 1].
    """
    if n < 2:
        return 0.0

    var_term = 1.0 - skew * sharpe + (kurt - 1.0) / 4.0 * sharpe**2
    # El radicando puede volverse no-positivo con kurtosis bajas y |SR| grande;
    # lo acotamos para mantener la estabilidad numérica.
    if var_term <= 1e-12:
        var_term = 1e-12

    numerator = (sharpe - benchmark_sharpe) * np.sqrt(n - 1)
    psr = norm.cdf(numerator / np.sqrt(var_term))
    return float(np.clip(psr, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio (DSR)
# ---------------------------------------------------------------------------

def expected_max_sharpe(trial_sharpes: list[float] | np.ndarray, n_trials: int) -> float:
    """Sharpe máximo *esperado por azar* tras `n_trials` pruebas independientes.

    Aproximación de López de Prado basada en estadística de extremos de una
    normal:

        E[max] ≈ σ_SR * ( (1 - γ) * Φ⁻¹(1 - 1/N) + γ * Φ⁻¹(1 - 1/(N·e)) )

    donde σ_SR es la desviación típica de los Sharpes probados (la varianza
    entre estrategias), N el nº de pruebas y γ ≈ 0.5772 la constante de
    Euler-Mascheroni. Cuanto más dispersos los Sharpes de los ensayos y más
    ensayos, mayor el listón que debe superar la estrategia ganadora.
    """
    if n_trials <= 1:
        return 0.0

    sr = np.asarray(trial_sharpes, dtype=float)
    sr = sr[np.isfinite(sr)]
    sigma = float(sr.std(ddof=1)) if sr.size > 1 else 0.0
    if sigma == 0:
        return 0.0

    gamma = 0.5772156649  # Euler-Mascheroni
    n = float(n_trials)
    e = np.e
    z1 = norm.ppf(1.0 - 1.0 / n)
    z2 = norm.ppf(1.0 - 1.0 / (n * e))
    return float(sigma * ((1.0 - gamma) * z1 + gamma * z2))


def deflated_sharpe_ratio(
    sharpe: float,
    n: int,
    skew: float,
    kurt: float,
    trial_sharpes: list[float] | np.ndarray,
    n_trials: int,
) -> float:
    """DSR: PSR donde el benchmark es el Sharpe máximo esperado por azar.

    DSR = PSR(SR* = E[max_SR | N trials]). Corrige el sesgo de selección: tras
    probar N estrategias y quedarnos con la mejor, parte del Sharpe observado
    se debe simplemente a la suerte. El DSR descuenta ese efecto, por lo que
    siempre DSR ≤ PSR cuando N > 1 y la dispersión de Sharpes es > 0.

    `sharpe`, `skew`, `kurt`, `n` describen la serie de la estrategia elegida;
    `trial_sharpes` son los Sharpes (a la misma frecuencia) de todas las
    estrategias probadas.
    """
    sr_benchmark = expected_max_sharpe(trial_sharpes, n_trials)
    return probabilistic_sharpe_ratio(sharpe, n, skew, kurt, benchmark_sharpe=sr_benchmark)


def sharpe_metrics(
    returns: np.ndarray | pd.Series,
    trial_sharpes_periodic: list[float] | None = None,
    n_trials: int = 1,
) -> dict[str, Any]:
    """Calcula PSR y DSR a partir de una serie de retornos por periodo.

    `trial_sharpes_periodic` son los Sharpes *por periodo* (no anualizados) de
    todas las estrategias probadas, usados para deflactar. Si no se pasan, el
    DSR usa solo el propio Sharpe (dispersión nula → DSR = PSR).
    """
    r = np.asarray(returns, dtype=float)
    n, sharpe_p, skew, kurt = _returns_stats(r)
    if n < 2:
        return {"psr": 0.0, "deflated_sharpe": 0.0, "n_trials": int(n_trials)}

    psr = probabilistic_sharpe_ratio(sharpe_p, n, skew, kurt, benchmark_sharpe=0.0)

    trials = list(trial_sharpes_periodic) if trial_sharpes_periodic else [sharpe_p]
    dsr = deflated_sharpe_ratio(sharpe_p, n, skew, kurt, trials, n_trials)

    return {
        "psr": round(float(psr), 4),
        "deflated_sharpe": round(float(dsr), 4),
        "n_trials": int(n_trials),
        "sharpe_periodic": round(float(sharpe_p), 4),
        "sharpe_annualized": round(float(sharpe_p) * np.sqrt(TRADING_DAYS), 4),
        "skew": round(skew, 4),
        "kurtosis": round(kurt, 4),
        "n_obs": int(n),
        "expected_max_sharpe": round(expected_max_sharpe(trials, n_trials), 4),
    }


# ---------------------------------------------------------------------------
# Walk-forward purgado + embargo (out-of-sample)
# ---------------------------------------------------------------------------

def purged_walk_forward(
    prices: pd.DataFrame,
    run_fold: Callable[[pd.DataFrame], pd.Series],
    n_folds: int = 5,
    purge_days: int = 5,
    embargo_pct: float = 0.01,
) -> dict[str, Any]:
    """Evaluación out-of-sample con walk-forward, purga y embargo.

    Parte el histórico en `n_folds` tramos secuenciales. Para cada fold de test
    se aplica `run_fold` (que debe ejecutar la estrategia sobre ese tramo y
    devolver la serie de equity), y se mide el retorno y el Sharpe OOS del
    tramo. Entre tramos se descarta un hueco de `purge_days` (purga) más un
    embargo de `embargo_pct` del histórico, para evitar que información del
    borde de un tramo contamine el siguiente (leakage), siguiendo López de
    Prado (AFML, cap. 7).

    Como las estrategias aquí no entrenan parámetros sobre el train, el train
    no se usa para ajustar — pero mantenemos el hueco purga+embargo como
    separación temporal limpia entre folds para que el resultado sea
    comparable a un walk-forward real y no haya solapamiento de barras.

    Devuelve {folds: [...], aggregate: {oos_sharpe, hit_rate, mean_return_pct}}.
    """
    n = len(prices)
    if n < n_folds * 10:
        logger.warning("purged_walk_forward: histórico corto ({} barras) para {} folds", n, n_folds)
        n_folds = max(2, n // 20)
    if n_folds < 2 or n < 20:
        return {"folds": [], "aggregate": {}, "note": "insufficient history for walk-forward"}

    embargo = max(int(n * embargo_pct), 0)
    fold_size = n // n_folds

    fold_results: list[dict] = []
    all_oos_returns: list[float] = []  # retornos por barra agregados OOS (para Sharpe global)
    fold_total_returns: list[float] = []

    for k in range(n_folds):
        test_start = k * fold_size
        test_end = (k + 1) * fold_size if k < n_folds - 1 else n
        # Aplicamos purga + embargo recortando el inicio del tramo de test, de
        # forma que sus primeras barras no solapen con el final del fold previo.
        gap = (purge_days + embargo) if k > 0 else 0
        eff_start = min(test_start + gap, test_end - 1)
        test_slice = prices.iloc[eff_start:test_end]
        if len(test_slice) < 3:
            continue

        try:
            equity = run_fold(test_slice)
        except Exception as exc:  # noqa: BLE001
            logger.warning("walk-forward fold {} falló: {}", k, exc)
            continue
        if equity is None or len(equity) < 2:
            continue

        equity = equity[equity > 0]
        if len(equity) < 2:
            continue

        fold_returns = equity.pct_change().dropna()
        fold_returns = fold_returns[np.isfinite(fold_returns)]
        if fold_returns.empty:
            continue

        total_ret = float(equity.iloc[-1] / equity.iloc[0] - 1.0) * 100
        std = fold_returns.std(ddof=1)
        fold_sharpe = float(fold_returns.mean() / std * np.sqrt(TRADING_DAYS)) if std > 0 else 0.0

        fold_results.append({
            "fold": k + 1,
            "test_start": test_slice.index[0].strftime("%Y-%m-%d"),
            "test_end": test_slice.index[-1].strftime("%Y-%m-%d"),
            "n_bars": int(len(test_slice)),
            "return_pct": round(total_ret, 2),
            "sharpe": round(fold_sharpe, 2),
        })
        fold_total_returns.append(total_ret)
        all_oos_returns.extend(fold_returns.tolist())

    if not fold_results:
        return {"folds": [], "aggregate": {}, "note": "no valid folds"}

    oos = np.asarray(all_oos_returns, dtype=float)
    oos_std = oos.std(ddof=1) if oos.size > 1 else 0.0
    oos_sharpe = float(oos.mean() / oos_std * np.sqrt(TRADING_DAYS)) if oos_std > 0 else 0.0
    # Hit rate: fracción de folds con retorno OOS positivo.
    hit_rate = float(np.mean([1.0 if r > 0 else 0.0 for r in fold_total_returns]))

    return {
        "folds": fold_results,
        "aggregate": {
            "n_folds": len(fold_results),
            "oos_sharpe": round(oos_sharpe, 2),
            "hit_rate": round(hit_rate, 4),
            "mean_return_pct": round(float(np.mean(fold_total_returns)), 2),
            "purge_days": int(purge_days),
            "embargo_bars": int(embargo),
        },
    }
