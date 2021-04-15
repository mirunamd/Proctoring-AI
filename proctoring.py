import subprocess
import sys

fileInput = sys.argv[1]
user = sys.argv[2]
cmd = f"python mouth_opening_detector.py {fileInput} & python head_pose_estimation.py {fileInput} & python eye_tracker.py {fileInput}"
subprocess.call(cmd, shell=True)
cmd = f"python scoring.py {fileInput} {user}"
subprocess.call(cmd, shell=True)
