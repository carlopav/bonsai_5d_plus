"""
Generate IFC4 classification library files for SOA, DM17 Z-1 and TOL.

Run once from Blender background mode:
  blender.exe --background --python tools/generate_classifications.py

Output: src/data/classifications/SOA.ifc, DM17.ifc, TOL.ifc
"""

import os
import sys

import ifcopenshell
import ifcopenshell.guid

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data", "classifications")

# ---------------------------------------------------------------------------
# Category definitions (mirrors CostClassification.py)
# ---------------------------------------------------------------------------

_SOA = [
    ("OG1",    "Edifici civili e industriali"),
    ("OG2",    "Restauro e manutenzione dei beni immobili sottoposti a tutela"),
    ("OG3",    "Strade, autostrade, ponti, viadotti, ferrovie, metropolitane"),
    ("OG4",    "Opere d'arte nel sottosuolo"),
    ("OG5",    "Dighe"),
    ("OG6",    "Acquedotti, gasdotti, oleodotti, opere di irrigazione e di evacuazione"),
    ("OG7",    "Opere marittime e lavori di dragaggio"),
    ("OG8",    "Opere fluviali, di difesa, di sistemazione idraulica e di bonifica"),
    ("OG9",    "Impianti per la produzione di energia elettrica"),
    ("OG10",   "Impianti per la trasformazione alta/media tensione e distribuzione in alta tensione"),
    ("OG11",   "Impianti tecnologici"),
    ("OG12",   "Opere ed impianti di bonifica e protezione ambientale"),
    ("OG13",   "Opere e impianti di smaltimento e recupero di rifiuti"),
    ("OS1",    "Lavori in terra"),
    ("OS2-A",  "Superfici decorate di beni del patrimonio culturale immobile"),
    ("OS2-B",  "Beni culturali mobili di interesse archivistico e librario"),
    ("OS3",    "Impianti idrico-sanitari, cucine, lavanderie"),
    ("OS4",    "Impianti elettromeccanici trasportatori"),
    ("OS5",    "Impianti pneumatici e antintrusione"),
    ("OS6",    "Finiture in materiali lignei, plastici, metallici e vetrosi"),
    ("OS7",    "Finiture di natura edile e tecnica"),
    ("OS8",    "Finiture di impermeabilizzazione"),
    ("OS9",    "Impianti per la segnaletica luminosa e la sicurezza del traffico"),
    ("OS10",   "Segnaletica stradale non luminosa"),
    ("OS11",   "Apparecchiature strutturali speciali"),
    ("OS12-A", "Barriere stradali di sicurezza"),
    ("OS12-B", "Barriere paramassi, fermaneve e simili"),
    ("OS13",   "Strutture prefabbricate in cemento armato"),
    ("OS14",   "Impianti di smaltimento e recupero di rifiuti"),
    ("OS15",   "Pulizia di acque marine, lacustri, fluviali"),
    ("OS16",   "Impianti per energie rinnovabili"),
    ("OS17",   "Sistemi e tecnologie ad alta automazione e controllo"),
    ("OS18-A", "Componenti strutturali in acciaio"),
    ("OS18-B", "Componenti per facciate continue"),
    ("OS19",   "Impianti di reti di telecomunicazione"),
    ("OS20-A", "Rilevamenti topografici"),
    ("OS20-B", "Indagini geognostiche"),
    ("OS21",   "Opere strutturali speciali"),
    ("OS22",   "Impianti di potabilizzazione e depurazione"),
    ("OS23",   "Demolizione di opere"),
    ("OS24",   "Verde e arredo urbano"),
    ("OS25",   "Scavi archeologici"),
    ("OS26",   "Pavimentazioni e sovrastrutture speciali"),
    ("OS27",   "Impianti per la trazione elettrica"),
    ("OS28",   "Impianti termici e di condizionamento"),
    ("OS29",   "Armamento ferroviario"),
    ("OS30",   "Impianti interni elettrici, telefonici, radiotelefonici e televisivi"),
    ("OS31",   "Impianti per la mobilità sospesa"),
    ("OS32",   "Strutture in legno"),
    ("OS33",   "Coperture speciali"),
    ("OS34",   "Sistemi antirumore per infrastrutture di mobilità"),
    ("OS35",   "Navi e galleggianti"),
]

_DM17 = [
    ("E.01",  "Edifici rurali agricoli semplici; edifici industriali/artigianali correnti"),
    ("E.02",  "Edifici rurali agricoli complessi; edifici industriali/artigianali complessi"),
    ("E.03",  "Ostelli, ristoranti, negozi, mercati semplici"),
    ("E.04",  "Alberghi, villaggi turistici, centri commerciali complessi"),
    ("E.05",  "Edifici residenziali semplici, autorimesse, costruzioni provvisorie"),
    ("E.06",  "Edilizia residenziale privata/pubblica corrente"),
    ("E.07",  "Edifici residenziali pregiati con tipologie diversificate"),
    ("E.08",  "Strutture sanitarie, asili, scuole di base"),
    ("E.09",  "Scuole grandi, case di cura"),
    ("E.10",  "Ospedali, istituti ricerca, università, accademie"),
    ("E.11",  "Padiglioni esposizioni, strutture cimiteriali, stabilimenti balneari, impianti sportivi semplici"),
    ("E.12",  "Impianti sportivi complessi, palestre, piscine coperte"),
    ("E.13",  "Biblioteche, teatri, musei, chiese, stadi, palasport"),
    ("E.14",  "Edifici provvisori a servizio caserme"),
    ("E.15",  "Caserme con corredi tecnici correnti"),
    ("E.16",  "Sedi amministrative, tribunali, penitenziari, questure"),
    ("E.17",  "Verde, arredo urbano semplice, campeggi"),
    ("E.18",  "Arredamenti, giardini, parchi gioco, piazze pubbliche"),
    ("E.19",  "Arredamenti singolari, parchi urbani, riqualificazione paesaggistica"),
    ("E.20",  "Manutenzione straordinaria, ristrutturazione edifici esistenti"),
    ("E.21",  "Restauro edifici storici non tutelati"),
    ("E.22",  "Restauro edifici storici tutelati D.Lgs 42/2004"),
    ("S.01",  "Strutture c.a. non sismiche, riparazioni locali"),
    ("S.02",  "Strutture muratura, legno, metallo non sismiche"),
    ("S.03",  "Strutture c.a., strutture provvisionali durata > 2 anni"),
    ("S.04",  "Strutture muratura/legno/metallo, consolidamenti, ponti, paratie"),
    ("S.05",  "Dighe, gallerie, opere sotterranee, fondazioni speciali"),
    ("S.06",  "Opere strutturali notevoli, edifici alti con modellazione particolare"),
    ("IA.01", "Impianti acqua, fognature, combustibili, antincendio"),
    ("IA.02", "Impianti riscaldamento, raffrescamento, climatizzazione, solare termico"),
    ("IA.03", "Impianti elettrici, illuminazione, fotovoltaici correnti"),
    ("IA.04", "Impianti elettrici complessi, fibra ottica, sistemi sicurezza"),
    ("IB.04", "Discariche inerti"),
    ("IB.05", "Impianti industrie alimentari, legno, cuoio"),
    ("IB.06", "Impianti chimici, siderurgici, termovalorizzatori"),
    ("IB.07", "Impianti chimici/siderurgici/termovalorizzatori con complessità rilevante"),
    ("IB.08", "Reti trasmissione distribuzione energia elettrica"),
    ("IB.09", "Centrali idroelettriche, stazioni trasformazione"),
    ("IB.10", "Impianti termoelettrici, elettrometallurgia"),
    ("IB.11", "Campi fotovoltaici, parchi eolici"),
    ("IB.12", "Micro centrali idroelettriche, impianti termoelettrici complessi"),
    ("V.01",  "Manutenzione viabilità ordinaria"),
    ("V.02",  "Strade, tramvie, ferrovie ordinarie, piste ciclabili"),
    ("V.03",  "Viabilità con difficoltà particolari, teleferiche, piste aeroportuali"),
    ("D.01",  "Opere navigazione interna, portuali"),
    ("D.02",  "Bonifiche, irrigazioni a deflusso naturale"),
    ("D.03",  "Bonifiche con sollevamento meccanico, derivazioni d'acqua"),
    ("D.04",  "Acquedotti, fognature semplici, condotte ordinarie"),
    ("D.05",  "Impianti acqua, fognature, condotte con problemi tecnici speciali"),
    ("T.01",  "Sistemi informativi, data center, dematerializzazione"),
    ("T.02",  "Reti locali, cablaggi strutturati, fibra ottica, videosorveglianza"),
    ("T.03",  "Elettronica industriale, automazione, robotica"),
    ("P.01",  "Sistemazione ecosistemi naturali, restauro paesaggistico"),
    ("P.02",  "Opere a verde piccola/grande scala"),
    ("P.03",  "Riqualificazione ambientale, ripristino condizioni originarie"),
    ("P.04",  "Utilizzazione cave e torbiere"),
    ("P.05",  "Assetto forestale, piste forestali, meccanizzazione"),
    ("P.06",  "Infrastrutture rurali, miglioramento assetto rurale"),
    ("U.01",  "Infrastrutture filiere agroalimentari, zootecniche"),
    ("U.02",  "Valorizzazione ambiti naturali vegetazionali e faunistici"),
    ("U.03",  "Strumenti pianificazione generale e settoriale"),
]

_TOL = [
    ("TOL.1",  "Opere edili su edifici e manufatti non soggetti a tutela dei beni culturali"),
    ("TOL.2",  "Opere edili su edifici e manufatti soggetti a tutela dei beni culturali"),
    ("TOL.3",  "Scavi archeologici, restauri specialistici di beni del patrimonio culturale e di interesse storico"),
    ("TOL.4",  "Lavori di movimento terra, demolizioni, opere di protezione ambientale, ingegneria naturalistica e opere a verde"),
    ("TOL.5",  "Pavimentazioni in conglomerato bituminoso"),
    ("TOL.6",  "Strutture, opere di ingegneria e manufatti in acciaio"),
    ("TOL.7",  "Strutture, opere di ingegneria e manufatti in calcestruzzo armato, anche prefabbricato"),
    ("TOL.8",  "Strutture, opere di ingegneria e manufatti in legno"),
    ("TOL.9",  "Gallerie e opere d'arte nel sottosuolo realizzate con metodo tradizionale"),
    ("TOL.10", "Gallerie e opere d'arte nel sottosuolo realizzate con metodo meccanizzato"),
    ("TOL.11", "Acquedotti, gasdotti, opere di irrigazione e fognature"),
    ("TOL.12", "Opere marittime e lavori di dragaggio, opere fluviali e di difesa del suolo"),
    ("TOL.13", "Impianti per la produzione, trasformazione e distribuzione di energia elettrica in alta e media tensione per la trazione elettrica e l'illuminazione pubblica"),
    ("TOL.14", "Impianti elettrici, tecnologici, radiotelefonici e antintrusione"),
    ("TOL.15", "Impianti meccanici, termici, di condizionamento, idrico sanitari e trasportatori"),
    ("TOL.16", "Impianti di potabilizzazione e depurazione"),
    ("TOL.17", "Impianti di segnalamento, sicurezza del traffico e telecomunicazioni"),
    ("TOL.18", "Armamento ferroviario"),
    ("TOL.19", "Opere di fondazione speciale, indagini geologiche e geotecniche"),
    ("TOL.20", "Conferimento rifiuti a impianto di smaltimento o recupero"),
]

# ---------------------------------------------------------------------------
# IFC file builder
# ---------------------------------------------------------------------------

def build_classification_ifc(
    ifc_name: str,
    source: str,
    edition: str,
    location: str,
    categories: list,
    out_path: str,
):
    f = ifcopenshell.file(schema="IFC4")

    # Minimal project context (required for a valid IFC4 file)
    project = f.create_entity(
        "IfcProject",
        GlobalId=ifcopenshell.guid.new(),
        Name=f"{ifc_name} Classification Library",
    )

    # Root classification entity
    cls = f.create_entity(
        "IfcClassification",
        Source=source,
        Edition=edition,
        Name=ifc_name,
        Location=location,
    )

    # Link classification to project (standard Bonsai pattern)
    f.create_entity(
        "IfcRelAssociatesClassification",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[project],
        RelatingClassification=cls,
    )

    # One flat IfcClassificationReference per category
    for code, name in categories:
        f.create_entity(
            "IfcClassificationReference",
            Identification=code,
            Name=name,
            ReferencedSource=cls,
        )

    f.write(out_path)
    print(f"Written: {out_path}  ({len(categories)} categories)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    build_classification_ifc(
        ifc_name="SOA",
        source="D.Lgs. 36/2023 Allegato II.12",
        edition="2023",
        location="https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2023-03-31;36",
        categories=_SOA,
        out_path=os.path.join(OUT_DIR, "SOA.ifc"),
    )

    build_classification_ifc(
        ifc_name="DM 17/06/2016 Z-1",
        source="DM 17 giugno 2016 – Tavola Z-1 (tariffe professionali)",
        edition="2016",
        location="https://www.bosettiegatti.eu/info/norme/statali/2016_dm_17_06_tariffe_allegato.pdf",
        categories=_DM17,
        out_path=os.path.join(OUT_DIR, "DM17.ifc"),
    )

    build_classification_ifc(
        ifc_name="Tipologie Omogenee di Lavorazione",
        source="D.Lgs. 36/2023 Art. 60 – Tabella A.1",
        edition="2024",
        location="https://www.gazzettaufficiale.it/eli/gu/2024/12/31/305/so/45/sg/pdf",
        categories=_TOL,
        out_path=os.path.join(OUT_DIR, "TOL.ifc"),
    )
