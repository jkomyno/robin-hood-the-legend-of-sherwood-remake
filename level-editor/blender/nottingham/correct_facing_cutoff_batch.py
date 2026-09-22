"""Apply a reviewed list of property-only projection corrections; leave QA pending."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from correct_source_projection import main


if __name__ == '__main__':
    arguments = sys.argv[sys.argv.index('--') + 1:]
    if len(arguments) != 2:
        raise SystemExit('Expected jobs.json and frozen common tooling directory')
    jobs = json.loads(Path(arguments[0]).read_text())
    for job in jobs:
        main(Path(job['workspace']), [], Path(arguments[1]), Path(job['policy']))
