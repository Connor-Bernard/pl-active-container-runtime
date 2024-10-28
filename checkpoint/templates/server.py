import re

# It is imported in the template
from config import MISSIONS  # type: ignore
from terminado.management import UniqueTermManager
from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler


class TerminalHandler(RequestHandler):
    def check_origin(self, origin):
        return True

    def initialize(self, term_manager):
        self.term_manager = term_manager
        self.current_mission = 0

    async def websocket_handler(self, websocket):
        # Send initial state
        await websocket.write_message({
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

        try:
            while True:
                msg = await websocket.read_message()
                if msg is None:
                    return
                
                # Check mission completion
                await self._check_mission(msg, websocket)
                
                # Forward to terminal
                await self.term_manager.terminal.write_message(msg)
                
        except Exception as e:
            print(f"Error in websocket handler: {e}")

    async def _check_mission(self, output: str, websocket) -> None:
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
            await self._send_mission_complete(websocket)

    async def _send_mission_complete(self, websocket):
        await websocket.write_message({
            'type': 'mission_complete',
            'currentMission': self.current_mission,
            'missions': MISSIONS
        })

def main():
    """Start the terminal server"""
    term_manager = UniqueTermManager(shell_command=['gdb'])
    
    app = Application([
        (r"/websocket", TerminalHandler, {'term_manager': term_manager}),
        (r"/(.*)", RequestHandler, {"path": "."})  # Serve static files
    ])
    
    app.listen(8080, '0.0.0.0')
    IOLoop.current().start()

if __name__ == "__main__":
    main()
