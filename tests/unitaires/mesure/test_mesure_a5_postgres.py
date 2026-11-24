"""Contrainte A5 sur une vraie base PostgreSQL.

Lancé seulement si LEYPILOT_TEST_POSTGRES_URL est défini, par exemple :
LEYPILOT_TEST_POSTGRES_URL=postgresql+psycopg://localhost:5432/leypilot_test pytest
La base indiquée est vidée par le test.
"""

import os

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, create_engine, insert, update
from sqlalchemy.exc import DBAPIError

import leypilot.commun.modeles  # noqa: F401
from leypilot.commun.base import Base
from leypilot.commun.modeles.mesure import Mesure
from leypilot.mesure.graduation import installer_contrainte_a5, instructions_sql
from leypilot.mesure.schemas import Dispositif, StatutMesure

URL = os.environ.get("LEYPILOT_TEST_POSTGRES_URL")


def test_le_fichier_sql_contient_trois_instructions():
    instructions = instructions_sql()
    assert len(instructions) == 3
    assert "CREATE TRIGGER a5_action_mesure_votee" in instructions[-1]


@pytest.mark.skipif(not URL, reason="LEYPILOT_TEST_POSTGRES_URL non défini")
def test_trigger_a5_sur_postgres():
    assert URL is not None
    moteur = create_engine(URL)
    # Table action minimale : la vraie table appartient à P4.
    metadata_p4 = MetaData()
    action = Table(
        "action",
        metadata_p4,
        Column("id", Integer, primary_key=True),
        Column("mesure_id", Integer, ForeignKey(Mesure.__table__.c.id)),
    )
    with moteur.begin() as connexion:
        connexion.exec_driver_sql("DROP TABLE IF EXISTS action CASCADE")
        Base.metadata.drop_all(connexion)
        Base.metadata.create_all(connexion)
        metadata_p4.create_all(connexion)
        installer_contrainte_a5(connexion)
        installer_contrainte_a5(connexion)  # réinstallable sans erreur

        def creer_mesure(statut: StatutMesure) -> int:
            return connexion.execute(
                insert(Mesure)
                .values(
                    dispositif=Dispositif.CII.value,
                    article_vise="244 quater B",
                    parametre="taux",
                    statut=statut.value,
                    numeros_amendement=[],
                    a_revoir=False,
                )
                .returning(Mesure.id)
            ).scalar_one()

        proposee = creer_mesure(StatutMesure.PROPOSEE)
        votee = creer_mesure(StatutMesure.VOTEE)
        abandonnee = creer_mesure(StatutMesure.ABANDONNEE)

    with moteur.begin() as connexion:
        connexion.execute(insert(action).values(id=1, mesure_id=votee))
        connexion.execute(insert(action).values(id=2, mesure_id=None))

    for interdite in (proposee, abandonnee):
        with pytest.raises(DBAPIError, match="A5 : action interdite"):
            with moteur.begin() as connexion:
                connexion.execute(insert(action).values(id=10 + interdite, mesure_id=interdite))

    with pytest.raises(DBAPIError, match="A5 : action interdite"):
        with moteur.begin() as connexion:
            connexion.execute(update(action).where(action.c.id == 1).values(mesure_id=proposee))

    with moteur.begin() as connexion:
        connexion.exec_driver_sql("DROP TABLE IF EXISTS action CASCADE")
        Base.metadata.drop_all(connexion)
    moteur.dispose()
