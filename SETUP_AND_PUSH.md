# How to publish this repo (5 minutes)

This folder is a complete, working project. Here's how to get it onto your GitHub
(`github.com/vikas2987`) as your flagship repository.

## 1. Verify it runs locally (optional but nice)

```bash
cd enterprise-ai-eval-platform
pip install -r requirements.txt
PYTHONPATH=src python -m eval_platform.runner --dataset datasets/example_eval_set.jsonl
PYTHONPATH=src python -m pytest -q
```

You should see a passing regression gate and 22 passing tests.

## 2. Create the repo on GitHub

- Go to https://github.com/new
- Repository name: **enterprise-ai-eval-platform**
- Description: *A framework for evaluating enterprise LLM & RAG agents on faithfulness, groundedness, quality, latency, and cost.*
- Public. **Do not** initialize with a README/license (this folder already has them).

## 3. Push from your machine

```bash
cd enterprise-ai-eval-platform
git init
git add .
git commit -m "Enterprise AI Evaluation Platform: initial framework"
git branch -M main
git remote add origin https://github.com/vikas2987/enterprise-ai-eval-platform.git
git push -u origin main
```

## 4. Finish the polish on GitHub (2 minutes)

- **Pin it** to your profile: profile → Customize your pins → select this repo.
- Add **topics** (repo home → ⚙ next to About): `llm`, `rag`, `ai-evaluation`,
  `ai-agents`, `groundedness`, `enterprise-ai`.
- Confirm the **eval** GitHub Action ran green (Actions tab) — the passing badge
  is a strong signal to reviewers.

## Where to take it next (turns a scaffold into a story)

1. Add a **retrieval-completeness** metric aimed at Graph-RAG — "did we retrieve
   every relevant node?" This ties the repo directly to your Paytm agreement-agent
   case study.
2. Add a simple **HTML dashboard** in `report.py` for run-over-run trends.
3. Write a short LinkedIn post: *"I built an open-source enterprise AI evaluation
   platform — here's why BLEU/ROUGE fail for RAG."* Link the repo. That single
   post + repo is exactly the on-wedge proof your plan calls for.

> Tip: commit a little each week. A green, steadily-updated repo reads as
> "this person actually does the work" — which is the whole point.
