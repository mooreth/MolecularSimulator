
import numpy as np


class MolecularSystem:

    def __init__(self, atom_table):
        """
        Initialize a molecular system from the atom table
        returned by load_lammps_data().
        """

        self.atoms = atom_table
        self.n_atoms = len(atom_table)

        # Static atom information, indexed by IMD index.
        self.atom_by_imd_index = {
            atom["imd_index"]: atom
            for atom in atom_table
        }

        # Store atomic masses in IMD index order.
        self.masses = np.zeros(
            self.n_atoms,
            dtype=np.float32
        )

        # Dynamic simulation state.
        self.positions = np.zeros(
            (self.n_atoms, 3),
            dtype=np.float32
        )

        self.frame_number = 0
        self.timestamp = None
        self.frame_rate = 0.0

        # Initialize from original LAMMPS coordinates.
        for atom in atom_table:

            index = atom["imd_index"]

            self.positions[index] = atom["initial_position"]
            self.masses[index] = atom["mass"]


    def update(self, frame):
        """
        Update the molecular system from an IMD frame.
        """

        positions = np.asarray(
            frame.positions,
            dtype=np.float32
        )

        if positions.shape != (self.n_atoms, 3):
            raise ValueError(
                f"Expected {(self.n_atoms, 3)} positions, "
                f"received {positions.shape}"
            )

        self.positions[:] = positions

        self.frame_number = frame.frame_number
        self.timestamp = frame.timestamp


    def get_atom(self, imd_index):
        """Return static metadata for an atom."""

        return self.atom_by_imd_index[imd_index]


    def get_position(self, imd_index):
        """Return the current position of an atom."""

        return self.positions[imd_index]


    def get_element(self, imd_index):
        """Return the element of an atom."""

        return self.atom_by_imd_index[imd_index]["element"]


    def get_positions(self):
        """Return the current position array."""

        return self.positions


    # -----------------------------------------
    # Molecular system diagnostics
    # -----------------------------------------

    def get_element_counts(self):
        """
        Return the number of atoms of each element.

        Example:
        {'C': 10, 'H': 16}
        """

        counts = {}

        for atom in self.atoms:

            element = atom["element"]

            counts[element] = counts.get(element, 0) + 1

        return counts


    def get_coordinate_bounds(self):
        """
        Return minimum and maximum coordinates
        along each axis.
        """

        return {
            "min": np.min(self.positions, axis=0),
            "max": np.max(self.positions, axis=0)
        }


    def get_center_of_mass(self):
        """
        Calculate the current center of mass.

        Uses atomic masses and current positions.
        """

        total_mass = np.sum(self.masses)

        if total_mass <= 0:
            raise ValueError("Total molecular mass must be positive.")

        weighted_positions = (
            self.positions * self.masses[:, np.newaxis]
        )

        center_of_mass = (
            np.sum(weighted_positions, axis=0) / total_mass
        )

        return center_of_mass


    def get_molecular_extent(self):
        """
        Return the molecular dimensions along X, Y, Z.
        """

        bounds = self.get_coordinate_bounds()

        return bounds["max"] - bounds["min"]
