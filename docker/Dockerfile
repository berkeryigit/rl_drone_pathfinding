# RL drone pathfinding image
# Base: ROS 2 Jazzy desktop (Ubuntu 24.04). Adds Gazebo Harmonic bridge packages,
# Python ML stack (SB3 + Torch + CUDA 12.1 wheels), and a non-root dev user.
FROM osrf/ros:jazzy-desktop

ARG DEBIAN_FRONTEND=noninteractive
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000

# --- system deps (ROS-Gazebo bridge, build tools, python) ----------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git wget sudo nano less tmux \
        python3-pip python3-venv python3-colcon-common-extensions \
        python3-rosdep python3-vcstool \
        ros-jazzy-ros-gz \
        ros-jazzy-ros-gz-bridge \
        ros-jazzy-ros-gz-sim \
        ros-jazzy-rmw-cyclonedds-cpp \
        mesa-utils libglu1-mesa libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/*

# --- python ML deps (SB3 + Torch w/ CUDA 12.1 wheels) -------------------------
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages \
        --extra-index-url https://download.pytorch.org/whl/cu121 \
        -r /tmp/requirements.txt

# --- non-root user matching host UID/GID --------------------------------------
RUN if getent passwd ubuntu > /dev/null 2>&1; then userdel -r ubuntu; fi \
    && groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/bash ${USERNAME} \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \
    && mkdir -p /workspace && chown ${USER_UID}:${USER_GID} /workspace

USER ${USERNAME}
WORKDIR /workspace

# Auto-source ROS in interactive shells.
RUN echo 'source /opt/ros/jazzy/setup.bash' >> ~/.bashrc \
    && echo 'if [ -f /workspace/ros2_ws/install/setup.bash ]; then source /workspace/ros2_ws/install/setup.bash; fi' >> ~/.bashrc \
    && echo 'export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp' >> ~/.bashrc

ENV ROS_DISTRO=jazzy \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    PYTHONUNBUFFERED=1

CMD ["/bin/bash"]
