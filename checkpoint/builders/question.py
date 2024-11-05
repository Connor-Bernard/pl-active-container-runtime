import json
import shutil
from pathlib import Path

from ..constants import WORKSPACE_TEMPLATES_PATH
from ..models.question import CheckpointQuestion

QUESTION_INFO_PATH = Path("info.json")

class QuestionBuilder:
    def __init__(self, config: CheckpointQuestion):
        self.config = config
    
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
