import painel


def test_pacote_expoe_versao():
    assert isinstance(painel.__version__, str)
    assert painel.__version__
