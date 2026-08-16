from datetime import date

from app.geo import sample_dates_for_reference_month


def test_deriva_datas_com_ano_explicito_no_texto():
    check_in, check_out = sample_dates_for_reference_month("janeiro de 2027", 7, today=date(2026, 8, 16))
    assert check_in == date(2027, 1, 1)
    assert check_out == date(2027, 1, 8)


def test_deriva_datas_infere_proximo_ano_quando_mes_ja_passou():
    check_in, _ = sample_dates_for_reference_month("janeiro", 5, today=date(2026, 8, 16))
    assert check_in.year == 2027


def test_deriva_datas_usa_ano_corrente_quando_mes_ainda_nao_passou():
    check_in, _ = sample_dates_for_reference_month("outubro", 5, today=date(2026, 8, 16))
    assert check_in.year == 2026


def test_deriva_datas_retorna_none_sem_duracao():
    assert sample_dates_for_reference_month("janeiro de 2027", None) is None


def test_deriva_datas_retorna_none_sem_mes():
    assert sample_dates_for_reference_month(None, 7) is None


def test_deriva_datas_retorna_none_para_mes_nao_reconhecido():
    assert sample_dates_for_reference_month("algum dia", 7) is None
