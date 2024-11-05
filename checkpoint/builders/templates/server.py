import argparse
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from config import MISSIONS  # type: ignore
from terminado.management import UniqueTermManager
from terminado.websocket import TermSocket
from tornado.ioloop import IOLoop
from tornado.web import Application, StaticFileHandler
from tornado.websocket import WebSocketHandler


class GradeManager:
    GRADE_DIR = Path("/grade")
    GRADE_FILE = GRADE_DIR / "results.json"

    @classmethod
    def _create_grade_data(cls, completed_missions: int, total_missions: int) -> dict[str, Any]:
        """Create grade data structure"""
        score = completed_missions / total_missions if total_missions > 0 else 0
        return {
            "score": score,
            "max_points": 1.0,
            "feedback": {
                "completed_missions": completed_missions,
                "total_missions": total_missions,
                "message": f"Completed {completed_missions} out of {total_missions} missions"
            }
        }

    @classmethod
    def init(cls) -> None:
        """Initialize grade file and directory"""
        try:
            cls.GRADE_DIR.mkdir(exist_ok=True)
            cls.GRADE_DIR.chmod(stat.S_IRWXU)  # 700
            
            with open(cls.GRADE_FILE, 'w') as f:
                json.dump(cls._create_grade_data(0, len(MISSIONS)), f)
            
            cls.GRADE_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
        except Exception as e:
            print(f"Error initializing grade file: {e}")

    @classmethod
    def update(cls, completed_missions: int) -> None:
        """Update grade file"""
        try:
            with open(cls.GRADE_FILE, 'w') as f:
                json.dump(cls._create_grade_data(completed_missions, len(MISSIONS)), f)
        except Exception as e:
            print(f"Error updating grade file: {e}")


MISSIONS: list[dict[str, Any]]
class MissionHandler(WebSocketHandler):
    def initialize(self):
        self.current_mission = 0

    def check_origin(self, origin: str) -> bool:
        return True

    def open(self, *args: Any, **kwargs: Any) -> None:
        self.write_message({
            'type': 'init',
            'currentMission': self.current_mission,
            'missions': [
                {
                    'title': m['title'],
                    'prompt': m['prompt'],
                    'description': m['description']
                }
                for m in MISSIONS
            ]
        })
        GradeManager.update(self.current_mission)

    def on_message(self, message: str | bytes) -> None:
        try:
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            
            self._check_mission(message)
        except Exception as e:
            print(f"Error handling message: {e}")

    def _check_mission(self, output: str) -> None:
        if self.current_mission >= len(MISSIONS):
            return
            
        mission = MISSIONS[self.current_mission]
        listener = mission['listener']
        
        is_completed = False
        if listener['type'] == 'regex':
            is_completed = bool(re.search(listener['match'], output))
        elif listener['type'] == 'exact':
            is_completed = output.strip() == listener['match']
        
        if is_completed:
            self.current_mission += 1
            GradeManager.update(self.current_mission)
            self._send_mission_complete()

    def _send_mission_complete(self):
        self.write_message({
            'type': 'mission_complete',
            'currentMission': self.current_mission,
            'missions': MISSIONS
        })

def main():
    """Start the terminal server"""
    parser = argparse.ArgumentParser(description='Terminal server for checkpoint')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    args = parser.parse_args()

    GradeManager.init()

    term_manager = UniqueTermManager(shell_command=['gdb'])
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    settings = {
        "static_path": current_dir,
        "debug": True
    }
    
    app = Application([
        (r"/terminals/(.*)", TermSocket, {'term_manager': term_manager}),
        (r"/missions", MissionHandler),
        (r"/(.*)", StaticFileHandler, {
            "path": current_dir,
            "default_filename": "index.html"
        })
    ], None, None, **settings)
    
    print(f"Server starting on port {args.port}...")
    app.listen(args.port, '0.0.0.0')
    IOLoop.current().start()

if __name__ == "__main__":
    main()
