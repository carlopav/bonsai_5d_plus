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

"""Regione Basilicata price-list parser."""

from .base import PriceListParser


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


