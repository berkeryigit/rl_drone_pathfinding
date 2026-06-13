__all__ = ["Fast2DDroneExplorationEnv"]


def __getattr__(name):
    if name == "Fast2DDroneExplorationEnv":
        from .fast_2d_drone_env import Fast2DDroneExplorationEnv

        return Fast2DDroneExplorationEnv
    raise AttributeError(name)
