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

"""XPWE (DEI / PAT Trento) price-list parser."""

from .base import PriceListParser, apply_resource_category, classify_section


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

            # Resource category from the deepest classified section: a combined
            # supercapitolo ("MANODOPERA, NOLI, TRASPORTI, MATERIALI …", PAT)
            # is overridden by its specific capitolo ("NOLI E TRASPORTI" etc.);
            # DEI keeps the split at the supercapitolo ("MANO D'OPERA", "NOLI").
            category = (
                classify_section(subcaps.get(id_sbcap, {}).get("desc", ""))
                or classify_section(caps.get(id_cap, {}).get("desc", ""))
                or classify_section(supercaps.get(id_spcap, {}).get("desc", ""))
            )
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
                "category": category,
            }
            # Pure-resource items → 100% to their category; opere compiute keep
            # the Inc* breakdown above.
            apply_resource_category(ep_entry)
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
        The row quantity is computed as PartiUguali × Lunghezza × Larghezza × HPeso
        (empty factors count as 1). Expressions like '256.667-23' are evaluated
        via _eval_expr and kept verbatim in the formula.

        To avoid losing information, the formula keeps all four positions
        (empty factors shown as "1"), so which factor is which is preserved.
        Note/heading rows (no numeric dimension, qty 0) keep their description
        and carry no formula, so their text survives without affecting the total.
        """
        rows = []
        for rg in vc_elem.findall("PweVCMisure/RGItem"):
            desc = self.clean_string(self._text(rg, "Descrizione"))
            raws = [self._text(rg, tag).strip()
                    for tag in ("PartiUguali", "Lunghezza", "Larghezza", "HPeso")]

            present = [r for r in raws if r != ""]
            qty = 1.0
            for r in present:
                val = self._eval_expr(r)
                qty *= (val if val is not None else 0.0)
            qty = round(qty, 6) if present else 0.0

            if qty == 0.0:
                formula = ""  # note / heading / placeholder row
            else:
                parts = []
                for r in raws:
                    if r == "":
                        parts.append("1")
                    else:
                        try:
                            float(r.replace(",", "."))
                            parts.append(r)
                        except ValueError:
                            parts.append(f"({r})")
                formula = " × ".join(parts)

            rows.append({"desc": desc, "qty": qty, "formula": formula})
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


