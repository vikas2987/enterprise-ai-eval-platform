# Demo script — 3 to 4 minutes

A tight, recordable walkthrough. Each scene has an **on-screen action** and a
**voiceover line**. Everything runs offline with the mock judge, so the whole
thing records in one take with no API key. Target length: **3:30**.

> Recording tip: a terminal + browser side by side is enough. Commands assume
> `pip install -e ".[dev]"` (or `PYTHONPATH=src`) from the repo root.

---

### Scene 1 — The problem (0:00–0:30)

**On screen:** the README title; then the "Why this exists" section.

**Voiceover:**
> "Most enterprise AI projects don't fail because the model is weak. They fail
> because nobody can prove the answers are trustworthy. BLEU and ROUGE were
> built for translation — they can't tell you whether a RAG answer is grounded
> in the source. This platform measures the things that actually decide
> adoption: is the answer faithful, is it grounded, and did retrieval even find
> everything it needed?"

---

### Scene 2 — Run an evaluation (0:30–1:15)

**On screen:** run the command, let the scorecard print.

```bash
python -m eval_platform.runner \
  --dataset datasets/enterprise_finance_legal.jsonl \
  --html reports/run.html
```

**Voiceover:**
> "Here's a run over a Finance and Legal eval set — vendor agreements, MSAs,
> liability caps, invoices. In one command we get faithfulness, groundedness,
> answer relevance, latency, cost — and a GraphRAG retrieval score. Notice the
> regression gate at the bottom: faithfulness clears the 0.80 threshold, so
> this run passes. Wire that into CI and a bad prompt change can't merge."

---

### Scene 3 — The dashboard (1:15–1:50)

**On screen:** open `reports/run.html` in the browser. Scroll the metric cards,
then the per-example table. Hover the red/amber cells.

**Voiceover:**
> "The same run renders as a self-contained HTML dashboard — no server, no
> dependencies. Green is healthy, amber and red flag the examples a reviewer
> should look at first. This is what a business stakeholder actually opens."

---

### Scene 4 — Catch a silent regression (1:50–2:35)

**On screen:** run the comparison.

```bash
python -m eval_platform.compare \
  --baseline datasets/ab_baseline.jsonl \
  --candidate datasets/ab_candidate.jsonl \
  --html reports/compare.html
```

**Voiceover:**
> "Now the scenario every AI team fears. We swap in a new prompt. It's faster
> and slightly cheaper — latency's down almost fifteen percent. But look:
> faithfulness dropped. The candidate started hallucinating on payment terms.
> The comparison gate fails with a non-zero exit code, so this 'improvement'
> never ships. That's the whole point — catch the quiet regression before your
> users do."

---

### Scene 5 — Keep the judge honest (2:35–3:10)

**On screen:** run the calibration command.

```bash
python -m eval_platform.human_eval agreement \
  --dataset datasets/enterprise_finance_legal.jsonl \
  --labels datasets/human_labels_sample.csv
```

**Voiceover:**
> "An LLM judge scales, but it isn't ground truth. So we sample its scores
> against human labels and measure agreement — error and correlation, per
> metric. On the hallucinated invoice example, the human caught what the judge
> missed. That gap is exactly the signal you use to re-tune the rubric before
> you trust the judge in production."

---

### Scene 6 — Close (3:10–3:30)

**On screen:** the architecture diagram in `docs/architecture.md`.

**Voiceover:**
> "Dataset in, scored report and a pass/fail gate out. Pluggable judges, zero
> hard dependencies, and every path ends in a CI-gateable decision. For
> enterprise AI, evaluation and trust *are* the product — and this is a
> practical harness for building that trust."

---

## Shot list (for a quick edit)

1. README hero + "Why this exists"
2. Terminal: `runner` scorecard (hold on the gate line)
3. Browser: `run.html` cards + table
4. Terminal: `compare` output (hold on the FAIL line)
5. Terminal: `human_eval agreement` table
6. `docs/architecture.md` mermaid diagram
