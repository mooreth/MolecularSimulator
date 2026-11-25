# Multi-motor setup (Pass 2.4)

This note summarizes the multi-motor controls. For complete installation instructions, see [docs/INSTALLATION.md](docs/INSTALLATION.md). For every TOML option, see [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Default keyboard mapping

| Motor | Forward | Stop | Reverse | Default axis |
|---|---|---|---|---|
| `motor1` | J | K | L | +X |
| `motor2` | F | G | H | +Y |
| Optional `motor3` | U | I | O | +Z rotation axis |

`Q` quits the controller. Keys can be changed in `IMD_client/config.toml`.

## Required SAMSON groups

The default configuration enables `motor1` and `motor2`. Create both groups on the live molecular model created by `IMD_client/SAMSON_run.py`. Static groups such as `anchor1` can coexist. Then execute `SAMSON_groups_setup.py` in the same SAMSON Python session and verify that the expected groups and atom counts are reported.

The controller checks that every configured motor group is present in the exported LAMMPS group file before starting. The exporter defines `free` as all atoms outside the discovered jig groups, so motor and anchor atoms are excluded from the supplied `fix integrate_free` and thermostat commands.

Do not assign the same atoms to two independently controlled motor groups.

## Linear motion

Each motor has its own LAMMPS fix ID and direction state. `axis = [x, y, z]` specifies a global LAMMPS direction; the vector is normalized automatically. `velocity` is the speed magnitude. Forward applies the positive direction and reverse applies the negative direction.

With the supplied `units metal`, linear velocity is in Å/ps.

## Rotational motion

Set `motion = "rotate"`, provide an `axis`, a `period`, and a `pivot`:

```toml
[motors.motor3]
group = "motor3"
fix_id = "motor3_rotate"
motion = "rotate"
axis = [0.0, 0.0, 1.0]
period = 10.0
pivot = "group_centroid"  # or [x, y, z] in Angstroms
forward_key = "u"
stop_key = "i"
reverse_key = "o"
```

Uncomment/enable this section only after creating and exporting a SAMSON structural group named `motor3`. `period` is one complete revolution in active LAMMPS time units. Positive and negative rotation follow the right-hand rule. The centroid pivot uses the initial exported atom coordinates.

Rotation is prescribed kinematic motion through `fix move rotate`; it does not respond to torque. A motor group must not also be time-integrated by another fix.
