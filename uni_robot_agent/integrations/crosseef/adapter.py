"""Native SAPIEN execution and observations for dual xArm7/G2 episodes."""
import time

import numpy as np
from scipy.spatial.transform import Rotation

from uni_robot_agent.services.environment.contracts import (
    ArmControlCapabilities, ArmDescription, ArmState, CameraDescription,
    EnvironmentDescription, EnvironmentState, JointTarget, Pose, PoseCommand,
    RequestRejected, StepReceipt,
)
from uni_robot_agent.services.environment.snapshots import CameraFrame, CapturedObservation


def camera_pose(eye, target):
    import sapien
    forward = np.asarray(target, dtype=float) - eye
    forward /= np.linalg.norm(forward)
    left = np.cross([0., 0., 1.], forward)
    left /= np.linalg.norm(left)
    up = np.cross(forward, left)
    xyzw = Rotation.from_matrix(np.column_stack([forward, left, up])).as_quat()
    return sapien.Pose(eye, np.roll(xyzw, 1))


class CrossEefAdapter:
    def __init__(self, env, *, root, instruction, metadata, episode_id,
                 depth_enabled=False, cameras=('front', 'top')):
        self.env, self.instruction, self.metadata = env, instruction, metadata
        self.episode_id, self.depth_enabled = episode_id, depth_enabled
        self.steps, self.finished, self.success, self.closed = 0, False, False, False
        self.outcome = None
        self.agents = {'left': env.agent.left, 'right': env.agent.right}
        self.models, self.links, self.indices, self.bounds = {}, {}, {}, {}
        self.openings = {}
        arms = []
        for name, agent in self.agents.items():
            robot = agent.robot
            indices = np.asarray(agent.controller.active_joint_indices, dtype=int)
            if len(indices) != 8:
                raise ValueError('Expected seven arm joints and one G2 drive joint')
            links = robot.get_links()
            self.links[name] = next(i for i, link in enumerate(links) if link.name == 'link_tcp')
            self.models[name] = robot.create_pinocchio_model()
            self.indices[name] = indices
            self.bounds[name] = tuple(np.asarray(x, dtype=float) for x in agent.get_physical_action_bounds())
            self.openings[name] = self._opening(name)
            arms.append(ArmDescription(name=name, control_frame='world', rotation_radius_m=.18,
                grasp_site_description='xArm7 G2 link_tcp, 0.172 m along gripper base +Z; wxyz orientation. Opening 0 closed, 1 open.',
                joint_names=[robot.get_active_joints()[i].name for i in indices[:7]],
                control=ArmControlCapabilities(commands=['pose'])))
        if not cameras or len(set(cameras)) != len(cameras) or set(cameras) - {'front', 'top'}:
            raise ValueError('Select unique front/top cameras')
        self.cameras = {}
        # Fixed sensor placement is part of this evaluation profile, not object state.
        poses = {'front': ([-.95, -1.15, 1.85], [0., 0., 1.0]),
                 'top': ([0., -.01, 2.5], [0., 0., .85])}
        for name in cameras:
            camera = env.scene.add_camera(name, 640, 480, 1.05, .05, 10.)
            camera.set_pose(camera_pose(*poses[name]))
            self.cameras[name] = camera
        self.description = EnvironmentDescription(arms=arms,
            cameras=[CameraDescription(name=n, has_depth=depth_enabled) for n in self.cameras],
            control_frequency_hz=env.control_freq, max_episode_steps=env.horizon,
            observation_interval_steps=1, metadata={
                'observation_source': 'native_sapien',
                'normalized_opening_tolerance': .05,
                'control_constraints': 'World-frame absolute link_tcp poses; native IK and PD control. Both arms use xarm7_g2_gripper. No collision-free planning guarantee.',
                'evaluation_protocol': 'single_task'})
        from uni_robot_agent.integrations.robot_resources import add_robot_resources, urdf_kinematics
        model = urdf_kinematics(root / 'assets/robots/xarm7_g2_gripper/xarm7_with_gripper.urdf')
        model['control'] = {'tcp_link': 'link_tcp', 'arms': {
            name: {'base_position': agent.robot.get_root_pose().p.tolist(),
                   'base_quaternion_wxyz': agent.robot.get_root_pose().q.tolist(),
                   'arm_joint_indices': self.indices[name][:7].tolist()}
            for name, agent in self.agents.items()},
            'gripper': 'G2 drive_joint: external opening 0 closed, 1 open; native controller handles flip and mimic joints.'}
        add_robot_resources(self.description, model=model)
        self._capture_frames()

    def episode_identity(self):
        return self.instruction, self.metadata

    def _opening(self, name):
        lo, hi = self.bounds[name]
        actual = self.agents[name].robot.get_qpos()[self.indices[name][-1]]
        return float(np.clip(1 - (actual - lo[-1]) / (hi[-1] - lo[-1]), 0, 1))

    def read_state(self):
        arms = {}
        for name, agent in self.agents.items():
            pose = agent.robot.get_links()[self.links[name]].pose
            arms[name] = ArmState(control_pose=Pose(position=pose.p.tolist(), quaternion=pose.q.tolist()),
                joints=agent.robot.get_qpos()[self.indices[name][:7]].tolist(),
                gripper=self._opening(name), gripper_command=self.openings[name],
                metadata={'gripper_opening_measured': True})
        return EnvironmentState(arms=arms, state_version=self.steps, native_steps=self.steps,
            ended=self.finished or self.success or self.steps >= self.env.horizon)

    def validate_commands(self, commands, mode):
        if mode != 'pose':
            raise RequestRejected('Cross-EEF accepts native pose control only')
        for command in commands:
            if not isinstance(command, PoseCommand) or command.solver != 'native' or set(command.arms) != set(self.agents):
                raise RequestRejected('Supply native-solver commands for left and right arms')
            for name, arm in command.arms.items():
                if isinstance(arm, JointTarget):
                    lo, hi = self.bounds[name]
                    if len(arm.joints) != 7 or np.any(np.asarray(arm.joints) < lo[:7]) or np.any(np.asarray(arm.joints) > hi[:7]):
                        raise RequestRejected('Held arm requires seven in-bounds joint positions')

    def _solve(self, name, command):
        import sapien
        agent, indices = self.agents[name], self.indices[name]
        q0 = np.asarray(agent.robot.get_qpos(), dtype=float)
        if isinstance(command, JointTarget):
            joints = np.asarray(command.joints)
        else:
            target = agent.robot.get_root_pose().inv() * sapien.Pose(command.pose.position, command.pose.quaternion)
            mask = np.zeros(len(q0), dtype=int)
            mask[indices[:7]] = 1
            model = self.models[name]
            solution, _, _ = model.compute_inverse_kinematics(
                self.links[name], target, q0, mask, 1e-4, 200, .1, 1e-6)
            model.compute_forward_kinematics(solution)
            actual = model.get_link_pose(self.links[name])
            position_error = np.linalg.norm(actual.p - target.p)
            rotation_error = 2 * np.arccos(np.clip(abs(np.dot(actual.q, target.q)), 0, 1))
            if not np.all(np.isfinite(solution)) or position_error > .003 or rotation_error > .03:
                raise RequestRejected(f'{name} target is unreachable by native IK; use a closer waypoint')
            joints = np.asarray(solution)[indices[:7]]
        lo, hi = self.bounds[name]
        if np.any(joints < lo[:7] - 1e-5) or np.any(joints > hi[:7] + 1e-5):
            raise RequestRejected(f'{name} target exceeds arm joint limits')
        # Bound per-tick drive changes; shared tools use measured feedback to converge.
        joints = np.clip(joints, q0[indices[:7]] - .12, q0[indices[:7]] + .12)
        physical = np.r_[np.clip(joints, lo[:7], hi[:7]), lo[-1] + command.gripper * (hi[-1] - lo[-1])]
        return agent.policy_action_from_physical(physical)

    def step_pose(self, command):
        self.validate_commands([command], 'pose')
        if self.closed or self.read_state().ended:
            raise RequestRejected('Episode has ended')
        # Solve both before mutating native state; rejected commands never advance physics.
        action = np.concatenate([self._solve(name, command.arms[name]) for name in self.agents])
        _, _, terminated, truncated, _ = self.env.step(action)
        self.steps += 1
        self.success = bool(terminated)
        self.finished = bool(truncated)
        self.openings = {name: command.arms[name].gripper for name in self.agents}
        self._capture_frames()
        return StepReceipt(accepted=True, state=self.read_state(), diagnostics={'executed_steps': 1})

    def _capture_frames(self):
        self.env.scene.update_render()
        self.frames = {}
        for name, camera in self.cameras.items():
            camera.take_picture()
            color = np.asarray(camera.get_picture('Color'))
            rgb = (np.clip(color[..., :3], 0, 1) * 255).astype(np.uint8)
            depth = None
            if self.depth_enabled:
                position = np.asarray(camera.get_picture('Position'))
                depth = np.where(position[..., 3] < 1, -position[..., 2], 0).astype(np.float32)
                depth[~np.isfinite(depth) | (depth < 0)] = 0
            self.frames[name] = CameraFrame(rgb, depth, np.asarray(camera.get_intrinsic_matrix()).copy(),
                np.asarray(camera.get_model_matrix()) @ np.diag([1., -1., -1., 1.]))

    def capture(self, cameras=None, *, high_resolution=False):
        names = list(self.cameras) if cameras is None else cameras
        if not names or len(set(names)) != len(names) or set(names) - set(self.cameras):
            raise RequestRejected('Select unique configured cameras')
        state = self.read_state()
        truncated = self.steps >= self.env.horizon and not self.success
        return CapturedObservation(self.episode_id, self.steps, time.time(), state.model_dump(mode='json'),
            {name: self.frames[name] for name in names},
            terminated=state.ended and not truncated, truncated=truncated)

    def step_joints(self, command):
        raise RequestRejected('Joint control is unavailable')

    def step_native(self, command):
        raise RequestRejected('Raw action control is unavailable')

    def preview_joints(self, commands):
        raise RequestRejected('Joint previews are unavailable')

    def finish(self, reason, status=None):
        if self.outcome is None:
            self.finished = True
            self.outcome = {'task_success': self.success, 'reason': reason, 'native_steps': self.steps,
                'benchmark': 'crosseef', 'task_id': self.metadata['task_id'], 'evaluation_protocol': 'single_task'}
        return dict(self.outcome)

    def close(self):
        if not self.closed:
            self.closed = True
            for camera in self.cameras.values():
                self.env.scene.remove_camera(camera)
            self.cameras.clear()
            self.models.clear()
            self.agents.clear()
            self.env.agent = None
            self.env.robots = []
            self.env.scene = None
