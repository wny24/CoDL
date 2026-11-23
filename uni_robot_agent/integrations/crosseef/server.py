"""Serve a native Cross-EEF episode on the shared owner-thread service."""
import hashlib
import os
from importlib.metadata import version
import sys
from pathlib import Path
from uni_robot_agent.integrations.simulation import server_parser, serve_episode
from .tasks import TASKS, ROBOT, native_root, task_name


def prepare(args):
    if os.environ.get('CROSS_EEF_SIM_NO_RENDER', '').lower() in {'1', 'true', 'yes', 'on'}:
        raise ValueError('Cross-EEF agent observations require SAPIEN rendering; unset CROSS_EEF_SIM_NO_RENDER')
    name = task_name(args.task)
    root = native_root(args.native_root)
    sys.path.insert(0, str(root / 'src'))
    import cross_eef_sim
    if not Path(cross_eef_sim.__file__).resolve().is_relative_to(root):
        raise ValueError('A different Cross-EEF checkout was imported')
    from cross_eef_sim.envs.factory import EnvironmentFactory
    from .adapter import CrossEefAdapter
    native, module, instruction = TASKS[name]
    env = EnvironmentFactory().create_env(native, robot_combination=ROBOT,
        left_robot_combination=ROBOT, right_robot_combination=ROBOT,
        controller_type='pd', horizon=args.max_steps)
    try:
        env.reset(seed=args.seed)
        if os.environ.get('CROSS_EEF_SIM_NO_RENDER', '').lower() in {'1', 'true', 'yes', 'on'}:
            raise RuntimeError('SAPIEN could not create a renderer. Run with access to the host GPU/Vulkan device.')
        sources = [f'src/cross_eef_sim/envs/tasks/{module}.py', 'src/cross_eef_sim/envs/base.py',
            'src/cross_eef_sim/agents/loader.py', 'src/cross_eef_sim/agents/assemblies.py',
            'src/cross_eef_sim/agents/controllers/pd_joint_pos.py',
            'assets/robots/xarm7_g2_gripper/xarm7_with_gripper.urdf']
        metadata = {'task_id': name, 'native_task': native, 'robot': ROBOT,
            'seed': args.seed, 'max_steps': args.max_steps,
            'sapien_version': version('sapien'),
            'source_sha256': {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources},
            'evaluation_profile': 'crosseef-native-direct-rgbd' if args.depth else 'crosseef-native-direct-rgb',
            'handover_semantics': 'Native BimanualTransport predicate: payload in target bin; transfer contact is not separately graded.' if name == 'Handover' else None}
        return CrossEefAdapter(env, root=root, instruction=instruction, metadata=metadata,
            episode_id=args.run_id, depth_enabled=args.depth, cameras=args.cameras)
    except BaseException:
        env.scene = None
        raise


def main():
    parser = server_parser(__doc__, 18790)
    parser.add_argument('--max-steps', type=int, default=1200)
    parser.add_argument('--cameras', nargs='+', choices=['front', 'top'], default=['front', 'top'])
    args = parser.parse_args()
    if args.max_steps < 1 or args.seed < 0:
        parser.error('Use positive --max-steps and nonnegative --seed')
    task_name(args.task)
    serve_episode(lambda: prepare(args), args, 'crosseef')


if __name__ == '__main__':
    main()
