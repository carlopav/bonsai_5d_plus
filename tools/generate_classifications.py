# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.
#
# Bonsai5D+ is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Bonsai5D+ is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai5D+.  If not, see <http://www.gnu.org/licenses/>.
#
# This file was modified with the assistance of an AI coding tool.

"""
Generate IFC4X3 classification library files for SOA, DM17 Z-1 and TOL.

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

_TOL_DESCRIPTIONS = {
    "TOL.1": (
        "Riguarda la nuova costruzione, la manutenzione, la ristrutturazione o il consolidamento di edifici civili e "
        "industriali non soggetti a tutela dei beni culturali quali, in via esemplificativa, le residenze, le carceri, "
        "le scuole, le caserme, gli uffici, i teatri, gli ospedali, gli stadi, gli edifici per le industrie, gli "
        "edifici per parcheggi, le stazioni ferroviarie e metropolitane e gli edifici aeroportuali. Include, in via "
        "esemplificativa e non esaustiva: infissi e rivestimenti interni ed esterni, pavimentazioni, massetti e "
        "sottofondi, solai (esclusi quelli interamente in cemento armato), altri manufatti in materie plastiche, "
        "materiali vetrosi e simili, murature e tramezzature comprensive di intonacatura, rasatura, tinteggiatura, "
        "verniciatura, opere di finitura quali isolamenti termici e acustici, controsoffittature, barriere al fuoco e "
        "opere di impermeabilizzazione, facciate continue e coperture in alluminio, apparecchi di appoggio in gomma. "
        "Sono da escludere: impianti elettrici, tecnologici, radiotelefonici, antintrusione, meccanici, termici, di "
        "condizionamento, idrico sanitari e trasportatori, le strutture e i manufatti in legno, in acciaio (travi, "
        "coperture, ecc.), in cemento armato gettato in opera o prefabbricato (pilastri, travi, pozzetti, serbatoi "
        "pensili e silos), gli scavi e i movimenti terra, le demolizioni, la raccolta di materiali di risulta e il "
        "loro smaltimento e qualsiasi lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
    ),
    "TOL.2": (
        "Riguarda la manutenzione, la ristrutturazione o il consolidamento di edifici civili e industriali soggetti "
        "a tutela dei beni culturali quali, in via esemplificativa, le residenze, le carceri, le scuole, gli ospedali, "
        "le caserme, gli uffici, i teatri, gli stadi, gli edifici per le industrie, gli edifici per parcheggi, le "
        "stazioni ferroviarie e metropolitane e gli edifici aeroportuali. Include, in via esemplificativa e non "
        "esaustiva: infissi e rivestimenti interni ed esterni, pavimentazioni, massetti e sottofondi, solai (esclusi "
        "quelli interamente in cemento armato), altri manufatti in materie plastiche, materiali vetrosi e simili, "
        "murature e tramezzature comprensive di intonacatura, rasatura, tinteggiatura, verniciatura, opere di finitura "
        "quali isolamenti termici e acustici, controsoffittature, barriere al fuoco e opere di impermeabilizzazione, "
        "facciate continue e coperture in alluminio, apparecchi di appoggio in gomma. Sono da escludere: impianti "
        "elettrici, tecnologici, radiotelefonici, antintrusione, meccanici, termici, di condizionamento, idrico "
        "sanitari e trasportatori, le strutture e i manufatti in legno, in acciaio (travi, coperture, ecc.), in "
        "cemento armato gettato in opera o prefabbricato (pilastri, travi, pozzetti, serbatoi pensili e silos), gli "
        "scavi e i movimenti terra, le demolizioni, la raccolta di materiali di risulta e il loro smaltimento e "
        "qualsiasi lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
    ),
    "TOL.3": (
        "Riguarda gli scavi archeologici e le attività strettamente connesse da eseguirsi sia in aree dichiarate di "
        "interesse culturale sia in aree non dichiarate, condotti secondo normativa vigente. Per scavi archeologici si "
        "intendono anche quelli preparatori alla nuova costruzione, alla ristrutturazione, al restauro ed alla "
        "manutenzione da progettarsi, eseguirsi ed effettuarsi da imprese in possesso dei requisiti e della "
        "manodopera specializzata, secondo normativa vigente. Sono altresì inclusi gli scavi archeologici subacquei. "
        "Riguarda interventi relativi alla conservazione, alla diagnostica, al monitoraggio, alla manutenzione e al "
        "restauro di beni culturali di qualsiasi genere e materiale in tutti i tipi di contesto - museale, "
        "archeologico, di cantiere e/o laboratorio - effettuati da imprese qualificate e mano d'opera specializzata "
        "secondo la normativa vigente. Include la lavorazione di beni culturali mobili, superfici decorate e materiali "
        "storicizzati di beni architettonici ed archeologici, di beni demoetnoantropologici e di qualsiasi altro bene "
        "di interesse culturale appartenente a soggetti pubblici e privati, come stabilito dal Dlgs 42/2004."
    ),
    "TOL.4": (
        "Riguarda lo scavo e i movimenti terra di qualsiasi genere, trincee e rilevati, ripristino, modifica e "
        "bonifica di volumi di terra, realizzati qualunque sia la natura del terreno da scavare, ripristinare e "
        "bonificare, i campionamenti di terreni e le analisi chimiche, le demolizioni in genere, compreso lo "
        "smontaggio di impianti, la demolizione completa di edifici e il taglio di strutture in cemento armato, le "
        "attività di raccolta dei materiali di risulta ed il loro conferimento, la realizzazione delle cunette, "
        "caditoie, canalette in terra o in calcestruzzo direttamente relazionate con i movimenti terra, la "
        "realizzazione del verde urbano, compresi gli arredi urbani e le opere a verde quali la realizzazione di "
        "tappeti erbosi, inerbimenti, la messa a dimora di piante arbustive o alberi, la piantagione di essenze "
        "arboree e la manutenzione del verde in generale, compresi i geotessuti, le geogriglie, le terre rinforzate, "
        "i materiali in grado di aumentare la capacità portante del rilevato, dune antirumore, la stabilizzazione a "
        "calce e/o cemento, il misto stabilizzato, il misto cementato e le trincee drenanti."
    ),
    "TOL.5": (
        "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di pavimentazioni in conglomerato "
        "bituminoso. Include, in via esemplificativa e non esaustiva: le pavimentazioni stradali, di piazzali e "
        "marciapiedi, le impermeabilizzazioni a base di materiali bituminosi di impalcati, la segnaletica orizzontale. "
        "Sono da escludere: le pavimentazioni in calcestruzzo, strutture e i manufatti in acciaio, in cemento armato "
        "gettato in opera o prefabbricato, gli scavi e i movimenti terra, le demolizioni, la raccolta di materiali di "
        "risulta e il loro smaltimento e qualsiasi lavorazione o materiale direttamente riconducibile alle TOL "
        "Specializzate."
    ),
    "TOL.6": (
        "Riguarda la produzione in stabilimenti industriali, il montaggio in situ e più in generale la nuova "
        "costruzione, la manutenzione e la ristrutturazione di strutture, opere di ingegneria e manufatti realizzati "
        "in acciaio, compresi gli edifici in carpenteria pesante e leggera, ponti, viadotti e profilati, lavorazioni e "
        "trattamenti protettivi delle strutture in acciaio, i dispositivi strutturali quali, in via esemplificativa e "
        "non esaustiva, qualsiasi tipologia di giunti di dilatazione, di apparecchi di appoggio, di dispositivi di "
        "ancoraggio e di ritegni antisismici, compresi elementi quali rotaie, paraurti ferroviari, dispositivi di "
        "sicurezza stradale in acciaio, barriere di sicurezza e fonoassorbenti, attenuatori, terminali, chiusure "
        "varchi, segnaletica stradale verticale, tralicci e pali, recinzioni, lamiere per copertura, chiusini, "
        "canalette, passerelle, portacavi, canali di gronda, portali stradali e ferroviari, reti paramassi, scale, "
        "tubi in acciaio di qualsiasi tipologia e applicazione. Comprende inoltre le coperture particolari quali per "
        "esempio le tensostrutture e le coperture geodetiche. Sono esclusi gli acciai d'armatura del calcestruzzo e i "
        "consolidamenti strutturali in galleria, i quali si considerano inclusi nelle specifiche TOL di riferimento."
    ),
    "TOL.7": (
        "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di strutture, opere di ingegneria e "
        "manufatti realizzati in cemento armato normale o precompresso, gettato in opera o prefabbricato, in "
        "elevazione o in fondazione, comprese le casseforme, l'acciaio di armatura e le reti d'acciaio elettrosaldate, "
        "compresi elementi particolari quali ad esempio, in via esemplificativa e non esaustiva, pavimentazioni in "
        "calcestruzzo, cunicoli, pozzetti, cordoli, tubi prefabbricati, traverse ferroviarie, barriere stradali tipo "
        "New Jersey ed altri profili redirettivi in calcestruzzo anche per gallerie stradali, blocchi di fondazione per "
        "pali, apparecchi di appoggio in gomma, pannelli di calcestruzzo prefabbricato, canalette ecc. Riguarda "
        "altresì la realizzazione di opere atte a migliorare la capacità resistente e la duttilità delle strutture in "
        "cemento armato o in muratura mediante l'applicazione di materiali compositi fibrorinforzati (FRP) al fine di "
        "consentire un incremento dei carichi agenti e/o il miglioramento sismico. Comprende l'esecuzione di rinforzi "
        "di travi, pilastri, setti, solai, volte mediante placcaggi o fasciature di materiali compositi a matrice "
        "polimerica (FRP). Sono escluse le fondazioni speciali profonde e i rivestimenti in galleria, i quali si "
        "considerano inclusi nelle specifiche TOL Specializzate."
    ),
    "TOL.8": (
        "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di strutture, opere di ingegneria e "
        "manufatti realizzati interamente o nella maggior parte in legno, compresi elementi particolari quali ad "
        "esempio, in via esemplificativa e non esaustiva, strutture portanti, tamponature, infissi, rivestimenti, "
        "pareti, coperture, la impermeabilizzazione o copertura con tegole o similari, scale, pavimenti, pannellature, "
        "ecc. Si includono anche la eventuale verniciatura e/o protezione esterna o interna del legno."
    ),
    "TOL.9": (
        "Riguarda la nuova costruzione attraverso il metodo di scavo tradizionale e la manutenzione, la "
        "ristrutturazione e la messa in sicurezza delle opere d'arte in sotterraneo, qualsiasi sia il loro grado di "
        "importanza. Comprende in via esemplificativa gallerie naturali, trafori, passaggi sotterranei, tunnel, "
        "rivestimenti primari e definitivi, impermeabilizzazioni, strati separatori, segnaletica di emergenza, "
        "perforazioni e iniezioni, infilaggi sub orizzontali, armatura metallica e conglomerato cementizio per opere "
        "di sostegno e consolidamento, le centine e le opere di finitura. Sono esclusi: gli impianti elettrici e "
        "tecnologici per la sicurezza in galleria (Es: impianti di ventilazione, ecc.), pavimentazioni in conglomerato "
        "bituminoso e profili redirettivi, riconducibili alle T.O.L. Specializzate."
    ),
    "TOL.10": (
        "Riguarda la nuova costruzione attraverso il metodo di scavo meccanizzato. Comprende in via esemplificativa "
        "gallerie naturali, trafori, passaggi sotterranei, tunnel, rivestimenti, impermeabilizzazioni, strati "
        "separatori, segnaletica di emergenza, perforazioni e iniezioni, infilaggi sub orizzontali, armatura metallica "
        "e conglomerato cementizio per opere di sostegno e consolidamento, opere di finitura, ecc. Sono esclusi gli "
        "impianti elettrici e tecnologici per la sicurezza in galleria (Es: impianti di ventilazione, ecc.), "
        "pavimentazioni in conglomerato bituminoso e profili redirettivi, riconducibili alle T.O.L. Specializzate."
    ),
    "TOL.11": (
        "Riguarda la costruzione, la manutenzione o la ristrutturazione di interventi a rete, gli acquedotti, le "
        "fognature, i gasdotti, gli oleodotti, le torri piezometriche, la rete di distribuzione all'utente finale, "
        "che siano necessari per attuare il \"servizio idrico integrato\" ovvero per trasportare ai punti di "
        "utilizzazione fluidi aeriformi o liquidi. Include, in via esemplificativa e non esaustiva: la fornitura e la "
        "posa in opera delle tubazioni e dei manufatti idraulici in materiale plastico e di tutte le componenti "
        "accessorie, gli impianti elettromeccanici di sollevamento, realizzate all'aperto e/o in galleria. Sono da "
        "escludere: gli impianti (per ambienti interni) elettromeccanici, meccanici, idrico-sanitari, elettrici, "
        "elettronici e trasportatori, le strutture e i manufatti in acciaio, in cemento armato gettato in opera o "
        "prefabbricato, comprese le tubazioni in acciaio o in cemento armato, gli scavi e i movimenti terra, le "
        "demolizioni, la raccolta di materiali di risulta, la loro separazione, il conferimento e l'eventuale "
        "riciclaggio e qualsiasi lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
    ),
    "TOL.12": (
        "Riguarda la costruzione, la manutenzione o la ristrutturazione di interventi comunque realizzati in acque "
        "dolci e salate, che costituiscono terminali per la mobilità su \"acqua\" ovvero opere di difesa del "
        "territorio dalle stesse acque dolci o salate, compresa la pulizia o bonifica idraulica. Include, in via "
        "esemplificativa e non esaustiva: scavi in alveo, scavi per l'apertura di nuovi canali, formazione di rilevati "
        "arginali, realizzazione di scogliere e relativi strati di base e a protezione delle fondazioni, le "
        "perforazioni, le iniezioni di miscele di acqua e cemento e le tubazioni in resina per interventi di "
        "consolidamento, la fornitura e la posa in opera di gabbioni metallici, le lavorazioni finalizzate alla difesa "
        "e/o bonifica del mare e dei fiumi. Sono da escludere: gli impianti elettromeccanici, meccanici, "
        "idrico-sanitari, elettrici, telefonici, elettronici e di sollevamento, le strutture e i manufatti in legno, "
        "in acciaio, in cemento armato gettato in opera o prefabbricato, comprese le tubazioni in acciaio o in cemento "
        "armato, gli scavi e i movimenti terra diversi da quelli esplicitamente inclusi, le demolizioni, la raccolta "
        "di materiali di risulta, la loro separazione, il conferimento e l'eventuale riciclaggio e qualsiasi "
        "lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
    ),
    "TOL.13": (
        "Riguarda la costruzione, la manutenzione o la ristrutturazione degli interventi a rete che sono necessari "
        "per la produzione, distribuzione ad alta e media tensione e per la trasformazione e distribuzione a bassa "
        "tensione all'utente finale di energia elettrica, gli impianti fotovoltaici, gli impianti eolici, geotermici e "
        "gli impianti di cogenerazione; la costruzione, la manutenzione e la ristrutturazione degli impianti di "
        "pubblica illuminazione, da realizzare all'esterno degli edifici; la costruzione, la manutenzione o "
        "ristrutturazione degli impianti per la trazione elettrica di qualsiasi ferrovia, metropolitana o linea "
        "tranviaria. Include, in via esemplificativa e non esaustiva: le turbine, i generatori, i pannelli "
        "fotovoltaici, le centrali e le cabine di trasformazione, i conduttori e cavi elettrici per qualsiasi numero "
        "di fasi su tralicci, pali o interrati, le canalizzazioni, i sistemi di controllo e automazione, i quadri, "
        "gli switch, i trasformatori, gli isolatori, gli scaricatori di tensione, le unità di alimentazione, "
        "sezionamento e misura/diagnostica, gli interruttori, i raddrizzatori, le sospensioni, gli apparecchi di "
        "appoggio in gomma, i morsetti, gli impianti di messa a terra, gli apparecchi di illuminazione stradale, ecc. "
        "Sono da escludere: le strutture e i manufatti in acciaio (Es. tralicci, pali, ecc.), in cemento armato "
        "prefabbricato o gettato in opera (Es. fondazioni, muri, pozzetti, ecc.), gli scavi e i movimenti terra, le "
        "fondazioni profonde, le demolizioni e qualsiasi lavorazione o materiale direttamente riconducibile alle "
        "relative TOL Specializzate."
    ),
    "TOL.14": (
        "Riguarda la fornitura, l'installazione, la manutenzione o la ristrutturazione di un insieme di impianti "
        "elettrici, tecnologici, antintrusione, antincendio (esclusa la parte idraulica), telefonici, radiotelefonici, "
        "televisivi nonché di reti di trasmissione dati e simili, per fabbricati e per la sicurezza in galleria. "
        "Include, in via esemplificativa e non esaustiva: le cabine, gli armadi, i quadri elettrici, i cavi, le "
        "centraline di controllo a distanza, i rilevatori gas, le videocamere, gli apparecchi illuminanti da interno, "
        "i gruppi di continuità, ecc. Sono da escludere: gli impianti meccanici, termici, di condizionamento, idrico "
        "sanitari e trasportatori, le strutture e i manufatti in acciaio, in cemento armato gettato in opera o "
        "prefabbricato e in legno, gli scavi e i movimenti terra, le demolizioni e qualsiasi lavorazione o materiale "
        "direttamente riconducibile alle altre TOL Specializzate."
    ),
    "TOL.15": (
        "Riguarda la fornitura, l'installazione, la manutenzione o la ristrutturazione di impianti meccanici, "
        "idro-sanitari, del gas, antincendio (solo la parte idraulica), termici e per il condizionamento del clima, "
        "pneumatici e di sollevamento e trasporto, per fabbricati e per la sicurezza in galleria. Include, in via "
        "esemplificativa e non esaustiva: le tubazioni in materiale plastico di adduzione e di scarico, i raccordi, "
        "le valvole, le pompe, le caldaie, i condizionatori, i sistemi di ventilazione dell'aria, i filtri, i "
        "sanitari, le cassette di scarico, gli idranti, gli ascensori, le scale mobili, ecc. Sono da escludere: le "
        "strutture e i manufatti in acciaio, in cemento armato gettato in opera o prefabbricato, in legno, gli scavi "
        "e i movimenti terra, le demolizioni, la raccolta di materiali di risulta e il loro conferimento, non "
        "direttamente relazionati con gli stessi impianti e qualsiasi lavorazione o materiale direttamente "
        "riconducibile alle altre TOL Specializzate."
    ),
    "TOL.16": (
        "Riguarda la fornitura, l'installazione, la manutenzione o la ristrutturazione di impianti di "
        "potabilizzazione e depurazione. Include, in via esemplificativa e non esaustiva: le tubazioni in materiale "
        "plastico di adduzione e di scarico, i raccordi, le valvole, le pompe, i filtri, la ghiaia e sabbia, le "
        "centrifughe, le coclee, i ventilatori, ecc. Sono da escludere: le strutture e i manufatti in acciaio, in "
        "cemento armato gettato in opera o prefabbricato, in legno, i movimenti terra, le demolizioni non direttamente "
        "relazionati con gli stessi impianti e qualsiasi lavorazione o materiale direttamente riconducibile alle "
        "altre TOL Specializzate."
    ),
    "TOL.17": (
        "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di impianti di telecomunicazioni e gli "
        "impianti automatici per la segnaletica luminosa e la sicurezza del traffico stradale, ferroviario, "
        "metropolitano o tranviario, aeroportuale, compreso il rilevamento e l'elaborazione delle informazioni. "
        "Include, in via esemplificativa e non esaustiva: le tecnologie hardware e software di elaborazione dei dati "
        "per il controllo a distanza, i sistemi di radiotrasmissione dei dati, i quadri, gli apparecchi di "
        "segnalazione luminosa, i pannelli a messaggio variabile, i sistemi di automazione e manovra elettrica, i "
        "sistemi di alimentazione, i sistemi di monitoraggio e diagnostica, i cavi elettrici e di trasmissione dati, "
        "le canalizzazioni. Sono da escludere: le strutture e i manufatti in acciaio (Es. tralicci, pali, ecc.), in "
        "cemento armato gettato in opera o prefabbricato (Es. fondazioni, muri, pozzetti, ecc.), gli scavi e i "
        "movimenti terra, le demolizioni, la raccolta di materiali di risulta e il loro conferimento e qualsiasi "
        "lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
    ),
    "TOL.18": (
        "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione dei binari per qualsiasi ferrovia, "
        "metropolitana o linea tranviaria. Include, in via esemplificativa e non esaustiva: la nuova costruzione, il "
        "rinnovo, il risanamento e la demolizione di binari, la posa e la rimozione del ballast, di traverse, rotaie, "
        "giunti, scambi, paraurti, ecc.; il taglio, la molatura e la saldatura di rotaie e scambi, il livellamento "
        "del ballast, ecc. Sono da escludere: la fornitura e lo smaltimento di ballast, di strutture e i manufatti in "
        "acciaio (Es. rotaie, scambi, paraurti, ecc.), e in cemento armato gettato in opera o prefabbricato (Es. "
        "traverse in c.a.p., muretti paraballast, ecc.), gli scavi e i movimenti terra, le demolizioni di opere "
        "civili, la raccolta di terreni di risulta e residui di demolizioni ed il loro smaltimento e qualsiasi "
        "lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
    ),
    "TOL.19": (
        "Riguarda la costruzione di opere destinate a trasferire i carichi di manufatti poggianti su terreni non "
        "idonei a reggere i carichi stessi, di opere destinate a conferire ai terreni caratteristiche di resistenza e "
        "di indeformabilità tali da rendere stabili l'imposta dei manufatti e da prevenire dissesti geologici, di "
        "opere per rendere antisismiche le strutture esistenti e funzionanti e l'esecuzione di indagini geognostiche "
        "ed esplorazioni del sottosuolo con mezzi speciali, anche ai fini ambientali, compreso il prelievo di campioni "
        "di terreno o di roccia e l'esecuzione di prove in situ. Comprende in via esemplificativa e non esaustiva: "
        "l'esecuzione di pali, micropali, palancolate e diaframmi di qualsiasi tipo, di sottofondazioni, di palificate "
        "e muri di sostegno speciali, di ancoraggi, di opere per ripristinare la funzionalità statica delle strutture, "
        "di pozzi, di opere per garantire la stabilità dei pendii e di lavorazioni speciali per il prosciugamento, "
        "l'impermeabilizzazione ed il consolidamento di terreni e dei piani di posa dei rilevati. Sono compresi "
        "inoltre i monitoraggi geotecnici e strutturali e tutte le relative attrezzature, sondaggi geognostici, scavi "
        "esplorativi e prelievi di aggregati."
    ),
    "TOL.20": (
        "Riguarda lo smaltimento o recupero a discarica di qualsiasi tipo di rifiuto pericoloso o non pericoloso, "
        "prodotto ed autorizzato in ogni singolo progetto, costituito, in via esemplificativa e non esaustiva, da "
        "terre da scavi o perforazioni a cielo aperto, da scavi o perforazioni nel sottosuolo, da pietrisco di "
        "massicciate ferroviarie e dalle operazioni di demolizione, per i quali è particolarmente difficile "
        "determinare la specifica tipologia e quantità."
    ),
}

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
    descriptions: dict = None,
):
    f = ifcopenshell.file(schema="IFC4X3")

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
        kwargs = dict(Identification=code, Name=name, ReferencedSource=cls)
        if descriptions and code in descriptions:
            kwargs["Description"] = descriptions[code]
        f.create_entity("IfcClassificationReference", **kwargs)

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
        descriptions=_TOL_DESCRIPTIONS,
    )
