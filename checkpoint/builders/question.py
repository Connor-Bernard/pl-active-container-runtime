import json
import shutil
from pathlib import Path

from ..constants import QUESTION_HTML_PATH, WORKSPACE_TEMPLATES_PATH
from ..models.question import CheckpointQuestion

QUESTION_INFO_PATH = Path("info.json")
PL_SERVER_PATH = Path("server.py")

class QuestionBuilder:
    def __init__(self, config: CheckpointQuestion):
        self.config = config
        self.builder_dir = Path(__file__).parent
    
    def build(self, image_name: str):
        """Build PrairieLearn question files"""
        # 1. Create workspaceTemplates directory
        WORKSPACE_TEMPLATES_PATH.mkdir(exist_ok=True)
        
        # 2. Copy all files
        for src, dest in self.config.get_all_files().items():
            target = WORKSPACE_TEMPLATES_PATH / dest
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(src, target)
        
        # 3. Generate question info.json
        info = self.config.generate_info_json(image_name)
        QUESTION_INFO_PATH.write_text(json.dumps(info, indent=2))
        
        # 4. Copy PrairieLearn server.py
        shutil.copy2(self.builder_dir / "pl_server.py.template", PL_SERVER_PATH)

        # 5. Copy question.html
        shutil.copy2(self.builder_dir / "question.html.template", QUESTION_HTML_PATH)
