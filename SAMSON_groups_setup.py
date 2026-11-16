"""Export the registered SAMSON model and its structural groups to LAMMPS.

Run SAMSON_run.py first, define structural groups on that live model, then
execute this script in the same SAMSON Python session. The script reuses the
registered SAMSON atom objects; it does not import or create another model.
"""

from pathlib import Path
import math
import os
import re
import sys
import tempfile


# ---------------------------------------------------------------------------
# Locate the application configuration and shared SAMSON session.
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
IMD_CLIENT_DIR = PROJECT_DIR / "IMD_client"
if str(IMD_CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(IMD_CLIENT_DIR))

from configuration import load_config
import samson_session

CONFIG = load_config(IMD_CLIENT_DIR / "config.toml")
DATA_FILE = CONFIG["resolved_files"]["data_file"]
GROUP_FILE = CONFIG["resolved_files"]["group_file"]
ATOM_STYLE = CONFIG["lammps"]["atom_style"]
BOX_PADDING = float(CONFIG.get("export", {}).get("box_padding", 10.0))

if BOX_PADDING < 0:
    raise ValueError("[export] box_padding must be zero or greater")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LAMMPS_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RESERVED_GROUP_NAMES = {"all", "free"}


def atomic_write_text(path, writer):
    """Write a file beside its destination, then replace it atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=str(path.parent),
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            writer(stream)

        os.replace(str(temporary_path), str(path))

    except Exception:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def atom_position_angstrom(atom):
    """Return an atom's current SAMSON coordinates in angstroms."""
    return (
        float(SBQuantity.angstrom(atom.getX()).value),
        float(SBQuantity.angstrom(atom.getY()).value),
        float(SBQuantity.angstrom(atom.getZ()).value),
    )


def get_group_name(group):
    """Read a structural group's name using the SAMSON Python binding."""
    name = getattr(group, "name", None)
    if name is None and hasattr(group, "getName"):
        name = group.getName()
    name = str(name or "").strip()

    if not name:
        raise ValueError("Found a SAMSON structural group with no name")
    if not LAMMPS_ID_PATTERN.fullmatch(name):
        raise ValueError(
            f"SAMSON group name {name!r} is not a valid LAMMPS group ID. "
            "Use only letters, numbers, and underscores, and begin with a "
            "letter or underscore."
        )
    if name in RESERVED_GROUP_NAMES:
        raise ValueError(
            f"SAMSON group name {name!r} is reserved by the exporter. "
            f"Choose another name; reserved names are {sorted(RESERVED_GROUP_NAMES)}."
        )
    return name


def discover_jig_groups(ordered_atoms, atom_table):
    """Find group nodes by capability, then intersect membership with the model.

    SAMSON documents can contain different kinds of node groups. Rather than
    assuming that every user-created group is classified by the NSL type
    ``structuralGroup``, inspect the active document's nodes and retain nodes
    that expose the documented getGroupNodes() interface. This also supports
    groups created through the Document view's grouping commands.
    """
    if len(ordered_atoms) != len(atom_table):
        raise RuntimeError(
            "The registered SAMSON atom count does not match the loaded "
            "LAMMPS atom table. Restart SAMSON_run.py before exporting."
        )

    atom_id_by_object = {
        id(atom): int(entry["lammps_id"])
        for atom, entry in zip(ordered_atoms, atom_table)
    }

    # SAMSON.getNodes() with no NSL expression returns all nodes in the active
    # document. Group node classes expose getGroupNodes().
    all_nodes = SAMSON.getNodes()
    group_nodes = []
    for node in all_nodes:
        get_members = getattr(node, "getGroupNodes", None)
        if callable(get_members):
            group_nodes.append(node)

    print(
        f"Nodes in active SAMSON document: {len(all_nodes)}; "
        f"group-capable nodes found: {len(group_nodes)}"
    )

    groups = {}
    for group in group_nodes:
        members = group.getGroupNodes()
        atom_ids = []
        for atom in ordered_atoms:
            if members.hasNode(atom):
                atom_ids.append(atom_id_by_object[id(atom)])

        # Ignore groups unrelated to the registered live model.
        if atom_ids:
            name = get_group_name(group)
            if name in groups:
                raise ValueError(f"Duplicate SAMSON group name: {name!r}")
            groups[name] = sorted(atom_ids)
            print(f"  {name}: {len(atom_ids)} atoms")

    return groups


def validate_atom_table(atom_table, atom_style):
    """Check that the atom table has all fields needed for the selected style."""
    if not atom_table:
        raise ValueError("The registered molecular system contains no atoms")

    atom_ids = [int(atom["lammps_id"]) for atom in atom_table]
    if len(atom_ids) != len(set(atom_ids)):
        raise ValueError("The LAMMPS atom table contains duplicate atom IDs")

    type_masses = {}
    for atom in atom_table:
        atom_type = int(atom["atom_type"])
        mass = atom.get("mass")
        if atom_type < 1:
            raise ValueError(f"Invalid LAMMPS atom type: {atom_type}")
        if mass is None:
            raise ValueError(
                f"No mass was found for LAMMPS atom type {atom_type}"
            )
        mass = float(mass)
        if atom_type in type_masses and not math.isclose(
            type_masses[atom_type], mass, rel_tol=0.0, abs_tol=1e-8
        ):
            raise ValueError(
                f"Conflicting masses found for LAMMPS atom type {atom_type}"
            )
        type_masses[atom_type] = mass

        if atom_style in {"molecular", "full"} and atom.get("molecule_id") is None:
            raise ValueError(
                f"Atom {atom['lammps_id']} has no molecule ID, but atom_style "
                f"is {atom_style!r}"
            )
        if atom_style in {"charge", "full"} and atom.get("charge") is None:
            raise ValueError(
                f"Atom {atom['lammps_id']} has no charge, but atom_style "
                f"is {atom_style!r}"
            )

    max_type = max(type_masses)
    missing_types = [atom_type for atom_type in range(1, max_type + 1)
                     if atom_type not in type_masses]
    if missing_types:
        raise ValueError(
            "The exported atoms do not contain masses for every type from 1 "
            f"through {max_type}. Missing types: {missing_types}"
        )

    return type_masses


def calculate_box_bounds(positions, padding):
    """Return correctly padded LAMMPS bounds for x, y, and z."""
    if not positions:
        raise ValueError("Cannot calculate a simulation box without atoms")

    bounds = []
    for axis in range(3):
        values = [position[axis] for position in positions]
        low = min(values) - padding
        high = max(values) + padding
        if low == high:
            high = low + 1.0
        bounds.append((low, high))
    return bounds


def write_lammps_data(path, atom_table, positions, atom_style, padding):
    """Write a LAMMPS data file using original IDs/types/masses and live xyz."""
    type_masses = validate_atom_table(atom_table, atom_style)
    bounds = calculate_box_bounds(positions, padding)

    if len(positions) != len(atom_table):
        raise ValueError("Position count does not match the LAMMPS atom count")

    def writer(stream):
        stream.write("Molecular Simulator export from SAMSON\n\n")
        stream.write(f"{len(atom_table)} atoms\n")
        stream.write(f"{max(type_masses)} atom types\n\n")
        for (low, high), axis in zip(bounds, "xyz"):
            stream.write(f"{low:.8f} {high:.8f} {axis}lo {axis}hi\n")

        stream.write("\nMasses\n\n")
        for atom_type in sorted(type_masses):
            stream.write(f"{atom_type} {type_masses[atom_type]:.10g}\n")

        stream.write(f"\nAtoms # {atom_style}\n\n")
        for atom, (x, y, z) in zip(atom_table, positions):
            atom_id = int(atom["lammps_id"])
            atom_type = int(atom["atom_type"])

            if atom_style == "atomic":
                fields = [atom_id, atom_type]
            elif atom_style == "molecular":
                fields = [atom_id, int(atom["molecule_id"]), atom_type]
            elif atom_style == "charge":
                fields = [atom_id, atom_type, f"{float(atom['charge']):.10g}"]
            elif atom_style == "full":
                fields = [
                    atom_id,
                    int(atom["molecule_id"]),
                    atom_type,
                    f"{float(atom['charge']):.10g}",
                ]
            else:
                raise ValueError(f"Unsupported LAMMPS atom style: {atom_style}")

            fields.extend((f"{x:.8f}", f"{y:.8f}", f"{z:.8f}"))
            stream.write(" ".join(map(str, fields)) + "\n")

    atomic_write_text(path, writer)
    print(f"LAMMPS data file written: {path}")


def write_lammps_groups(path, groups, atom_count):
    """Write discovered jig groups and a complementary free group."""
    def writer(stream):
        stream.write("# Generated from SAMSON structural groups\n")
        stream.write(f"# Total atoms in exported model: {atom_count}\n\n")

        for name in sorted(groups):
            ids = " ".join(str(atom_id) for atom_id in groups[name])
            stream.write(f"group {name} id {ids}\n")

        if groups:
            names = " ".join(sorted(groups))
            stream.write(f"group free subtract all {names}\n")
        else:
            stream.write("group free union all\n")

    atomic_write_text(path, writer)
    print(f"LAMMPS group definitions written: {path}")


def print_group_centroids(groups, atom_table, positions):
    """Print group atom counts and geometric centroids for diagnostics."""
    position_by_id = {
        int(atom["lammps_id"]): position
        for atom, position in zip(atom_table, positions)
    }

    memberships = dict(groups)
    jig_ids = set()
    for atom_ids in groups.values():
        jig_ids.update(atom_ids)
    memberships["free"] = [
        int(atom["lammps_id"]) for atom in atom_table
        if int(atom["lammps_id"]) not in jig_ids
    ]

    print("\nGroup summary:")
    for name, atom_ids in memberships.items():
        if not atom_ids:
            print(f"  {name}: 0 atoms")
            continue
        xyz = [position_by_id[atom_id] for atom_id in atom_ids]
        centroid = tuple(
            sum(position[axis] for position in xyz) / len(xyz)
            for axis in range(3)
        )
        print(
            f"  {name}: {len(atom_ids)} atoms; centroid "
            f"({centroid[0]:.3f}, {centroid[1]:.3f}, {centroid[2]:.3f}) A"
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_samson_groups():
    if not samson_session.has_molecular_system():
        raise RuntimeError(
            "No molecular system is registered. Run IMD_client/SAMSON_run.py "
            "first, define structural groups on its model, and then run "
            "SAMSON_groups_setup.py in the same SAMSON session."
        )

    atom_table = samson_session.atom_table
    ordered_atoms = samson_session.get_ordered_atoms()

    if len(ordered_atoms) != samson_session.expected_atom_count:
        raise RuntimeError("SAMSON session atom references are incomplete")

    print(
        "Exporting registered SAMSON model:",
        len(ordered_atoms),
        "atoms; no additional structure will be imported."
    )

    positions = [atom_position_angstrom(atom) for atom in ordered_atoms]
    groups = discover_jig_groups(ordered_atoms, atom_table)

    # Write the group file first. If data-file export fails, LAMMPS will not
    # see a partially rewritten data file.
    write_lammps_groups(GROUP_FILE, groups, len(atom_table))
    write_lammps_data(
        DATA_FILE,
        atom_table,
        positions,
        ATOM_STYLE,
        BOX_PADDING,
    )
    print_group_centroids(groups, atom_table, positions)

    print("\nExport complete.")
    print("Data file:", DATA_FILE)
    print("Group file:", GROUP_FILE)
    print("Discovered jig groups:", sorted(groups) if groups else "None")


export_samson_groups()
