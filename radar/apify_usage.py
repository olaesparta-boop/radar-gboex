"""
Mede o que a coleta paga (redes sociais e Reclame Aqui) consome.

Duas camadas, de propósito:

* `snapshot()` fala com a API do provedor e enxerga o consumo da CONTA — é
  interno, serve só para calcular quanto ESTA rodada custou (diferença
  antes/depois). Nada disso vai para o painel.
* `painel()` monta o que o `data.json` publica: apenas a verba reservada ao
  radar (`config.RADAR_BUDGET_USD`), quanto dela já foi usada no ciclo e
  quando o ciclo vira. O saldo e o plano da conta ficam de fora — o painel
  é público.

Sem `APIFY_TOKEN` não há medição e o medidor não aparece.
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


def custo_da_rodada(antes: dict | None, depois: dict | None) -> float:
    """
    Quanto esta coleta consumiu (diferença entre as duas fotos). A
    contabilização do provedor tem alguma latência, então delta <= 0 vira 0.0
    ("não dá para afirmar") em vez de número negativo.
    """
    if not antes or not depois:
        return 0.0
    return max(0.0, round(depois["usado_usd"] - antes["usado_usd"], 2))


def painel(gasto_ciclo_usd: float, ciclo_fim: str | None,
           custo_coleta_usd: float = 0.0, freado: bool = False) -> dict:
    """Bloco público do data.json: só a verba do radar, nunca o saldo da conta."""
    orcamento = float(config.RADAR_BUDGET_USD)
    gasto = round(min(max(gasto_ciclo_usd, 0.0), orcamento * 99), 2)
    restante = round(max(orcamento - gasto, 0.0), 2)

    bloco = {
        "orcamento_usd": round(orcamento, 2),
        "gasto_usd": gasto,
        "restante_usd": restante,
        "ciclo_fim": ciclo_fim,
        "freado": bool(freado),
    }
    if custo_coleta_usd > 0:
        bloco["custo_coleta_usd"] = round(custo_coleta_usd, 2)
        bloco["coletas_restantes"] = int(restante // custo_coleta_usd)
    return bloco
