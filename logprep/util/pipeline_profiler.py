"""This module implements a pipeline profiler that can be activated in the config."""

import cProfile
import pstats
from datetime import datetime
import os


class PipelineProfiler:
    """Used profile the pipeline."""

    @staticmethod
    def profile_function(function, *args):
        """Profile a given function from within a pipeline.

        Parameters
        ----------
        function : function
            Function to be profiled
        args : any
            Arguments for the function to be profiled

        """
        profiles_path = ".profile"

        cprofile = cProfile.Profile()
        cprofile.enable()
        function(*args)
        cprofile.disable()
        pstats.Stats(cprofile).strip_dirs().sort_stats("cumtime").print_stats(50)

        if not os.path.exists(profiles_path):
            os.makedirs(profiles_path)

        profile_output = os.path.join(
            profiles_path, "output_{}.prof".format(datetime.now()).replace(":", "_")
        )
        pstats.Stats(cprofile).strip_dirs().sort_stats("cumtime").dump_stats(profile_output)
