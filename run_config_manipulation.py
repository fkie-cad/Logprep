import subprocess
import sys
import time


def main(delay_seconds: int):
    python_executable = sys.executable  # ensures correct interpreter (venv-safe)

    # Delay before starting script
    print(f"Waiting {delay_seconds} seconds before starting config manipulation...")
    time.sleep(delay_seconds)

    # Start script
    print("Starting config manipulation...")
    proc = subprocess.Popen([python_executable, "config_manipulator.py"])

    print("Process are now running.")

    proc.wait()

    print("Processes finished.")


if __name__ == "__main__":
    main(delay_seconds=5)
