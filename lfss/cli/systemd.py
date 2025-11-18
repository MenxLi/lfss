import os, sys
import subprocess
import argparse
from pathlib import Path

__doc = """
This will generate a systemd service that runs `lfss-serve` on startup and prints the unit file content to stdout. 
Should put the output to global systemd unit directory, e.g. 

> [this_command] | sudo tee /etc/systemd/system/lfss.service

and enable it with:  \n
> systemctl daemon-reload && systemctl enable lfss.service && systemctl start lfss.service
"""

def systemd_unit(
    host: str = "0.0.0.0",
    port = 8000, 
    workers = 2
    ) -> None:
    CMD = "lfss-serve"

    def run_command(cmd: str) -> str:
        """
        Run a shell command and return its output.
        Raises an error if the command fails.
        """
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True, 
            shell=True
        )
        return result.stdout.strip()

    cmd_path = run_command(f"which {CMD}")
    if not cmd_path:
        print(f"Error: Command '{CMD}' not found in PATH.", file=sys.stderr)
        raise SystemExit(1)
    
    username = run_command("whoami")
    if not username:
        print(f"Error: Unable to determine the current user.", file=sys.stderr)
        raise SystemExit(1)

    env = dict(os.environ)
    enviroment = " ".join(
        f'"{key}={value}"' 
        for key, value in env.items() 
        if key.startswith("LFSS_") and \
            not (key in ["LFSS_ENDPOINT", "LFSS_TOKEN", "LFSS_CLIENT_VERIFY"])
        )

    # Build ExecStart command
    exec_start = f"{cmd_path} --host {host} --port {port} --workers {workers}"

    # Generate unit file content
    unit_content = f"""\
[Unit]
Description=Run lfss-serve on {host}:{port} at boot
After=network.target

[Service]
Type=simple
User={username}
Environment={enviroment}
ExecStart={exec_start}
WorkingDirectory={Path.home()}
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
"""
    print(unit_content)

def main():
    parser = argparse.ArgumentParser(
        description="Generate a systemd unit file for the LFSS service to start on boot.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc
    )
    parser.add_argument(
        "--host", 
        type=str, 
        default="0.0.0.0",
        help="Host address to bind the LFSS service (default: 0.0.0.0)", 
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="Port number for the LFSS service (default: 8000)", 
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of worker processes for handling requests (default: 2)",
    )
    args = parser.parse_args()
    systemd_unit(
        host=args.host, 
        port=args.port, 
        workers=args.workers
    )