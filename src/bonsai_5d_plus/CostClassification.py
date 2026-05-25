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

import os
import textwrap
import bpy
import ifcopenshell
import ifcopenshell.api.classification
import ifcopenshell.util.classification
import ifcopenshell.util.cost

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


# ---------------------------------------------------------------------------
# Load classification systems from src/data/classifications/*.ifc
# ---------------------------------------------------------------------------

_CLASSIFICATIONS_DIR = os.path.join(os.path.dirname(__file__), "data", "classifications")


def _load_systems():
    """Return {key: (ifc_name, label, [(code, name), ...], {code: desc})} from IFC files."""
    systems = {}
    if not os.path.isdir(_CLASSIFICATIONS_DIR):
        return systems
    for fname in sorted(os.listdir(_CLASSIFICATIONS_DIR)):
        if not fname.lower().endswith(".ifc"):
            continue
        key = os.path.splitext(fname)[0]
        path = os.path.join(_CLASSIFICATIONS_DIR, fname)
        try:
            f = ifcopenshell.open(path)
            clss = f.by_type("IfcClassification")
            if not clss:
                continue
            ifc_name = clss[0].Name or key
            cats = []
            descs = {}
            for ref in f.by_type("IfcClassificationReference"):
                ident = getattr(ref, "Identification", None) or getattr(ref, "ItemReference", None) or ""
                name = ref.Name or ident
                desc = getattr(ref, "Description", None) or ""
                if ident:
                    cats.append((ident, name))
                    if desc:
                        descs[ident] = desc
            systems[key] = (ifc_name, key, cats, descs)
        except Exception as e:
            print(f"[CostClassification] Cannot load {fname}: {e}")
    return systems


# Extended descriptions (declaratorie) per classificazioni che non le espongono via IFC4.
# Structured as {file_stem: {code: description}}.
_BUILTIN_DESCRIPTIONS = {
    "TOL": {
        "TOL.1": (
            "Riguarda la nuova costruzione, la manutenzione, la ristrutturazione o il consolidamento di edifici civili "
            "e industriali non soggetti a tutela dei beni culturali quali, in via esemplificativa, le residenze, le "
            "carceri, le scuole, le caserme, gli uffici, i teatri, gli ospedali, gli stadi, gli edifici per le "
            "industrie, gli edifici per parcheggi, le stazioni ferroviarie e metropolitane e gli edifici aeroportuali. "
            "Include, in via esemplificativa e non esaustiva: infissi e rivestimenti interni ed esterni, "
            "pavimentazioni, massetti e sottofondi, solai (esclusi quelli interamente in cemento armato), altri "
            "manufatti in materie plastiche, materiali vetrosi e simili, murature e tramezzature comprensive di "
            "intonacatura, rasatura, tinteggiatura, verniciatura, opere di finitura quali isolamenti termici e "
            "acustici, controsoffittature, barriere al fuoco e opere di impermeabilizzazione, facciate continue e "
            "coperture in alluminio, apparecchi di appoggio in gomma. Sono da escludere: impianti elettrici, "
            "tecnologici, radiotelefonici, antintrusione, meccanici, termici, di condizionamento, idrico sanitari e "
            "trasportatori, le strutture e i manufatti in legno, in acciaio (travi, coperture, ecc.), in cemento "
            "armato gettato in opera o prefabbricato (pilastri, travi, pozzetti, serbatoi pensili e silos), gli scavi "
            "e i movimenti terra, le demolizioni, la raccolta di materiali di risulta e il loro smaltimento e "
            "qualsiasi lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
        ),
        "TOL.2": (
            "Riguarda la manutenzione, la ristrutturazione o il consolidamento di edifici civili e industriali "
            "soggetti a tutela dei beni culturali quali, in via esemplificativa, le residenze, le carceri, le scuole, "
            "gli ospedali, le caserme, gli uffici, i teatri, gli stadi, gli edifici per le industrie, gli edifici per "
            "parcheggi, le stazioni ferroviarie e metropolitane e gli edifici aeroportuali. Include, in via "
            "esemplificativa e non esaustiva: infissi e rivestimenti interni ed esterni, pavimentazioni, massetti e "
            "sottofondi, solai (esclusi quelli interamente in cemento armato), altri manufatti in materie plastiche, "
            "materiali vetrosi e simili, murature e tramezzature comprensive di intonacatura, rasatura, tinteggiatura, "
            "verniciatura, opere di finitura quali isolamenti termici e acustici, controsoffittature, barriere al "
            "fuoco e opere di impermeabilizzazione, facciate continue e coperture in alluminio, apparecchi di "
            "appoggio in gomma. Sono da escludere: impianti elettrici, tecnologici, radiotelefonici, antintrusione, "
            "meccanici, termici, di condizionamento, idrico sanitari e trasportatori, le strutture e i manufatti in "
            "legno, in acciaio (travi, coperture, ecc.), in cemento armato gettato in opera o prefabbricato "
            "(pilastri, travi, pozzetti, serbatoi pensili e silos), gli scavi e i movimenti terra, le demolizioni, "
            "la raccolta di materiali di risulta e il loro smaltimento e qualsiasi lavorazione o materiale "
            "direttamente riconducibile alle TOL Specializzate."
        ),
        "TOL.3": (
            "Riguarda gli scavi archeologici e le attività strettamente connesse da eseguirsi sia in aree dichiarate "
            "di interesse culturale sia in aree non dichiarate, condotti secondo normativa vigente. Per scavi "
            "archeologici si intendono anche quelli preparatori alla nuova costruzione, alla ristrutturazione, al "
            "restauro ed alla manutenzione da progettarsi, eseguirsi ed effettuarsi da imprese in possesso dei "
            "requisiti e della manodopera specializzata, secondo normativa vigente. Sono altresì inclusi gli scavi "
            "archeologici subacquei. Riguarda interventi relativi alla conservazione, alla diagnostica, al "
            "monitoraggio, alla manutenzione e al restauro di beni culturali di qualsiasi genere e materiale in tutti "
            "i tipi di contesto - museale, archeologico, di cantiere e/o laboratorio - effettuati da imprese "
            "qualificate e mano d'opera specializzata secondo la normativa vigente. Include la lavorazione di beni "
            "culturali mobili, superfici decorate e materiali storicizzati di beni architettonici ed archeologici, di "
            "beni demoetnoantropologici e di qualsiasi altro bene di interesse culturale appartenente a soggetti "
            "pubblici e privati, come stabilito dal Dlgs 42/2004."
        ),
        "TOL.4": (
            "Riguarda lo scavo e i movimenti terra di qualsiasi genere, trincee e rilevati, ripristino, modifica e "
            "bonifica di volumi di terra, realizzati qualunque sia la natura del terreno da scavare, ripristinare e "
            "bonificare, i campionamenti di terreni e le analisi chimiche, le demolizioni in genere, compreso lo "
            "smontaggio di impianti, la demolizione completa di edifici e il taglio di strutture in cemento armato, "
            "le attività di raccolta dei materiali di risulta ed il loro conferimento, la realizzazione delle cunette, "
            "caditoie, canalette in terra o in calcestruzzo direttamente relazionate con i movimenti terra, la "
            "realizzazione del verde urbano, compresi gli arredi urbani e le opere a verde quali la realizzazione di "
            "tappeti erbosi, inerbimenti, la messa a dimora di piante arbustive o alberi, la piantagione di essenze "
            "arboree e la manutenzione del verde in generale, compresi i geotessuti, le geogriglie, le terre "
            "rinforzate, i materiali in grado di aumentare la capacità portante del rilevato, dune antirumore, la "
            "stabilizzazione a calce e/o cemento, il misto stabilizzato, il misto cementato e le trincee drenanti."
        ),
        "TOL.5": (
            "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di pavimentazioni in conglomerato "
            "bituminoso. Include, in via esemplificativa e non esaustiva: le pavimentazioni stradali, di piazzali e "
            "marciapiedi, le impermeabilizzazioni a base di materiali bituminosi di impalcati, la segnaletica "
            "orizzontale. Sono da escludere: le pavimentazioni in calcestruzzo, strutture e i manufatti in acciaio, "
            "in cemento armato gettato in opera o prefabbricato, gli scavi e i movimenti terra, le demolizioni, la "
            "raccolta di materiali di risulta e il loro smaltimento e qualsiasi lavorazione o materiale direttamente "
            "riconducibile alle TOL Specializzate."
        ),
        "TOL.6": (
            "Riguarda la produzione in stabilimenti industriali, il montaggio in situ e più in generale la nuova "
            "costruzione, la manutenzione e la ristrutturazione di strutture, opere di ingegneria e manufatti "
            "realizzati in acciaio, compresi gli edifici in carpenteria pesante e leggera, ponti, viadotti e "
            "profilati, lavorazioni e trattamenti protettivi delle strutture in acciaio, i dispositivi strutturali "
            "quali, in via esemplificativa e non esaustiva, qualsiasi tipologia di giunti di dilatazione, di "
            "apparecchi di appoggio, di dispositivi di ancoraggio e di ritegni antisismici, compresi elementi quali "
            "rotaie, paraurti ferroviari, dispositivi di sicurezza stradale in acciaio, barriere di sicurezza e "
            "fonoassorbenti, attenuatori, terminali, chiusure varchi, segnaletica stradale verticale, tralicci e "
            "pali, recinzioni, lamiere per copertura, chiusini, canalette, passerelle, portacavi, canali di gronda, "
            "portali stradali e ferroviari, reti paramassi, scale, tubi in acciaio di qualsiasi tipologia e "
            "applicazione. Comprende inoltre le coperture particolari quali per esempio le tensostrutture e le "
            "coperture geodetiche. Sono esclusi gli acciai d'armatura del calcestruzzo e i consolidamenti strutturali "
            "in galleria, i quali si considerano inclusi nelle specifiche TOL di riferimento."
        ),
        "TOL.7": (
            "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di strutture, opere di ingegneria "
            "e manufatti realizzati in cemento armato normale o precompresso, gettato in opera o prefabbricato, in "
            "elevazione o in fondazione, comprese le casseforme, l'acciaio di armatura e le reti d'acciaio "
            "elettrosaldate, compresi elementi particolari quali ad esempio, in via esemplificativa e non esaustiva, "
            "pavimentazioni in calcestruzzo, cunicoli, pozzetti, cordoli, tubi prefabbricati, traverse ferroviarie, "
            "barriere stradali tipo New Jersey ed altri profili redirettivi in calcestruzzo anche per gallerie "
            "stradali, blocchi di fondazione per pali, apparecchi di appoggio in gomma, pannelli di calcestruzzo "
            "prefabbricato, canalette ecc. Riguarda altresì la realizzazione di opere atte a migliorare la capacità "
            "resistente e la duttilità delle strutture in cemento armato o in muratura mediante l'applicazione di "
            "materiali compositi fibrorinforzati (FRP) al fine di consentire un incremento dei carichi agenti e/o il "
            "miglioramento sismico. Comprende l'esecuzione di rinforzi di travi, pilastri, setti, solai, volte "
            "mediante placcaggi o fasciature di materiali compositi a matrice polimerica (FRP). Sono escluse le "
            "fondazioni speciali profonde e i rivestimenti in galleria, i quali si considerano inclusi nelle "
            "specifiche TOL Specializzate."
        ),
        "TOL.8": (
            "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di strutture, opere di ingegneria "
            "e manufatti realizzati interamente o nella maggior parte in legno, compresi elementi particolari quali "
            "ad esempio, in via esemplificativa e non esaustiva, strutture portanti, tamponature, infissi, "
            "rivestimenti, pareti, coperture, la impermeabilizzazione o copertura con tegole o similari, scale, "
            "pavimenti, pannellature, ecc. Si includono anche la eventuale verniciatura e/o protezione esterna o "
            "interna del legno."
        ),
        "TOL.9": (
            "Riguarda la nuova costruzione attraverso il metodo di scavo tradizionale e la manutenzione, la "
            "ristrutturazione e la messa in sicurezza delle opere d'arte in sotterraneo, qualsiasi sia il loro grado "
            "di importanza. Comprende in via esemplificativa gallerie naturali, trafori, passaggi sotterranei, "
            "tunnel, rivestimenti primari e definitivi, impermeabilizzazioni, strati separatori, segnaletica di "
            "emergenza, perforazioni e iniezioni, infilaggi sub orizzontali, armatura metallica e conglomerato "
            "cementizio per opere di sostegno e consolidamento, le centine e le opere di finitura. Sono esclusi: "
            "gli impianti elettrici e tecnologici per la sicurezza in galleria (Es: impianti di ventilazione, ecc.), "
            "pavimentazioni in conglomerato bituminoso e profili redirettivi, riconducibili alle T.O.L. Specializzate."
        ),
        "TOL.10": (
            "Riguarda la nuova costruzione attraverso il metodo di scavo meccanizzato. Comprende in via "
            "esemplificativa gallerie naturali, trafori, passaggi sotterranei, tunnel, rivestimenti, "
            "impermeabilizzazioni, strati separatori, segnaletica di emergenza, perforazioni e iniezioni, infilaggi "
            "sub orizzontali, armatura metallica e conglomerato cementizio per opere di sostegno e consolidamento, "
            "opere di finitura, ecc. Sono esclusi gli impianti elettrici e tecnologici per la sicurezza in galleria "
            "(Es: impianti di ventilazione, ecc.), pavimentazioni in conglomerato bituminoso e profili redirettivi, "
            "riconducibili alle T.O.L. Specializzate."
        ),
        "TOL.11": (
            "Riguarda la costruzione, la manutenzione o la ristrutturazione di interventi a rete, gli acquedotti, le "
            "fognature, i gasdotti, gli oleodotti, le torri piezometriche, la rete di distribuzione all'utente "
            "finale, che siano necessari per attuare il \"servizio idrico integrato\" ovvero per trasportare ai punti "
            "di utilizzazione fluidi aeriformi o liquidi. Include, in via esemplificativa e non esaustiva: la "
            "fornitura e la posa in opera delle tubazioni e dei manufatti idraulici in materiale plastico e di tutte "
            "le componenti accessorie, gli impianti elettromeccanici di sollevamento, realizzate all'aperto e/o in "
            "galleria. Sono da escludere: gli impianti (per ambienti interni) elettromeccanici, meccanici, "
            "idrico-sanitari, elettrici, elettronici e trasportatori, le strutture e i manufatti in acciaio, in "
            "cemento armato gettato in opera o prefabbricato, comprese le tubazioni in acciaio o in cemento armato, "
            "gli scavi e i movimenti terra, le demolizioni, la raccolta di materiali di risulta, la loro separazione, "
            "il conferimento e l'eventuale riciclaggio e qualsiasi lavorazione o materiale direttamente riconducibile "
            "alle TOL Specializzate."
        ),
        "TOL.12": (
            "Riguarda la costruzione, la manutenzione o la ristrutturazione di interventi comunque realizzati in "
            "acque dolci e salate, che costituiscono terminali per la mobilità su \"acqua\" ovvero opere di difesa "
            "del territorio dalle stesse acque dolci o salate, compresa la pulizia o bonifica idraulica. Include, in "
            "via esemplificativa e non esaustiva: scavi in alveo, scavi per l'apertura di nuovi canali, formazione di "
            "rilevati arginali, realizzazione di scogliere e relativi strati di base e a protezione delle fondazioni, "
            "le perforazioni, le iniezioni di miscele di acqua e cemento e le tubazioni in resina per interventi di "
            "consolidamento, la fornitura e la posa in opera di gabbioni metallici, le lavorazioni finalizzate alla "
            "difesa e/o bonifica del mare e dei fiumi. Sono da escludere: gli impianti elettromeccanici, meccanici, "
            "idrico-sanitari, elettrici, telefonici, elettronici e di sollevamento, le strutture e i manufatti in "
            "legno, in acciaio, in cemento armato gettato in opera o prefabbricato, comprese le tubazioni in acciaio "
            "o in cemento armato, gli scavi e i movimenti terra diversi da quelli esplicitamente inclusi, le "
            "demolizioni, la raccolta di materiali di risulta, la loro separazione, il conferimento e l'eventuale "
            "riciclaggio e qualsiasi lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
        ),
        "TOL.13": (
            "Riguarda la costruzione, la manutenzione o la ristrutturazione degli interventi a rete che sono "
            "necessari per la produzione, distribuzione ad alta e media tensione e per la trasformazione e "
            "distribuzione a bassa tensione all'utente finale di energia elettrica, gli impianti fotovoltaici, gli "
            "impianti eolici, geotermici e gli impianti di cogenerazione; la costruzione, la manutenzione e la "
            "ristrutturazione degli impianti di pubblica illuminazione, da realizzare all'esterno degli edifici; la "
            "costruzione, la manutenzione o ristrutturazione degli impianti per la trazione elettrica di qualsiasi "
            "ferrovia, metropolitana o linea tranviaria. Include, in via esemplificativa e non esaustiva: le turbine, "
            "i generatori, i pannelli fotovoltaici, le centrali e le cabine di trasformazione, i conduttori e cavi "
            "elettrici per qualsiasi numero di fasi su tralicci, pali o interrati, le canalizzazioni, i sistemi di "
            "controllo e automazione, i quadri, gli switch, i trasformatori, gli isolatori, gli scaricatori di "
            "tensione, le unità di alimentazione, sezionamento e misura/diagnostica, gli interruttori, i "
            "raddrizzatori, le sospensioni, gli apparecchi di appoggio in gomma, i morsetti, gli impianti di messa a "
            "terra, gli apparecchi di illuminazione stradale, ecc. Sono da escludere: le strutture e i manufatti in "
            "acciaio (Es. tralicci, pali, ecc.), in cemento armato prefabbricato o gettato in opera (Es. fondazioni, "
            "muri, pozzetti, ecc.), gli scavi e i movimenti terra, le fondazioni profonde, le demolizioni e qualsiasi "
            "lavorazione o materiale direttamente riconducibile alle relative TOL Specializzate."
        ),
        "TOL.14": (
            "Riguarda la fornitura, l'installazione, la manutenzione o la ristrutturazione di un insieme di impianti "
            "elettrici, tecnologici, antintrusione, antincendio (esclusa la parte idraulica), telefonici, "
            "radiotelefonici, televisivi nonché di reti di trasmissione dati e simili, per fabbricati e per la "
            "sicurezza in galleria. Include, in via esemplificativa e non esaustiva: le cabine, gli armadi, i quadri "
            "elettrici, i cavi, le centraline di controllo a distanza, i rilevatori gas, le videocamere, gli "
            "apparecchi illuminanti da interno, i gruppi di continuità, ecc. Sono da escludere: gli impianti "
            "meccanici, termici, di condizionamento, idrico sanitari e trasportatori, le strutture e i manufatti in "
            "acciaio, in cemento armato gettato in opera o prefabbricato e in legno, gli scavi e i movimenti terra, "
            "le demolizioni e qualsiasi lavorazione o materiale direttamente riconducibile alle altre TOL Specializzate."
        ),
        "TOL.15": (
            "Riguarda la fornitura, l'installazione, la manutenzione o la ristrutturazione di impianti meccanici, "
            "idro-sanitari, del gas, antincendio (solo la parte idraulica), termici e per il condizionamento del "
            "clima, pneumatici e di sollevamento e trasporto, per fabbricati e per la sicurezza in galleria. Include, "
            "in via esemplificativa e non esaustiva: le tubazioni in materiale plastico di adduzione e di scarico, i "
            "raccordi, le valvole, le pompe, le caldaie, i condizionatori, i sistemi di ventilazione dell'aria, i "
            "filtri, i sanitari, le cassette di scarico, gli idranti, gli ascensori, le scale mobili, ecc. Sono da "
            "escludere: le strutture e i manufatti in acciaio, in cemento armato gettato in opera o prefabbricato, in "
            "legno, gli scavi e i movimenti terra, le demolizioni, la raccolta di materiali di risulta e il loro "
            "conferimento, non direttamente relazionati con gli stessi impianti e qualsiasi lavorazione o materiale "
            "direttamente riconducibile alle altre TOL Specializzate."
        ),
        "TOL.16": (
            "Riguarda la fornitura, l'installazione, la manutenzione o la ristrutturazione di impianti di "
            "potabilizzazione e depurazione. Include, in via esemplificativa e non esaustiva: le tubazioni in "
            "materiale plastico di adduzione e di scarico, i raccordi, le valvole, le pompe, i filtri, la ghiaia e "
            "sabbia, le centrifughe, le coclee, i ventilatori, ecc. Sono da escludere: le strutture e i manufatti in "
            "acciaio, in cemento armato gettato in opera o prefabbricato, in legno, i movimenti terra, le demolizioni "
            "non direttamente relazionati con gli stessi impianti e qualsiasi lavorazione o materiale direttamente "
            "riconducibile alle altre TOL Specializzate."
        ),
        "TOL.17": (
            "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione di impianti di telecomunicazioni e "
            "gli impianti automatici per la segnaletica luminosa e la sicurezza del traffico stradale, ferroviario, "
            "metropolitano o tranviario, aeroportuale, compreso il rilevamento e l'elaborazione delle informazioni. "
            "Include, in via esemplificativa e non esaustiva: le tecnologie hardware e software di elaborazione dei "
            "dati per il controllo a distanza, i sistemi di radiotrasmissione dei dati, i quadri, gli apparecchi di "
            "segnalazione luminosa, i pannelli a messaggio variabile, i sistemi di automazione e manovra elettrica, i "
            "sistemi di alimentazione, i sistemi di monitoraggio e diagnostica, i cavi elettrici e di trasmissione "
            "dati, le canalizzazioni. Sono da escludere: le strutture e i manufatti in acciaio (Es. tralicci, pali, "
            "ecc.), in cemento armato gettato in opera o prefabbricato (Es. fondazioni, muri, pozzetti, ecc.), gli "
            "scavi e i movimenti terra, le demolizioni, la raccolta di materiali di risulta e il loro conferimento e "
            "qualsiasi lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
        ),
        "TOL.18": (
            "Riguarda la nuova costruzione, la manutenzione o la ristrutturazione dei binari per qualsiasi ferrovia, "
            "metropolitana o linea tranviaria. Include, in via esemplificativa e non esaustiva: la nuova costruzione, "
            "il rinnovo, il risanamento e la demolizione di binari, la posa e la rimozione del ballast, di traverse, "
            "rotaie, giunti, scambi, paraurti, ecc.; il taglio, la molatura e la saldatura di rotaie e scambi, il "
            "livellamento del ballast, ecc. Sono da escludere: la fornitura e lo smaltimento di ballast, di strutture "
            "e i manufatti in acciaio (Es. rotaie, scambi, paraurti, ecc.), e in cemento armato gettato in opera o "
            "prefabbricato (Es. traverse in c.a.p., muretti paraballast, ecc.), gli scavi e i movimenti terra, le "
            "demolizioni di opere civili, la raccolta di terreni di risulta e residui di demolizioni ed il loro "
            "smaltimento e qualsiasi lavorazione o materiale direttamente riconducibile alle TOL Specializzate."
        ),
        "TOL.19": (
            "Riguarda la costruzione di opere destinate a trasferire i carichi di manufatti poggianti su terreni non "
            "idonei a reggere i carichi stessi, di opere destinate a conferire ai terreni caratteristiche di "
            "resistenza e di indeformabilità tali da rendere stabili l'imposta dei manufatti e da prevenire dissesti "
            "geologici, di opere per rendere antisismiche le strutture esistenti e funzionanti e l'esecuzione di "
            "indagini geognostiche ed esplorazioni del sottosuolo con mezzi speciali, anche ai fini ambientali, "
            "compreso il prelievo di campioni di terreno o di roccia e l'esecuzione di prove in situ. Comprende in "
            "via esemplificativa e non esaustiva: l'esecuzione di pali, micropali, palancolate e diaframmi di "
            "qualsiasi tipo, di sottofondazioni, di palificate e muri di sostegno speciali, di ancoraggi, di opere "
            "per ripristinare la funzionalità statica delle strutture, di pozzi, di opere per garantire la stabilità "
            "dei pendii e di lavorazioni speciali per il prosciugamento, l'impermeabilizzazione ed il consolidamento "
            "di terreni e dei piani di posa dei rilevati. Sono compresi inoltre i monitoraggi geotecnici e "
            "strutturali e tutte le relative attrezzature, sondaggi geognostici, scavi esplorativi e prelievi di "
            "aggregati."
        ),
        "TOL.20": (
            "Riguarda lo smaltimento o recupero a discarica di qualsiasi tipo di rifiuto pericoloso o non pericoloso, "
            "prodotto ed autorizzato in ogni singolo progetto, costituito, in via esemplificativa e non esaustiva, da "
            "terre da scavi o perforazioni a cielo aperto, da scavi o perforazioni nel sottosuolo, da pietrisco di "
            "massicciate ferroviarie e dalle operazioni di demolizione, per i quali è particolarmente difficile "
            "determinare la specifica tipologia e quantità."
        ),
    },
}


# Built once at import time — reloading the addon refreshes this
_SYSTEMS = _load_systems()

_BY_CODE = {
    key: {code: name for code, name in cats}
    for key, (_, _, cats, _) in _SYSTEMS.items()
}

_DESCRIPTIONS = {
    key: descs
    for key, (_, _, _, descs) in _SYSTEMS.items()
}

_ENUM_ITEMS = {
    key: [("", "—", "")] + [
        (code, f"{code}  –  {name}", _DESCRIPTIONS.get(key, {}).get(code, name))
        for code, name in cats
    ]
    for key, (_, _, cats, _) in _SYSTEMS.items()
}


def _prop_name(key):
    return f"cc_{key}_category"


# ---------------------------------------------------------------------------
# Generic IFC helpers
# ---------------------------------------------------------------------------

def _get_or_create_classification(file, ifc_name):
    for cls in file.by_type("IfcClassification"):
        if cls.Name == ifc_name:
            return cls
    return ifcopenshell.api.classification.add_classification(file, classification=ifc_name)


def _get_code(cost_item, ifc_name):
    for ref in ifcopenshell.util.classification.get_references(cost_item):
        cls = ifcopenshell.util.classification.get_classification(ref)
        if cls and cls.Name == ifc_name:
            return getattr(ref, "Identification", None) or getattr(ref, "ItemReference", None) or ""
    return ""


def _set_code(file, cost_item, ifc_name, code, code_names):
    for ref in list(ifcopenshell.util.classification.get_references(cost_item)):
        cls = ifcopenshell.util.classification.get_classification(ref)
        if cls and cls.Name == ifc_name:
            ifcopenshell.api.classification.remove_reference(file, reference=ref, products=[cost_item])

    if not code:
        return

    classification = _get_or_create_classification(file, ifc_name)
    ifcopenshell.api.classification.add_reference(
        file,
        products=[cost_item],
        classification=classification,
        identification=code,
        name=code_names.get(code, code),
    )


# ---------------------------------------------------------------------------
# Total + summary traversal
# ---------------------------------------------------------------------------

def _get_item_total(cost_item):
    rate = 0.0
    for cv in (cost_item.CostValues or []):
        try:
            v = cv.AppliedValue
            if v is not None:
                rate += float(v.wrappedValue if hasattr(v, "wrappedValue") else v)
        except Exception:
            pass
    qty = 0.0
    for cq in (cost_item.CostQuantities or []):
        for attr in ("LengthValue", "AreaValue", "VolumeValue", "WeightValue", "CountValue", "TimeValue"):
            v = getattr(cq, attr, None)
            if v is not None:
                try:
                    qty += float(v)
                except Exception:
                    pass
                break
    return rate * qty if qty else rate


def _collect_totals(cost_item, inherited_code, ifc_name, accumulator):
    """Traverse propagating classification code downward; only leaf values counted."""
    code = _get_code(cost_item, ifc_name) or inherited_code
    children = [c for rel in (cost_item.IsNestedBy or []) for c in rel.RelatedObjects]
    if not children:
        key = code or "__none__"
        accumulator[key] = accumulator.get(key, 0.0) + _get_item_total(cost_item)
    else:
        for child in children:
            _collect_totals(child, code, ifc_name, accumulator)


def _build_summary(file, schedule_id, ifc_name):
    schedule = file.by_id(int(schedule_id))
    acc = {}
    for root in ifcopenshell.util.cost.get_root_cost_items(schedule):
        _collect_totals(root, "", ifc_name, acc)
    return acc


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class CC_OT_SetCode(*_IfcOperatorBase):
    """Assign the selected classification code to the active cost item."""
    bl_idname = "cost_classification.set_code"
    bl_label = "Assign Classification"
    bl_options = {"REGISTER", "UNDO"}

    system: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        ifc_name, _, cats, _ = _SYSTEMS[self.system]
        code = getattr(context.scene, _prop_name(self.system), "")
        _set_code(file, cost_item, ifc_name, code, {c: n for c, n in cats})


class CC_OT_ClearCode(*_IfcOperatorBase):
    """Remove the classification from the active cost item."""
    bl_idname = "cost_classification.clear_code"
    bl_label = "Clear Classification"
    bl_options = {"REGISTER", "UNDO"}

    system: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        ifc_name, _, cats, _ = _SYSTEMS[self.system]
        _set_code(file, cost_item, ifc_name, "", {c: n for c, n in cats})


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class CostClassificationPanel(bpy.types.Panel):
    bl_label = "Cost Item Classification"
    bl_idname = "SCENE_PT_cost_classification"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        if not _SYSTEMS:
            layout.label(text="Nessun sistema di classificazione trovato.", icon="INFO")
            layout.label(text=f"Cartella: {_CLASSIFICATIONS_DIR}")
            return

        try:
            from bonsai import tool
            file = tool.Ifc.get()
        except Exception:
            layout.label(text="Bonsai non disponibile.", icon="ERROR")
            return

        if not file:
            layout.label(text="Nessun file IFC caricato.", icon="INFO")
            return

        props = context.scene.BIMCostProperties
        if props.active_cost_schedule_id == 0:
            layout.label(text="Nessun cost schedule attivo.", icon="INFO")
            return

        cost_item = None
        if props.active_cost_item:
            cost_item = file.by_id(props.active_cost_item.ifc_definition_id)

        # --- One box per classification system ---
        for system_key, (ifc_name, label, _, _) in _SYSTEMS.items():
            by_code = _BY_CODE[system_key]
            descs = _DESCRIPTIONS.get(system_key, {})

            box = layout.box()
            row = box.row()
            row.label(text=label, icon="ASSET_MANAGER")

            if cost_item:
                current = _get_code(cost_item, ifc_name)
                if current:
                    row.label(text=current)
                    op = row.operator("cost_classification.clear_code", text="", icon="X")
                    op.system = system_key
                else:
                    row.label(text="—")

                if current and current in by_code:
                    box.label(text=by_code[current])
                    desc = descs.get(current, "")
                    if desc:
                        desc_col = box.column(align=True)
                        desc_col.scale_y = 0.7
                        for line in textwrap.wrap(desc, 60):
                            desc_col.label(text=line)

                row2 = box.row(align=True)
                row2.prop(context.scene, _prop_name(system_key), text="")
                op = row2.operator("cost_classification.set_code", text="", icon="CHECKMARK")
                op.system = system_key
            else:
                box.label(text="Nessuna voce attiva.", icon="INFO")

        # --- Summary ---
        layout.separator()
        layout.label(text="Riepilogo schedule:", icon="LINENUMBERS_ON")
        layout.prop(context.scene, "cc_summary_system", text="Sistema")

        summary_key = context.scene.cc_summary_system
        if summary_key not in _SYSTEMS:
            return
        ifc_name, _, _, _ = _SYSTEMS[summary_key]
        by_code = _BY_CODE[summary_key]

        totals = _build_summary(file, props.active_cost_schedule_id, ifc_name)
        if not totals:
            layout.label(text="Nessuna voce trovata.", icon="INFO")
            return

        grand_total = sum(totals.values())
        box = layout.box()

        classified = sorted(k for k in totals if k != "__none__")
        if "__none__" in totals:
            classified.append("__none__")

        for key in classified:
            amount = totals[key]
            pct = (amount / grand_total * 100) if grand_total else 0.0
            split = box.split(factor=0.30)
            if key == "__none__":
                split.label(text="(non classif.)", icon="QUESTION")
            else:
                split.label(text=key)
            split2 = split.split(factor=0.62)
            split2.label(text=f"{amount:,.2f}")
            split2.label(text=f"{pct:.1f}%")

        box.separator()
        split = box.split(factor=0.30)
        split.label(text="TOTALE")
        split2 = split.split(factor=0.62)
        split2.label(text=f"{grand_total:,.2f}")
        split2.label(text="100%")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = [
    CC_OT_SetCode,
    CC_OT_ClearCode,
    CostClassificationPanel,
]

class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()

    for key, (ifc_name, label, _, _) in _SYSTEMS.items():
        setattr(
            bpy.types.Scene,
            _prop_name(key),
            bpy.props.EnumProperty(
                name=f"Categoria {label}",
                description=ifc_name,
                items=_ENUM_ITEMS[key],
                default="",
            ),
        )

    if _SYSTEMS:
        bpy.types.Scene.cc_summary_system = bpy.props.EnumProperty(
            name="Sistema di classificazione",
            items=[(key, f"{key} – {ifc_name}", ifc_name) for key, (ifc_name, _, _, _) in _SYSTEMS.items()],
            default=next(iter(_SYSTEMS)),
        )


def unregister():
    class_unregister()
    for key in _SYSTEMS:
        prop = _prop_name(key)
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    if hasattr(bpy.types.Scene, "cc_summary_system"):
        del bpy.types.Scene.cc_summary_system
