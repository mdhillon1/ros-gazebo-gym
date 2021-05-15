#!/usr/bin/env python3
"""Robot environment for the CartPole environment. This is a 3D gazebo version of the
original `CartPole-v1 <https://gym.openai.com/envs/CartPole-v1/>`_ OpenAi gym
environment.
"""
import rospy
from gym.utils import seeding
from openai_ros import robot_gazebo_env
from openai_ros.core import ROSLauncher
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64


class CartPoleEnv(robot_gazebo_env.RobotGazeboEnv):
    """CartPole robot environment class.

    Attributes:
        controllers_list (list): The controllers that are used.
        robot_name_space (str): The robot namespace that is used.
        gazebo (:class:`openai_ros.core.gazebo_connection.GazeboConnection`): Object
            that can be used to talk with the gazebo simulator.
    """

    def __init__(self, control_type, workspace_path=None):
        """Initializes a new CartPole robot environment.

        The Sensors: The sensors accessible are the ones considered usefull for AI
        learning.

        Sensor Topic List:
        * /cartpole_v0/joint_states: Joint state reading that come from the sensors.

        Actuators Topic List:
        * /cartpole_v0/foot_joint_velocity_controller/command: Foot velocity command
            topic.
        * /cartpole_v0/pole_joint_velocity_controller/command: Pole velocity command
            topic.

        Args:
            workspace_path (str, optional): The path of the workspace in which the
                turtlebot3_gazebo package should be found. Defaults to ``None``.
        """
        rospy.logdebug("Initialize CartPoleEnv robot environment...")

        # Launch the ROS launch that spawns the robot into the world
        ROSLauncher.launch(
            package_name="cartpole_description",
            launch_file_name="put_robot_in_world.launch",
            workspace_path=workspace_path,
        )

        # Setup internal robot environment variables
        self.control_type = control_type
        if self.control_type == "velocity":
            self.controllers_list = [
                "joint_state_controller",
                "pole_joint_velocity_controller",
                "foot_joint_velocity_controller",
            ]

        elif self.control_type == "position":
            self.controllers_list = [
                "joint_state_controller",
                "pole_joint_position_controller",
                "foot_joint_position_controller",
            ]

        elif self.control_type == "effort":
            self.controllers_list = [
                "joint_state_controller",
                "pole_joint_effort_controller",
                "foot_joint_effort_controller",
            ]
        self.robot_name_space = "cartpole_v0"
        self.reset_controls = True

        # Seed the environment
        self.seed()
        self.steps_beyond_done = None

        # Initialize gazebo environment
        super(CartPoleEnv, self).__init__(
            controllers_list=self.controllers_list,
            robot_name_space=self.robot_name_space,
            reset_controls=self.reset_controls,
        )

        # Create ROS related Subscribers and publishers
        self.publishers_array = []
        self._base_pub = rospy.Publisher(
            "/cartpole_v0/foot_joint_velocity_controller/command", Float64, queue_size=1
        )
        self._pole_pub = rospy.Publisher(
            "/cartpole_v0/pole_joint_velocity_controller/command", Float64, queue_size=1
        )
        self.publishers_array.append(self._base_pub)
        self.publishers_array.append(self._pole_pub)
        rospy.Subscriber("/cartpole_v0/joint_states", JointState, self._joints_callback)
        rospy.logdebug("CartPoleEnv environment initialized.")

    #############################################
    # Overload Gazebo env virtual methods #######
    #############################################
    # NOTE: Methods needed by the RobotGazeboEnv
    def _check_all_systems_ready(self, init=True):
        """Checks that all the sensors, publishers and other simulation systems are
        operational.

        Returns:
            bool: Whether the systems are ready. Will not return if the systems are not
                yet ready.
        """
        self.base_position = None
        while self.base_position is None and not rospy.is_shutdown():
            try:
                self.base_position = rospy.wait_for_message(
                    "/cartpole_v0/joint_states", JointState, timeout=1.0
                )
                rospy.logdebug(
                    "Current cartpole_v0/joint_states READY=>" + str(self.base_position)
                )
                if init:
                    # We Check all the sensors are in their initial values
                    positions_ok = all(
                        abs(i) <= 1.0e-02 for i in self.base_position.position
                    )
                    velocity_ok = all(
                        abs(i) <= 1.0e-02 for i in self.base_position.velocity
                    )
                    efforts_ok = all(
                        abs(i) <= 1.0e-01 for i in self.base_position.effort
                    )
                    base_data_ok = positions_ok and velocity_ok and efforts_ok
                    rospy.logdebug("Checking Init Values Ok=>" + str(base_data_ok))
            except Exception:
                rospy.logerr(
                    "Current cartpole_v0/joint_states not ready yet, retrying for "
                    "getting joint_states."
                )
        rospy.logdebug("ALL SYSTEMS READY")

    #############################################
    # Overload Gazebo env virtual methods #######
    #############################################
    # NOTE: Methods needed by the RobotGazeboEnv
    def _env_setup(self, initial_qpos):
        """Initial configuration of the environment. Can be used to configure initial
        state and extract information from the simulation.

        Args:
            initial_qpos (numpy.ndarray): The initial agent pose (generalized
                coordinates).
        """
        self.init_internal_vars(self.init_pos)
        self.set_init_pose()
        self.check_all_systems_ready()

    #############################################
    # Robot environment internal methods ########
    #############################################
    def _joints_callback(self, data):
        """Joint states subscriber callback function.

        Args:
            data (:obj:`sensor_msgs.msg._JointState.JointState`): The data that is
                returned by the subscriber.
        """
        self.joints = data

    #############################################
    # Robot env main methods ####################
    #############################################
    # NOTE: Contains methods that the TrainingEnvironment will need.
    def init_internal_vars(self, init_pos_value):
        self.pos = [init_pos_value]
        self.joints = None

    def check_publishers_connection(self):
        """
        Checks that all the publishers are working
        :return:
        """
        rate = rospy.Rate(10)  # 10hz
        while self._base_pub.get_num_connections() == 0 and not rospy.is_shutdown():
            rospy.logdebug("No susbribers to _base_pub yet so we wait and try again")
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                # This is to avoid error when world is rested, time when backwards.
                pass
        rospy.logdebug("_base_pub Publisher Connected")

        while self._pole_pub.get_num_connections() == 0 and not rospy.is_shutdown():
            rospy.logdebug("No susbribers to _pole_pub yet so we wait and try again")
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                # This is to avoid error when world is rested, time when backwards.
                pass
        rospy.logdebug("_pole_pub Publisher Connected")

        rospy.logdebug("All Publishers READY")

    def move_joints(self, joints_array):
        """Move the cartpole joints.

        Args:
            joints_array (numpy.ndarray): The
        """
        joint_value = Float64()
        joint_value.data = joints_array[0]
        rospy.logdebug("Single Base JointsPos>>" + str(joint_value))
        self._base_pub.publish(joint_value)

    def get_clock_time(self):

        self.clock_time = None
        while self.clock_time is None and not rospy.is_shutdown():
            try:
                self.clock_time = rospy.wait_for_message("/clock", Clock, timeout=1.0)
                rospy.logdebug("Current clock_time READY=>" + str(self.clock_time))
            except Exception:
                rospy.logdebug(
                    "Current clock_time not ready yet, retrying for getting Current "
                    "clock_time"
                )
        return self.clock_time
