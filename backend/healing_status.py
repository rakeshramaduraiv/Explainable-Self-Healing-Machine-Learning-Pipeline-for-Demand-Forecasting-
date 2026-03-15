import json
from datetime import datetime
from pathlib import Path

class HealingStatusIndicator:
    """Real-time indicator for fine-tuning and retraining status"""
    
    def __init__(self, status_file="logs/healing_status.json"):
        self.status_file = Path(status_file)
        self.status_file.parent.mkdir(exist_ok=True)
    
    def start_fine_tune(self, month, drift_magnitude):
        """Mark fine-tuning as started"""
        status = {
            "status": "FINE_TUNING",
            "month": str(month),
            "action": "FINE_TUNE",
            "drift_magnitude": float(drift_magnitude),
            "started_at": datetime.now().isoformat(),
            "progress": "Calculating drift magnitude...",
        }
        self._write_status(status)
        print(f"\n🔧 FINE-TUNING STARTED: {month}")
        print(f"   Drift Magnitude: {drift_magnitude:.2f}")
    
    def fine_tune_progress(self, step, message):
        """Update fine-tuning progress"""
        status = self._read_status()
        status.update({
            "progress": message,
            "step": step,
            "updated_at": datetime.now().isoformat(),
        })
        self._write_status(status)
        print(f"   ⏳ {message}")
    
    def fine_tune_complete(self, old_mae, new_mae, improvement, deployed):
        """Mark fine-tuning as complete"""
        status = self._read_status()
        status.update({
            "status": "FINE_TUNE_COMPLETE",
            "old_mae": float(old_mae),
            "new_mae": float(new_mae),
            "improvement": float(improvement),
            "deployed": deployed,
            "completed_at": datetime.now().isoformat(),
        })
        self._write_status(status)
        
        symbol = "✅" if deployed else "❌"
        print(f"   {symbol} FINE-TUNE COMPLETE")
        print(f"      MAE: ${old_mae:,.0f} → ${new_mae:,.0f}")
        print(f"      Improvement: {improvement*100:.2f}%")
        print(f"      Status: {'DEPLOYED' if deployed else 'ROLLBACK'}\n")
    
    def start_retrain(self, month, drift_magnitude):
        """Mark retraining as started"""
        status = {
            "status": "RETRAINING",
            "month": str(month),
            "action": "RETRAIN",
            "drift_magnitude": float(drift_magnitude),
            "started_at": datetime.now().isoformat(),
            "progress": "Initializing retrain...",
        }
        self._write_status(status)
        print(f"\n🔄 RETRAINING STARTED: {month}")
        print(f"   Drift Magnitude: {drift_magnitude:.2f}")
    
    def retrain_progress(self, step, message):
        """Update retraining progress"""
        status = self._read_status()
        status.update({
            "progress": message,
            "step": step,
            "updated_at": datetime.now().isoformat(),
        })
        self._write_status(status)
        print(f"   ⏳ {message}")
    
    def retrain_complete(self, old_mae, new_mae, improvement, deployed, train_samples):
        """Mark retraining as complete"""
        status = self._read_status()
        status.update({
            "status": "RETRAIN_COMPLETE",
            "old_mae": float(old_mae),
            "new_mae": float(new_mae),
            "improvement": float(improvement),
            "deployed": deployed,
            "train_samples": int(train_samples),
            "completed_at": datetime.now().isoformat(),
        })
        self._write_status(status)
        
        symbol = "✅" if deployed else "❌"
        print(f"   {symbol} RETRAIN COMPLETE")
        print(f"      Train Samples: {train_samples:,}")
        print(f"      MAE: ${old_mae:,.0f} → ${new_mae:,.0f}")
        print(f"      Improvement: {improvement*100:.2f}%")
        print(f"      Status: {'DEPLOYED' if deployed else 'ROLLBACK'}\n")
    
    def monitor_only(self, month):
        """Mark as monitoring only"""
        status = {
            "status": "MONITORING",
            "month": str(month),
            "action": "MONITOR",
            "started_at": datetime.now().isoformat(),
        }
        self._write_status(status)
        print(f"\n👁️  MONITORING: {month} (No drift action needed)")
    
    def rollback(self, month, reason):
        """Mark as rollback"""
        status = {
            "status": "ROLLBACK",
            "month": str(month),
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        self._write_status(status)
        print(f"\n⚠️  ROLLBACK: {month}")
        print(f"   Reason: {reason}\n")
    
    def _write_status(self, status):
        """Write status to file"""
        with open(self.status_file, 'w') as f:
            json.dump(status, f, indent=2)
    
    def _read_status(self):
        """Read current status"""
        if self.status_file.exists():
            with open(self.status_file, 'r') as f:
                return json.load(f)
        return {}
    
    def get_current_status(self):
        """Get current healing status"""
        return self._read_status()
