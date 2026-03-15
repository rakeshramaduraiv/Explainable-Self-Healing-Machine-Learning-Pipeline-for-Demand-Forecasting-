import json
from pathlib import Path
from datetime import datetime
from logger import get_logger

log = get_logger(__name__)

BASE = Path(__file__).parent.resolve()
LOGS = BASE / "logs"


class HealingStatusIndicator:
    """Track and display healing action status with visual indicators"""
    
    def __init__(self):
        self.status_file = LOGS / "healing_status.json"
        self.current_status = self._load_status()
    
    def _load_status(self):
        if self.status_file.exists():
            try:
                with open(self.status_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"action": "idle", "progress": 0, "message": "Ready"}
    
    def _save_status(self):
        LOGS.mkdir(exist_ok=True)
        with open(self.status_file, "w") as f:
            json.dump(self.current_status, f)
    
    def start_fine_tune(self, month):
        """Mark fine-tuning start"""
        self.current_status = {
            "action": "fine_tune",
            "month": str(month),
            "progress": 10,
            "message": f"🔧 Fine-tuning started for {month}",
            "timestamp": datetime.now().isoformat()
        }
        self._save_status()
        log.info(self.current_status["message"])
    
    def fine_tune_progress(self, step, total_steps):
        """Update fine-tuning progress"""
        progress = int(10 + (step / total_steps) * 80)
        self.current_status["progress"] = progress
        self.current_status["message"] = f"🔧 Fine-tuning in progress... {progress}%"
        self._save_status()
    
    def fine_tune_complete(self, improvement, success=True):
        """Mark fine-tuning complete"""
        if success:
            self.current_status = {
                "action": "fine_tune_complete",
                "progress": 100,
                "message": f"✅ Fine-tuning complete: {improvement*100:.1f}% improvement",
                "improvement": round(improvement, 4),
                "timestamp": datetime.now().isoformat()
            }
            log.info(self.current_status["message"])
        else:
            self.current_status = {
                "action": "fine_tune_failed",
                "progress": 0,
                "message": f"❌ Fine-tuning failed or rolled back",
                "timestamp": datetime.now().isoformat()
            }
            log.warning(self.current_status["message"])
        self._save_status()
    

    def start_monitoring(self, month):
        """Mark monitoring start"""
        self.current_status = {
            "action": "monitor",
            "month": str(month),
            "progress": 100,
            "message": f"👁️ Monitoring {month} (low drift, no action needed)",
            "timestamp": datetime.now().isoformat()
        }
        self._save_status()
        log.info(self.current_status["message"])
    
    def get_current_status(self):
        """Get current healing status"""
        return self._load_status()
