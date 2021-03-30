import subprocess
import sys

fileInput = sys.argv[1]
cmd = f"python mouth_opening_detector.py {fileInput} & python head_pose_estimation.py {fileInput} & python eye_tracker.py {fileInput}"
subprocess.run(cmd, shell=True)
