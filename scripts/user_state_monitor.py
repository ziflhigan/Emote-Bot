#!/usr/bin/env python
"""ROS launch entry point for the Module 2 user-state monitor."""

import os
import runpy


MODULE_SCRIPT = os.path.join(
    os.path.dirname(__file__), "Module_2", "user_state_monitor.py"
)

runpy.run_path(MODULE_SCRIPT, run_name="__main__")
