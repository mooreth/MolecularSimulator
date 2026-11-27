"""Load and validate the Molecular Simulator TOML configuration."""

from pathlib import Path
import math
import re

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - used by older embedded Python
    try:
        import tomli as tomllib
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "TOML support is required. Use Python 3.11+ or install tomli."
        ) from error


DEFAULT_CONFIG_FILE = Path(__file__).resolve().with_name("config.toml")


def _require(mapping, key, section):
    if key not in mapping:
        raise ValueError(f"Missing configuration value [{section}] {key}")
    return mapping[key]


def _resolve_path(value, config_dir, key):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = config_dir / path
    return path.resolve()


def load_config(config_file=None):
    """Load TOML settings and resolve configured file paths.

    Relative paths are interpreted relative to the directory containing
    config.toml, not relative to the process working directory.
    """
    config_path = Path(config_file or DEFAULT_CONFIG_FILE).expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("rb") as stream:
        config = tomllib.load(stream)

    files = config.setdefault("files", {})
    paths = {}
    for key in ("data_file", "group_file", "simulation_file"):
        value = _require(files, key, "files")
        resolved = _resolve_path(value, config_path.parent, key)
        if not resolved.is_file():
            raise FileNotFoundError(
                f"Configured [{key}] file does not exist: {resolved}"
            )
        paths[key] = resolved
    config["resolved_files"] = paths

    network = config.setdefault("network", {})
    network.setdefault("imd_host", "127.0.0.1")
    network.setdefault("samson_host", "127.0.0.1")
    network.setdefault("imd_port", 5678)
    network.setdefault("samson_port", 5679)
    
    for key in ("imd_host", "samson_host"):
        network[key] = str(network[key]).strip()
        if not network[key]:
            raise ValueError(f"[network] {key} cannot be empty")
    
    for key in ("imd_port", "samson_port"):
        port = int(network[key])
        if not 1 <= port <= 65535:
            raise ValueError(f"[network] {key} must be between 1 and 65535")
        network[key] = port

    simulation = config.setdefault("simulation", {})
    simulation.setdefault("steps_per_update", 10)
    simulation["steps_per_update"] = int(simulation["steps_per_update"])
    if simulation["steps_per_update"] < 1:
        raise ValueError("[simulation] steps_per_update must be at least 1")

    lammps_settings = config.setdefault("lammps", {})
    lammps_settings.setdefault("atom_style", "molecular")
    lammps_settings["atom_style"] = str(lammps_settings["atom_style"]).lower()
    if lammps_settings["atom_style"] not in {"atomic", "molecular", "charge", "full"}:
        raise ValueError(
            "[lammps] atom_style must be atomic, molecular, charge, or full"
        )

    imd = config.setdefault("imd", {})
    imd.setdefault("transfer_rate", 10)
    imd["transfer_rate"] = int(imd["transfer_rate"])
    if imd["transfer_rate"] < 1:
        raise ValueError("[imd] transfer_rate must be at least 1")

    # Multiple independently controlled motors. Each motor has its own
    # group, fix ID, speed and three keyboard bindings.
    # Backward compatibility: a legacy [motor] plus [controls] configuration
    # is converted into a one-entry [motors] mapping.
    legacy_motor = config.get("motor")
    legacy_controls = config.get("controls", {})
    motors = config.get("motors")
    if motors is None:
        if legacy_motor is None:
            legacy_motor = {}
        motors = {
            "motor1": {
                "group": legacy_motor.get("group", "motor1"),
                "fix_id": legacy_motor.get("fix_id", "motor1_move"),
                "velocity": legacy_motor.get("velocity", 10.0),
                "forward_key": legacy_controls.get("forward_key", "j"),
                "stop_key": legacy_controls.get("stop_key", "k"),
                "reverse_key": legacy_controls.get("reverse_key", "l"),
            }
        }
    if not isinstance(motors, dict) or not motors:
        raise ValueError("[motors] must define at least one motor")

    used_groups = set()
    used_fix_ids = set()
    used_keys = set()
    for motor_name, motor in motors.items():
        if not isinstance(motor, dict):
            raise ValueError(f"[motors.{motor_name}] must be a table")
        motor.setdefault("group", motor_name)
        motor.setdefault("fix_id", f"{motor_name}_move")
        motor.setdefault("motion", "linear")
        motor["motion"] = str(motor["motion"]).lower()
        if motor["motion"] not in {"linear", "rotate", "force"}:
            raise ValueError(
                f"[motors.{motor_name}] motion must be 'linear', 'rotate', or 'force'"
            )
        # Defaults preserve the original J/K/L mapping for motor1. The
        # second motor defaults to F/G/H; further motors require explicit keys.
        defaults = ("j", "k", "l") if motor_name == "motor1" else ("f", "g", "h") if motor_name == "motor2" else (None, None, None)
        for key, default in zip(("forward_key", "stop_key", "reverse_key"), defaults):
            if key not in motor and default is not None:
                motor[key] = default
            if key not in motor:
                raise ValueError(f"Missing [motors.{motor_name}] {key}")
            motor[key] = str(motor[key]).lower()
            if len(motor[key]) != 1:
                raise ValueError(f"[motors.{motor_name}] {key} must be one character")
            if motor[key] in used_keys:
                raise ValueError(f"Keyboard key '{motor[key]}' is assigned more than once")
            used_keys.add(motor[key])

        motor["group"] = str(motor["group"])
        motor["fix_id"] = str(motor["fix_id"])
        for key in ("group", "fix_id"):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", motor[key]):
                raise ValueError(f"[motors.{motor_name}] {key} must be a valid LAMMPS identifier")
        if motor["group"] in used_groups:
            raise ValueError(f"Multiple motors cannot control the same LAMMPS group: {motor['group']}")
        if motor["fix_id"] in used_fix_ids:
            raise ValueError(f"LAMMPS fix ID is duplicated: {motor['fix_id']}")
        used_groups.add(motor["group"])
        used_fix_ids.add(motor["fix_id"])
        if motor["motion"] == "linear":
            motor.setdefault("velocity", 10.0)
            motor["velocity"] = float(motor["velocity"])
            if not math.isfinite(motor["velocity"]) or motor["velocity"] <= 0:
                raise ValueError(
                    f"[motors.{motor_name}] velocity must be a finite value greater than zero"
                )
        elif motor["motion"] == "rotate":
            if "period" not in motor:
                raise ValueError(
                    f"[motors.{motor_name}] period is required for rotational motion"
                )
            motor["period"] = float(motor["period"])
            if not math.isfinite(motor["period"]) or motor["period"] <= 0:
                raise ValueError(
                    f"[motors.{motor_name}] period must be a finite value greater than zero"
                )
            motor.setdefault("pivot", "group_centroid")
            pivot = motor["pivot"]
            if isinstance(pivot, str):
                if pivot.lower() != "group_centroid":
                    raise ValueError(
                        f"[motors.{motor_name}] pivot string must be 'group_centroid'"
                    )
                motor["pivot"] = "group_centroid"
            elif isinstance(pivot, (list, tuple)) and len(pivot) == 3:
                try:
                    pivot = [float(value) for value in pivot]
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"[motors.{motor_name}] pivot coordinates must be numeric"
                    ) from error
                if not all(math.isfinite(value) for value in pivot):
                    raise ValueError(
                        f"[motors.{motor_name}] pivot coordinates must be finite"
                    )
                motor["pivot"] = pivot
            else:
                raise ValueError(
                    f"[motors.{motor_name}] pivot must be 'group_centroid' or [x, y, z]"
                )
        else:
            if "force" not in motor:
                raise ValueError(
                    f"[motors.{motor_name}] force is required for force-driven motion"
                )
            motor["force"] = float(motor["force"])
            if not math.isfinite(motor["force"]) or motor["force"] <= 0:
                raise ValueError(
                    f"[motors.{motor_name}] force must be a finite value greater than zero, in nN"
                )
            motor.setdefault("force_units", "nN")
            motor["force_units"] = str(motor["force_units"]).lower()
            if motor["force_units"] != "nn":
                raise ValueError(
                    f"[motors.{motor_name}] force_units must be 'nN'; force is configured in nanonewtons"
                )

        # Normalize the direction vector so speed/period semantics remain
        # independent of the length of the configured direction vector.
        axis = motor.get("axis", [1.0, 0.0, 0.0])
        if not isinstance(axis, (list, tuple)) or len(axis) != 3:
            raise ValueError(f"[motors.{motor_name}] axis must contain exactly three numbers")
        try:
            axis = [float(component) for component in axis]
        except (TypeError, ValueError) as error:
            raise ValueError(f"[motors.{motor_name}] axis components must be numeric") from error
        if not all(math.isfinite(component) for component in axis):
            raise ValueError(f"[motors.{motor_name}] axis components must be finite")
        magnitude = math.sqrt(sum(component * component for component in axis))
        if magnitude == 0.0:
            raise ValueError(f"[motors.{motor_name}] axis cannot be the zero vector")
        motor["axis"] = [component / magnitude for component in axis]

    controls = config.setdefault("controls", {})
    controls.setdefault("quit_key", legacy_controls.get("quit_key", "q"))
    controls["quit_key"] = str(controls["quit_key"]).lower()
    if len(controls["quit_key"]) != 1:
        raise ValueError("[controls] quit_key must be exactly one character")
    if controls["quit_key"] in used_keys:
        raise ValueError("The quit key must be different from all motor keys")
    config["motors"] = motors
    config["controls"] = controls
    # Main controller consumes the normalized config; remove obsolete aliases.
    config.pop("motor", None)

    samson = config.setdefault("samson", {})
    samson.setdefault("display_interval_ms", 16)
    samson["display_interval_ms"] = int(samson["display_interval_ms"])
    if samson["display_interval_ms"] < 1:
        raise ValueError("[samson] display_interval_ms must be at least 1")

    elements = config.setdefault("elements", {})
    overrides = elements.setdefault("overrides", {})
    elements["overrides"] = {int(atom_type): str(symbol)
                              for atom_type, symbol in overrides.items()}

    config["config_file"] = config_path
    return config


def lammps_quote(value):
    """Quote a string for safe insertion into a LAMMPS input command."""
    value = str(value)
    if '"' in value or "\n" in value or "\r" in value:
        raise ValueError("LAMMPS path values cannot contain quotes or newlines")
    return f'"{value}"'
