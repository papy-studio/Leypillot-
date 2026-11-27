"""Tables du lot 1 (propriétaire : P1) : execution_collecte, document, cible, changement.
Les autres lots les lisent sans les modifier.

Le lot 2 relie ses mesures aux changements dans sa propre table ``version_mesure`` :
la table ``changement`` n'a donc pas de colonne ``mesure_id`` (une table, un propriétaire).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum as EnumPython

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leypilot.collecte.schemas import Methode, Statut
from leypilot.collecte.sources.base import Source, TypeTexte
from leypilot.commun.base import Base, maintenant


def _enum(type_enum: type[EnumPython], nom: str) -> Enum:
    """Énumération stockée en texte, contrôlée par une contrainte CHECK."""
    return Enum(
        type_enum,
        name=nom,
        native_enum=False,
        length=32,
        values_callable=lambda membres: [m.value for m in membres],
        validate_strings=True,
    )


class ExecutionCollecte(Base):
    """Un passage d'un connecteur sur un fichier : sert au contrôle de complétude (A1)
    et aux alertes techniques."""

    __tablename__ = "execution_collecte"
    __table_args__ = (
        CheckConstraint(
            "statut IN ('en_cours', 'ok', 'ecart', 'echec')", name="ck_execution_statut"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[Source] = mapped_column(_enum(Source, "source_collecte"), index=True)
    fichier: Mapped[str | None] = mapped_column(String(300))
    debut: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    statut: Mapped[str] = mapped_column(String(10), default="en_cours")
    nb_lus: Mapped[int | None] = mapped_column(Integer)
    nb_attendus: Mapped[int | None] = mapped_column(Integer)
    nb_recus: Mapped[int | None] = mapped_column(Integer)
    nb_retenus: Mapped[int | None] = mapped_column(Integer)
    ecarts: Mapped[list[str]] = mapped_column(JSON, default=list)
    message: Mapped[str | None] = mapped_column(Text)


class Document(Base):
    """Un texte retenu par le filtre large. Une nouvelle ligne à chaque nouvelle version
    (texte ou état changé) ; un texte identique n'est jamais enregistré deux fois."""

    __tablename__ = "document"
    __table_args__ = (
        UniqueConstraint("source", "identifiant", "version", name="uq_document_version"),
        UniqueConstraint(
            "source", "identifiant", "empreinte_texte", "empreinte_etat", name="uq_document_contenu"
        ),
        CheckConstraint(
            "evenement IN ('nouveau', 'texte_modifie', 'changement_etat')",
            name="ck_document_evenement",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[Source] = mapped_column(_enum(Source, "source_collecte"), index=True)
    identifiant: Mapped[str] = mapped_column(String(200), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    version_precedente_id: Mapped[int | None] = mapped_column(ForeignKey("document.id"))
    evenement: Mapped[str] = mapped_column(String(20))
    empreinte_texte: Mapped[str] = mapped_column(String(64), index=True)
    empreinte_etat: Mapped[str] = mapped_column(String(64))
    nature: Mapped[str] = mapped_column(String(50))
    type_texte: Mapped[TypeTexte] = mapped_column(_enum(TypeTexte, "type_texte"))
    titre: Mapped[str | None] = mapped_column(Text)
    date_document: Mapped[date | None] = mapped_column(Date, index=True)
    url_officielle: Mapped[str] = mapped_column(String(500))
    nor: Mapped[str | None] = mapped_column(String(50))
    eli: Mapped[str | None] = mapped_column(String(300))
    dossier_legislatif: Mapped[str | None] = mapped_column(String(200))
    numero_amendement: Mapped[str | None] = mapped_column(String(50))
    etape: Mapped[str | None] = mapped_column(String(32))
    etat: Mapped[dict] = mapped_column(JSON, default=dict)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    texte: Mapped[str] = mapped_column(Text)  # normalisé : base de la vérification mot pour mot
    chemin_brut: Mapped[str] = mapped_column(String(500))
    execution_id: Mapped[int] = mapped_column(ForeignKey("execution_collecte.id"), index=True)
    collecte_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)

    changements: Mapped[list[ChangementExtrait]] = relationship(back_populates="document")


class Cible(Base):
    """Article (ou subdivision) surveillé, avec le dispositif qu'il porte."""

    __tablename__ = "cible"
    __table_args__ = (CheckConstraint("niveau IN ('coeur', 'connexe')", name="ck_cible_niveau"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dispositif: Mapped[str] = mapped_column(String(10), index=True)
    code: Mapped[str] = mapped_column(String(200))
    article: Mapped[str] = mapped_column(String(50))
    subdivision: Mapped[str | None] = mapped_column(String(200))
    legi_id: Mapped[str | None] = mapped_column(String(30))
    niveau: Mapped[str] = mapped_column(String(10))
    confirme: Mapped[bool] = mapped_column(Boolean, default=False)
    valide_du: Mapped[date | None] = mapped_column(Date)
    valide_au: Mapped[date | None] = mapped_column(Date)


class ChangementExtrait(Base):
    """Une modification repérée dans un document (S2). Format : ``collecte.schemas.Changement``."""

    __tablename__ = "changement"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"), index=True)
    operation: Mapped[str] = mapped_column(String(32))
    code: Mapped[str | None] = mapped_column(String(200))
    article: Mapped[str | None] = mapped_column(String(50))
    localisation: Mapped[str] = mapped_column(Text, default="")
    dispositif: Mapped[str | None] = mapped_column(String(10), index=True)
    parametre: Mapped[str | None] = mapped_column(String(300))
    objet: Mapped[str | None] = mapped_column(String(50))
    ancienne_valeur: Mapped[str | None] = mapped_column(Text)
    nouvelle_valeur: Mapped[str | None] = mapped_column(Text)
    passage_debut: Mapped[int] = mapped_column(Integer)
    passage_fin: Mapped[int] = mapped_column(Integer)
    passage_texte: Mapped[str] = mapped_column(Text)
    # Méthode « legi » : {document_id, debut, fin, texte} dans la version précédente.
    passage_precedent: Mapped[dict | None] = mapped_column(JSON)
    clauses_application: Mapped[list[str]] = mapped_column(JSON, default=list)
    methode: Mapped[Methode] = mapped_column(_enum(Methode, "methode_extraction"))
    coordination: Mapped[bool] = mapped_column(Boolean, default=False)
    alinea_projet: Mapped[int | None] = mapped_column(Integer)
    statut: Mapped[Statut] = mapped_column(_enum(Statut, "statut_changement"), index=True)
    motifs: Mapped[list[str]] = mapped_column(JSON, default=list)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)

    document: Mapped[Document] = relationship(back_populates="changements")
