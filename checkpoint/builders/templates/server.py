import argparse
import json
import logging
import os
import re
import stat
import time
from asyncio import Future
from pathlib import Path
from typing import Any

from config import MISSIONS  # type: ignore
from terminado.management import UniqueTermManager
from terminado.websocket import TermSocket
from tornado.ioloop import IOLoop
from tornado.web import Application, StaticFileHandler
from tornado.websocket import WebSocketHandler, websocket_connect


class GradeManager:
    GRADE_DIR = Path("/checkpoint_grade")
    GRADE_FILE = GRADE_DIR / "results.json"
    LOG_FILE = GRADE_DIR / "session.log"

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
        """Initialize grade file, directory and logging"""
        try:
            # Create directory and set permissions
            cls.GRADE_DIR.mkdir(exist_ok=True)
            cls.GRADE_DIR.chmod(stat.S_IRWXU)  # 700
            
            # Setup logging
            logging.basicConfig(
                filename=cls.LOG_FILE,
                level=logging.INFO,
                format='%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Initialize grade file
            with open(cls.GRADE_FILE, 'w') as f:
                json.dump(cls._create_grade_data(0, len(MISSIONS)), f)
            
            # Set permissions for files
            cls.GRADE_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
            cls.LOG_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
            
            logging.info("=== New Session Started ===")
        except Exception as e:
            print(f"Error initializing grade file and logging: {e}")

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

    def on_message(self, message: str | bytes) -> Future[None]:
        try:
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            
            data = json.loads(message)
            content = data['content']
            message_type = data['type']  # 'command' or 'output'
            
            return self._check_mission(content, message_type)
        except Exception as e:
            logging.error(f"Error handling message: {e}")
            return Future()

    def _check_mission(self, content: str, message_type: str) -> Future[None]:
        if self.current_mission >= len(MISSIONS):
            return Future()
            
        mission = MISSIONS[self.current_mission]
        listener = mission['listener']
        
        # Skip if message type doesn't match the target
        if listener['target'] != message_type:
            return Future()
            
        is_completed = False
        if listener['type'] == 'regex':
            is_completed = bool(re.search(listener['match'], content))
        elif listener['type'] == 'exact':
            is_completed = content.strip() == listener['match']
        
        if is_completed:
            self.current_mission += 1
            GradeManager.update(self.current_mission)
            return self._send_mission_complete()
    
        return Future()

    def _send_mission_complete(self) -> Future[None]:
        return self.write_message({
            'type': 'mission_complete',
            'currentMission': self.current_mission,
            'missions': MISSIONS
        })

class TermSocketWithLogging(TermSocket):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._current_input: list[str] = []
        self._output_buffer: list[str] = []
        self._last_output_time = time.time()
        self._flush_scheduled = False

    def on_message(self, message: str | bytes) -> Future[None]:
        """Deal with messages from the client"""
        try:
            if isinstance(message, str):
                data = json.loads(message)
                if data[0] == "stdin":
                    input_text = data[1]
                    if input_text == "\r":
                        command = ''.join(self._current_input)
                        if command.strip():
                            logging.info(f"User Command: {command}")
                            # Send clean command to mission handler
                            IOLoop.current().add_callback(
                                self._notify_mission_handler,
                                {'type': 'command', 'content': command}
                            )
                        self._current_input = []
                    elif input_text in ('\b', '\x7f'):
                        if self._current_input:
                            self._current_input.pop()
                    else:
                        self._current_input.append(input_text)
        except Exception as e:
            logging.error(f"Error parsing terminal input: {e}")
        
        return TermSocket.on_message(self, message)

    def write_message(self, message: str | bytes | dict[str, Any], binary: bool = False) -> Future[None]:
        """Deal with messages sent to the client"""
        try:
            if isinstance(message, str):
                data = json.loads(message)
                if data[0] == "stdout":
                    text = data[1]
                    # Clean control characters
                    clean_text = re.sub(r'\x1b\[[0-9;]*[mK]', '', text)
                    clean_text = re.sub(r'\x1b\[\?[0-9]+[hl]', '', clean_text)
                    clean_text = re.sub(r'\r\n?', '\n', clean_text)
                    clean_text = clean_text.replace('\b', '')
                    
                    # If it's an echo of user input, don't record
                    if clean_text.strip() and not any(
                        clean_text.strip() == x for x in self._current_input
                    ):
                        self._output_buffer.append(clean_text)
                        self._last_output_time = time.time()
                        
                        # If the buffer is too large, flush immediately
                        if len(''.join(self._output_buffer)) > 1024:
                            self._flush_output_buffer()
                        # Otherwise, schedule a delayed flush
                        elif not self._flush_scheduled:
                            self._schedule_flush()
        except Exception as e:
            logging.error(f"Error in write_message: {e}")
        
        return TermSocket.write_message(self, message, binary)

    def _schedule_flush(self):
        """Schedule a delayed flush"""
        self._flush_scheduled = True
        IOLoop.current().call_later( # type: ignore
            0.1,  # 100ms delay
            self._delayed_flush
        )

    def _delayed_flush(self):
        """Delayed flush handling"""
        self._flush_scheduled = False
        # If the last output is more than 50ms ago, flush
        if time.time() - self._last_output_time >= 0.05:
            self._flush_output_buffer()

    def _flush_output_buffer(self):
        """Flush the output buffer"""
        if self._output_buffer:
            output = ''.join(self._output_buffer)
            if output.strip():
                clean_lines = [line for line in output.splitlines() if line.strip()]
                if clean_lines:
                    clean_output = '\n'.join(clean_lines)
                    logging.info(f"Program Output: {clean_output}")
                    # Send clean output to mission handler
                    IOLoop.current().add_callback(
                        self._notify_mission_handler,
                        {'type': 'output', 'content': clean_output}
                    )
            self._output_buffer = []

    def on_close(self):
        """Handle connection closure"""
        self._flush_output_buffer()
        logging.info("Terminal connection closed")
        super().on_close()

    async def _notify_mission_handler(self, data: dict[str, Any]):
        try:
            ws = await websocket_connect("ws://localhost:8080/missions")
            await ws.write_message(json.dumps(data))
            ws.close()
        except Exception as e:
            logging.error(f"Failed to notify mission handler: {e}")

def main():
    """Start the terminal server"""
    parser = argparse.ArgumentParser(description='Terminal server for checkpoint')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    parser.add_argument('--user', type=str, required=True, help='User to run as')
    parser.add_argument('--workdir', type=str, required=True, help='Working directory')
    args = parser.parse_args()

    GradeManager.init()

    program = ['gdb']

    term_manager = UniqueTermManager(
        shell_command=[
            'su', '-', args.user, '-c',
            f'cd {args.workdir} && exec {" ".join(program)}'
        ]
    )

    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    settings = {
        "static_path": current_dir,
        "debug": True
    }
    
    app = Application([
        (r"/terminals/(.*)", TermSocketWithLogging, {'term_manager': term_manager}),
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
