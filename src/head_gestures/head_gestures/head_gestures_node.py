import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from control_msgs.action import FollowJointTrajectory
from control_msgs.msg import JointTrajectoryControllerState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration
from std_msgs.msg import String, Float32

""" Head shake message
ros2 action send_goal /head_controller/follow_joint_trajectory control_msgs/action/FollowJointTrajectory
"   { trajectory:
        { joint_names:
            [head_pan_joint],
            points: [
                { positions: [1.25], time_from_start: { sec: 0, nanosec: 200000000 }},
                { positions: [0.25], time_from_start: { sec: 0, nanosec: 500000000 }},
                { positions: [0.75], time_from_start: { sec: 0, nanosec: 900000000 }}
            ]
        }
    }"
"""

"""
    Head joint starting values that don't break the whole thing. Not exactly looking straight ahead.
    head_pan_joint:             0.5
    head_tilt_right_joint:      0.5
    head_tilt_left_joint:      -0.5
    head_tilt_vertical_joint:  -0.5
"""

class HeadGesturesNode(Node):

    def __init__(self):
        super().__init__('head_gesture_client')
        self.head_action_client = ActionClient(self, FollowJointTrajectory, '/head_controller/follow_joint_trajectory')
        self.eye_action_client = ActionClient(self, FollowJointTrajectory, '/eyes_controller/follow_joint_trajectory')
        self.head_state_subscription = self.create_subscription(JointTrajectoryControllerState, '/head_controller/state', self.head_state_callback, 5)
        #self.eyes_state_subscription = self.create_subscription(JointTrajectoryControllerState, '/eyes_controller/state', self.eyes_state_callback, 5)
        self.head_gesture_subscription = self.create_subscription(String, '/head_gestures/head_gesture_topic', self.head_gesture_callback, 10)

        self.head_gesture_length_publisher = self.create_publisher(Float32, '/head_gestures/length', 1)
        
        self.head_state = None
        self.eye_state = None
        """
        # Values that should work with the actual hardware
        self.head_vertical_lower_limit = 0.8
        self.head_vertical_upper_limit = 1.5
        self.head_pan_lower_limit = -0.25
        self.head_pan_upper_limit = 1.75
        self.eye_vertical_lower_limit = -0.7
        self.eye_vertical_upper_limit = -0.2
        self.eye_horizontal_lower_limit = -2.0
        self.eye_horizontal_upper_limit = 0.0
        """

        
        # Values that should work in the simulator
        self.head_vertical_lower_limit = -0.3
        self.head_vertical_upper_limit = 0.3
        self.head_pan_lower_limit = -1.0
        self.head_pan_upper_limit = 1.0
        self.eye_vertical_lower_limit = -0.5
        self.eye_vertical_upper_limit = 0.5
        self.eye_horizontal_lower_limit = -0.6
        self.eye_horizontal_upper_limit = 0.6
        
        self.logger = self.get_logger()
        self.logger.info('Head gesture client initialized.')
        
    def send_pan_and_vertical_tilt_goal(self, pan, verticalTilt, duration=Duration(sec=0, nanosec=400000000)):
        goal_msg = FollowJointTrajectory.Goal()
        trajectory_points = JointTrajectoryPoint(positions=[pan, verticalTilt], time_from_start=duration)
        goal_msg.trajectory = JointTrajectory(joint_names=['head_pan_joint', 'head_tilt_vertical_joint'],
                                              points=[trajectory_points])

        self.head_action_client.wait_for_server()

        self.head_action_client.send_goal_async(goal_msg)

    def send_eye_goal(self, horizontal, vertical, duration=Duration(sec=0, nanosec=400000000)):
        goal_msg = FollowJointTrajectory.Goal()
        trajectory_points = JointTrajectoryPoint(positions=[horizontal, vertical], time_from_start=duration)
        goal_msg.trajectory = JointTrajectory(joint_names=['eyes_shift_horizontal_joint', 'eyes_shift_vertical_joint'],
                                              points=[trajectory_points])

        self.eye_action_client.wait_for_server()

        self.eye_action_client.send_goal_async(goal_msg)

    def head_state_callback(self, msg):
        self.head_state = msg.actual.positions

    def eyes_state_callback(self, msg):
        self.eye_state = msg.actual.positions

    def fixed_gaze_head_turn(self, direction, magnitude, duration=0.4):
        """
        Turns the head while keeping the gaze steady by rotating the eyes in the opposite direction as the head.
        Decreases the magnitude of the movement, if it would exceed the maximum range of either the head or the eyes. 
        Takes 3 arguments: direction, magnitude and duration.
            direction: The direction of the head turn. Can be "left", "right", "up" or "down".
            magnitude: The magnitude of the head turn.
            duration: The time in seconds it should take to finish the head turn.
        """
        duration = Duration(sec=0, nanosec=int(duration * 100000000))
        pan, _, _, verticalTilt = self.head_state
        #eye_x, eye_y = self.eye_state

        if direction == 'left':
            if pan + magnitude > self.head_pan_upper_limit:
                magnitude = self.head_pan_upper_limit - pan
            #if eye_x - magnitude < self.eye_horizontal_lower_limit:
             #   magnitude = self.eye_horizontal_lower_limit - eye_x

            self.send_pan_and_vertical_tilt_goal(pan + magnitude, verticalTilt, duration)
            #self.send_eye_goal(eye_x - magnitude, eye_y, duration)
        
        elif direction == 'right':
            if pan - magnitude < self.head_pan_lower_limit:
                magnitude = pan - self.head_pan_lower_limit
            #if eye_x + magnitude > self.eye_horizontal_upper_limit:
             #   magnitude = self.eye_horizontal_upper_limit - eye_x

            self.send_pan_and_vertical_tilt_goal(pan - magnitude, verticalTilt, duration)
            #self.send_eye_goal(eye_x + magnitude, eye_y, duration)
        
        elif direction == 'up':
            if verticalTilt - magnitude < self.head_vertical_lower_limit:
                magnitude = verticalTilt - self.head_vertical_lower_limit
            #if eye_y + magnitude > self.eye_vertical_upper_limit:
             #   magnitude = self.eye_vertical_upper_limit - eye_y

            self.send_pan_and_vertical_tilt_goal(pan, verticalTilt - magnitude, duration)
            #self.send_eye_goal(eye_x, eye_y + magnitude)
        
        elif direction == 'down':
            if verticalTilt + magnitude > self.head_vertical_upper_limit:
                magnitude = self.head_vertical_upper_limit - verticalTilt
            #if eye_y - magnitude < self.eye_vertical_lower_limit:
             #   magnitude = eye_y - self.eye_vertical_lower_limit

            self.send_pan_and_vertical_tilt_goal(pan, verticalTilt + magnitude, duration)
            #self.send_eye_goal(eye_x, eye_y - magnitude)


    def nod(self, magnitude=0.4, delay=0.5, duration_of_individual_movements=0.4):
        """
        Makes the head nod.
        Takes two optional arguments:
            magnitude: The interval between the highest and lowest points of the nod
            delay: The delay (in seconds) between the start of each individual movement
            duration_of_individual_movements: The time (in seconds) it takes for an individual movement to finish. Should be less than delay.
        """
        if self.head_state:
            verticalTilt_start = self.head_state[3]
            msg = Float32()
            msg.data = delay * 3
            self.head_gesture_length_publisher.publish(msg)
            self.fixed_gaze_head_turn('up', magnitude / 2, duration_of_individual_movements)
            time.sleep(delay)
            self.fixed_gaze_head_turn('down', magnitude, duration_of_individual_movements)
            time.sleep(delay)
            verticalTilt = self.head_state[3]
            self.fixed_gaze_head_turn('up', verticalTilt - verticalTilt_start, duration_of_individual_movements)

    def head_shake(self, magnitude=0.5, delay=0.5, duration_of_individual_movements=0.4):
        """
        Shakes the head.
        Takes two optional arguments:
            magnitude: The interval between the leftmost and rightmost points of the head shakes
            delay: The delay (in seconds) between the start of each individual movement
            duration_of_individual_movements: The time (in seconds) it takes for an individual movement to finish. Should be less than delay.
        """
        if self.head_state:
            pan_start = self.head_state[0]
            msg = Float32()
            msg.data = delay * 3
            self.head_gesture_length_publisher.publish(msg)
            self.fixed_gaze_head_turn('left', magnitude / 2, duration_of_individual_movements)
            time.sleep(delay)
            self.fixed_gaze_head_turn('right', magnitude, duration_of_individual_movements)
            time.sleep(delay)
            pan = self.head_state[0]
            self.fixed_gaze_head_turn('left', pan_start - pan, duration_of_individual_movements)

    def head_gesture_callback(self, msg):
        gesture = msg.data
        self.logger.info(gesture)
        gesture = gesture.split(",")
        args = {}
        for i in range(1, len(gesture)):
            gesture[i] = gesture[i].strip(" ")
            if gesture[i][:10] == "magnitude=":
                args['magnitude'] = float(gesture[i][10:])
            if gesture[i][:6] == "delay=":
                args['delay'] = float(gesture[i][6:])
            if gesture[i][:9] == "duration=":
                args['duration_of_individual_movements'] = float(gesture[i][9:])
        gesture = gesture[0]
        if gesture == 'nod':
            self.nod(**args)
        elif gesture == 'shake':
            self.head_shake(**args)
        else:
            self.logger.info("Gesture not implemented")



def main():
    print('Hello from head_gestures.')

    rclpy.init()

    action_client = HeadGesturesNode()

    rclpy.spin(action_client)

    # Shutdown
    action_client.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
