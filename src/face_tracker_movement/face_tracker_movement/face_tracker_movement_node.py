import math
import sys
import time
import random

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from control_msgs.action import FollowJointTrajectory
from control_msgs.msg import JointTrajectoryControllerState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration
from face_tracker_msgs.msg import Point2


class FaceTrackerMovementNode(Node):

    def __init__(self, functionality):
        super().__init__('face_tracker_movement_client')
        self.eye_action_client = ActionClient(self, FollowJointTrajectory, '/eyes_controller/follow_joint_trajectory')
        self.subscription = self.create_subscription(Point2, '/face_tracker/face_location_topic', self.listener_callback, 2)
        self.head_action_client = ActionClient(self, FollowJointTrajectory, '/head_controller/follow_joint_trajectory')
        self.head_state_subscription = self.create_subscription(JointTrajectoryControllerState, '/head_controller/state', self.head_state_callback, 5)
        self.eyes_state_subscription = self.create_subscription(JointTrajectoryControllerState, '/eyes_controller/state', self.eyes_state_callback, 5)
        # Middle point of image view
        self.middle_x = 640
        self.middle_y = 400
        self.is_glancing = False
        self.moving = False
        self.idling = False
        self.head_joint_ids = [4, 1, 3, 2]
        self.start_head_state = [0.6, 0.5, -0.5, -0.6]
        self.head_state = self.start_head_state
        self.eyes_joint_ids = [9, 11]
        self.start_eyes_state = [-0.7, -0.75]
        self.eyes_state = self.start_eyes_state
        self.pan_diff = 0
        self.v_diff = 0
        self.head_enabled = True
        self.eyes_enabled = True

        if functionality.lower() == "head":
            self.get_logger().info('Eye movement is disabled.')
            self.eyes_enabled = False
        elif functionality.lower() == "eyes":
            self.get_logger().info('Head movement is disabled.')
            self.head_enabled = False

        self.center_eyes()
        self.send_head_goal(self.head_state[0], self.head_state[3], self.head_state[1])
        time.sleep(1)

        self.idle_timer = self.create_timer(5, self.idle_timer_callback)

        self.get_logger().info('Face tracking movement client initialized.')
        
    def head_state_callback(self, msg):
        self.head_state = msg.actual.positions
        for i, val in enumerate(self.head_state):
            if math.isnan(val):
                self.head_state[i] = self.start_head_state[i]
                self.get_logger().info("Head joint ID" + str(self.head_joint_ids[i]) + " is not responding")

    def eyes_state_callback(self, msg):
        self.eyes_state = msg.actual.positions
        for i, val in enumerate(self.eyes_state):
            if math.isnan(val):
                self.eyes_state[i] = self.start_eyes_state[i]
                self.get_logger().info("Eye joint ID" + str(self.eyes_joint_ids[i]) + " is not responding")

    def idle_timer_callback(self):
        self.get_logger().info("Idling...\x1B[1A")
        self.send_eye_goal(-0.75, self.get_random_eye_location()[0])
        self.send_pan_and_vertical_tilt_goal(random.uniform(0.25, 1.25), -0.6, Duration(sec=0, nanosec= random.randint(1000000000, 4000000000)))
        self.idle_timer.timer_period_ns = random.randint(1000000000, 5000000000)
        self.idle_timer.reset()


    def listener_callback(self, msg):
        self.idle_timer.timer_period_ns = 5000000000
        self.idle_timer.reset()

        if self.eyes_enabled:
            #self.get_logger().info('x: %d, y: %d' % (msg.x, msg.y))
            glance_percentage = 0.005
            randomvalue = random.uniform(0, 1)

            # Check if doing the glance or not
            if randomvalue <= glance_percentage:
                eye_location_x, eye_location_y = self.get_random_eye_location()
                self.is_glancing = True
                self.get_logger().info('glance')
            else:
                eye_location_x, eye_location_y = self.transform_face_location_to_eye_location(msg.x, msg.y)

            # Move eyes
            self.send_eye_goal(eye_location_y, eye_location_x)

            if self.is_glancing:
                # Center the eyes back to the face after glancing
                time.sleep(0.5)
                self.center_eyes()
                time.sleep(0.5)
                self.is_glancing = False
                return
        
        if self.head_enabled:
            self.pan_diff, self.v_diff = self.transform_face_location_to_head_values(msg.x, msg.y)
            if self.pan_diff != 0 or self.v_diff != 0: 
                goal_pan = max(min(1.75, self.head_state[0] + self.pan_diff), -0.25) # limit head values to reasonable values
                goal_vertical_tilt = max(min(-0.2, self.head_state[3] + self.v_diff), -0.6)
                self.get_logger().info("Turning head to x: " + str(goal_pan) + " y: " + str(goal_vertical_tilt))
                self.send_pan_and_vertical_tilt_goal(goal_pan, goal_vertical_tilt)
                time.sleep(0.5)

    def send_eye_goal(self, vertical, horizontal):
        # The eyes lock up if they try to move too fast so it'll go a bit slower for longer movements (also faster for short movements)
        x_diff = abs(self.eyes_state[0] - horizontal)
        duration = max(int(200000000 * x_diff), 200000000)

        goal_msg = FollowJointTrajectory.Goal()
        trajectory_points = JointTrajectoryPoint(positions=[vertical, horizontal], time_from_start=Duration(sec=0, nanosec=duration))
        goal_msg.trajectory = JointTrajectory(joint_names=['eyes_shift_vertical_joint', 'eyes_shift_horizontal_joint'],
                                              points=[trajectory_points])

        self.eye_action_client.wait_for_server()

        self.eye_action_client.send_goal_async(goal_msg)
        #self.get_logger().info('eye location x: %f, eye location y: %f' % (horizontal, vertical))

    def send_horizontal_tilt_goal(self, horizontalTilt):
        goal_msg = FollowJointTrajectory.Goal()
        trajectory_points = JointTrajectoryPoint(positions=[-horizontalTilt, horizontalTilt], time_from_start=Duration(sec=1, nanosec=0))
        goal_msg.trajectory = JointTrajectory(joint_names=['head_tilt_left_joint', 'head_tilt_right_joint'],
                                              points=[trajectory_points])
        
        self.head_action_client.wait_for_server()

        self.head_action_client.send_goal_async(goal_msg)
        
    def send_pan_and_vertical_tilt_goal(self, pan, verticalTilt, duration=Duration(sec=0, nanosec=500000000)):
        goal_msg = FollowJointTrajectory.Goal()
        trajectory_points = JointTrajectoryPoint(positions=[pan, verticalTilt], time_from_start=duration)
        goal_msg.trajectory = JointTrajectory(joint_names=['head_pan_joint', 'head_tilt_vertical_joint'],
                                              points=[trajectory_points])

        self.head_action_client.wait_for_server()

        self.head_action_client.send_goal_async(goal_msg)

    def send_head_goal(self, pan, verticalTilt, horizontalTilt):
        # Horizontal tilt is done separately and slower because the joints easily get stuck when moving quickly.
        self.send_horizontal_tilt_goal(horizontalTilt)
        time.sleep(1)
        self.send_pan_and_vertical_tilt_goal(pan, verticalTilt)

    def transform_face_location_to_head_values(self, face_location_x, face_location_y):
        """
        Calculates new pan and vertical tilt values corresponding to the face location coordinates given
        as arguments.
        """
        # Calculate face movement
        x_diff = self.middle_x - face_location_x
        y_diff = self.middle_y - face_location_y

        # If the face is close enough to the center, leave the small movements for the eyes.
        if abs(x_diff) < 100:
            x_diff = 0
        if abs(y_diff) < 50:
            y_diff = 0

        # Transform face movement to head joint values
        # Head pan
        h_coeff = -0.00078
        # Adjust the pan value slightly to make smaller movements a bit bigger
        pan = 0.8 * abs(x_diff * h_coeff) ** 0.8
        pan = math.copysign(pan, -x_diff)
        # Vertical tilt
        v_coeff = -0.002
        vertical_tilt = y_diff * v_coeff

        return pan, vertical_tilt

    def transform_face_location_to_eye_location(self, face_location_x, face_location_y):
        """
        Calculates new x and y location for the eyes corresponding to the face location coordinates given
        as arguments.
        """
        # Calculate face movement
        x_diff = self.middle_x - face_location_x
        y_diff = self.middle_y - face_location_y

        # Transform face movement to eye movement
        # Horizontal eye movement
        h_coeff = -0.002
        eye_location_x = x_diff * h_coeff - 0.7
        # Vertical eye movement
        v_coeff = 0.003
        eye_location_y = y_diff * v_coeff - 0.75

        return eye_location_x, eye_location_y
    
    def center_eyes(self):
        self.send_eye_goal(-0.75, -0.7)

    def get_random_eye_location(self):
        """
        Returns a random location coordinates which is far enough from the current state of the eyes to be called a glance.
        """
        random_x = random.uniform(-2, 0.5)
        random_y = random.uniform(-1.5, -0)

        # Can possibly loop for a while because of the random number being too close multiple times but it should only rarely affect performance
        while abs(self.eyes_state[0] - random_x) < 0.5:
            random_x = random.uniform(-2, 0.5)

        return random_x, random_y


def main():
    print('Hi from face_tracker_movement.')

    rclpy.init()

    arg = "full"

    if len(sys.argv) > 1:
        arg = sys.argv[1]

    action_client = FaceTrackerMovementNode(arg)

    rclpy.spin(action_client)

    # Shutdown
    action_client.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
