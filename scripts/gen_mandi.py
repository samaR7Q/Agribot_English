"""Generate demo mandi rates for every district in data/districts.json.

The rates are made up (seeded, so re-running gives the same file). Each district gets
its own spread around a base price, and provinces that don't trade a commodity skip it.

    python scripts/gen_mandi.py
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261102

ALL = ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Islamabad Capital Territory",
       "Azad Kashmir", "Gilgit-Baltistan"]
PLAINS = ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Islamabad Capital Territory"]

# key: (display name, unit, base price PKR, provinces where the mandi trades it)
COMMODITIES = {
    "wheat":          ("Wheat", "per 40 kg", 3600, ALL),
    "rice_basmati":   ("Basmati paddy", "per 40 kg", 4600, ["Punjab", "Sindh", "Islamabad Capital Territory"]),
    "rice_irri":      ("IRRI-6 paddy", "per 40 kg", 2900, ["Punjab", "Sindh", "Balochistan"]),
    "maize":          ("Maize", "per 40 kg", 2600, ALL),
    "cotton":         ("Cotton (phutti)", "per 40 kg", 8500, ["Punjab", "Sindh", "Balochistan"]),
    "sugarcane":      ("Sugarcane", "per 40 kg", 450, ["Punjab", "Sindh", "Khyber Pakhtunkhwa"]),
    "sesame":         ("Sesame", "per 40 kg", 12000, PLAINS),
    "canola":         ("Canola", "per 40 kg", 7800, PLAINS),
    "mustard":        ("Mustard (sarson)", "per 40 kg", 7200, PLAINS),
    "raya":           ("Raya", "per 40 kg", 7000, PLAINS),
    "toria":          ("Toria", "per 40 kg", 6800, PLAINS),
    "taramira":       ("Taramira", "per 40 kg", 6500, PLAINS),
    "camelina":       ("Camelina", "per 40 kg", 6000, ["Punjab", "Khyber Pakhtunkhwa"]),
    "linseed":        ("Linseed", "per 40 kg", 8000, PLAINS),
    "sunflower":      ("Sunflower", "per 40 kg", 6800, PLAINS),
    "guar":           ("Guar seed", "per 40 kg", 9500, ["Punjab", "Sindh"]),
    "berseem":        ("Berseem (green fodder)", "per 40 kg", 350, ALL),
    "lucerne":        ("Lucerne (green fodder)", "per 40 kg", 400, ALL),
    "oats":           ("Oats (green fodder)", "per 40 kg", 380, ALL),
    "ryegrass":       ("Ryegrass (green fodder)", "per 40 kg", 350, ALL),
    "mooli":          ("Radish (mooli)", "per 40 kg", 300, ALL),
    "hay":            ("Hay (dry fodder)", "per 40 kg", 1400, ALL),
    "apple":          ("Apple", "per kg", 220, ALL),
    "cow":            ("Cow (milking, average)", "per animal", 180000, ALL),
    "buffalo":        ("Buffalo (milking, average)", "per animal", 280000, ALL),
}

# Remote areas pay more for what comes from the plains.
PROVINCE_FACTOR = {
    "Punjab": 1.00, "Sindh": 1.01, "Islamabad Capital Territory": 1.04,
    "Khyber Pakhtunkhwa": 1.05, "Balochistan": 1.07, "Azad Kashmir": 1.08, "Gilgit-Baltistan": 1.12,
}
# Apples are cheaper where they grow.
APPLE_FACTOR = {"Balochistan": 0.85, "Gilgit-Baltistan": 0.9, "Khyber Pakhtunkhwa": 0.92}


def _round(value: float, unit: str) -> int:
    step = 1000 if unit == "per animal" else (5 if unit == "per kg" else 10)
    return int(round(value / step) * step)


def main() -> None:
    rng = random.Random(SEED)
    districts = json.loads((ROOT / "data" / "districts.json").read_text())
    mandis = {}
    for d in districts:
        rates = {}
        for key, (name, unit, base, provinces) in COMMODITIES.items():
            if d["province"] not in provinces:
                continue
            factor = PROVINCE_FACTOR[d["province"]] * rng.uniform(0.94, 1.06)
            if key == "apple":
                factor *= APPLE_FACTOR.get(d["province"], 1.0)
            avg = base * factor
            spread = rng.uniform(0.04, 0.09)
            rates[key] = {
                "name": name,
                "unit": unit,
                "min": _round(avg * (1 - spread), unit),
                "max": _round(avg * (1 + spread), unit),
                "avg": _round(avg, unit),
            }
        mandis[d["district"]] = {"province": d["province"], "mandi": f"{d['district']} grain and fodder market", "rates": rates}

    out = {
        "note": "DEMO DATA: made-up rates for the English demo bot, not real market prices.",
        "currency": "PKR",
        "commodities": {k: {"name": v[0], "unit": v[1]} for k, v in COMMODITIES.items()},
        "mandis": mandis,
    }
    path = ROOT / "data" / "mandi_rates.json"
    path.write_text(json.dumps(out, indent=1))
    rows = sum(len(m["rates"]) for m in mandis.values())
    print(f"{len(mandis)} mandis, {rows} rates → {path}")


if __name__ == "__main__":
    main()
