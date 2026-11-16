# Pass 2.4 — Rotational motor support

This pass adds `motion = "rotate"` while preserving `motion = "linear"` as the default.

For a rotational motor:

- `axis = [x, y, z]` defines the rotation axis direction; it is normalized.
- `period` is the time for one full 360-degree revolution, in LAMMPS time units.
- `pivot = "group_centroid"` calculates the pivot from the initial exported coordinates of the motor group.
- Alternatively, `pivot = [x, y, z]` specifies the pivot explicitly in Angstroms.
- Forward follows the right-hand rule along the configured axis; reverse uses the opposite axis; stop unfixes the prescribed motion.
- The generated command uses `units box`, ensuring the pivot is interpreted in box distance units.

The optional motor3 example is commented out in `IMD_client/config.toml`. Uncomment it after creating and exporting a SAMSON structural group named `motor3`. Default example keys are U (forward), I (stop), and O (reverse).

This is prescribed kinematic motion, not torque-driven rotation. The motor group must not also be time-integrated by another fix. The SAMSON exporter places all jig groups outside `free`, so this condition is maintained by the current project workflow.
