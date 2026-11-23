# Native source and assets

This adapter uses an explicitly supplied Cross-EEF (`cross_eef_sim`) checkout.
It does not vendor, modify or redistribute its simulator, task implementations,
robot meshes or object assets. Their upstream licenses continue to apply.

Both arms load `assets/robots/xarm7_g2_gripper/xarm7_with_gripper.urdf` through
the native assembly registry. The native loader retains its joint exclusions,
G2 mimic mapping, flipped opening convention, PD gains and collision setup.

The four public names map to these native environment classes:

- `CanSortDual`: `BimanualCanSortDual`
- `LaptopCleanup`: `BimanualLaptopCleanup`
- `LiftTray`: `BimanualLiftTray`
- `Handover`: `BimanualTransport`

The last mapping follows the native DCD simulation experiment scripts. Its
success predicate checks that the payload reaches the target bin, not that
an inter-arm handover contact occurred. The adapter does not strengthen it.

The native checkout may contain local research changes. The service records
source and robot URDF hashes rather than requiring a clean Git revision.
See [the integration guide](../../../docs/crosseef.md) for the control and
observation profile and validation scope.
