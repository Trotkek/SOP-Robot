# Copyright 2020 ROS2-Control Development Team (2020)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

import xacro

dynamixel_config_file = "NOT_SET"

DYNAMIXEL_CONFIG_FILE_PREFIX = "config/"
DYNAMIXEL_CONFIG_FILEPATH_HEAD = DYNAMIXEL_CONFIG_FILE_PREFIX + "dynamixel_head.yaml"
DYNAMIXEL_CONFIG_FILEPATH_ARM = DYNAMIXEL_CONFIG_FILE_PREFIX + "dynamixel_arm.yaml"
ALL_AVAILABLE_DYNAMIXEL_CONFIG_FILES = [DYNAMIXEL_CONFIG_FILEPATH_HEAD, DYNAMIXEL_CONFIG_FILEPATH_ARM]

DYNAMIXEL_CONFIG_FILEPATH_FOR_LAUNCH = DYNAMIXEL_CONFIG_FILE_PREFIX + "temp_dynamixel_for_launch.yaml" # Dynamic file created during launch if both arm and head are enabled




def generate_launch_description():

    dynamixel_config_file = generate_dynamixel_config_file()

    robot_description_content = Command(
      [
          # Get URDF via xacro
          PathJoinSubstitution([FindExecutable(name="xacro")]),
          " ",
          PathJoinSubstitution(
              [
                  FindPackageShare("inmoov_description"),
                  "robots",
                  "inmoov.urdf.xacro",
              ]
          ),
          " dynamixel_config_file:=",
          dynamixel_config_file,
          " use_fake_hardware:=false", # No fake hardware, this is real.
          " fake_sensor_commands:=false", # No fake sensors, only real ones.
      ]
    )
    robot_description = {"robot_description": robot_description_content}


    controller = os.path.join(
        get_package_share_directory('robot'),
        'controllers',
        'robot.yaml'
        )

    ros2_control_node = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[robot_description, controller],
        output={
          'stdout': 'screen',
          'stderr': 'screen',
          },
    )
    
    controllers_to_start = [
        "head_controller",
        "eyes_controller",
        "jaw_controller",
        "r_hand_controller",
        "r_shoulder_controller"
    ]
    
    controller_spawners = [
        Node(
        package="controller_manager",
        executable="spawner.py",
        arguments=[controller_name]
        ) for controller_name in controllers_to_start
    ]

    nodes = [
        ros2_control_node,
        *controller_spawners
    ]

    return LaunchDescription(nodes)



# Generates a "launch-time" configuration file for Dynamixel servos.
# The idea is to enable using only arm or only head without the need to touch the code. 
# Launch only arm (and hand):
#   ros2 launch robot robot.launch.py robot_parts:=arm
# Launch only head:
#   ros2 launch robot robot.launch.py robot_parts:=head
# If no parameter or invalid parameter is given, includes all available parts (currently arm+hand and head).
def generate_dynamixel_config_file():
    included_files = []
    for arg in sys.argv:
        if arg.startswith("robot_parts:="):
            parts = arg.split(":=")[1]
            if len(parts) <= 0:
                # Use all if parts not correctly specified
                included_files = ALL_AVAILABLE_DYNAMIXEL_CONFIG_FILES
                print("Warning, robot parts not correctly specified! Using all available parts.")
            else:
                if "head" in parts:
                    print("Note: Configuring servos only for robot head!")
                    included_files.append(DYNAMIXEL_CONFIG_FILEPATH_HEAD)
                elif "arm" in parts:
                    print("Note: Configuring servos only for robot arm!")
                    included_files.append(DYNAMIXEL_CONFIG_FILEPATH_ARM)

    if len(included_files) == 0:
        # Use all if argument was not given
        print("Note: Configuring servos for all robot parts!")
        included_files = ALL_AVAILABLE_DYNAMIXEL_CONFIG_FILES

    with open(DYNAMIXEL_CONFIG_FILEPATH_FOR_LAUNCH, 'w') as outfile:
        outfile.write("# NOTE! This is a temporary file generated during the launch. It is generated based on the enabled robot parts\n" + 
        "# so that only the needed Dynamixel servos are configured and therefore no errors are thrown for missing servo IDs.\n\n")
        for filename in included_files:
            with open(filename) as infile:
                outfile.write(infile.read())

    return DYNAMIXEL_CONFIG_FILEPATH_FOR_LAUNCH