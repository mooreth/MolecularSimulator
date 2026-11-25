# Contributing

Thanks for your interest in MolecularSimulator. The project is an experimental research codebase, and practical reports from people trying it on real systems are especially valuable.

## Before opening an issue

Please check existing issues and include enough information to reproduce the problem.

### Bug reports

Include:

- Operating system and version.
- Python version and the exact interpreter used for `main.py`.
- SAMSON version.
- LAMMPS version, build type, and enabled packages (especially IMD and MANYBODY for the supplied example).
- Whether the problem occurs in SAMSON startup, group export, LAMMPS startup, IMD streaming, or motor control.
- Relevant `config.toml` sections (remove private paths or information if necessary).
- Complete error messages and console output.
- A minimal data file or reproducible example when possible.

### Feature requests

Describe the scientific or engineering workflow the feature would enable, the system/force field involved, and whether you are interested in testing or contributing an implementation.

## Pull requests

- Keep changes focused and explain the problem they solve.
- Preserve the supplied C60/AIREBO demonstration unless a change intentionally updates it.
- Do not silently change units, timestep semantics, atom ordering, or network protocol behavior.
- Document new configuration options and limitations.
- Include tests or a reproducible manual test procedure.
- Clearly identify any feature that has not been tested in a live SAMSON/LAMMPS session.

## Current development focus

The near-term focus is diamond systems, topology handling for diamond structures, and integration of a diamond force field. Protein/AMBER support is not part of the current release scope, but community interest and contributions can help shape future work.

## AI-assisted contributions

AI tools may be used as development assistants, but contributors remain responsible for reviewing, testing, and understanding submitted changes. When ChatGPT materially assists with a commit, this project recommends adding the following commit-message trailer:

```text
Assisted-by: ChatGPT (OpenAI, GPT-6)
```

Use an equivalent, accurate attribution for other AI tools. This records tool assistance; it does not make the tool a legal co-author. See [AI_ASSISTANCE.md](AI_ASSISTANCE.md).
