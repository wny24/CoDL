"""Cross-EEF SAPIEN dual xArm7/G2 tasks using shared Direct tools."""


def get_integration_spec():
    from uni_robot_agent.integrations.gripper import CLEAN_TOOLS, DIRECT_TOOLS
    from uni_robot_agent.integrations.simulation import build_simulation_spec
    spec = build_simulation_spec('crosseef', tool_profiles={'direct': DIRECT_TOOLS, 'clean': CLEAN_TOOLS})
    spec.deployment_module = 'uni_robot_agent.integrations.crosseef.deployment'
    validate_shared = spec.validate_cli

    def validate(args):
        from .tasks import task_name
        validate_shared(args)
        if args.task:
            args.task = task_name(args.task)

    spec.validate_cli = validate
    return spec
