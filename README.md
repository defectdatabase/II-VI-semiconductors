# materialHUB — Bulk and Defect DFT for Semiconductors

[![Website](https://img.shields.io/badge/website-defectdatabase.github.io-0e7490)](https://defectdatabase.github.io/material_hub/)
[![nanoHUB tool](https://img.shields.io/badge/nanoHUB-defectdatabase-2e7d32)](https://nanohub.org/tools/defectdatabase)
[![Dataset](https://img.shields.io/badge/dataset-DefectDB.zip%20(640%20MB)-blue)](https://github.com/msehabibur/DefectDB/releases/download/DefectDB/DefectDB.zip)
[![Python](https://img.shields.io/badge/python-3.12-3776ab)](#installation)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

DefectDB is an open-source, ML-accelerated defect-informatics platform for **Cd/Zn–S/Se/Te (II–VI) semiconductors**. It combines a high-throughput DFT defect dataset (PBEsol and HSE), machine-learning force fields (M3GNet-based, trained on defect supercells), and an interactive Jupyter tool for building, relaxing, and analyzing point defects, defect migration, grain boundaries, dislocation cores, and heterointerfaces.

The tool runs live in the browser on nanoHUB — no installation required:

> **▶ Launch the tool: [nanohub.org/tools/defectdatabase](https://nanohub.org/tools/defectdatabase)**
>
> **🌐 Browse the library: [defectdatabase.github.io/material_hub](https://defectdatabase.github.io/material_hub/)** — a compound explorer with 6763 DFT-computed I–III–VI₂ / I₂–II–IV–VI₄ chalcogenides (formation energy, decomposition energy, band gap, dielectric constant, SLME) plus interactive defect formation-energy diagrams for II–VI hosts at PBEsol and HSE+SOC, computed live from the published dataset. The website reports DFT data only; the MLFF models are used in the simulation tool.

Developed in the Mannodi research group at Purdue University (Md Habibur Rahman, Yi Yang, Arun Mannodi-Kanakkithodi).

---

## Modules

The main application is [`Cd_Zn_X_v3.ipynb`](Cd_Zn_X_v3.ipynb), organized into five consolidated modules:

| # | Module | What it does |
|---|--------|--------------|
| 1 | **Access DFT Defect Dataset** | Query the PBEsol/HSE defect dataset (vacancies, interstitials, antisites, substitutional dopants, complexes across CdTe, CdSe, CdS, ZnTe, ZnSe, ZnS and their alloys); formation-energy diagrams vs. Fermi level under user-selected chemical potentials; interactive 3D structure viewing with [MatterViz](https://github.com/janosh/matterviz) |
| 2 | **Simulating Defects using MLFF** | Build any defect in any II–VI supercell, relax it with the bundled machine-learning force fields (PBE- and HSE-fidelity, charge states −2…+2), compute formation energies, and run finite-temperature molecular dynamics |
| 3 | **Diffusion of Defect (NEB)** | Automated migration-path construction (neighbor finding, endpoint generation) and CI-NEB barrier calculations with the MLFFs |
| 4 | **GB & Dislocation Core** | Grain-boundary and dislocation-core structure construction and energetics |
| 5 | **CdTe–ZnTe Interface** | Heterointerface construction and defect energetics across the interface |

A standalone, lightweight structure viewer is provided in [`Defect_Structure_Viewer.ipynb`](Defect_Structure_Viewer.ipynb) — it renders any defect supercell from the dataset in an interactive four-view MatterViz grid (front / side / top / isometric) with the defect site highlighted in black.

## Screenshots

All images below are captured from the live tool.

**Module 1 — dataset access, formation-energy diagram, and the MatterViz four-view structure viewer (defect site in black):**

<p align="center"><img src="docs/figures/Figure_1.png" width="850" alt="Module 1: DFT defect dataset and MatterViz viewer"></p>

**Module 2 — defect construction and MLFF site sampling (V_Cd, As_Te, Cu_i, Cl_Te + V_Cd in CdTe, Cd-rich conditions):**

<p align="center"><img src="docs/figures/Figure_2.png" width="850" alt="Module 2: defect building and MLFF sampling"></p>

**Module 2 — relaxation trajectories and per-charge-state energy table:**

<p align="center"><img src="docs/figures/Figure_3.png" width="850" alt="Module 2: trajectories and energies"></p>

**Module 2 — staged molecular dynamics (NPT, 300 → 500 K):**

<p align="center"><img src="docs/figures/Figure_4.png" width="850" alt="Module 2: MLFF molecular dynamics"></p>

**Module 3 — CI-NEB migration barrier for V_Cd in CdTe (7 images, converged):**

<p align="center"><img src="docs/figures/Figure_5.png" width="850" alt="Module 3: NEB migration barrier"></p>

## Repository layout

```
Cd_Zn_X_v3.ipynb                # main application (5 modules, ipywidgets)
Defect_Structure_Viewer.ipynb   # standalone MatterViz defect viewer
PES/                            # bundled MLFF models
  PES_PBE/                      #   PBE-fidelity potentials  (q = -2 … +2)
  PES_HSE/                      #   HSE-fidelity potentials  (q = -2 … +2)
matterviz/                      # prebuilt MatterViz web bundle (served via jsDelivr)
middleware/invoke               # nanoHUB launcher (classic notebook / appmode)
docs/figures/                   # screenshots used in this README and the paper
cdsete_defect_library_generation_pbesol.csv
```

## Dataset

The DFT defect dataset (relaxed supercells, total energies, formation energies, chemical potentials) is distributed as a release asset:

- [`DefectDB.zip`](https://github.com/msehabibur/DefectDB/releases/download/DefectDB/DefectDB.zip) (~640 MB) — PBEsol defect library; the tool downloads and caches it automatically on first use.
- Competing-phase calculations for chemical-potential limits: [PBE](https://github.com/msehabibur/DefectDB/releases/tag/competing_phases_pbe) and [HSE](https://github.com/msehabibur/DefectDB/releases/tag/competing_phases_hse).

## Installation

The recommended way to use DefectDB is the hosted tool on [nanoHUB](https://nanohub.org/tools/defectdatabase). To run locally (Python 3.12):

```bash
git clone https://github.com/defectdatabase/material_hub.git
cd material_hub
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
jupyter nbclassic Cd_Zn_X_v3.ipynb
```

The pinned versions in `requirements.txt` matter: `matgl 1.1.3` requires `torch 2.2.1` + `dgl 2.2.0` + `numpy < 2`, and the CIF structure viewer requires `monty 2024.2.26`. Run under the classic Jupyter notebook (`nbclassic`) rather than Voilà — the widget callbacks rely on classic-notebook output handling, which is also what nanoHUB uses.

The interactive 3D viewer loads the prebuilt [MatterViz](https://github.com/janosh/matterviz) bundle in `matterviz/` from jsDelivr; set the `DEFECTDB_MATTERVIZ_BASE` environment variable to point at a different copy (e.g. a local server) if needed.

## Citation

If you use DefectDB, please cite:

> M. H. Rahman, Y. Yang, and A. Mannodi-Kanakkithodi, *DefectDB: An Open-Source Infrastructure for Defect Thermodynamics in Chalcogenide Semiconductors* (2026, in preparation).

## License

Released under the [MIT License](LICENSE).
