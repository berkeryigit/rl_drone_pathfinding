import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'rl_drone_pathfinding'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
        (os.path.join('share', package_name, 'worlds'),
            glob('worlds/*.sdf')),
        (os.path.join('share', package_name, 'models'),
            glob('models/*')),
        (os.path.join('share', package_name, 'config'),
            glob('config/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Berker Yigit',
    maintainer_email='berkerygt@gmail.com',
    description='RL-based indoor drone exploration with Lidar + Odometry (PPO).',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'train_ppo = rl_drone_pathfinding.agents.train_ppo:main',
            'eval_ppo = rl_drone_pathfinding.agents.eval_ppo:main',
            'env_smoke_test = rl_drone_pathfinding.envs.smoke_test:main',
        ],
    },
)
