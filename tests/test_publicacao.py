import os
from datetime import timedelta

import httpx
import pytest

from painel.publicacao import baixar_banco, banco_desatualizado

URL = "https://raw.githubusercontent.com/dono/repo/dados/painel.duckdb"


def transporte(conteudo=b"banco", status=200, chamadas=None):
    def tratador(requisicao):
        if chamadas is not None:
            chamadas.append(requisicao)
        return httpx.Response(status, content=conteudo)

    return httpx.MockTransport(tratador)


def test_baixa_quando_nao_existe_copia_local(tmp_path):
    destino = tmp_path / "data" / "painel.duckdb"

    baixou = baixar_banco(URL, destino, transporte=transporte(b"conteudo"))

    assert baixou
    assert destino.read_bytes() == b"conteudo"
    assert not destino.with_suffix(".duckdb.baixando").exists()


def test_copia_recente_nao_e_baixada_de_novo(tmp_path):
    destino = tmp_path / "painel.duckdb"
    destino.write_bytes(b"antigo")
    chamadas = []

    baixou = baixar_banco(
        URL, destino, timedelta(hours=1), transporte=transporte(chamadas=chamadas)
    )

    assert not baixou
    assert chamadas == []
    assert destino.read_bytes() == b"antigo"


def test_copia_velha_e_substituida(tmp_path):
    destino = tmp_path / "painel.duckdb"
    destino.write_bytes(b"antigo")
    duas_horas_atras = destino.stat().st_mtime - 2 * 3600
    os.utime(destino, (duas_horas_atras, duas_horas_atras))

    baixou = baixar_banco(URL, destino, timedelta(hours=1), transporte=transporte(b"novo"))

    assert baixou
    assert destino.read_bytes() == b"novo"


def test_falha_no_download_mantem_a_copia_existente(tmp_path):
    destino = tmp_path / "painel.duckdb"
    destino.write_bytes(b"antigo")

    baixou = baixar_banco(
        URL,
        destino,
        timedelta(0),
        transporte=transporte(status=503),
        agora=lambda: destino.stat().st_mtime + 10,
    )

    assert not baixou
    assert destino.read_bytes() == b"antigo"
    assert not destino.with_suffix(".duckdb.baixando").exists()


def test_falha_sem_copia_local_propaga_o_erro(tmp_path):
    destino = tmp_path / "painel.duckdb"

    with pytest.raises(httpx.HTTPStatusError):
        baixar_banco(URL, destino, transporte=transporte(status=404))
    assert not destino.exists()


def test_banco_desatualizado(tmp_path):
    caminho = tmp_path / "painel.duckdb"
    assert banco_desatualizado(caminho, timedelta(hours=1))

    caminho.write_bytes(b"x")
    criado = caminho.stat().st_mtime
    assert not banco_desatualizado(caminho, timedelta(hours=1), agora=lambda: criado + 60)
    assert banco_desatualizado(caminho, timedelta(hours=1), agora=lambda: criado + 3601)
