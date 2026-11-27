"""S2 · Comparaison LEGI : ce qui a changé entre deux versions consolidées d'un article.

Deuxième regard sur les changements lus dans le JO. Pour un article suivi :

- première version reçue : version de référence, aucun changement ;
- article abrogé (ABROGE, ABROGE_DIFF) : un changement ``abrogation_article`` ;
- texte modifié : comparaison mot à mot des deux versions ; chaque écart donne un
  changement (``remplacement``, ``insertion_mots``, ``suppression_mots`` ou ``redaction``
  si l'écart est long), avec le passage de la nouvelle version et celui de l'ancienne.

Ensuite ``confirmer`` compare ces écarts aux changements lus dans le texte du JO qui a
modifié l'article : mêmes valeurs, le changement est confirmé ; valeurs différentes, il
part « à revoir » avec le motif ``desaccord_legi``.

Les changements LEGI ne sont pas transmis au lot 2 (le type ``version_consolidee`` n'y
est pas prévu) : ils servent au contrôle et aux indicateurs du lot 1.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from leypilot.collecte.cibles import rattacher
from leypilot.collecte.schemas import Changement, Methode, Motif, Operation, Passage, Statut
from leypilot.collecte.sources.legi import ETATS_ABROGES

# Un nombre et son unité forment un seul mot : « 30 % », « 400 000 € », « 2,5 % ».
MOTS = re.compile(r"\d+(?: \d{3})*(?:,\d+)?(?: ?%| ?€)?|\S+")
FIN_DE_PHRASE = re.compile(r"(?<=[.;:])\s+|\n")
ECART_LONG = 30  # au-delà de 30 mots, l'écart est une réécriture : pas de valeurs extraites


def _phrase(texte: str, debut: int, fin: int) -> tuple[int, int]:
    """Bornes de la phrase (ou des phrases) qui contiennent [debut, fin)."""
    coupures = [0, *(m.end() for m in FIN_DE_PHRASE.finditer(texte)), len(texte)]
    gauche = max(c for c in coupures if c <= debut)
    droite = min((c for c in coupures if c >= max(fin, debut + 1)), default=len(texte))
    return gauche, droite


def _passage(document_id: int, texte: str, debut: int, fin: int) -> Passage:
    gauche, droite = _phrase(texte, debut, fin)
    extrait = texte[gauche:droite].strip()
    gauche = texte.index(extrait, gauche)
    return Passage(document_id=document_id, debut=gauche, fin=gauche + len(extrait), texte=extrait)


def _objet(valeur: str | None) -> str:
    if valeur and "%" in valeur:
        return "le taux"
    if valeur and re.fullmatch(r"(?:19|20)\d\d", valeur):
        return "l'année"
    return "les mots"


def comparer(
    document_id: int,
    code: str,
    article: str,
    avant: str | None,
    apres: str,
    etat: str,
    document_precedent_id: int | None = None,
) -> list[Changement]:
    """Changements entre la version précédente (``avant``) et la nouvelle (``apres``)."""
    if avant is None:
        return []
    if etat in ETATS_ABROGES:
        dispositifs = rattacher([(code, article)], "", "") or [None]
        return [
            Changement(
                document_id=document_id,
                operation=Operation.ABROGATION_ARTICLE,
                code=code,
                article=article,
                dispositif=dispositif,
                passage=Passage(document_id=document_id, debut=0, fin=len(apres), texte=apres),
                methode=Methode.LEGI,
                statut=Statut.OK,
            )
            for dispositif in dispositifs
        ]

    mots_avant = list(MOTS.finditer(avant))
    mots_apres = list(MOTS.finditer(apres))
    comparaison = SequenceMatcher(
        None, [m.group() for m in mots_avant], [m.group() for m in mots_apres], autojunk=False
    )
    changements: list[Changement] = []
    for etiquette, i1, i2, j1, j2 in comparaison.get_opcodes():
        if etiquette == "equal":
            continue
        ancien = avant[mots_avant[i1].start() : mots_avant[i2 - 1].end()] if i2 > i1 else None
        nouveau = apres[mots_apres[j1].start() : mots_apres[j2 - 1].end()] if j2 > j1 else None
        pos_apres = mots_apres[j1].start() if j1 < len(mots_apres) else len(apres)
        fin_apres = mots_apres[j2 - 1].end() if j2 > j1 else pos_apres
        pos_avant = mots_avant[i1].start() if i1 < len(mots_avant) else len(avant)
        fin_avant = mots_avant[i2 - 1].end() if i2 > i1 else pos_avant
        passage = _passage(document_id, apres, pos_apres, fin_apres)
        precedent = _passage(document_precedent_id or document_id, avant, pos_avant, fin_avant)
        if max(i2 - i1, j2 - j1) > ECART_LONG:
            operation, ancien, nouveau = Operation.REDACTION, None, None
        else:
            operation = {
                "replace": Operation.REMPLACEMENT,
                "insert": Operation.INSERTION_MOTS,
                "delete": Operation.SUPPRESSION_MOTS,
            }[etiquette]
        zone = f"{precedent.texte} {passage.texte}"
        for dispositif in rattacher([(code, article)], "", zone) or [None]:
            changements.append(
                Changement(
                    document_id=document_id,
                    operation=operation,
                    code=code,
                    article=article,
                    dispositif=dispositif,
                    objet=_objet(nouveau or ancien),
                    ancienne_valeur=ancien,
                    nouvelle_valeur=nouveau,
                    passage=passage,
                    passage_precedent=precedent,
                    methode=Methode.LEGI,
                    statut=Statut.OK,
                )
            )
    return changements


def confirmer(
    changements_legi: list[Changement], changements_jo: list[Changement]
) -> list[Changement]:
    """Marque « à revoir » (``desaccord_legi``) chaque écart LEGI qu'aucun changement lu
    dans le JO modificateur ne porte. Sans changement JO connu, rien n'est marqué."""
    if not changements_jo:
        return changements_legi
    valeurs_jo = {
        (c.article, c.ancienne_valeur, c.nouvelle_valeur) for c in changements_jo if c.article
    }
    resultat = []
    for changement in changements_legi:
        cle = (changement.article, changement.ancienne_valeur, changement.nouvelle_valeur)
        if changement.operation == Operation.ABROGATION_ARTICLE or cle in valeurs_jo:
            resultat.append(changement)
            continue
        resultat.append(
            Changement.model_validate(
                changement.model_dump()
                | {"statut": Statut.A_REVOIR, "motifs": [Motif.DESACCORD_LEGI]}
            )
        )
    return resultat
