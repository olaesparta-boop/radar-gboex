"""
Consulta quanto do crédito Apify já foi consumido no ciclo de cobrança.

O painel mostra isso como medidor: a coleta de redes/Reclame Aqui é o único
item pago do radar, e o teto é mensal. Sem `APIFY_TOKEN` devolve None e o
medidor simplesmente não aparece.
"""
from __future__ import annotations

import requests

import config

API_LIMITS = "https://api.apify.com/v2/users/me/limits"


def snapshot() -> dict | None:
    """Foto do consumo atual. None se não houver token ou a API falhar."""
    if not config.APIFY_TOKEN:
        return None
    try:
        resp = requests.get(
            API_LIMITS,
            headers={"Authorization": f"Bearer {config.APIFY_TOKEN}"},
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        dados = resp.json().get("data") or {}
        usado = float(dados["current"]["monthlyUsageUsd"])
        teto = float(dados["limits"]["maxMonthlyUsageUsd"])
        ciclo = dados.get("monthlyUsageCycle") or {}
    except Exception:
        return None

    return {
        "usado_usd": round(usado, 2),
        "teto_usd": round(teto, 2),
        "restante_usd": round(max(teto - usado, 0.0), 2),
        "ciclo_inicio": ciclo.get("startAt"),
        "ciclo_fim": ciclo.get("endAt"),
    }


def com_custo_da_coleta(antes: dict | None, depois: dict | None) -> dict | None:
    """
    Junta as duas fotos (antes/depois da coleta) e acrescenta quanto a rodada
    custou. A contabilização do Apify tem alguma latência, então um delta <= 0
    é tratado como "não dá para afirmar" e fica de fora.
    """
    if not depois:
        return None
    resultado = dict(depois)
    if antes:
        custo = round(depois["usado_usd"] - antes["usado_usd"], 2)
        if custo > 0:
            resultado["custo_coleta_usd"] = custo
            if custo:
                resultado["coletas_restantes"] = int(depois["restante_usd"] // custo)
    return resultado
