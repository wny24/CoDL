"""Adopt a prepared SAPIEN interpreter without modifying the native checkout."""
from pathlib import Path
from uni_robot_agent.services.deployment.config import LaunchPlan, Recipe
from uni_robot_agent.services.deployment.runtime import check_python
from .tasks import native_root, task_name


def recipe(args):
    return Recipe.load(__package__, 'deployment.toml')


def validate(args):
    if getattr(args, 'runtime_profile', None):
        raise ValueError('Cross-EEF has one runtime; omit --runtime-profile')
    if args.command == 'setup' and not args.runtime_python:
        raise ValueError('Prepare a SAPIEN interpreter, then adopt it using --runtime-python and --native-root')
    if args.command != 'setup':
        task_name(args.task or '')
    if args.runtime_python:
        native_root(args.native_root)
    cameras = getattr(args, 'cameras', None)
    if cameras and (len(set(cameras)) != len(cameras) or set(cameras) - {'front', 'top'}):
        raise ValueError('Cross-EEF cameras must be unique front/top names')
    if getattr(args, 'seed', None) is not None and args.seed < 0:
        raise ValueError('Cross-EEF requires a nonnegative --seed')


def external_data(args):
    return {'native_root': str(native_root(args.native_root))}


def verify(runtime):
    native_root(runtime.data['native_root'])
    return check_python(runtime.python, ['sapien', 'scipy', 'transforms3d'], environment=runtime.environment)


def plan(args, runtime, output, run_id):
    task = task_name(args.task)
    port = args.port or 18790
    command = [runtime.python, '-m', 'uni_robot_agent.integrations.crosseef.server',
        '--native-root', str(native_root(runtime.data['native_root'])), '--task', task,
        '--output-dir', str(output / 'environment'), '--run-id', run_id,
        '--seed', str(args.seed if args.seed is not None else 0),
        '--host', args.host, '--port', str(port), '--depth' if args.depth else '--no-depth']
    if args.cameras:
        command.extend(['--cameras', *args.cameras])
    host = '127.0.0.1' if args.host == '0.0.0.0' else args.host
    return LaunchPlan(tuple(command), f'http://{host}:{port}',
        {'integration': 'crosseef', 'episode_id': run_id, 'metadata.task_id': task},
        runtime.environment, Path(output))
