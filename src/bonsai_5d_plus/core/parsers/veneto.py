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

"""Regione Veneto price-list parser."""

from .base import PriceListParser, apply_resource_category, classify_section


class ParserXmlVeneto(PriceListParser):
    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)
        index = 0
        settori = root.findall("settore")
        for settore in settori:
            # Resource sections (MANODOPERA, NOLI, MATERIALI, SEMILAVORATI) hold
            # single-category items; the OPERE sections hold composite works.
            section_category = classify_section(settore.attrib.get("desc", ""))
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
                    "category": section_category,
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
                        "category": section_category,
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
                            "category": section_category,
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
                        item = {
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
                            "category": section_category,
                        }
                        # Pure-resource sections → 100% to the matching category;
                        # composite works keep the man%-derived labor incidence.
                        apply_resource_category(item)
                        self.xml_rate_list.append(item)
                        index += 1


