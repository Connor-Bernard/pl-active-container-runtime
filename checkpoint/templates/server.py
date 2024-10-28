import os
import re

from config import MISSIONS  # type: ignore
from terminado.management import UniqueTermManager
from terminado.websocket import TermSocket
from tornado.ioloop import IOLoop
from tornado.web import Application, StaticFileHandler
from tornado.websocket import WebSocketHandler


class MissionHandler(WebSocketHandler):
    def initialize(self):
        self.current_mission = 0

    def check_origin(self, origin):
        return True

    def open(self):
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

    def on_message(self, _message: str | bytes) -> None:
        try:
            if isinstance(_message, bytes):
                message: str = _message.decode('utf-8')
            elif isinstance(_message, str):
                message: str = _message
            else:
                raise ValueError(f"Invalid message type: {type(_message)}")
            
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
            self._send_mission_complete()

    def _send_mission_complete(self):
        self.write_message({
            'type': 'mission_complete',
            'currentMission': self.current_mission,
            'missions': MISSIONS
        })

def main():
    """Start the terminal server"""
    term_manager = UniqueTermManager(shell_command=['gdb'])
    
    settings = {
        "static_path": os.path.dirname(os.path.abspath(__file__)),
        "debug": True
    }
    
    app = Application([
        (r"/terminals/(.*)", TermSocket, {'term_manager': term_manager}),
        (r"/missions", MissionHandler),
        (r"/(.*)", StaticFileHandler, {
            "path": settings["static_path"],
            "default_filename": "index.html"
        })
    ], **settings)
    
    print("Server starting on port 8080...")
    app.listen(8080, '0.0.0.0')
    IOLoop.current().start()

if __name__ == "__main__":
    main()
