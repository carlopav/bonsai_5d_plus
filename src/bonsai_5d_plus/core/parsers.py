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

"""Pure-Python price list parser classes — zero bpy dependency.

Imported by module/rate_list and module/import_export.
"""

from typing import List, TypedDict


class XmlRateItem(TypedDict):
    index: int
    level: int
    is_parent: bool
    parents: str
    id: str
    name: str
    desc: str
    unit: str
    value: float
    labor: float
    equipment: float
    materials: float
    safety: float


class PriceListParser:
    title: str
    desc: str
    year: str
    language: []
    xml_rate_list: List[XmlRateItem]

    def __init__(self):
        self.xml_rate_list = []
        self.title = ""
        self.year = ""

    @staticmethod
    def get_xml_content(filename):
        with open(filename, "r", errors="ignore", encoding="utf8") as file:
            data = file.read()
        return data

    def parse_header(self, root):
        pass

    def parse_items(self, xml_content):
        pass

    def clean_xml_content(self, data):
        import re
        return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", data)

    def get_stripped_xml_namespaces_root(self, data):
        import xml.etree.ElementTree as ET
        from io import StringIO

        it = ET.iterparse(StringIO(data))
        for _, el in it:
            if isinstance(el.tag, str) and "}" in el.tag:
                el.tag = el.tag.rpartition("}")[-1]
        return it.root

    def get_root(self, data):
        import xml.etree.ElementTree as ET
        from io import StringIO

        tree = ET.parse(StringIO(data))
        return tree.getroot()

    def clean_string(self, text):
        # sistema_cose (da Leeno)
        text = text.replace("\t", " ").replace("Ã¨", "è").replace("", "")
        text = text.replace("Â°", "°").replace("Ã", "à").replace(" $", "")
        text = text.replace("Ó", "à").replace("Þ", "é").replace("&#x13;", "")
        text = text.replace("&#xD;&#xA;", "").replace("&#xA;", "")
        text = text.replace("&apos;", "'").replace("&#x3;&#x1;", "")
        text = text.replace("\n \n", "\n")
        while "  " in text:
            text = text.replace("  ", " ")
        while "\n\n" in text:
            text = text.replace("\n\n", "\n")
        return text.strip()


class ParserXmlVeneto(PriceListParser):
    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)
        index = 0
        settori = root.findall("settore")
        for settore in settori:
            self.xml_rate_list.append(
                {
                    "index": index,
                    "level": 0,
                    "is_parent": True,
                    "parents": "",
                    "id": settore.attrib.get("cod", ""),
                    "name": settore.attrib.get("desc", ""),
                    "desc": "",
                    "unit": "",
                    "value": 0.0,
                    "labor": 0.0,
                    "equipment": 0.0,
                    "materials": 0.0,
                    "safety": 0.0,
                }
            )
            n_settore = index
            index += 1
            for capitolo in settore.findall("capitolo"):
                self.xml_rate_list.append(
                    {
                        "index": index,
                        "level": 1,
                        "is_parent": True,
                        "parents": str(n_settore),
                        "id": capitolo.attrib.get("cod", ""),
                        "name": capitolo.attrib.get("desc", ""),
                        "desc": "",
                        "unit": "",
                        "value": 0.0,
                        "labor": 0.0,
                        "equipment": 0.0,
                        "materials": 0.0,
                        "safety": 0.0,
                    }
                )
                n_capitolo = index
                index += 1
                for paragrafo in capitolo.findall("paragrafo"):
                    children = list(paragrafo)
                    para_name = (children[0].text or "") if len(children) > 0 else ""
                    para_desc = (children[1].text or "") if len(children) > 1 else ""
                    self.xml_rate_list.append(
                        {
                            "index": index,
                            "level": 2,
                            "is_parent": True,
                            "parents": str(n_settore) + "," + str(n_capitolo),
                            "id": paragrafo.attrib.get("cod", ""),
                            "name": para_name,
                            "desc": para_desc,
                            "unit": "",
                            "value": 0.0,
                            "labor": 0.0,
                            "equipment": 0.0,
                            "materials": 0.0,
                            "safety": 0.0,
                        }
                    )
                    prezzi = paragrafo.findall(".//prezzo")
                    n_paragrafo = index
                    index += 1
                    for prezzo in prezzi:
                        try:
                            val = float(prezzo.attrib.get("val", 0))
                        except (ValueError, TypeError):
                            val = 0.0
                        try:
                            labor = float(prezzo.attrib.get("man", 0)) * val / 100
                        except (ValueError, TypeError):
                            labor = 0.0
                        self.xml_rate_list.append(
                            {
                                "index": index,
                                "level": 3,
                                "is_parent": False,
                                "parents": str(n_settore)
                                + ","
                                + str(n_capitolo)
                                + ","
                                + str(n_paragrafo),
                                "id": prezzo.attrib.get("cod", ""),
                                "name": prezzo.text or "",
                                "desc": para_desc,
                                "unit": prezzo.attrib.get("umi", ""),
                                "value": val,
                                "labor": labor,
                                "equipment": 0.0,
                                "materials": 0.0,
                                "safety": 0.0,
                            }
                        )
                        index += 1


class ParserXmlBasilicata(PriceListParser):
    """Parser per formato XML Basilicata (struttura gerarchica capitoli/categorie/voci/sottovoci)."""

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)

        pdf_el = root.find('pdf')
        if pdf_el is not None and pdf_el.text:
            titolo = pdf_el.text
            if titolo.endswith('.pdf'):
                titolo = titolo[:-4]
            self.title = ' '.join(titolo.split('_'))

        capitoli = root.find('capitoli')
        if capitoli is None:
            return

        index = 0

        for capitolo in capitoli:
            codice_sc = (capitolo.findtext('codice') or '').strip()
            desc_sc = (capitolo.findtext('descrizione') or '').strip()
            self.xml_rate_list.append({
                "index": index, "level": 0, "is_parent": True, "parents": "",
                "id": codice_sc, "name": desc_sc, "desc": "", "unit": "",
                "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
            })
            sc_idx = index
            index += 1

            categorie = capitolo.find('categorie')
            if categorie is None:
                continue

            for categoria in categorie:
                codice_cat_raw = (categoria.findtext('codice') or '').strip()
                codice_cat = codice_sc + '.' + codice_cat_raw
                desc_cat = (categoria.findtext('descrizione') or '').strip()
                self.xml_rate_list.append({
                    "index": index, "level": 1, "is_parent": True, "parents": str(sc_idx),
                    "id": codice_cat, "name": desc_cat, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                cat_idx = index
                index += 1

                voci = categoria.find('voci')
                if voci is None:
                    continue

                for voce in voci:
                    codice_v = (voce.findtext('codice') or '').strip()
                    codice_voce = codice_cat + '.' + codice_v
                    voce_desc = (voce.findtext('descrizione') or '').strip()

                    sottovoci = voce.find('sottovoci')
                    if sottovoci is None:
                        continue

                    for sottovoce in sottovoci:
                        codice_sv = (sottovoce.findtext('codice') or '').strip()
                        sv_desc = (sottovoce.findtext('descrizione') or '').strip()
                        codice = codice_voce + '.' + codice_sv
                        desc = self.clean_string(voce_desc + ('\n- ' + sv_desc if sv_desc else ''))

                        um_el = sottovoce.find('unitaMisura')
                        um = ''
                        if um_el is not None:
                            um = (um_el.findtext('codice') or '').strip()

                        prezzo = 0.0
                        try:
                            prezzo = float(sottovoce.findtext('prezzo') or 0)
                        except (ValueError, TypeError):
                            pass

                        labor = 0.0
                        try:
                            labor = float(sottovoce.findtext('manodopera') or 0) * prezzo / 100
                        except (ValueError, TypeError):
                            pass

                        self.xml_rate_list.append({
                            "index": index, "level": 2, "is_parent": False,
                            "parents": str(sc_idx) + ',' + str(cat_idx),
                            "id": codice, "name": desc, "desc": desc, "unit": um,
                            "value": prezzo, "labor": labor,
                            "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                        })
                        index += 1


class ParserXmlToscana(PriceListParser):
    """Parser per formato XML Toscana (PRT/EASY namespace variants).
    Usato anche da Calabria, Campania, Sardegna."""

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        xml_content = self._fix_namespace(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)

        intestazione = root.find('intestazione')
        if intestazione is not None:
            dettaglio = intestazione.find('dettaglio')
            if dettaglio is not None:
                anno = dettaglio.attrib.get('anno', '')
                area = dettaglio.attrib.get('area', '')
                self.title = f"{area} {anno}".strip()
                self.year = anno

        contenuto = root.find('Contenuto')
        if contenuto is None:
            return
        articoli = contenuto.findall('Articolo')

        index = 0
        supercat_idx = {}
        cat_idx = {}

        for articolo in articoli:
            codice = articolo.attrib.get('codice', '').strip()
            if not codice:
                continue
            parts = codice.split('.')
            if len(parts) < 2:
                continue
            codice_sc = parts[0]
            codice_cat = parts[0] + '.' + parts[1]

            supercat = (articolo.findtext('tipo') or articolo.findtext('livello1') or '').strip()
            cat = (articolo.findtext('capitolo') or articolo.findtext('livello2') or '').strip()

            if codice_sc not in supercat_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": codice_sc, "name": supercat or codice_sc, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                supercat_idx[codice_sc] = index
                index += 1

            if codice_cat not in cat_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 1, "is_parent": True,
                    "parents": str(supercat_idx[codice_sc]),
                    "id": codice_cat, "name": cat or codice_cat, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                cat_idx[codice_cat] = index
                index += 1

            voce = (articolo.findtext('voce') or articolo.findtext('livello3') or '').strip()
            art = (articolo.findtext('articolo') or articolo.findtext('livello4') or '').strip()
            desc = self.clean_string(voce + ('\n' + art if art else ''))

            um_el = articolo.find('um')
            um = (um_el.text or '').strip() if um_el is not None else ''
            prezzo = self._parse_price(articolo.findtext('prezzo') or '')

            labor = 0.0
            safety = 0.0
            analisi = articolo.find('Analisi')
            if analisi is not None:
                try:
                    safety = float(analisi.find('onerisicurezza').attrib.get('valore', 0))
                except Exception:
                    pass
                try:
                    labor = float(analisi.find('incidenzamanodopera').attrib.get('percentuale', 0)) * prezzo / 100
                except Exception:
                    pass

            self.xml_rate_list.append({
                "index": index, "level": 2, "is_parent": False,
                "parents": str(supercat_idx[codice_sc]) + ',' + str(cat_idx[codice_cat]),
                "id": codice, "name": desc, "desc": desc, "unit": um,
                "value": prezzo, "labor": labor, "equipment": 0.0, "materials": 0.0, "safety": safety,
            })
            index += 1

    @staticmethod
    def _fix_namespace(data):
        if '<EASY:' in data and 'xmlns:EASY=' not in data:
            tag = '<EASY:Prezzario>'
            pos = data.find(tag)
            if pos >= 0:
                ins = pos + len(tag) - 1
                data = data[:ins] + ' xmlns:EASY="mynamespace"' + data[ins:]
        if '<PRT:' in data and 'xmlns:PRT=' not in data:
            tag = '<PRT:Prezzario>'
            pos = data.find(tag)
            if pos >= 0:
                ins = pos + len(tag) - 1
                data = data[:ins] + ' xmlns:PRT="mynamespace"' + data[ins:]
        return data

    @staticmethod
    def _parse_price(text):
        if not text:
            return 0.0
        text = text.strip().replace(',', '.')
        parts = text.split('.')
        if len(parts) > 2:
            text = ''.join(parts[:-1]) + '.' + parts[-1]
        try:
            return float(text)
        except ValueError:
            return 0.0


class ParserXmlLiguria(PriceListParser):
    """Parser per formato XML Liguria (stessa struttura Toscana, differenze nei campi)."""

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)

        intestazione = root.find('intestazione')
        if intestazione is not None:
            dettaglio = intestazione.find('dettaglio')
            if dettaglio is not None:
                anno = dettaglio.attrib.get('anno', '')
                area = dettaglio.attrib.get('area', '')
                self.title = f"{area} {anno}".strip()
                self.year = anno

        contenuto = root.find('Contenuto')
        if contenuto is None:
            return
        articoli = contenuto.findall('Articolo')

        index = 0
        supercat_idx = {}
        cat_idx = {}

        for articolo in articoli:
            codice = articolo.attrib.get('codice', '').strip()
            if not codice:
                continue
            parts = codice.split('.')
            if len(parts) < 2:
                continue
            codice_sc = parts[0]
            codice_cat = parts[0] + '.' + parts[1]

            tipo_el = articolo.find('tipo')
            supercat = (tipo_el.text or '').strip() if tipo_el is not None else ''
            cap_el = articolo.find('capitolo')
            cat = (cap_el.text or '').strip() if cap_el is not None else ''

            if codice_sc not in supercat_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": codice_sc, "name": supercat or codice_sc, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                supercat_idx[codice_sc] = index
                index += 1

            if codice_cat not in cat_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 1, "is_parent": True,
                    "parents": str(supercat_idx[codice_sc]),
                    "id": codice_cat, "name": cat or codice_cat, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                cat_idx[codice_cat] = index
                index += 1

            voce_el = articolo.find('voce')
            voce = (voce_el.text or '').strip() if voce_el is not None else ''
            art_el = articolo.find('articolo')
            art = (art_el.text or '').strip() if art_el is not None else ''
            desc = self.clean_string(voce + ('\n- ' + art if art else ''))

            um_el = articolo.find('um')
            um = ''
            if um_el is not None and um_el.text:
                um = um_el.text.split('(')[-1].rstrip(')').strip()

            prezzo_el = articolo.find('prezzo')
            prezzo = 0.0
            if prezzo_el is not None:
                try:
                    prezzo = float(prezzo_el.attrib.get('valore', 0))
                except (ValueError, TypeError):
                    pass

            labor = 0.0
            mo_el = articolo.find('mo')
            if mo_el is not None and mo_el.text:
                try:
                    labor = float(mo_el.text) * prezzo / 100
                except (ValueError, TypeError):
                    pass

            safety = 0.0
            sic_el = articolo.find('sicurezza')
            if sic_el is not None and sic_el.text:
                try:
                    safety = float(sic_el.text)
                except (ValueError, TypeError):
                    pass

            self.xml_rate_list.append({
                "index": index, "level": 2, "is_parent": False,
                "parents": str(supercat_idx[codice_sc]) + ',' + str(cat_idx[codice_cat]),
                "id": codice, "name": desc, "desc": desc, "unit": um,
                "value": prezzo, "labor": labor, "equipment": 0.0, "materials": 0.0, "safety": safety,
            })
            index += 1


class ParserXmlLombardia(PriceListParser):
    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)
        if root.find("voci/voci") is not None:
            self._parse_format1(root)
        else:
            self._parse_format2(root)

    def _parse_format1(self, root):
        voci_voci = root.find("voci/voci")
        rifvoce = voci_voci.find("riferimenti_voce") if voci_voci is not None else None
        if rifvoce is not None:
            import re
            parts = [rifvoce.find(t) for t in ("autore", "invigore", "anno")]
            self.title = " ".join(p.text for p in parts if p is not None and p.text)
            anno = rifvoce.find("anno")
            if anno is not None and anno.text:
                m = re.search(r"\b(\d{4})\b", anno.text)
                self.year = m.group(1) if m else ""

        voci = root.find("voci")
        if voci is None:
            return

        index = 0
        level1_idx = {}
        level2_idx = {}

        for voce in voci:
            children = list(voce)
            if len(children) < 2:
                continue
            det = children[1]

            codice = det.attrib.get("CMPcodifica_voce") or det.attrib.get("codice_voce", "")
            desc_el = det.find("declaratoria_voce")
            desc = self.clean_string(desc_el.text if desc_el is not None else "")
            um = det.attrib.get("udm_voce") or det.attrib.get("unita_misura_voce", "")

            try:
                prezzo = float(det.attrib.get("prezzo_voce", 0))
            except ValueError:
                prezzo = 0.0

            labor = 0.0
            try:
                labor = float(det.attrib.get("rapporto_RU_voce", 0)) * prezzo / 100
            except ValueError:
                pass
            if not labor:
                risorse = det.find("risorse")
                if risorse is not None:
                    for el in risorse:
                        if el.attrib.get("tipologia_risorsa") == "MANODOPERA":
                            try:
                                labor = float(el.attrib.get("perc_importo_tipo_risorsa", 0)) * prezzo / 100
                            except ValueError:
                                pass
                            break

            lvl1_cod = det.attrib.get("codifica_I_livello_voce", "")
            lvl1_des = det.attrib.get("declaratoria_I_livello_voce", "")
            lvl2_cod = det.attrib.get("codifica_II_livello_voce", "")
            lvl2_des = det.attrib.get("declaratoria_II_livello_voce", "")

            if lvl1_cod and lvl1_cod not in level1_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": lvl1_cod, "name": lvl1_des, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                level1_idx[lvl1_cod] = index
                index += 1

            key2 = (lvl1_cod, lvl2_cod)
            if lvl2_cod and lvl2_cod != lvl1_cod and key2 not in level2_idx:
                sp_parent = str(level1_idx[lvl1_cod]) if lvl1_cod in level1_idx else ""
                self.xml_rate_list.append({
                    "index": index, "level": 1 if sp_parent else 0,
                    "is_parent": True, "parents": sp_parent,
                    "id": lvl2_cod, "name": lvl2_des, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                level2_idx[key2] = index
                index += 1

            parents_parts = []
            if lvl1_cod in level1_idx:
                parents_parts.append(str(level1_idx[lvl1_cod]))
            if key2 in level2_idx:
                parents_parts.append(str(level2_idx[key2]))

            self.xml_rate_list.append({
                "index": index, "level": len(parents_parts), "is_parent": False,
                "parents": ",".join(parents_parts),
                "id": codice, "name": desc, "desc": desc, "unit": um,
                "value": prezzo, "labor": labor,
                "equipment": 0.0, "materials": 0.0, "safety": 0.0,
            })
            index += 1

    def _parse_format2(self, root):
        try:
            attrs = root.items()
            if attrs:
                self.title = attrs[0][-1].split(".")[0].replace(":", "_")
        except Exception:
            pass

        index = 0
        madre_index = None

        for voce in list(root):
            codice_el = voce.find("Codice")
            if codice_el is None:
                continue
            codice = (codice_el.text or "").split(" - ")[0].strip()

            desc_el = voce.find("Declaratoria")
            desc = self.clean_string(desc_el.text if desc_el is not None else "")

            um_el = voce.find("UM")
            um = (um_el.text or "").strip() if um_el is not None else ""

            if not um:
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": codice, "name": desc, "desc": desc, "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                madre_index = index
                index += 1
            else:
                prezzo = 0.0
                try:
                    t = voce.find("Prezzo").text.strip().replace(" €", "").replace(".", "").replace(",", ".")
                    prezzo = float(t) if t else 0.0
                except Exception:
                    pass

                labor = 0.0
                try:
                    t = voce.find("Rapporto_RU").text.strip().replace(" €", "").replace(".", "").replace(",", ".")
                    labor = float(t) if t else 0.0
                except Exception:
                    pass

                parents = str(madre_index) if madre_index is not None else ""
                self.xml_rate_list.append({
                    "index": index, "level": 1 if parents else 0, "is_parent": False,
                    "parents": parents,
                    "id": codice, "name": desc, "desc": desc, "unit": um,
                    "value": prezzo, "labor": labor,
                    "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                index += 1


class ParserXpwe(PriceListParser):
    """Parser per formato XPWE (Primus e compatibili)."""

    def __init__(self):
        super().__init__()
        self.xml_computo_list = []   # populated by parse_computo()
        self._ep_by_xml_id = {}      # EPItem XML-ID → rate dict (set by parse_items)

    @staticmethod
    def _text(elem, path, default=""):
        try:
            found = elem.find(path)
            return (found.text or default) if found is not None else default
        except Exception:
            return default

    @staticmethod
    def _float(text):
        if not text:
            return 0.0
        try:
            return float(text.replace(",", "."))
        except (ValueError, TypeError):
            return 0.0

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_root(xml_content)

        dati = root.find("PweDatiGenerali")
        if dati is None:
            try:
                dati = list(root)[0].find("PweDatiGenerali")
            except Exception:
                return

        self._parse_header(dati)
        supercaps, caps, subcaps = self._read_categories(dati)

        misurazioni = root.find("PweMisurazioni")
        if misurazioni is None:
            try:
                misurazioni = list(root)[0].find("PweMisurazioni")
            except Exception:
                return
        if misurazioni is None or len(list(misurazioni)) == 0:
            return

        ep_root = list(misurazioni)[0]  # PweElencoPrezzi
        ep_elements = ep_root.findall("EPItem")

        index = 0
        spcap_to_index = {}
        cap_to_index = {}
        sbcap_to_index = {}

        for ep in ep_elements:
            if not ep.get("ID"):
                continue

            tariffa = self._text(ep, "Tariffa")
            if self._text(ep, "Flags") == "134217728":
                tariffa = "VDS_" + tariffa

            name = self.clean_string(self._text(ep, "DesBreve") or self._text(ep, "DesRidotta"))
            desc = self.clean_string(self._text(ep, "DesEstesa"))
            unit = self._text(ep, "UnMisura")
            prezzo_raw = self._text(ep, "Prezzo1")
            prezzo = self._float(prezzo_raw) if prezzo_raw and prezzo_raw != "0" else 0.0

            def incidenza(tag):
                val = self._float(self._text(ep, tag))
                return round(val * prezzo / 100, 6) if val else 0.0

            id_spcap = self._text(ep, "IDSpCap")
            id_cap = self._text(ep, "IDCap")
            id_sbcap = self._text(ep, "IDSbCap")

            if id_spcap and id_spcap not in spcap_to_index:
                sc = supercaps.get(id_spcap, {})
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": sc.get("codice", ""), "name": sc.get("desc", ""),
                    "desc": "", "unit": "", "value": 0.0,
                    "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                spcap_to_index[id_spcap] = index
                index += 1

            cap_key = (id_spcap, id_cap)
            if id_cap and cap_key not in cap_to_index:
                cap = caps.get(id_cap, {})
                sp_parent = str(spcap_to_index[id_spcap]) if id_spcap in spcap_to_index else ""
                self.xml_rate_list.append({
                    "index": index, "level": 1 if sp_parent else 0,
                    "is_parent": True, "parents": sp_parent,
                    "id": cap.get("codice", ""), "name": cap.get("desc", ""),
                    "desc": "", "unit": "", "value": 0.0,
                    "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                cap_to_index[cap_key] = index
                index += 1

            sbcap_key = (id_spcap, id_cap, id_sbcap)
            if id_sbcap and sbcap_key not in sbcap_to_index:
                sbcap = subcaps.get(id_sbcap, {})
                sb_parents_parts = []
                if id_spcap in spcap_to_index:
                    sb_parents_parts.append(str(spcap_to_index[id_spcap]))
                if cap_key in cap_to_index:
                    sb_parents_parts.append(str(cap_to_index[cap_key]))
                self.xml_rate_list.append({
                    "index": index, "level": len(sb_parents_parts),
                    "is_parent": True, "parents": ",".join(sb_parents_parts),
                    "id": sbcap.get("codice", ""), "name": sbcap.get("desc", ""),
                    "desc": "", "unit": "", "value": 0.0,
                    "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                sbcap_to_index[sbcap_key] = index
                index += 1

            parents_parts = []
            if id_spcap in spcap_to_index:
                parents_parts.append(str(spcap_to_index[id_spcap]))
            if cap_key in cap_to_index:
                parents_parts.append(str(cap_to_index[cap_key]))
            if sbcap_key in sbcap_to_index:
                parents_parts.append(str(sbcap_to_index[sbcap_key]))

            ep_entry = {
                "index": index,
                "level": len(parents_parts),
                "is_parent": False,
                "parents": ",".join(parents_parts),
                "id": tariffa,
                "name": name,
                "desc": desc,
                "unit": unit,
                "value": prezzo,
                "labor": incidenza("IncMDO"),
                "equipment": incidenza("IncATTR"),
                "materials": incidenza("IncMAT"),
                "safety": incidenza("IncSIC"),
            }
            self.xml_rate_list.append(ep_entry)
            xml_id = ep.get("ID")
            if xml_id:
                self._ep_by_xml_id[xml_id] = ep_entry
            index += 1

    def _parse_header(self, dati):
        try:
            child = list(dati)[0]
            content = list(child)[0] if list(child) else child
            oggetto = self._text(content, "Oggetto")
            if oggetto:
                self.title = self.clean_string(oggetto)
        except Exception:
            pass

    @staticmethod
    def _read_categories(dati):
        supercaps = {}
        caps = {}
        subcaps = {}
        try:
            cap_cat = dati.find("PweDGCapitoliCategorie")
            if cap_cat is None:
                return supercaps, caps, subcaps

            sc_found = cap_cat.find("PweDGSuperCapitoli")
            if sc_found is not None:
                for elem in sc_found:
                    sc_id = elem.get("ID")
                    if sc_id:
                        supercaps[sc_id] = {
                            "codice": ParserXpwe._text(elem, "Codice").strip(),
                            "desc": ParserXpwe._text(elem, "DesSintetica").strip(),
                        }

            cap_found = cap_cat.find("PweDGCapitoli")
            if cap_found is not None:
                for elem in cap_found:
                    cap_id = elem.get("ID")
                    if cap_id:
                        desc = ParserXpwe._text(elem, "DesSintetica").strip()
                        if desc == "Nuova voce":
                            desc = ParserXpwe._text(elem, "DesEstesa").strip()
                        caps[cap_id] = {
                            "codice": ParserXpwe._text(elem, "Codice").strip(),
                            "desc": desc,
                        }

            sbcap_found = cap_cat.find("PweDGSubCapitoli")
            if sbcap_found is not None:
                for elem in sbcap_found:
                    sb_id = elem.get("ID")
                    if sb_id:
                        desc = ParserXpwe._text(elem, "DesSintetica").strip()
                        if desc == "Nuova voce":
                            desc = ParserXpwe._text(elem, "DesEstesa").strip()
                        subcaps[sb_id] = {
                            "codice": ParserXpwe._text(elem, "Codice").strip(),
                            "desc": desc,
                        }
        except Exception:
            pass
        return supercaps, caps, subcaps

    @staticmethod
    def _read_categories_computo(dati):
        """Read SuperCategorie/Categorie/SubCategorie (used by VCItems in computo)."""
        supercats = {}
        cats = {}
        subcats = {}
        try:
            cap_cat = dati.find("PweDGCapitoliCategorie")
            if cap_cat is None:
                return supercats, cats, subcats

            for xml_tag, dest in [
                ("PweDGSuperCategorie", supercats),
                ("PweDGCategorie", cats),
                ("PweDGSubCategorie", subcats),
            ]:
                section = cap_cat.find(xml_tag)
                if section is not None:
                    for elem in section:
                        eid = elem.get("ID")
                        if eid:
                            desc = ParserXpwe._text(elem, "DesSintetica").strip()
                            dest[eid] = {
                                "codice": ParserXpwe._text(elem, "Codice").strip(),
                                "desc": desc,
                            }
        except Exception:
            pass
        return supercats, cats, subcats

    def parse_computo(self, xml_content):
        """Parse PweVociComputo into xml_computo_list, organized by Categorie."""
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_root(xml_content)

        dati = root.find("PweDatiGenerali")
        if dati is None:
            try:
                dati = list(root)[0].find("PweDatiGenerali")
            except Exception:
                return

        supercats, cats, subcats = self._read_categories_computo(dati)

        misurazioni = root.find("PweMisurazioni")
        if misurazioni is None:
            try:
                misurazioni = list(root)[0].find("PweMisurazioni")
            except Exception:
                return
        if misurazioni is None:
            return

        vc_root = misurazioni.find("PweVociComputo")
        if vc_root is None or len(list(vc_root)) == 0:
            return

        index = 0
        spcat_to_index = {}
        cat_to_index = {}
        sbcat_to_index = {}

        def _parent_entry(codice, desc):
            return {"desc": "", "unit": "", "value": 0.0,
                    "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                    "id": codice, "name": desc, "quantity": 0.0}

        for vc in vc_root.findall("VCItem"):
            if not vc.get("ID"):
                continue

            id_ep = self._text(vc, "IDEP")
            quantita = self._float(self._text(vc, "Quantita"))
            des_voce = self.clean_string(self._text(vc, "Descrizione"))
            rg_items = self._parse_rg_items(vc)
            id_spcat = self._text(vc, "IDSpCat")
            id_cat = self._text(vc, "IDCat")
            id_sbcat = self._text(vc, "IDSbCat")

            ep = self._ep_by_xml_id.get(id_ep, {})

            if id_spcat and id_spcat not in spcat_to_index:
                sc = supercats.get(id_spcat, {})
                e = _parent_entry(sc.get("codice", ""), sc.get("desc", ""))
                e.update({"index": index, "level": 0, "is_parent": True, "parents": ""})
                self.xml_computo_list.append(e)
                spcat_to_index[id_spcat] = index
                index += 1

            cat_key = (id_spcat, id_cat)
            if id_cat and cat_key not in cat_to_index:
                cat = cats.get(id_cat, {})
                sp_p = str(spcat_to_index[id_spcat]) if id_spcat in spcat_to_index else ""
                e = _parent_entry(cat.get("codice", ""), cat.get("desc", ""))
                e.update({"index": index, "level": 1 if sp_p else 0,
                          "is_parent": True, "parents": sp_p})
                self.xml_computo_list.append(e)
                cat_to_index[cat_key] = index
                index += 1

            sbcat_key = (id_spcat, id_cat, id_sbcat)
            if id_sbcat and sbcat_key not in sbcat_to_index:
                sbcat = subcats.get(id_sbcat, {})
                sb_pp = []
                if id_spcat in spcat_to_index:
                    sb_pp.append(str(spcat_to_index[id_spcat]))
                if cat_key in cat_to_index:
                    sb_pp.append(str(cat_to_index[cat_key]))
                e = _parent_entry(sbcat.get("codice", ""), sbcat.get("desc", ""))
                e.update({"index": index, "level": len(sb_pp),
                          "is_parent": True, "parents": ",".join(sb_pp)})
                self.xml_computo_list.append(e)
                sbcat_to_index[sbcat_key] = index
                index += 1

            pp = []
            if id_spcat in spcat_to_index:
                pp.append(str(spcat_to_index[id_spcat]))
            if cat_key in cat_to_index:
                pp.append(str(cat_to_index[cat_key]))
            if sbcat_key in sbcat_to_index:
                pp.append(str(sbcat_to_index[sbcat_key]))

            self.xml_computo_list.append({
                "index": index,
                "level": len(pp),
                "is_parent": False,
                "parents": ",".join(pp),
                "ep_xml_id": id_ep,
                "id": ep.get("id", ""),
                "name": ep.get("name", ""),
                "desc": ep.get("desc", ""),
                "unit": ep.get("unit", ""),
                "value": ep.get("value", 0.0),
                "quantity": quantita,
                "qty_name": des_voce,
                "rg_items": rg_items,
                "labor": ep.get("labor", 0.0),
                "equipment": ep.get("equipment", 0.0),
                "materials": ep.get("materials", 0.0),
                "safety": ep.get("safety", 0.0),
            })
            index += 1

    def _parse_rg_items(self, vc_elem):
        """Parse RGItem children of a VCItem into a list of measurement row dicts.

        RGItem.Quantita stores the VCItem total (not the individual row value).
        The row quantity must be computed as PartiUguali × Lunghezza × Larghezza × HPeso.
        Expressions like '17.3+1+1' are evaluated via _eval_expr.
        """
        rows = []
        for rg in vc_elem.findall("PweVCMisure/RGItem"):
            desc = self.clean_string(self._text(rg, "Descrizione"))
            formula_parts = []
            qty = 1.0
            has_field = False
            for tag in ("PartiUguali", "Lunghezza", "Larghezza", "HPeso"):
                raw = self._text(rg, tag).strip()
                if not raw:
                    continue
                has_field = True
                try:
                    float(raw.replace(",", "."))
                    formula_parts.append(raw)
                except ValueError:
                    formula_parts.append(f"({raw})")
                val = self._eval_expr(raw)
                if val is not None:
                    qty *= val
            rows.append({
                "desc": desc,
                "qty": round(qty, 6) if has_field else 0.0,
                "formula": " × ".join(formula_parts),
            })
        return rows

    @staticmethod
    def _eval_expr(expr):
        """Safely evaluate a simple arithmetic expression (digits, +-*/.() only)."""
        import re
        cleaned = expr.replace(",", ".").strip()
        if not re.fullmatch(r'[\d\s\+\-\*\/\.\(\)]+', cleaned):
            return None
        try:
            return float(eval(cleaned))
        except Exception:
            return None


class ParserXmlSix(PriceListParser):
    """Parser per formato XML SIX."""

    def __init__(self, language=None):
        super().__init__()
        self.language = language
        self.default_list_id = None

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)
        prezzario = root.find("prezzario")
        if prezzario is None:
            return

        prz_desc = prezzario.find("przDescrizione")
        if prz_desc is not None:
            self.title = self.clean_string(prz_desc.attrib.get("breve", ""))

        self.default_list_id = self._get_default_quotazione_id(prezzario)
        units = self.get_units(prezzario)
        products = prezzario.findall("prodotto")
        products = sorted(products, key=lambda p: p.attrib.get("prdId", ""))

        index = 0
        prdId_to_index = {}

        for product in products:
            prdId = product.attrib.get("prdId", "")
            level = self.get_level_from_prdId(product)
            is_parent = self.is_parent(product)

            if is_parent:
                prdId_to_index[prdId] = str(index)

            parts = prdId.split(".")
            ancestors = [".".join(parts[:i]) for i in range(1, len(parts))]
            parents = ",".join(prdId_to_index[p] for p in ancestors if p in prdId_to_index)

            desc = product.find("prdDescrizione")
            name = self.clean_string(desc.attrib.get("breve", "")) if desc is not None else ""
            description = self.clean_string(desc.attrib.get("estesa", "")) if desc is not None else ""
            cost_value = self.get_value(product)

            self.xml_rate_list.append({
                "index": index,
                "level": level,
                "is_parent": is_parent,
                "parents": parents,
                "id": prdId,
                "name": name,
                "desc": description,
                "unit": self.get_unit(units, product),
                "value": cost_value,
                "labor": self.get_value_component(product, cost_value, "incidenzaManodopera"),
                "equipment": self.get_value_component(product, cost_value, "incidenzaAttrezzatura"),
                "materials": self.get_value_component(product, cost_value, "incidenzaMateriali"),
                "safety": self._get_safety(product, cost_value),
            })
            index += 1

    def _get_default_quotazione_id(self, prezzario):
        lista = prezzario.find("listaQuotazione")
        if lista is not None:
            return lista.attrib.get("listaQuotazioneId")
        return None

    @staticmethod
    def _get_safety(product, cost_value):
        try:
            return float(product.attrib.get("onereSicurezza", 0)) * cost_value / 100
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def get_units(prezzario):
        units = {}
        umList = prezzario.findall("unitaDiMisura")
        for um in umList:
            attr = um.attrib
            try:
                sym = attr.get("simbolo", attr.get("udmId", ""))
                units[attr["unitaDiMisuraId"]] = sym
            except KeyError:
                pass
        return units

    @staticmethod
    def get_unit(units, product):
        try:
            return units.get(product.attrib.get("unitaDiMisuraId", ""), "")
        except Exception:
            return ""

    def get_value(self, product):
        prezzo = 0.0
        quotazioni = product.findall("prdQuotazione")
        if not quotazioni:
            return 0.0

        for el in quotazioni:
            if self.default_list_id and el.attrib.get("listaQuotazioneId") == self.default_list_id:
                try:
                    return float(el.attrib.get("valore", 0.0))
                except ValueError:
                    return 0.0

        try:
            return float(quotazioni[0].attrib.get("valore", 0.0))
        except ValueError:
            return 0.0

    @staticmethod
    def get_value_component(product, cost_value, component_type):
        if component_type not in ("incidenzaManodopera", "incidenzaMateriali", "incidenzaAttrezzatura"):
            return 0.0
        component_ratio = product.find(component_type)
        try:
            return float(getattr(component_ratio, "text", 0.0)) * cost_value / 100
        except Exception:
            return 0.0

    @staticmethod
    def get_level_from_prdId(product):
        return len(product.attrib.get("prdId", "").split(".")) - 1

    @staticmethod
    def is_parent(product):
        quotazioni = product.findall("prdQuotazione")
        if not quotazioni:
            return True
        return all(float(q.attrib.get("valore", 0)) == 0.0 for q in quotazioni)


class ParserIfcCostSchedule(PriceListParser):
    """Parser per IfcCostSchedule — progetto corrente o file IFC esterno."""

    def parse_schedule(self, file, schedule_id):
        import ifcopenshell.util.cost as cost_util
        schedule = file.by_id(int(schedule_id))
        self.title = schedule.Name or f"Schedule {schedule_id}"
        root_items = cost_util.get_root_cost_items(schedule)
        index = 0

        def _val(cost_item):
            for cv in (cost_item.CostValues or []):
                try:
                    v = cv.AppliedValue
                    if v is not None:
                        return float(v.wrappedValue if hasattr(v, 'wrappedValue') else v)
                except Exception:
                    pass
            return 0.0

        def _labor(cost_item):
            for cv in (cost_item.CostValues or []):
                for sub in (getattr(cv, 'Components', None) or []):
                    if getattr(sub, 'Category', None) == 'Labor':
                        try:
                            v = sub.AppliedValue
                            return float(v.wrappedValue if hasattr(v, 'wrappedValue') else v)
                        except Exception:
                            pass
            return 0.0

        def traverse(cost_item, level, parent_indices):
            nonlocal index
            has_children = bool(cost_item.IsNestedBy)
            self.xml_rate_list.append({
                "index": index,
                "ifc_id": cost_item.id(),
                "level": level,
                "is_parent": has_children,
                "parents": ",".join(str(p) for p in parent_indices),
                "id": cost_item.Identification or "",
                "name": cost_item.Name or "",
                "desc": cost_item.Description or "",
                "unit": "",
                "value": _val(cost_item),
                "labor": _labor(cost_item),
                "equipment": 0.0,
                "materials": 0.0,
                "safety": 0.0,
            })
            current_index = index
            index += 1
            for rel in (cost_item.IsNestedBy or []):
                for child in rel.RelatedObjects:
                    traverse(child, level + 1, parent_indices + [current_index])

        for root_item in root_items:
            traverse(root_item, 0, [])


def _find_xml_parser(xml_content):
    """From Leeno (thanks Giuserpe): pre-scans the XML to pick the right parser."""
    parsers = {
        "PweDatiGenerali": ParserXpwe,
        'xmlns="six.xsd"': ParserXmlSix,
        'autore="Regione Toscana"': ParserXmlToscana,
        'autore="Regione Calabria"': ParserXmlToscana,
        'autore="Regione Campania"': ParserXmlToscana,
        'autore="Regione Sardegna"': ParserXmlToscana,
        'autore="Regione Liguria"': ParserXmlLiguria,
        "rks=": ParserXmlVeneto,
        "<settore cod=": ParserXmlVeneto,
        "<pdf>Prezzario_Regione_Basilicata": ParserXmlBasilicata,
        "<autore>Regione Lombardia": ParserXmlLombardia,
        "<autore>LOM": ParserXmlLombardia,
    }
    for pattern, parser_class in parsers.items():
        if pattern in xml_content:
            return parser_class
    return None
