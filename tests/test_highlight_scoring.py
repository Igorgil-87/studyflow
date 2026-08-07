"""tests/test_highlight_scoring.py — testa a fórmula de score
determinística e a regra de eliminação do highlight_extractor.py
(framework de 13 dimensões, calculado em código, não pela IA)."""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import tools.highlight_extractor as _mod  # noqa: E402
Highlight = _mod.Highlight
calcular_viral_score = _mod.calcular_viral_score
deve_eliminar = _mod.deve_eliminar
_PESOS_SCORE = _mod._PESOS_SCORE


def test_pesos_somam_um():
    assert abs(sum(_PESOS_SCORE.values()) - 1.0) < 0.001


def test_nota_maxima_em_tudo_da_100():
    h = Highlight(inicio=0, fim=30, s_hook=10, s_retencao=10, s_curiosidade=10,
                   s_emocao=10, s_tema=10, s_share=10, s_controversia=10,
                   s_novidade=10, s_autoridade=10, s_densidade=10, s_ritmo=10)
    assert calcular_viral_score(h) == 100


def test_nota_zero_em_tudo_da_0():
    h = Highlight(inicio=0, fim=30)
    assert calcular_viral_score(h) == 0


def test_formula_bate_com_calculo_manual():
    h = Highlight(inicio=0, fim=30, s_hook=9, s_retencao=8, s_curiosidade=7,
                   s_emocao=6, s_tema=8, s_share=6, s_controversia=3,
                   s_novidade=7, s_autoridade=8, s_densidade=6, s_ritmo=5)
    esperado = round((9*0.18 + 8*0.18 + 7*0.12 + 6*0.08 + 8*0.10 + 6*0.08 +
                       3*0.05 + 7*0.06 + 8*0.05 + 6*0.05 + 5*0.05) * 10)
    assert calcular_viral_score(h) == esperado


def test_elimina_hook_fraco_mesmo_se_ia_marcou_elegivel():
    """A checagem em código não pode confiar cegamente na IA."""
    h = Highlight(inicio=0, fim=30, s_hook=3, s_retencao=9, elegivel=True)
    assert deve_eliminar(h) is True


def test_elimina_retencao_fraca_mesmo_se_ia_marcou_elegivel():
    h = Highlight(inicio=0, fim=30, s_hook=9, s_retencao=3, elegivel=True)
    assert deve_eliminar(h) is True


def test_clip_bom_nao_e_eliminado():
    h = Highlight(inicio=0, fim=30, s_hook=8, s_retencao=8, elegivel=True)
    assert deve_eliminar(h) is False


def test_ia_pode_eliminar_mesmo_com_scores_bons():
    """Se a IA marcar elegivel=False (por outro motivo, tipo corte no
    meio de frase), respeita — mesmo com hook/retenção altos."""
    h = Highlight(inicio=0, fim=30, s_hook=9, s_retencao=9, elegivel=False)
    assert deve_eliminar(h) is True
