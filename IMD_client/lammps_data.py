
import numpy as np

##REPLACED BY main.py can be deleted

# Approximate standard atomic masses.
ELEMENT_MASSES = {
    "H": 1.008,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "F": 18.998,
    "Si": 28.085,
    "P": 30.974,
    "S": 32.06,
    "Cl": 35.45,
    "Br": 79.904,
}


def identify_element(mass, tolerance=0.15):
    """
    Identify an element from its atomic mass.

    Returns an element symbol or 'Unknown'.
    """

    best_element = "Unknown"
    best_difference = float("inf")

    for element, reference_mass in ELEMENT_MASSES.items():

        difference = abs(mass - reference_mass)

        if difference < best_difference:
            best_difference = difference
            best_element = element

    if best_difference <= tolerance:
        return best_element

    return "Unknown"


def load_lammps_data(filename, atom_style=None, element_map=None):
    """
    Read a LAMMPS data file using atomic or molecular atom style.

    Supported atom styles:

        atomic:
            atom-ID atom-type x y z

        molecular:
            atom-ID molecule-ID atom-type x y z

    Returns:
        atom_table: list of atom dictionaries
    """

    if element_map is None:
        element_map = {}

    masses = {}
    atoms = []

    section = None
    declared_atom_count = None

    with open(filename, "r") as file:

        for line_number, line in enumerate(file, start=1):

            line = line.split("#", 1)[0].strip()

            if not line:
                continue

            fields = line.split()

            # Detect section headers.
            if fields[0] == "Masses":
                section = "Masses"
                continue

            if fields[0] == "Atoms":
                section = "Atoms"

                # An optional comment may identify atom style.
                continue

            if section is None:

                if len(fields) >= 2 and fields[1] == "atoms":
                    declared_atom_count = int(fields[0])

                continue

            if section == "Masses":

                if len(fields) < 2:
                    continue

                atom_type = int(fields[0])
                mass = float(fields[1])

                masses[atom_type] = mass

            elif section == "Atoms":

                values = fields

                if atom_style == "atomic":

                    if len(values) < 5:
                        continue

                    atom_id = int(values[0])
                    molecule_id = None
                    atom_type = int(values[1])

                    x, y, z = map(float, values[2:5])

                elif atom_style == "molecular":

                    if len(values) < 6:
                        continue

                    atom_id = int(values[0])
                    molecule_id = int(values[1])
                    atom_type = int(values[2])

                    x, y, z = map(float, values[3:6])

                else:

                    # Automatic detection by column count.
                    if len(values) == 5:

                        atom_id = int(values[0])
                        molecule_id = None
                        atom_type = int(values[1])

                        x, y, z = map(float, values[2:5])

                    elif len(values) == 6:

                        atom_id = int(values[0])
                        molecule_id = int(values[1])
                        atom_type = int(values[2])

                        x, y, z = map(float, values[3:6])

                    else:
                        raise ValueError(
                            f"Unsupported atom format on line "
                            f"{line_number}: {values}"
                        )

                mass = masses.get(atom_type)

                element = element_map.get(
                    atom_type,
                    identify_element(mass) if mass is not None
                    else "Unknown"
                )

                atoms.append({
                    "lammps_id": atom_id,
                    "molecule_id": molecule_id,
                    "atom_type": atom_type,
                    "element": element,
                    "mass": mass,
                    "initial_position": np.array(
                        [x, y, z],
                        dtype=np.float64
                    )
                })

    # Sort atoms to match LAMMPS IMD ordering.
    atoms.sort(key=lambda atom: atom["lammps_id"])

    if declared_atom_count is not None:
        if len(atoms) != declared_atom_count:
            raise ValueError(
                f"Expected {declared_atom_count} atoms, "
                f"but parsed {len(atoms)}"
            )

    # Assign consecutive IMD indices.
    for imd_index, atom in enumerate(atoms):
        atom["imd_index"] = imd_index

    return atoms
