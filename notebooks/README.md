# Notebook status

`state_park_accessibility_analysis_backup.ipynb` is the preserved exploratory notebook from the original analysis session. It is valid notebook JSON, but it contains a long interactive troubleshooting history and stored outputs.

For a clean, reproducible run, use:

```bash
python scripts/reproduce_analysis.py
```

If opening the notebook in Jupyter, select the Conda environment created from `environment.yml` or the original `myenvironment` kernel. The Miniconda base kernel on the original computer does not include GeoPandas.
