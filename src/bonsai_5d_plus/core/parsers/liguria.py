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

"""Regione Liguria price-list parser."""

from .base import PriceListParser


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


