import base64
import json
from typing import Any


def parse(data: dict[str, Any]) -> dict[str, Any]:
    data["submitted_answers"] = {}
    data["feedback"] = {
        "completed_missions": 0,
        "total_missions": 0,
        "message": "Start working on missions!"
    }
    return data

def grade(data: dict[str, Any]) -> dict[str, Any]:
    try:
        results_file = next(
            (f for f in data['raw_submitted_answers']['_files'] if f['name'] == '.checkpoint/results.json'),
            None
        )
        
        if not results_file:
            data["score"] = 0
            data["feedback"] = {
                "completed_missions": 0,
                "total_missions": 0,
                "message": "No results.json file found in submission"
            }
            return data
        
        results_content = base64.b64decode(results_file['contents']).decode('utf-8')
        grade_data = json.loads(results_content)
        
        data["score"] = grade_data.get("score", 0)
        if "feedback" in grade_data:
            data["feedback"] = grade_data["feedback"]
        if "partial_scores" in grade_data:
            data["partial_scores"] = grade_data["partial_scores"]
            
    except Exception as e:
        data["score"] = 0
        data["feedback"] = {
            "completed_missions": 0,
            "total_missions": 0,
            "message": f"Error processing grade: {str(e)}"
        }
    
    return data