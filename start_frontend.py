"""Start AgentVerse Hub frontend"""
import subprocess

proc = subprocess.Popen(
    ["npm", "run", "dev"],
    cwd=r"D:\JARVES\agentverse-hub\frontend",
    shell=True,
)

print(f"Frontend PID: {proc.pid}")
