# Public release checklist

Use this checklist when creating the public GitHub repository and tagging the first release.

## Before publishing

- [x] Add the MIT License (`LICENSE`); verify the copyright holder and year before publishing.
- [ ] Review the README and installation guide against the exact release environment.
- [ ] Confirm the default C60 data file, AIREBO potential availability, and LAMMPS build requirements.
- [ ] Back up the working Pass 2.4 project before making repository changes.
- [ ] Run Python syntax compilation and the documented configuration/data-file smoke checks.
- [ ] Run a live SAMSON/LAMMPS test with the default two motors.
- [ ] If possible, run a live rotational-motor test using an exported `motor3` group.
- [ ] Check that no local paths, credentials, private data, or generated simulation output are committed.

## Suggested GitHub setup

- Repository name: `MolecularSimulator`
- Initial release label: `v0.2.4-alpha` (suggested; choose a versioning convention before tagging)
- Repository description: `Interactive atomistic simulation and molecular-machine control using LAMMPS, Python, and SAMSON.`
- Topics: `molecular-dynamics`, `lammps`, `samson`, `atomistic-simulation`, `molecular-machines`, `nanotechnology`
- Enable GitHub Issues so users can report problems and request features.
- Add the README, installation guide, configuration reference, contributing guide, and changelog to the repository.

## After publishing

- [ ] Create a GitHub release with the matching tag.
- [ ] Include a concise summary of Pass 2.4 features and known limitations.
- [ ] Invite users to test the C60 example and report their environment details.
- [ ] Keep protein/AMBER support out of the initial scope unless community feedback justifies it.
