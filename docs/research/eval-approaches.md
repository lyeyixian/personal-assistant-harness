# Eval approaches for fit-analysis and resume quality

**Ticket:** [#8](https://github.com/lyeyixian/personal-assistant-harness/issues/8) · **Date:** 2026-07-15 · **Status:** research complete

Question: practical, low-ceremony evaluation approaches for the two v1 outputs — job-fit/gap analyses and tailored resumes — suitable for a solo dev, where evals are also a deliberate portfolio skill for the AI-engineer transition. All claims below are cited to primary sources (vendor docs, first-party cookbooks, original papers, tool repos), verified by fetching each source.

---

## TL;DR recommendation

1. **Build the v1 eval harness yourself in plain pytest** — a golden set of ~20–50 real job postings + the dev's actual profile, code assertions for everything mechanical, and hand-rolled LLM judges for the subjective criteria. This is Anthropic's documented pattern ([develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests), [cookbook eval notebook](https://github.com/anthropics/claude-cookbooks/blob/main/misc/building_evals.ipynb)), it is fully local, and building the judge *is* the portfolio skill.
2. **Judge design:** per-criterion binary/low-cardinality verdicts (not 1–10), chain-of-thought before the verdict, a different (stronger) model as judge than the generator, positions swapped for pairwise comparisons. Each of these is a first-party recommendation (sources in §2–§3).
3. **Split grading by output type:** fit/gap analyses are **reference-based** (the dev labels the true verdict and gaps for each golden posting; the judge compares against the label). Resumes are **reference-free rubric** territory (no single correct resume) with one non-negotiable check: every claim must be entailed by the experience store — the summarization-faithfulness pattern from [OpenAI's summarization eval cookbook](https://developers.openai.com/cookbook/examples/evaluation/how_to_eval_abstractive_summarization).
4. **Regressions:** run the suite before/after every prompt or model change, gate on pass-rate against a baseline run, grow the golden set from real usage. ([Anthropic engineering blog](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), [OpenAI best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices))
5. **Human-in-the-loop:** the dev hand-grades a small sample of outputs, then measures judge agreement against those labels before trusting the judge at scale. As the actual job-seeker, the dev is the domain expert — this calibration loop is cheap here.
6. **Tooling:** pytest DIY first; **Inspect AI** (UK AISI, MIT, no SaaS) as the proportionate graduation step if run history/transcript inspection starts to hurt. DeepEval is a reasonable middle ground; promptfoo adds a Node runtime to a Python project; Braintrust's hard SaaS dependency is disproportionate; OpenAI's hosted Evals platform shuts down Nov 2026 and is disqualified.

---

## 1. First-party framing: three grading tiers

Anthropic's eval guide ranks grading methods ([develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests)):

1. **Code-based grading** — "Fastest and most reliable, extremely scalable, but also lacks nuance for more complex judgements" (exact match, string match; their examples also include ROUGE-L and cosine similarity).
2. **Human grading** — "Most flexible and high quality, but slow and expensive. Avoid if possible."
3. **LLM-based grading** — "Fast and flexible, scalable and suitable for complex judgement. Test to ensure reliability first then scale."

The same page's design principles: mirror the real-world task distribution including edge cases; structure questions for automated grading; and "prioritize volume over quality: more questions with slightly lower signal automated grading is better than fewer questions with high-quality human hand-graded evals."

The Anthropic cookbook's [building_evals notebook](https://github.com/anthropics/claude-cookbooks/blob/main/misc/building_evals.ipynb) demonstrates all three tiers in plain Python: an eval = input prompt + model output + golden answer + score; the model-graded example passes a rubric and instructs the judge to output only `correct`/`incorrect` in XML tags.

**Implication for this project:** everything mechanical gets a code assertion (free, deterministic); the judge is reserved for the genuinely subjective criteria; human grading is a calibration tool, not the pipeline.

## 2. LLM-as-judge: rubric scoring done right

Convergent first-party guidance on judge design:

- **Detailed, explicit rubrics; several rubrics per use case.** "Have detailed, clear rubrics… A given use case, or even a specific success criteria for that use case, might require several rubrics for holistic evaluation." ([Anthropic develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests))
- **Low-cardinality output scales.** Anthropic: "instruct the LLM to output only 'correct' or 'incorrect', or to judge from a scale of 1-5. Purely qualitative evaluations are hard to assess quickly and at scale" (their worked examples use binary yes/no and 1–5 Likert; no 1–10 scales appear). OpenAI's best-practices guide: "Use pairwise comparison or pass/fail for more reliability" ([evaluation-best-practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)). OpenAI's [Custom-LLM-as-a-Judge cookbook](https://developers.openai.com/cookbook/examples/custom-llm-as-a-judge) measured it: classification against five discrete categories hit 98% accuracy vs 95% for a 1–N numeric rater, because numeric scales invite unintended partial credit.
- **Chain-of-thought before the verdict, then discard the reasoning.** Anthropic: "Ask the LLM to think first before deciding an evaluation score, and then discard the reasoning. This increases evaluation performance, particularly for tasks requiring complex judgement" ([develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests)). OpenAI: "reasoning before scoring improves eval performance" ([evaluation-best-practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)). Nuance: in OpenAI's judge experiment CoT did not raise the numeric rater's accuracy but was kept for interpretability/debugging ([Custom-LLM-as-a-Judge](https://developers.openai.com/cookbook/examples/custom-llm-as-a-judge)).
- **Different, stronger model as judge.** Anthropic: it is "generally best practice to use a different model to evaluate than the model used to generate the evaluated output" ([develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests)). OpenAI: start with the strongest available judge model, "then validate agreement against your human labels before optimizing for cost or latency" ([evaluation-best-practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)); same advice in the [Getting Started with OpenAI Evals cookbook](https://developers.openai.com/cookbook/examples/evaluation/getting_started_with_openai_evals).
- **Separate judge call per criterion.** OpenAI's [abstractive-summarization eval cookbook](https://developers.openai.com/cookbook/examples/evaluation/how_to_eval_abstractive_summarization) (the G-Eval pattern) grades each of four criteria — relevance, coherence, consistency, fluency — in its own judge call with criterion-specific evaluation steps and its own small scale.

## 3. Pairwise comparison and judge failure modes

The canonical primary source is Zheng et al., *"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"* (NeurIPS 2023, [arXiv 2306.05685](https://arxiv.org/abs/2306.05685); [full text](https://arxiv.org/html/2306.05685v4)).

**Three judge modes** (§3.1): pairwise comparison (which of two answers is better, or tie), single-answer grading (score one output in isolation), and reference-guided grading (judge sees a gold answer). Trade-off: pairwise "may lack scalability when the number of players increases" (pairs grow quadratically), while single-answer grading "may be unable to discern subtle differences between specific pairs." **Use pairwise when comparing two close candidates — e.g. resume output before vs after a prompt change; use single-answer rubric grading for routine per-output scoring.**

**Validation:** a GPT-4 judge agreed with humans 85% of the time (setup without ties) — higher than human–human agreement at 81% (§4.2).

**Failure modes** (§3.3), with vendor acknowledgment in [OpenAI's best-practices guide](https://developers.openai.com/api/docs/guides/evaluation-best-practices), which explicitly lists position and verbosity bias:

| Failure mode | Evidence (Zheng et al.) |
|---|---|
| **Position bias** | GPT-4 position-consistent only 65% when answer order swapped; Claude-v1 23.8% |
| **Verbosity bias** | Under a padded "repetitive list" attack: Claude-v1 and GPT-3.5 fooled 91.3% of the time; GPT-4 8.7% |
| **Self-enhancement bias** | GPT-4 favors its own outputs by ~10% win rate; Claude-v1 by ~25% |
| **Weak math/reasoning grading** | GPT-4 default-prompt judge failed 14/20 math grading cases it could itself solve |

**Mitigations** (§3.4): swap positions and only declare a win if preferred in *both* orders (else tie); few-shot judge examples (raised GPT-4 position consistency 65%→77.5%); reference-guided judging (cut math grading failures 70%→15%). Anthropic's "different model as judge" advice addresses self-preference. Additional vendor caveats: "LLM-based metrics could have a bias towards preferring LLM-generated texts over human-written texts" ([OpenAI summarization cookbook](https://developers.openai.com/cookbook/examples/evaluation/how_to_eval_abstractive_summarization)) and graders can be reward-hacked — "a model that's hacked the grader will score highly on model grader evals but score poorly on expert human evaluations" ([OpenAI graders guide](https://developers.openai.com/api/docs/guides/graders)).

## 4. Golden / reference sets

- **Starting size:** "20-50 simple tasks drawn from real failures is a great start" ([Anthropic engineering: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)). Anthropic's docs then push volume once grading is automated, and note: "Writing hundreds of test cases can be hard to do by hand! Get Claude to help you generate more from a baseline set of example test cases" ([develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests)).
- **Sourcing:** mine real usage. OpenAI: "Log everything: Log as you develop so you can mine your logs for good eval cases" ([evaluation-best-practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)). Anthropic: "Begin with the manual checks you run during development… If you're already in production, look at your bug tracker and support queue" ([demystifying-evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).
- **Edge cases:** deliberately include irrelevant/nonexistent input data, overly long inputs, and ambiguous cases "where even humans would find it hard to reach an assessment consensus" ([develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests)); OpenAI adds input-format variability, typos, and conflicting instructions ([evaluation-best-practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)).
- **Evolution:** "Owning and iterating on evaluations should be as routine as maintaining unit tests," and watch for saturation — "An eval at 100% tracks regressions but provides no signal for improvement" ([demystifying-evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).

**For this project:** ~20–50 real job postings paired with the dev's actual profile snapshot, seeded with postings where the right verdict is already known — clear fit, clear non-fit, borderline — plus edge cases (sparse posting, oddly formatted posting, role far outside the dev's field, posting demanding half-held skills). Each fit-analysis case gets a hand-written label: expected verdict + expected gap list. Every real run of the agent that produces a surprising output becomes a new case.

## 5. Grading the two v1 outputs

### 5a. Job-fit/gap analysis → reference-based judging

Both vendors document grading against a gold answer: Anthropic's docs show a judge grading completions against a `golden_answer` with a rubric, thinking in `<thinking>` tags, then outputting `correct`/`incorrect` ([develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests)); OpenAI names "reference-guided grading: provide the judge model with a reference or 'gold standard' answer" as a distinct mode ([evaluation-best-practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)), and reference-guided judging is the mitigation that most improved judge accuracy in Zheng et al. §3.4.

Concrete checks per golden case, each its own binary judge verdict (per §2):
- Fit verdict matches the labeled verdict.
- Each labeled gap is identified (judge checks recall against the label).
- No hallucinated requirements — every cited requirement actually appears in the posting.
- No hallucinated experience — every claimed strength is entailed by the experience store.

### 5b. Tailored resume → code assertions + reference-free rubric

There is no single correct resume, exactly as Anthropic concedes for summaries: "There is no single correct summary for any given document… The process can be highly subjective"; their fallback is LLM grading "against a scoring rubric… assessing key factors like accuracy, completeness, and coherence" ([Anthropic legal summarization guide](https://platform.claude.com/docs/en/docs/about-claude/use-case-guides/legal-summarization)).

**Code assertions first** (cheap, deterministic — [develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests), [OpenAI graders](https://developers.openai.com/api/docs/guides/graders)): required sections present, length/page budget respected, job-description keywords covered, no forbidden content. Since the deterministic pipeline owns layout (LLM writes content only, per the project's standing decision), format assertions are mostly the renderer's contract; content-side assertions operate on the LLM's structured output.

**Rubric judge criteria**, adapted from the summarization-eval dimensions ([OpenAI summarization cookbook](https://developers.openai.com/cookbook/examples/evaluation/how_to_eval_abstractive_summarization), [Anthropic legal summarization](https://platform.claude.com/docs/en/docs/about-claude/use-case-guides/legal-summarization)) — one judge call each:
- **Grounding/faithfulness (non-negotiable, hard fail):** the summarization "consistency" dimension — output "contains only statements entailed by the source document" — transfers directly as *every resume claim must be entailed by the source experience store*. The judge receives the experience store and the resume and hunts for unsupported claims.
- **Relevance/tailoring:** the most job-relevant experience is selected and foregrounded for this specific posting.
- **Conciseness and readability** (Anthropic's summarization criteria transfer almost verbatim: factual correctness, conciseness, consistency of structure, readability).
- **Pairwise A/B** (positions swapped, both-orders rule) when comparing a prompt change's resume against the baseline's — this is where pairwise beats absolute scoring (Zheng et al. §3.1).

Also relevant: "It's often better to grade what the agent produced, not the path it took" ([demystifying-evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)) — grade the final analysis/resume, not the agent's intermediate steps.

## 6. Regression checks on prompt changes

- Anthropic makes evals a *precondition* of prompt engineering: their prompt-engineering guide assumes "a clear definition of the success criteria… some ways to empirically test against those criteria… a first draft prompt you want to improve. If not, we highly suggest you spend time establishing that first" ([prompt-engineering overview](https://platform.claude.com/docs/en/docs/build-with-claude/prompt-engineering/overview)); the engineering blog's framing is "as routine as maintaining unit tests" ([demystifying-evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).
- The regression pattern (from [OpenAI's prompt-regression cookbook](https://developers.openai.com/cookbook/examples/evaluation/use-cases/regression)): fixed eval definition (dataset + criteria), one run per prompt version, compare the candidate run against the baseline run. (The hosted platform behind that cookbook is being sunset — see §7 — so adopt the pattern, not the product.)
- **Explicit pass/fail thresholds** as success criteria: Anthropic's examples ("an F1 score of at least 0.85… 99.5% of outputs are non-toxic" — [develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests)); OpenAI: "Include a pass/fail threshold in addition to the numerical score" ([evaluation-best-practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)).
- **CI wiring** (if wanted later): promptfoo's CI docs show triggering evals on PRs that touch `prompts/**` and failing the build on failures or pass-rate < threshold ([promptfoo CI/CD](https://www.promptfoo.dev/docs/integrations/ci-cd/), [GitHub Action](https://www.promptfoo.dev/docs/integrations/github-action/)); Braintrust ships an equivalent [eval-action](https://github.com/braintrustdata/eval-action). For a solo repo, `pytest` in a GitHub Action (or run locally pre-commit) achieves the same gate with zero extra tooling.
- **Comparing runs statistically:** Anthropic's [statistical approach to model evals](https://www.anthropic.com/research/statistical-approach-to-model-evals) recommends error bars and paired-difference tests — "Eval scores don't have any meaning on their own; they only make sense in relation to one another." For a 20–50-case suite, the lightweight takeaway is: compare per-case (paired), not just aggregate score, and don't over-read small score deltas.

## 7. Human-in-the-loop grading

- Human grading is the gold standard but "slow and expensive. Avoid if possible" ([develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests)); the sanctioned lightweight pattern is spot-checking "a few summaries as a sanity check" rather than grading everything ([legal summarization](https://platform.claude.com/docs/en/docs/about-claude/use-case-guides/legal-summarization)).
- **Judge calibration loop:** "LLM-based rubrics should be frequently calibrated against expert human judgment" ([demystifying-evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)); scale up only "once the LLM judge… consistently agrees with human annotations" ([evaluation-best-practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)). Concretely ([Custom-LLM-as-a-Judge](https://developers.openai.com/cookbook/examples/custom-llm-as-a-judge)): build a small ground-truth set including known-bad outputs, measure how often the judge gets them right, iterate on the judge prompt (meta-evaluation).
- For human graders, OpenAI recommends "show rather than tell" — provide worked examples of different score levels ([evaluation-best-practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)).

**Solo-dev shape:** the dev *is* the expert user here. Hand-grade ~a dozen outputs per output type (including deliberately bad ones — e.g. a resume with a planted fabricated claim, to verify the grounding judge catches it), store the labels next to the golden set, and re-check judge agreement whenever the judge prompt or judge model changes.

## 8. Tooling survey and proportionality

Landscape notes first: **OpenAI's hosted Evals platform goes read-only 2026-10-31 and shuts down 2026-11-30** ([OpenAI evals guide](https://developers.openai.com/api/docs/guides/evals)) — do not build on it. **OpenAI acquired promptfoo (2026-03-09)**; it "will remain open source under the current license" but roadmap drift is possible ([OpenAI announcement](https://openai.com/index/openai-to-acquire-promptfoo/), [promptfoo blog](https://www.promptfoo.dev/blog/promptfoo-joining-openai/)). Anthropic pushes no platform — their docs teach grader design in code ([develop-tests](https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests)); the Console has a manual side-by-side [Evaluation tool](https://platform.claude.com/docs/en/docs/test-and-evaluate/eval-tool) useful for quick prompt iteration but not a CI/regression system.

| Option | Definition style | Judge support | Local? | Ceremony | Teaches vs hides |
|---|---|---|---|---|---|
| **pytest DIY** | pure Python | write it yourself (~20 lines w/ structured output) | fully local, model key only | near zero | teaches the most — dataset format, judge prompts, thresholds all hand-built |
| **[Inspect AI](https://inspect.aisi.org.uk/)** (UK AISI, MIT) | Python `Task` = dataset + solver + scorer | built-in `model_graded_qa()` + custom Python scorers | fully local; ships `inspect view` log viewer; no account ever | moderate (more concepts) | exposes the canonical task/solver/scorer architecture; 200+ reference evals to read ([repo](https://github.com/UKGovernmentBEIS/inspect_ai)) |
| **[DeepEval](https://deepeval.com/docs/getting-started)** (Apache-2.0) | pytest-native: `LLMTestCase` + `assert_test` | G-Eval (criteria → judge), DAG, custom metrics | "DeepEval runs locally. Confident AI is optional" (docs FAQ); judge defaults to OpenAI but any provider works | low | middle — G-Eval exercises rubric-writing, hides judge scaffolding ([repo](https://github.com/confident-ai/deepeval)) |
| **[promptfoo](https://www.promptfoo.dev/docs/intro/)** (MIT) | YAML config + assertions (`llm-rubric`, `factuality`, code checks); Python graders via `file://script.py` ([docs](https://www.promptfoo.dev/docs/configuration/expected-outputs/python/)) | prewritten model-graded asserts | "runs completely locally", no account ([repo](https://github.com/promptfoo/promptfoo)) | low-moderate, but **requires Node** + YAML→Python bridge | teaches assertion taxonomy/regression flow; hides judge prompts |
| **[Braintrust](https://www.braintrust.dev/docs/start/eval-sdk)** | Python `Eval()` SDK | LLM + code scorers | **no** — requires account + API key; results live on their servers; self-host is Enterprise-only; free tier has 14-day retention ([pricing](https://www.braintrust.dev/pricing)) | low | hides the most — you learn the platform, not eval construction |

Worth stealing regardless of harness: **[autoevals](https://github.com/braintrustdata/autoevals)** (MIT, from Braintrust but "completely optional and not required" to have an account) — Factuality/Summarization/Battle judges callable as plain Python functions inside pytest. One-liner alternatives: [Pydantic Evals](https://pydantic.dev/docs/ai/evals/evals/) is code-first, fully local, with an `LLMJudge` evaluator — a credible DeepEval alternative; LangSmith is account-centric SaaS like Braintrust and skippable here.

**Proportionality verdict (solo project + portfolio goal):**
- **Build:** pytest DIY harness now. Zero ceremony, fully local, and it is precisely the skill the portfolio needs — rubric design, judge prompts, calibration, thresholds. Optionally borrow autoevals scorers rather than writing every judge from scratch.
- **Graduate to:** Inspect AI when run history and transcript inspection start to hurt. No SaaS, serious provenance (UK AI Security Institute), and its vocabulary matches how the industry talks about evals — the strongest "portfolio artifact" among the frameworks.
- **Skip:** Braintrust (hard SaaS dependency, 14-day free retention, disproportionate); OpenAI Evals platform (shutting down); promptfoo (fine tool, wrong runtime for a Python-only project, post-acquisition uncertainty).
- **Learning-vs-hiding spectrum** (most teaching → most hiding): pytest DIY > Inspect AI > DeepEval ≈ promptfoo > Braintrust. "I built my judge prompts and regression suite in pytest, then ported them to Inspect tasks" is a better portfolio story than "I uploaded runs to a dashboard."

## 9. Proposed evaluation section shape for the spec

Distilling the above into the mechanism the spec needs:

1. **Golden set:** `evals/cases/` — 20–50 cases (real posting + profile snapshot), fit cases labeled with expected verdict + gaps; grown from every surprising real-world run.
2. **Three check layers per output:**
   - *Code assertions* (pytest, deterministic): structure, length, keyword coverage, schema validity.
   - *LLM judges* (one call per criterion, CoT-then-verdict, binary/1–5, judge model ≠ generator model): reference-based for fit analyses; reference-free rubric for resumes with grounding-in-experience-store as a hard fail.
   - *Pairwise A/B* (position-swapped) for prompt-change comparisons on resumes.
3. **Regression gate:** run the suite on any change to prompts or models; compare per-case against the baseline run; fixed pass thresholds; failures block the change.
4. **Judge calibration:** a small hand-labeled set (including planted failures) that the judge itself is measured against whenever judge prompt/model changes.
5. **Tooling:** plain pytest + JSONL cases in v1; Inspect AI as the named graduation path.

## Sources

**Anthropic (first-party):**
- Develop tests / empirical evals: https://platform.claude.com/docs/en/docs/test-and-evaluate/develop-tests (redirect target of docs.anthropic.com/en/docs/test-and-evaluate/develop-tests)
- Define success criteria: https://platform.claude.com/docs/en/docs/test-and-evaluate/define-success
- Console eval tool: https://platform.claude.com/docs/en/docs/test-and-evaluate/eval-tool
- Prompt engineering overview (evals as precondition): https://platform.claude.com/docs/en/docs/build-with-claude/prompt-engineering/overview
- Legal summarization guide (rubric grading of subjective documents): https://platform.claude.com/docs/en/docs/about-claude/use-case-guides/legal-summarization
- Engineering blog — Demystifying evals for AI agents: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Research — A statistical approach to model evals: https://www.anthropic.com/research/statistical-approach-to-model-evals
- Cookbook — building_evals notebook: https://github.com/anthropics/claude-cookbooks/blob/main/misc/building_evals.ipynb

**OpenAI (first-party):**
- Evaluation best practices: https://developers.openai.com/api/docs/guides/evaluation-best-practices
- Graders guide: https://developers.openai.com/api/docs/guides/graders
- Evals guide (incl. platform sunset dates): https://developers.openai.com/api/docs/guides/evals
- Cookbook — Getting started with OpenAI Evals: https://developers.openai.com/cookbook/examples/evaluation/getting_started_with_openai_evals
- Cookbook — Custom LLM-as-a-Judge: https://developers.openai.com/cookbook/examples/custom-llm-as-a-judge
- Cookbook — Evaluating abstractive summarization (G-Eval): https://developers.openai.com/cookbook/examples/evaluation/how_to_eval_abstractive_summarization
- Cookbook — Detecting prompt regressions: https://developers.openai.com/cookbook/examples/evaluation/use-cases/regression
- promptfoo acquisition: https://openai.com/index/openai-to-acquire-promptfoo/
- openai/evals repo: https://github.com/openai/evals

**Papers:**
- Zheng et al., Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (NeurIPS 2023): https://arxiv.org/abs/2306.05685 (full text: https://arxiv.org/html/2306.05685v4)

**Tool docs/repos:**
- Inspect AI: https://inspect.aisi.org.uk/ · https://github.com/UKGovernmentBEIS/inspect_ai
- DeepEval: https://deepeval.com/docs/getting-started · https://github.com/confident-ai/deepeval
- promptfoo: https://www.promptfoo.dev/docs/intro/ · https://www.promptfoo.dev/docs/configuration/expected-outputs/ · https://www.promptfoo.dev/docs/configuration/expected-outputs/python/ · https://www.promptfoo.dev/docs/integrations/ci-cd/ · https://www.promptfoo.dev/docs/integrations/github-action/ · https://github.com/promptfoo/promptfoo · https://www.promptfoo.dev/blog/promptfoo-joining-openai/
- Braintrust: https://www.braintrust.dev/docs/start/eval-sdk · https://www.braintrust.dev/docs/guides/evals · https://www.braintrust.dev/pricing · https://github.com/braintrustdata/eval-action
- autoevals: https://github.com/braintrustdata/autoevals
- Pydantic Evals: https://pydantic.dev/docs/ai/evals/evals/
