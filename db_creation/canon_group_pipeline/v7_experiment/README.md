# Canonical tag v7 experiment

This prototype replaces v6's transitive embedding clusters with a conservative
ontology. Embeddings retrieve possible relationships; a local relation judge then
labels each pair as a synonym, parent, child, related, or unrelated.

Only high-confidence synonyms are eligible to replace raw tags. Parent and related
links remain graph edges, so `psychological horror` can sit beneath `horror` without
erasing the more specific meaning. The script is evaluation-only and never writes to
either Steam database.

Run the adversarial benchmark:

```bash
python3 -m db_creation.canon_group_pipeline.v7_experiment.ontology_v7
```

The default local models are `qwen3-embedding:0.6b` and `qwen3.5:9b` through Ollama.
The JSON report is written under `db_creation/analysis/`.

The report separates exact five-way ontology accuracy from merge-decision accuracy.
That distinction matters: a conservative `related` judgment in place of `right_parent`
loses hierarchy detail, while a false `synonym` judgment corrupts every game's tags.

Audit the most suspicious v6 replacements across 14 representative real games:

```bash
python3 -m db_creation.canon_group_pipeline.v7_experiment.sample_games
```

This also writes a report under `db_creation/analysis/` and leaves the databases unchanged.

View the sample audit in a local dashboard:

```bash
python3 -m db_creation.canon_group_pipeline.v7_experiment.ui
```

Then open `http://localhost:9998`.
