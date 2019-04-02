#!/usr/bin/env python
import gym
from task_envs.task_envs_list import RegisterOpenAI_Ros_Env
import roslaunch
import rospy
import rospkg
import os
import git
import sys


def StartOpenAI_ROS_Environment(task_and_robot_environment_name):
    """
    It Does all the stuff that the user would have to do to make it simpler
    for the user.
    This means:
    0) Registers the TaskEnvironment wanted, if it exists in the Task_Envs.
    2) Checks that the workspace of the user has all that is needed for launching this.
    Which means that it will check that the robot spawn launch is there and the worls spawn is there.
    4) Launches the world launch and the robot spawn.
    5) It will import the Gym Env and Make it.
    """

    result = RegisterOpenAI_Ros_Env(task_env=task_and_robot_environment_name,
                                    timestep_limit_per_episode=10000)

    if result:
        print("Register of Task Env went OK, lets make the env...")
        env = gym.make(task_and_robot_environment_name)
    else:
        print("Something Went wrong in the register")
        env = None

    return env


class ROSLauncher(object):
    def __init__(self, rospackage_name, launch_file_name, ros_ws_abspath="/home/user/simulation_ws"):

        self._rospackage_name = rospackage_name
        self._launch_file_name = launch_file_name

        self.rospack = rospkg.RosPack()
        pkg_path = self.rospack.get_path(rospackage_name)

        # Check Package Exists
        try:
            pkg_path = self.rospack.get_path(rospackage_name)
            rospy.logdebug("Package FOUND...")
        except rospkg.common.ResourceNotFound:
            rospy.logwarn("Package NOT FOUND, lets Download it...")
            pkg_path = self.DownloadRepo(package_name=rospackage_name,
                                         ros_ws_abspath=ros_ws_abspath)

        # Now we check that the Package path is inside the ros_ws_abspath
        # This is to force the system to have the packages in that ws, and not in another.
        if ros_ws_abspath in pkg_path:
            rospy.logdebug("Package FOUND in the correct WS!")
        else:
            rospy.logwarn("Package FOUND in "+pkg_path +
                          ", BUT not in the ws="+ros_ws_abspath+", lets Download it...")
            pkg_path = self.DownloadRepo(package_name=rospackage_name,
                                         ros_ws_abspath=ros_ws_abspath)

        # If the package was found then we launch
        if pkg_path:
            rospy.loginfo(
                ">>>>>>>>>>Package found in workspace-->"+str(pkg_path))
            launch_dir = os.path.join(pkg_path, "launch")
            path_launch_file_name = os.path.join(launch_dir, launch_file_name)

            self.uuid = roslaunch.rlutil.get_or_generate_uuid(None, False)
            roslaunch.configure_logging(self.uuid)
            self.launch = roslaunch.parent.ROSLaunchParent(
                self.uuid, [path_launch_file_name])
            self.launch.start()

            rospy.loginfo("STARTED Roslaunch-->"+str(self._launch_file_name))
        else:
            assert False, "No Package Path was found for ROS apckage ==>" + \
                str(rospackage_name)

    def DownloadRepo(self, package_name, ros_ws_abspath):
        """
        This has to be installed
        sudo pip install gitpython
        """
        commands_to_take_effect = "\ncd "+ros_ws_abspath + \
            "\ncatkin_make\nsource devel/setup.bash\nrospack profile\n"

        ros_ws_src_abspath_src = os.path.join(ros_ws_abspath, "src")
        pkg_path = None
        # We retrieve the got for the package asked
        package_git = None
        if package_name == "moving_cube_description":
            package_git = "https://bitbucket.org/theconstructcore/moving_cube.git"

        if package_name == "rosbot_gazebo" or package_name == "rosbot_description":
            package_git = "https://github.com/husarion/rosbot_description.git"

        if package_name == "fetch_gazebo":
            package_git = "https://bitbucket.org/theconstructcore/fetch_tc.git"

        # ADD HERE THE GIT To Your Simuation

        else:
            rospy.logerr("Package [ "+package_name +
                         " ] is not supported for autodownload, do it manually into >"+str(ros_ws_abspath))
            assert False, "The package "++ \
                " is not supported, please check the package name and the git support in openai_ros_common.py"

        # If a Git for the package is supported
        if package_git:
            try:
                rospy.logdebug("Lets download git="+package_git +
                               ", in ws="+ros_ws_src_abspath_src)
                git.Git(ros_ws_src_abspath_src).clone(package_git)
                rospy.logdebug("Download git="+package_git +
                               ", in ws="+ros_ws_src_abspath_src+"...DONE")
            except git.exc.GitCommandError:
                rospy.logwarn("The Git "+package_git+" already exists in " +
                              ros_ws_src_abspath_src+", not downloading")

            # We check that the package is there
            try:
                pkg_path = self.rospack.get_path(package_name)
                rospy.logwarn("The package "+package_name+" was FOUND by ROS.")

                if ros_ws_abspath in pkg_path:
                    rospy.logdebug("Package FOUND in the correct WS!")
                else:
                    rospy.logwarn("Package FOUND in="+pkg_path +
                                  ", BUT not in the ws="+ros_ws_abspath)
                    rospy.logerr(
                        "IMPORTANT!: You need to execute the following commands and rerun to dowloads to take effect.")
                    rospy.logerr(commands_to_take_effect)
                    sys.exit()

            except rospkg.common.ResourceNotFound:
                rospy.logerr("Package "+package_name+" NOT FOUND by ROS.")
                # We have to make the user compile and source to make ROS be able to find the new packages
                # TODO: Make this automatic
                rospy.logerr(
                    "IMPORTANT!: You need to execute the following commands and rerun to dowloads to take effect.")
                rospy.logerr(commands_to_take_effect)
                sys.exit()

        return pkg_path