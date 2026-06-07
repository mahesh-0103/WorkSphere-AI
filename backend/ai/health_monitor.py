import time

class ModelHealthMonitor:
    def __init__(self, cooldown_seconds: int = 60, max_consecutive_failures: int = 2):
        self.cooldown_seconds = cooldown_seconds
        self.max_consecutive_failures = max_consecutive_failures
        # model_name -> {"consecutive_failures": int, "cooldown_until": float, "status": str}
        self.registry = {}

    def _init_model(self, model_name: str):
        if model_name not in self.registry:
            self.registry[model_name] = {
                "consecutive_failures": 0,
                "cooldown_until": 0.0,
                "status": "healthy"
            }

    def is_healthy(self, model_name: str) -> bool:
        """
        Returns True if the model is healthy and not in cooldown.
        """
        self._init_model(model_name)
        info = self.registry[model_name]
        
        if info["status"] == "cooldown":
            # If cooldown duration is passed, restore healthy status
            if time.time() > info["cooldown_until"]:
                info["status"] = "healthy"
                info["consecutive_failures"] = 0
            else:
                return False
        return True

    def report_success(self, model_name: str):
        """
        Resets failure counters on success.
        """
        self._init_model(model_name)
        info = self.registry[model_name]
        info["consecutive_failures"] = 0
        info["status"] = "healthy"
        info["cooldown_until"] = 0.0

    def report_failure(self, model_name: str):
        """
        Records failure and flags cooldown if threshold is hit.
        """
        self._init_model(model_name)
        info = self.registry[model_name]
        info["consecutive_failures"] += 1
        
        if info["consecutive_failures"] >= self.max_consecutive_failures:
            info["status"] = "cooldown"
            info["cooldown_until"] = time.time() + self.cooldown_seconds

    def get_status(self) -> dict:
        """
        Returns status summary of monitored models.
        """
        snapshot = {}
        for m in self.registry:
            self.is_healthy(m)  # update status based on elapsed time
            snapshot[m] = {
                "status": self.registry[m]["status"],
                "failures": self.registry[m]["consecutive_failures"],
                "cooldown_remaining": max(0.0, self.registry[m]["cooldown_until"] - time.time())
            }
        return snapshot

# Global Health Monitor Instance
health_monitor = ModelHealthMonitor()
