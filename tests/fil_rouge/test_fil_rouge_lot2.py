"""Fil rouge client B, lot 2 : du dépôt de l'amendement à l'application de la mesure.

CII de 30 % à 20 %, 400 000 € de dépenses, échéance dans six semaines.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

from leypilot.commun.modeles.mesure import Mesure
from leypilot.mesure.graduation import Niveau
from leypilot.mesure.requetes import VueMesure, mesures_publiees_depuis, vue_mesure
from leypilot.mesure.schemas import Changement, NatureDate, StatutMesure
from leypilot.mesure.suivi import SuiviMesures

DONNEES = json.loads(
    (Path(__file__).parents[2] / "donnees_exemple" / "lot2_client_b.json").read_text("utf-8")
)
AUJOURD_HUI = date.fromisoformat(DONNEES["aujourd_hui"])
S = StatutMesure


def vue(session, mesure_id: int | None, aujourd_hui: date | None = None) -> VueMesure:
    """Vue d'une mesure qui doit exister (échoue clairement sinon)."""
    assert mesure_id is not None
    trouvee = vue_mesure(session, mesure_id, aujourd_hui)
    assert trouvee is not None
    return trouvee


def test_fil_rouge_client_b(session):
    depot, adoption, publication = (Changement.model_validate(c) for c in DONNEES["changements"])
    suivi = SuiviMesures(session)

    # 1. L'amendement est déposé : une mesure naît, au niveau « information ».
    resultat = suivi.traiter(depot)
    mesure_id = resultat.mesure_id
    etat = vue(session, mesure_id, AUJOURD_HUI)
    assert resultat.nouvelle_mesure
    assert (etat.statut, etat.niveau) == (S.PROPOSEE, Niveau.INFORMATION)
    assert (etat.date_entree_vigueur, etat.nature_date) == (date(2026, 1, 1), NatureDate.CERTAINE)
    assert etat.jours_restants == 42  # six semaines
    assert etat.resume == (
        "CII : « taux du crédit d'impôt innovation » passe de 30 % à 20 % "
        "(article 244 quater B du code général des impôts). "
        "Étape : mesure proposée (amendement ou projet de texte déposé). "
        "Applicable à compter du 1er janvier 2026."
    )
    assert not etat.a_verifier
    # L'exposé sommaire cite 400 000 € ; le résumé n'invente aucun montant.
    assert etat.resume is not None
    assert "€" not in etat.resume

    # 2. Le texte est adopté sous un autre numéro d'article : même mesure, qui devient actionnable.
    resultat = suivi.traiter(adoption)
    assert (resultat.mesure_id, resultat.nouvelle_mesure) == (mesure_id, False)
    assert vue(session, mesure_id, AUJOURD_HUI).niveau == Niveau.ACTION

    # 3. La loi est publiée au JO : la personne 3 est prévenue (déclencheur de M3).
    resultat = suivi.traiter(publication)
    assert resultat.mesure_id == mesure_id
    publiees = mesures_publiees_depuis(session, datetime(2000, 1, 1, tzinfo=UTC))
    assert [m.id for m in publiees] == [mesure_id]

    # 4. Le 1er janvier 2026, la mesure s'applique.
    assert suivi.appliquer_entrees_en_vigueur(date(2026, 1, 1)) == [mesure_id]

    mesure = session.get(Mesure, mesure_id)
    assert session.query(Mesure).count() == 1
    assert [t.vers_statut for t in mesure.transitions] == [
        S.PROPOSEE,
        S.VOTEE,
        S.PUBLIEE,
        S.APPLIQUEE,
    ]
    assert mesure.numeros_amendement == ["I-1234"]
    assert mesure.nor == "ECOX0000000L"
    assert len(mesure.resumes) == 3
