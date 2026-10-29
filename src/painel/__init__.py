"""Painel de Métricas de Entrega.

Coleta dados do GitHub e calcula indicadores de fluxo e DORA.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("painel-metricas-entrega")
except PackageNotFoundError:  # pacote não instalado (ex.: execução direta do código-fonte)
    __version__ = "0.0.0"
