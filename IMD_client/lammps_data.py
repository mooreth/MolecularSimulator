"""Read atom metadata and coordinates from common LAMMPS data-file styles."""

import numpy as np

# Standard atomic weights (or representative isotope masses where no stable
# standard atomic weight exists). Mass-based identification is approximate;
# use [elements.overrides] in config.toml for isotopes or unusual force fields.
ELEMENT_MASSES = {
    "H": 1.008, "He": 4.0026, "Li": 6.94, "Be": 9.0122,
    "B": 10.81, "C": 12.011, "N": 14.007, "O": 15.999,
    "F": 18.998, "Ne": 20.180, "Na": 22.990, "Mg": 24.305,
    "Al": 26.982, "Si": 28.085, "P": 30.974, "S": 32.06,
    "Cl": 35.45, "Ar": 39.948, "K": 39.098, "Ca": 40.078,
    "Sc": 44.956, "Ti": 47.867, "V": 50.942, "Cr": 51.996,
    "Mn": 54.938, "Fe": 55.845, "Co": 58.933, "Ni": 58.693,
    "Cu": 63.546, "Zn": 65.38, "Ga": 69.723, "Ge": 72.630,
    "As": 74.922, "Se": 78.971, "Br": 79.904, "Kr": 83.798,
    "Rb": 85.468, "Sr": 87.62, "Zr": 91.224, "Nb": 92.906,
    "Mo": 95.95, "Ru": 101.07, "Rh": 102.906, "Pd": 106.42,
    "Ag": 107.868, "Cd": 112.414, "In": 114.818, "Sn": 118.710,
    "Sb": 121.760, "Te": 127.60, "I": 126.904, "Xe": 131.293,
    "Cs": 132.905, "Ba": 137.327, "La": 138.905, "Ce": 140.116,
    "W": 183.84, "Re": 186.207, "Os": 190.23, "Ir": 192.217,
    "Pt": 195.084, "Au": 196.967, "Hg": 200.592, "Pb": 207.2,
    "Bi": 208.980, "Th": 232.038, "U": 238.029,
}

SECTION_NAMES = {
    "Atoms", "Velocities", "Masses", "Pair Coeffs", "PairIJ Coeffs",
    "Bond Coeffs", "Angle Coeffs", "Dihedral Coeffs", "Improper Coeffs",
    "BondBond Coeffs", "BondAngle Coeffs", "MiddleBondTorsion Coeffs",
    "EndBondTorsion Coeffs", "AngleTorsion Coeffs", "AngleAngleTorsion Coeffs",
    "BondBond13 Coeffs", "AngleAngle Coeffs", "Ellipsoids", "Lines",
    "Triangles", "Bodies", "Bonds", "Angles", "Dihedrals", "Impropers",
}
SUPPORTED_ATOM_STYLES = {"atomic", "molecular", "charge", "full"}


def identify_element(mass, tolerance=0.20):
    """Infer an element symbol from atomic mass, or return ``Unknown``."""
    if mass is None:
        return "Unknown"

    best_element = "Unknown"
    best_difference = float("inf")
    for element, reference_mass in ELEMENT_MASSES.items():
        difference = abs(float(mass) - reference_mass)
        if difference < best_difference:
            best_difference = difference
            best_element = element

    return best_element if best_difference <= tolerance else "Unknown"


def _parse_atom_record(values, atom_style, line_number):
    """Extract ID, molecule ID, type and xyz from one Atoms record."""
    try:
        if atom_style == "atomic":
            if len(values) < 5:
                raise ValueError("atomic style requires at least 5 fields")
            atom_id = int(values[0])
            molecule_id = None
            atom_type = int(values[1])
            charge = None
            xyz = values[2:5]

        elif atom_style == "molecular":
            if len(values) < 6:
                raise ValueError("molecular style requires at least 6 fields")
            atom_id = int(values[0])
            molecule_id = int(values[1])
            atom_type = int(values[2])
            charge = None
            xyz = values[3:6]

        elif atom_style == "charge":
            if len(values) < 6:
                raise ValueError("charge style requires at least 6 fields")
            atom_id = int(values[0])
            molecule_id = None
            atom_type = int(values[1])
            charge = float(values[2])
            xyz = values[3:6]

        elif atom_style == "full":
            if len(values) < 7:
                raise ValueError("full style requires at least 7 fields")
            atom_id = int(values[0])
            molecule_id = int(values[1])
            atom_type = int(values[2])
            charge = float(values[3])
            xyz = values[4:7]

        else:
            raise ValueError(f"Unsupported atom style: {atom_style}")

        x, y, z = map(float, xyz)
        return atom_id, molecule_id, atom_type, charge, x, y, z

    except (IndexError, TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid {atom_style} atom record on line {line_number}: {values}. {error}"
        ) from error


def load_lammps_data(filename, atom_style=None, element_map=None):
    """Load atom metadata from a LAMMPS data file.

    Supported ``Atoms`` styles are atomic, molecular, charge and full. The
    style is read from the ``Atoms # style`` header when available. Pass
    ``atom_style`` explicitly when the file omits that comment and the format
    cannot be inferred unambiguously.

    ``element_map`` is an optional mapping of LAMMPS atom type integers to
    element symbols; missing entries are inferred from the ``Masses`` section.
    """
    element_map = {int(key): str(value) for key, value in (element_map or {}).items()}
    masses = {}
    atoms = []
    section = None
    declared_atom_count = None
    header_atom_style = None

    with open(filename, "r", encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue

            # Preserve the Atoms header comment; it identifies the atom style.
            if stripped.startswith("Atoms"):
                comment = stripped.partition("#")[2].strip().lower()
                if comment in SUPPORTED_ATOM_STYLES:
                    header_atom_style = comment
                section = "Atoms"
                continue

            content = stripped.split("#", 1)[0].strip()
            if not content:
                continue
            fields = content.split()

            # A section header ends the preceding data section.
            section_name = " ".join(fields[:2]) if len(fields) >= 2 else fields[0]
            if section_name in SECTION_NAMES:
                section = section_name
                continue

            if section is None:
                if len(fields) >= 2 and fields[1] == "atoms":
                    declared_atom_count = int(fields[0])
                continue

            if section == "Masses":
                if len(fields) >= 2:
                    try:
                        masses[int(fields[0])] = float(fields[1])
                    except ValueError as error:
                        raise ValueError(
                            f"Invalid Masses record on line {line_number}: {fields}"
                        ) from error

            elif section == "Atoms":
                style = atom_style or header_atom_style
                if style is None:
                    # Without a header comment, only the common uncharged
                    # atomic and molecular layouts can be inferred safely.
                    if len(fields) == 5:
                        style = "atomic"
                    elif len(fields) == 6:
                        style = "molecular"
                    else:
                        raise ValueError(
                            "Could not infer LAMMPS atom style. Add an atom-style "
                            "comment to the Atoms header or pass atom_style explicitly."
                        )

                if style not in SUPPORTED_ATOM_STYLES:
                    raise ValueError(
                        f"Unsupported atom_style '{style}'. Supported: "
                        f"{', '.join(sorted(SUPPORTED_ATOM_STYLES))}"
                    )

                atom_id, molecule_id, atom_type, charge, x, y, z = _parse_atom_record(
                    fields, style, line_number
                )
                mass = masses.get(atom_type)
                element = element_map.get(atom_type, identify_element(mass))

                atoms.append({
                    "lammps_id": atom_id,
                    "molecule_id": molecule_id,
                    "atom_type": atom_type,
                    "element": element,
                    "mass": mass,
                    "charge": charge,
                    "initial_position": np.array([x, y, z], dtype=np.float64),
                })

    atoms.sort(key=lambda atom: atom["lammps_id"])

    ids = [atom["lammps_id"] for atom in atoms]
    if len(ids) != len(set(ids)):
        raise ValueError("LAMMPS data file contains duplicate atom IDs")

    if declared_atom_count is not None and len(atoms) != declared_atom_count:
        raise ValueError(
            f"Expected {declared_atom_count} atoms, but parsed {len(atoms)}"
        )

    for imd_index, atom in enumerate(atoms):
        atom["imd_index"] = imd_index

    return atoms
