import os
import subprocess
import sys
import psutil
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class BotController:
    PID_FILE = "data/bot.pid"

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Returns the current status of the bot process."""
        if not os.path.exists(cls.PID_FILE):
            return {"status": "STOPPED", "pid": None, "mode": "OFFLINE"}

        try:
            with open(cls.PID_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    return {"status": "STOPPED", "pid": None, "mode": "OFFLINE"}
                pid, mode = content.split(",")
                pid = int(pid)

            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                    return {"status": "RUNNING", "pid": pid, "mode": mode}

            # Stale PID file
            BotController.stop_bot()
            return {"status": "STOPPED", "pid": None, "mode": "OFFLINE"}
        except Exception:
            return {"status": "STOPPED", "pid": None, "mode": "OFFLINE"}

    @classmethod
    def start_bot(cls, mode: str = "PAPER") -> bool:
        """Starts the bot in PAPER or LIVE mode as a background process."""
        status = cls.get_status()
        if status["status"] == "RUNNING":
            logger.warning("Bot is already running.")
            return False

        script = "run_paper_trade.py" if mode == "PAPER" else "run_live_trade.py"
        os.makedirs("data", exist_ok=True)

        try:
            proc = subprocess.Popen(
                [sys.executable, script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )

            with open(cls.PID_FILE, "w") as f:
                f.write(f"{proc.pid},{mode}")

            logger.info(f"Started bot process PID {proc.pid} in {mode} mode.")
            return True
        except Exception as e:
            logger.error(f"Failed to start bot: {str(e)}")
            return False

    @classmethod
    def stop_bot(cls) -> bool:
        """Stops the running bot process gracefully."""
        if not os.path.exists(cls.PID_FILE):
            return True

        try:
            with open(cls.PID_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    pid = int(content.split(",")[0])
                    if psutil.pid_exists(pid):
                        proc = psutil.Process(pid)
                        proc.terminate()
                        proc.wait(timeout=5)
        except Exception as e:
            logger.error(f"Error terminating process: {str(e)}")

        if os.path.exists(cls.PID_FILE):
            try:
                os.remove(cls.PID_FILE)
            except OSError:
                pass

        return True

    @classmethod
    def trigger_kill_switch(cls):
        """Creates the EMERGENCY KILL_SWITCH file."""
        with open("KILL_SWITCH", "w") as f:
            f.write("EMERGENCY STOP VIA DASHBOARD")
        cls.stop_bot()

    @classmethod
    def clear_kill_switch(cls):
        """Removes the KILL_SWITCH file."""
        if os.path.exists("KILL_SWITCH"):
            os.remove("KILL_SWITCH")
