import sys
from pipeline import Phase1Pipeline
from logger import get_logger

log = get_logger(__name__)

def main():
    try:
        summary = Phase1Pipeline().run_phase1()
        log.info(f"Final Drift Severity: {summary['final_severity'].upper()}")
        log.info(f"Recommendation: {summary['recommendation']}")
        return 0
    except Exception as e:
        log.error(f"Phase 1 failed: {e}")
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
