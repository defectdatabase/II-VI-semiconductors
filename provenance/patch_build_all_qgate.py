"""Apply on Eagle when it returns: per-charge-state settings gate in build_all.py.
python3 provenance/patch_build_all_qgate.py /eagle/wbg_defects/materialsHUB/telluride/log/build_all.py"""
import sys
P = sys.argv[1]
s = open(P).read()
old = """            if settings_bad:
                qrows[q] = {"q": qq, "dE": round(dE, 6), "E": Edef, "Ebulk": Ebulk,"""
new = """            dE0 = (byq["Neutral"]["F"] - hpa * n_super) if "Neutral" in byq else None
            if dE0 is not None and qq != 0 and abs(dE - dE0) > 15.0:
                qrows[q] = {"q": qq, "dE": round(dE, 6), "E": Edef, "Ebulk": Ebulk,
                            "Ef_VBM": None, "Ef_CBM": None,
                            "note": f"charge state {qq:+d} is {dE-dE0:+.1f} eV off the neutral run "
                                    "-- not the same calculation settings; withheld"}
                continue
            if settings_bad:
                qrows[q] = {"q": qq, "dE": round(dE, 6), "E": Edef, "Ebulk": Ebulk,"""
assert old in s, "anchor not found -- build_all changed"
open(P, "w").write(s.replace(old, new, 1))
print("build_all: per-charge gate applied")
