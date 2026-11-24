---
name: crosseef-xarm7-g2
description: Frame conventions, observation use and measured feedback for the Cross-EEF dual xArm7/G2 Direct integration.
---

# Cross-EEF dual xArm7 with G2 grippers

Use the current environment description and tools. This guide supplies robot
conventions, not a task solution or privileged object coordinates.

## Observe before computing

Inspect the attached front/top RGB images. With depth enabled, use the exposed
pixel localization operation on a few visible interior points from one immutable
snapshot. It already applies that image's calibration and returns validity and
world coordinates. Do not implement another projection or segmenter unless an
unresolved geometric question requires it. Without depth, use only the available
RGB/calibration methods and acknowledge missing geometric evidence.

For an actual image calculation, use the exact returned image_path. The snapshot
manifest is JSON; a snapshot ID or resource hash is not an image filename.
Read only the specific robot reference or skill needed for the next decision.

## Bound preparation to the next phase

Use 1-4 interior pixels per locate call, keeping different features in separate
calls. Inspect the overlay before treating returned depth as target evidence.
Once a safe approach target and the arm/finger swept clearance are established,
execute that bounded approach and inspect feedback before refining contact.
Do not postpone it to reconstruct every object, bin and finger numerically.
If another calculation is needed, name the missing fact and its effect on the
next action; stop once it is answered. Unresolved clearance is a reason to obtain
targeted evidence or report a blocker, not to force an arbitrary movement.

This integration publishes native pose IK and normalized G2 opening, but not the
general contact-calculation helper's hand.contact_geometry/metric gap model.
That helper is not a required startup step. Do not reconstruct IK, infer a linear
jaw-gap calibration or search robot meshes to satisfy an unavailable interface.

## Pose and opening conventions

- Arms are left/right; positions are world metres. Internal quaternions are wxyz.
  The move tool accepts XYZ plus fixed-axis XYZ roll/pitch/yaw in radians.
- The control point is link_tcp, offset 0.172 m along gripper-base +Z with no
  fixed rotation. It is not the wrist or the gripper base. Do not apply that
  offset a second time to a measured control_pose.
- Preserve measured orientation for an initial translation when appropriate.
  Euler angles near pitch +/-pi/2 can change sharply for a small physical
  rotation; use quaternion/rotation-matrix comparisons rather than subtracting
  Euler angles. Use clearance for any substantial reorientation.
- G2 opening is normalized: 0 closed, 1 open. The native controller handles its
  reversed drive joint and mimics. Do not invert the tool's opening yourself.
  This is a joint-based measure, not a linear gap in metres.

## Execute and check

### G2 pad axis: use local Y, not local X

The asset's left/right pad collision boxes are centered at the corresponding
left_finger_tip/right_finger_tip frames. Their connecting line is parallel to
gripper-base Y under symmetric finger motion. link_tcp has no fixed rotation
relative to the gripper base, so this is also **TCP local Y**, for both arms.
Local +Z runs from the base toward the fingers. Local X is not the closing axis.
This axis relation does not make the fixed TCP position the pad midpoint:
the midpoint's offset changes with finger articulation. Contact can also cause
asymmetric tracking; inspect actual fingers before assuming exact symmetry.

For a TCP-to-world rotation matrix R, use `pad_line_world = R[:, 1]`.
The horizontal-pad requirement is `pad_line_world[2]` approximately zero.
Do not impose this condition on `R[:, 0]` or `R[:, 2]`.
For move's fixed-axis XYZ angles, `R = Rz(yaw) @ Ry(pitch) @ Rx(roll)`;
the relevant component is `R[2, 1] = cos(pitch) * sin(roll)`.
For example, roll=0 keeps nominal local Y horizontal for any pitch/yaw;
this is an orientation relation, not a guaranteed reachable or collision-free pose.

Check the measured orientation once. If its pad line is already horizontal
within tracking accuracy and the approach has clearance, preserve that orientation
for the next translation instead of rebuilding a grasp frame or re-solving IK.
Changing pitch or yaw is only necessary when clearance or contact geometry needs
it. A horizontal endpoint does not certify a horizontal intermediate trajectory;
prefer fixed-orientation translations and inspect measured feedback. Do not repeat
scene localization to resolve a robot-axis question: the axis convention above
is fixed and does not depend on which can or bin is selected.

Native IK finds joint targets; PD control moves toward them over multiple ticks.
The robot does not teleport to an IK solution. The requested pose is not a
measurement. Inspect action_complete, pose_reached, stop_reason and each arm's
position/orientation errors before a dependent grasp or placement.

If max_steps expires while error decreases, a bounded continuation can be useful
after checking clearance. If stalled/diverging is reported, inspect the images
and actual pose, then choose a changed route or orientation. Do not blindly
repeat the same blocked target, disable guards, or edit simulator state.

Closing the G2 can take more than one short call. A nonzero opening while closing
may indicate pending motion or contact; it does not prove a grasp. Check visual
finger/object alignment, then a small lift with retention evidence. A grasp tool
returning normally does not certify object attachment or native task success.
