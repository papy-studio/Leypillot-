"""Tables du lot 2 (propriétaire : P2) : mesure, version_mesure, transition_mesure,
resume, rattachement_a_valider. Les autres lots les lisent sans les modifier."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum as EnumPython

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leypilot.commun.base import Base, maintenant
from leypilot.mesure.schemas import Dispositif, Evenement, NatureDate, StatutMesure


def _enum(type_enum: type[EnumPython], nom: str) -> Enum:
    """Énumération stockée en texte (« votee »), lisible par le trigger A5."""
    return Enum(
        type_enum,
        name=nom,
        native_enum=False,
        length=32,
        values_callable=lambda membres: [m.value for m in membres],
        validate_strings=True,
    )


class Mesure(Base):
    __tablename__ = "mesure"

    id: Mapped[int] = mapped_column(primary_key=True)
    dispositif: Mapped[Dispositif] = mapped_column(_enum(Dispositif, "dispositif"), index=True)
    article_vise: Mapped[str] = mapped_column(String(300))
    parametre: Mapped[str] = mapped_column(String(300))
    # Repris du dernier changement : le texte voté peut retenir une autre valeur
    # que l'amendement déposé. La personne 3 en tire la réforme à simuler.
    ancienne_valeur: Mapped[str | None] = mapped_column(String(200))
    nouvelle_valeur: Mapped[str | None] = mapped_column(String(200))
    conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    statut: Mapped[StatutMesure] = mapped_column(_enum(StatutMesure, "statut_mesure"), index=True)

    dossier_legislatif: Mapped[str | None] = mapped_column(String(200))
    numeros_amendement: Mapped[list[str]] = mapped_column(JSON, default=list)
    nor: Mapped[str | None] = mapped_column(String(50))
    eli: Mapped[str | None] = mapped_column(String(300))

    date_publication: Mapped[date | None] = mapped_column(Date)
    date_entree_vigueur: Mapped[date | None] = mapped_column(Date)
    nature_date: Mapped[NatureDate | None] = mapped_column(_enum(NatureDate, "nature_date"))
    clause_entree_vigueur: Mapped[str | None] = mapped_column(Text)

    a_revoir: Mapped[bool] = mapped_column(Boolean, default=False)
    motif_a_revoir: Mapped[str | None] = mapped_column(Text)

    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    maj_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=maintenant, onupdate=maintenant
    )

    transitions: Mapped[list[TransitionMesure]] = relationship(
        back_populates="mesure", order_by="TransitionMesure.id", cascade="all, delete-orphan"
    )
    resumes: Mapped[list[ResumeMesure]] = relationship(
        back_populates="mesure", order_by="ResumeMesure.id"
    )
    versions: Mapped[list[VersionMesure]] = relationship(
        back_populates="mesure", order_by="VersionMesure.id", cascade="all, delete-orphan"
    )


class VersionMesure(Base):
    """Un changement rattaché à une mesure (A2) : amendement, texte voté, loi publiée.

    Donne le lien de la mesure vers ses documents et garde une copie du changement,
    pour relancer un résumé en attente sans relire les tables du lot 1."""

    __tablename__ = "version_mesure"

    id: Mapped[int] = mapped_column(primary_key=True)
    mesure_id: Mapped[int] = mapped_column(ForeignKey("mesure.id"), index=True)
    changement_id: Mapped[int] = mapped_column(unique=True)
    document_id: Mapped[int] = mapped_column(index=True)
    evenement: Mapped[Evenement] = mapped_column(_enum(Evenement, "evenement"))
    date_document: Mapped[date] = mapped_column(Date)
    methode: Mapped[str] = mapped_column(String(20))  # creation, amendement, similarite, humain
    score: Mapped[float | None] = mapped_column(Float)
    changement_json: Mapped[str] = mapped_column(Text)
    rattache_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)

    mesure: Mapped[Mesure] = relationship(back_populates="versions")


class TransitionMesure(Base):
    """Historique des statuts : une ligne par changement de statut (création comprise)."""

    __tablename__ = "transition_mesure"

    id: Mapped[int] = mapped_column(primary_key=True)
    mesure_id: Mapped[int] = mapped_column(ForeignKey("mesure.id"), index=True)
    de_statut: Mapped[StatutMesure | None] = mapped_column(_enum(StatutMesure, "statut_mesure"))
    vers_statut: Mapped[StatutMesure] = mapped_column(_enum(StatutMesure, "statut_mesure"))
    evenement: Mapped[Evenement] = mapped_column(_enum(Evenement, "evenement"))
    date_evenement: Mapped[date] = mapped_column(Date)
    changement_id: Mapped[int | None]
    document_id: Mapped[int | None]
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=maintenant, index=True
    )

    mesure: Mapped[Mesure] = relationship(back_populates="transitions")


class ResumeMesure(Base):
    """Résumé S3. Sert aussi de cache : un même changement d'un même texte, avec la
    même version de rédacteur, n'est jamais résumé deux fois."""

    __tablename__ = "resume"
    __table_args__ = (
        UniqueConstraint("empreinte_texte", "empreinte_changement", "version", name="uq_resume"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mesure_id: Mapped[int | None] = mapped_column(ForeignKey("mesure.id"), index=True)
    changement_id: Mapped[int]
    empreinte_texte: Mapped[str] = mapped_column(String(64))
    empreinte_changement: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(100))
    methode: Mapped[str] = mapped_column(String(20))
    texte: Mapped[str] = mapped_column(Text)
    citation: Mapped[str] = mapped_column(Text)
    a_verifier: Mapped[bool] = mapped_column(Boolean, default=False)
    motifs_verification: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Vrai si le LLM a échoué après ses nouvelles tentatives : le texte vient du
    # gabarit, et le résumé sera relancé par ``SuiviMesures.relancer_resumes_en_attente``.
    en_attente: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)

    mesure: Mapped[Mesure | None] = relationship(back_populates="resumes")


class RattachementAValider(Base):
    """Rattachement ambigu (A2) en attente d'une décision humaine."""

    __tablename__ = "rattachement_a_valider"

    id: Mapped[int] = mapped_column(primary_key=True)
    changement_id: Mapped[int] = mapped_column(index=True)
    changement_json: Mapped[str] = mapped_column(Text)
    mesure_candidate_id: Mapped[int] = mapped_column(ForeignKey("mesure.id"))
    score: Mapped[float] = mapped_column(Float)
    decision: Mapped[str | None] = mapped_column(String(20))  # confirme ou refuse
    traite_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
