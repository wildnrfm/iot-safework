"""Label kanonis APD, alias nama kelas dari dataset, dan zona tubuh."""
from __future__ import annotations

PERSON = "person"

# APD (kelas positif) -> kelas "tidak dipakai" yang setara, bila model memilikinya.
NEGATIVE_LABEL = {
    "helmet": "no_helmet",
    "vest": "no_vest",
    "gloves": "no_gloves",
    "boots": "no_boots",
    "goggles": "no_goggle",
    "mask": "no_mask",
}
APD_ITEMS = tuple(NEGATIVE_LABEL)

ITEM_NAMES_ID = {
    "helmet": "Helm",
    "vest": "Rompi",
    "gloves": "Sarung tangan",
    "boots": "Sepatu/boot",
    "goggles": "Kacamata pelindung",
    "mask": "Masker",
}

# Zona tubuh tempat APD seharusnya terlihat, relatif terhadap kotak orang:
# (y_min, y_max, x_margin). y: 0 = tepi atas kotak orang, 1 = tepi bawah;
# x_margin = toleransi horizontal sebagai pecahan lebar kotak orang.
ZONES = {
    "helmet": (-0.15, 0.30, 0.15),
    "goggles": (-0.05, 0.30, 0.15),
    "mask": (0.05, 0.35, 0.15),
    "vest": (0.15, 0.70, 0.15),
    "gloves": (0.20, 0.95, 0.40),
    "boots": (0.75, 1.20, 0.15),
}

# Nama kelas dari dataset -> label kanonis. Kunci: huruf kecil, spasi/tanda hubung jadi "_".
# Periksa ulang pemetaan ini setiap kali menambah dataset baru.
ALIASES = {
    "person": "person", "worker": "person",
    "helmet": "helmet", "hardhat": "helmet", "hard_hat": "helmet", "safety_helmet": "helmet",
    "vest": "vest", "safety_vest": "vest", "reflective_vest": "vest",
    "gloves": "gloves", "glove": "gloves", "safety_gloves": "gloves",
    "boots": "boots", "boot": "boots", "safety_shoe": "boots", "safety_shoes": "boots", "shoes": "boots",
    "goggles": "goggles", "goggle": "goggles", "glasses": "goggles", "safety_glasses": "goggles",
    "mask": "mask", "face_mask": "mask",
    "no_helmet": "no_helmet", "no_hardhat": "no_helmet", "no_hard_hat": "no_helmet",
    "no_vest": "no_vest", "no_safety_vest": "no_vest",
    "no_gloves": "no_gloves", "no_glove": "no_gloves",
    "no_boots": "no_boots", "no_boot": "no_boots", "no_shoes": "no_boots", "no_safety_shoe": "no_boots",
    "no_goggle": "no_goggle", "no_goggles": "no_goggle", "no_glasses": "no_goggle",
    "no_mask": "no_mask", "no_face_mask": "no_mask",
}


def canonical_label(name: str) -> str | None:
    """Ubah nama kelas dataset menjadi label kanonis; None bila tidak dikenal (mis. kelas "none")."""
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    return ALIASES.get(key)
