"""Public task names and their native, unchanged success predicates."""
from pathlib import Path

ROBOT = 'xarm7_g2_gripper'
TASKS = {
    'CanSortDual': ('BimanualCanSortDual', 'can_sort',
        'First use the right arm to grasp the red can around the middle of its body and '
        'place it in the red bin on the left. Release it and confirm it is resting inside '
        'the bin. Then use the left arm to grasp the blue can around the middle of its '
        'body and place it in the blue bin on the right. Do not reverse this order or '
        'manipulate both cans at the same time. Throughout the entire task, keep the line '
        'connecting the two contact pads of each gripper horizontal.'),
    'LaptopCleanup': ('BimanualLaptopCleanup', 'laptop_cleanup',
        'Place the mouse on the laptop keyboard surface and close the laptop screen.'),
    'LiftTray': ('BimanualLiftTray', 'lift_tray',
        'Use both grippers to lift the tray by its handles so its bottom is more than 5 cm above the table.'),
    'Handover': ('BimanualTransport', 'transport',
        'Transfer the can from the start bin to the target bin, using a handover between the arms as needed.'),
}


def task_name(value: str) -> str:
    for name, (native, _, _) in TASKS.items():
        if value.lower() in (name.lower(), native.lower()):
            return name
    raise ValueError(f'Unknown Cross-EEF task {value!r}; choose {", ".join(TASKS)}')


def native_root(path) -> Path:
    if path is None:
        raise ValueError('Cross-EEF requires --native-root pointing to the existing crosseef-merged checkout')
    root = Path(path).expanduser().resolve(strict=True)
    required = ['src/cross_eef_sim/envs/base.py',
                'assets/robots/xarm7_g2_gripper/xarm7_with_gripper.urdf']
    required += [f'src/cross_eef_sim/envs/tasks/{item[1]}.py' for item in TASKS.values()]
    for relative in required:
        if not (root / relative).is_file():
            raise ValueError(f'Missing Cross-EEF source/asset: {relative}')
    return root
