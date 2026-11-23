"""Shared SAMSON session state for the live simulator scripts.

SAMSON_run.py creates the visual molecular model and registers its atom
objects here. SAMSON_groups_setup.py reuses those exact objects; it must not
create or import another molecular model.
"""

structural_model = None
samson_atoms = {}
atom_table = []
expected_atom_count = 0
server_running = False


def register_molecular_system(model, atoms_by_imd_index, loaded_atom_table):
    """Register the one SAMSON model created by SAMSON_run.py."""
    global structural_model, samson_atoms, atom_table, expected_atom_count

    structural_model = model
    samson_atoms = dict(atoms_by_imd_index)
    atom_table = list(loaded_atom_table)
    expected_atom_count = len(samson_atoms)


def has_molecular_system():
    return structural_model is not None and bool(samson_atoms)


def get_ordered_atoms():
    """Return the registered SAMSON atoms in LAMMPS/IMD index order."""
    if not has_molecular_system():
        raise RuntimeError(
            "No SAMSON molecular system is registered. Run SAMSON_run.py "
            "first, then run SAMSON_groups_setup.py in the same SAMSON session."
        )

    indices = sorted(samson_atoms)
    if indices != list(range(len(indices))):
        raise RuntimeError(
            "Registered SAMSON atom indices are not contiguous and zero-based."
        )
    return [samson_atoms[index] for index in indices]
