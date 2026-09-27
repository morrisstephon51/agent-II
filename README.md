# agent-II

Grant scraping + scoring agent for The Plug AI.

```
python main.py            # run once now
python main.py --dry-run  # scrape + score, don't save or email
python main.py --cron     # install weekly Monday 8am cron entry
```

## Tests

Standard-library `unittest`, no extra test dependency. From the repo root:

```
python -m unittest discover -s tests -v
```

CI runs the same command on every push and pull request
(`.github/workflows/tests.yml`).
