"""Allow ``python -m docshield`` to run the pipeline."""

from docshield.cli import main

raise SystemExit(main())
