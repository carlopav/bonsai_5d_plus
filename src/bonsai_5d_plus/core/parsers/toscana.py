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

"""Regione Toscana (and Calabria/Campania/Sardegna) price-list parser."""

from .base import PriceListParser, apply_resource_category, classify_section


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

            liv1 = articolo.find('livello1')
            supercat_breve = liv1.attrib.get('descrizionebreve', '') if liv1 is not None else ''
            supercat = (articolo.findtext('tipo') or articolo.findtext('livello1') or '').strip()
            cat = (articolo.findtext('capitolo') or articolo.findtext('livello2') or '').strip()
            # The livello1 'descrizionebreve' attribute carries the clean section
            # name (RISORSE UMANE / NOLEGGIO DI ATTREZZATURE / PRODOTTI DA
            # COSTRUZIONE / SALUTE E SICUREZZA …); fall back to the supercat text
            # for the PRT and other regional variants without that attribute.
            section_category = classify_section(supercat_breve or supercat)

            if codice_sc not in supercat_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": codice_sc, "name": supercat or codice_sc, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                    "category": section_category,
                })
                supercat_idx[codice_sc] = index
                index += 1

            if codice_cat not in cat_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 1, "is_parent": True,
                    "parents": str(supercat_idx[codice_sc]),
                    "id": codice_cat, "name": cat or codice_cat, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                    "category": section_category,
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

            item = {
                "index": index, "level": 2, "is_parent": False,
                "parents": str(supercat_idx[codice_sc]) + ',' + str(cat_idx[codice_cat]),
                "id": codice, "name": desc, "desc": desc, "unit": um,
                "value": prezzo, "labor": labor, "equipment": 0.0, "materials": 0.0, "safety": safety,
                "category": section_category,
            }
            # Pure-resource sections → 100% to their category; opere compiute keep
            # the incidenzamanodopera-derived labor share parsed above.
            apply_resource_category(item)
            self.xml_rate_list.append(item)
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


