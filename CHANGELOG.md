# Changelog

## Pass 2.4 — Public alpha preparation

- Added explicit acknowledgement of substantial ChatGPT (OpenAI, GPT-6) development assistance and a project-level `Assisted-by:` attribution convention.

- Added prescribed rotational motors using LAMMPS `fix move rotate`.
- Retained configurable linear motors and global XYZ translation axes.
- Added configuration validation for rotational axes, periods, and pivots.
- Added centroid-based or explicit rotational pivots.
- Documented the current carbon/AIREBO demonstration, setup workflow, configuration, validation notes, and known limitations.

## Pass 2.3

- Added independently configurable global XYZ translation axes for motors.
- Normalized axis vectors so configured velocity remains the speed magnitude.

## Earlier refactor work

- Centralized application settings in TOML.
- Added relative path resolution, LAMMPS data-file atom metadata reading, SAMSON group discovery/export, multi-motor keyboard control, and Python-mediated LAMMPS/SAMSON communication.
