"""Launch the RL drone simulation: Gazebo Harmonic + drone spawn + ros_gz bridges."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = get_package_share_directory('rl_drone_pathfinding')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    world_file = os.path.join(pkg_share, 'worlds', 'multi_room.sdf')
    drone_sdf = os.path.join(pkg_share, 'models', 'rl_drone', 'model.sdf')
    bridge_yaml = os.path.join(pkg_share, 'config', 'ros_gz_bridge.yaml')

    # Make our `models/` discoverable by Gazebo so SDF includes resolve.
    set_gz_resource = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=os.path.join(pkg_share, 'models')
        + ':' + os.environ.get('GZ_SIM_RESOURCE_PATH', '')
    )

    # `headless:=true` -> server-only (no GUI). Default true because training
    # is much faster without rendering; flip to false to inspect visually.
    headless_arg = DeclareLaunchArgument(
        'headless', default_value='true',
        description='Run Gazebo without GUI (server-only).')

    headless_str = os.environ.get('SIM_HEADLESS', '1')
    headless_flag = '-s' if headless_str not in ('0', 'false', 'False', '') else ''

    # `-r` runs the sim immediately; without it gz starts paused and no sensor
    # data flows. `-v 3` keeps log noise reasonable.
    gz_args_value = f'-r -v 3 {headless_flag} {world_file}'.strip()
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
        launch_arguments={
            'gz_args': gz_args_value,
        }.items(),
    )

    # Spawn drone at the FIXED start: R0 (sol-alt kose), env reset ile birebir.
    spawn_drone = Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_rl_drone',
        output='screen',
        arguments=[
            '-name', 'rl_drone',
            '-file', drone_sdf,
            '-x', '-5.0', '-y', '-5.0', '-z', '0.6',
            '-Y', '0.0',
        ],
    )

    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='ros_gz_bridge',
        output='screen',
        parameters=[{'config_file': bridge_yaml,
                     'qos_overrides./scan.publisher.reliability': 'best_effort'}],
    )

    return LaunchDescription([
        set_gz_resource,
        headless_arg,
        gz_sim,
        spawn_drone,
        bridge,
    ])
