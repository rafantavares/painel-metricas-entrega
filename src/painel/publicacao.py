"""Download do banco publicado pelo workflow de coleta (ver ADR 0006).

O workflow `coleta.yml` grava o `painel.duckdb` na branch `dados`. O dashboard publicado
não roda o coletor: baixa esse arquivo pela URL em `PAINEL_BANCO_URL` e só busca de novo
quando a cópia local fica mais velha que `max_idade`.
"""

import os
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import httpx

IDADE_MAXIMA_PADRAO = timedelta(hours=1)


def banco_desatualizado(
    caminho: Path, max_idade: timedelta, agora: Callable[[], float] = time.time
) -> bool:
    """Indica se o arquivo não existe ou foi baixado há mais tempo que `max_idade`."""
    if not caminho.exists():
        return True
    return agora() - caminho.stat().st_mtime > max_idade.total_seconds()


def baixar_banco(
    url: str,
    destino: Path,
    max_idade: timedelta = IDADE_MAXIMA_PADRAO,
    *,
    transporte: httpx.BaseTransport | None = None,
    agora: Callable[[], float] = time.time,
) -> bool:
    """Baixa o banco publicado se a cópia local estiver ausente ou desatualizada.

    A escrita é atômica (arquivo temporário + `replace`), para que uma sessão do
    dashboard nunca leia um arquivo pela metade. Retorna `True` se baixou.
    Se o download falhar e já existir uma cópia local, ela continua sendo usada.
    """
    if not banco_desatualizado(destino, max_idade, agora):
        return False

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(destino.suffix + ".baixando")
    try:
        with (
            httpx.Client(transport=transporte, timeout=60, follow_redirects=True) as cliente,
            cliente.stream("GET", url) as resposta,
        ):
            resposta.raise_for_status()
            with temporario.open("wb") as arquivo:
                for parte in resposta.iter_bytes():
                    arquivo.write(parte)
    except httpx.HTTPError:
        temporario.unlink(missing_ok=True)
        if destino.exists():
            return False
        raise
    os.replace(temporario, destino)
    return True
