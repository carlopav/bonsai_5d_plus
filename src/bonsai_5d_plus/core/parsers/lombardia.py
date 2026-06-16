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

"""Regione Lombardia price-list parser."""

from .base import PriceListParser, apply_resource_category


class ParserXmlLombardia(PriceListParser):
    # dettaglio_voce 'tipologia_risorsa' → IFC category. Composite types (OPERA
    # COMPIUTA / PRODOTTO IN OPERA / LAVORO PROVVISIONALE) map to "" and keep
    # their resource breakdown.
    _TIPOLOGIA_CATEGORY = {
        "RISORSA UMANA": "Labor",
        "RISORSA MATERIALE": "Material",
        "RISORSA STRUMENTALE PRODUTTIVA": "Equipment",
        "RISORSA STRUMENTALE TECNOLOGICA": "Equipment",
    }

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

            category = self._TIPOLOGIA_CATEGORY.get(
                det.attrib.get("tipologia_risorsa", "").strip().upper(), ""
            )
            item = {
                "index": index, "level": len(parents_parts), "is_parent": False,
                "parents": ",".join(parents_parts),
                "id": codice, "name": desc, "desc": desc, "unit": um,
                "value": prezzo, "labor": labor,
                "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                "category": category,
            }
            # Pure-resource voci → 100% to their category; opere compiute keep the
            # rapporto_RU/risorse-derived labor share parsed above.
            apply_resource_category(item)
            self.xml_rate_list.append(item)
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


