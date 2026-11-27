"""S1 et A1 : connecteurs (sur des fichiers reconstitués) et contrôle de complétude."""

import io
import tarfile
from datetime import date

from aide_collecte import DECRET, LOI, fabriquer_archive_jorf

from leypilot.collecte.completude import controler_numeros, controler_sommaire, trous
from leypilot.collecte.sources import assemblee, bofip, jorf, senat
from leypilot.collecte.sources.base import Source, TypeTexte, etape_depuis_sort
from leypilot.collecte.sources.dila import archives_publiees

# ------------------------------------------------------------------ complétude


def test_trous():
    assert trous([44, 45, 47, 48]) == [46]
    assert trous([]) == []


def test_controle_du_sommaire():
    rapport = controler_sommaire(["A", "B", "C"], ["A", "C", "Z"], [1, 3])
    assert not rapport.complet
    assert rapport.ecarts == [
        "absent de l'archive : B",
        "hors sommaire : Z",
        "séquence manquante : 2",
    ]
    assert controler_sommaire(["A"], ["A"], [1]).complet


def test_controle_des_numeros():
    assert controler_numeros([1, 2, 4], "amendement").ecarts == ["amendement manquant : 3"]


# ------------------------------------------------------------------ JO (DILA)


def test_jorf_lit_l_archive_et_controle_le_sommaire(archive_jorf):
    collecte = jorf.lire_fichier(archive_jorf)
    assert collecte.controle.complet
    assert (collecte.controle.attendus, collecte.controle.recus, collecte.nb_lus) == (2, 2, 2)
    (loi,) = collecte.documents  # le décret est hors périmètre
    assert (loi.source, loi.identifiant, loi.type_texte) == (Source.JORF, LOI, TypeTexte.LOI)
    assert loi.nor == "ECOX0000000L" and loi.date_document == date(2025, 2, 15)
    # Les articles suivent l'ordre de la structure, pas celui de l'archive.
    assert loi.texte.index("Article 55") < loi.texte.index("Article 56")
    assert "le taux : « 30 % » est remplacé par le taux : « 20 % »" in loi.texte


def test_jorf_signale_un_texte_absent(tmp_path):
    collecte = jorf.lire_fichier(fabriquer_archive_jorf(tmp_path, oublier_decret=True))
    assert collecte.controle.ecarts == [f"JO n° 40 : absent de l'archive : {DECRET}"]


def test_jorf_liste_des_archives():
    page = '<a href="JORF_20261121-003012.tar.gz">x</a> <a href="JORF_20261122-003015.tar.gz">'
    assert archives_publiees(page, date(2026, 11, 22)) == ["JORF_20261122-003015.tar.gz"]


# ------------------------------------------------------------------ Assemblée nationale


def test_assemblee(archive_an):
    collecte = assemblee.lire_archive(archive_an)
    (i_2211,) = collecte.documents
    assert i_2211.numero_amendement == "I-2211"
    assert i_2211.etape == "adoption"
    assert i_2211.texte.startswith("APRÈS L'ARTICLE 13")
    assert collecte.controle.ecarts == ["PRJLANR5L17B0324 [AN] : amendement manquant : 2210"]


def test_sort_vers_etape():
    assert etape_depuis_sort("Adopté") == "adoption"
    for sort in ("Rejeté", "Tombé", "Retiré avant séance", "Non soutenu", "Irrecevable LOLF"):
        assert etape_depuis_sort(sort) == "rejet"
    assert etape_depuis_sort(None) is None


# ------------------------------------------------------------------ Sénat


def test_senat_fichier_cp1252(tmp_path):
    entete = "Numéro \tSubdivision \tDate de dépôt \tSort \tDispositif \tObjet \tUrl amendement "
    lignes = [
        "sep=\t",
        entete,
        "I-1179\tArticle 13\t2024-11-20\tRejeté\tLe crédit d'impôt recherche est modifié.\tx\t",
        "I-1180\tArticle 14\t2024-11-20\tAdopté\tSans rapport.\ty\t",
        "I-1182\tArticle 15\t2024-11-21\t\tSans rapport.\tz\t",
    ]
    chemin = tmp_path / "jeu_complet_2024-2025_143.csv"
    chemin.write_bytes("\r\n".join(lignes).encode("cp1252"))
    collecte = senat.lire_fichier(chemin, "2024-2025", 143)
    (doc,) = collecte.documents
    assert (doc.identifiant, doc.etape, doc.date_document) == (
        "2024-2025/143/I-1179",
        "rejet",
        date(2024, 11, 20),
    )
    assert collecte.controle.ecarts == ["partie I : amendement manquant : 1181"]


# ------------------------------------------------------------------ BOFiP


def test_bofip_controle_par_numero_de_flux():
    lien = "https://bofip.impots.gouv.fr/opendata/flux/{}"
    flux = [
        {"telechargement": lien.format(45), "date_de_fin": "2026-11-04"},
        {"telechargement": lien.format(47), "date_de_fin": "2026-11-18"},
    ]
    rapport = bofip.controler_liste(flux, date(2026, 11, 20))
    assert rapport.ecarts == ["flux BOFiP manquant : 46"]
    rapport = bofip.controler_liste(flux, date(2026, 12, 10))
    assert "dernier flux terminé le 2026-11-18, il y a 22 jours" in rapport.ecarts


def test_bofip_lit_les_series_suivies(tmp_path):
    chemin = tmp_path / "flux.tgz"
    with tarfile.open(chemin, "w:gz") as archive:
        for dossier, ident in (("a", "BOI-BIC-RICI-10-10-45-20"), ("b", "BOI-TVA-BASE-10")):
            for nom, contenu in (
                (
                    f"{dossier}/document.xml",
                    f"<doc><identifier>{ident}</identifier>"
                    "<title>CII</title><date>2025-08-13</date></doc>",
                ),
                (
                    f"{dossier}/data.html",
                    "<p>Le taux du crédit d'impôt innovation est de 20 %.</p>",
                ),
            ):
                donnees = contenu.encode()
                info = tarfile.TarInfo(nom)
                info.size = len(donnees)
                archive.addfile(info, io.BytesIO(donnees))
    collecte = bofip.lire_archive(chemin)
    (doc,) = collecte.documents
    assert doc.identifiant == "BOI-BIC-RICI-10-10-45-20"
    assert doc.texte == "Le taux du crédit d'impôt innovation est de 20 %."
    assert doc.type_texte == TypeTexte.DOCTRINE
