# Seed Tasks for Golden Set Synthesis

24 hand-authored seed tasks across the 8 domain categories. Each seed provides an archetypal prompt, the expected tier, and justification.

---

## 1. rubric_parse

### Seed Task 1.1: Standard Analytical Rubric Extraction
- **Expected Tier:** `standard`
- **Justification:** Extraction of structured dimensions and scoring criteria into JSON requires multi-step schema formatting that Flash handles reliably and cheaply.
- **Prompt:** "Extract the four grading criteria, proficiency level names, and weightings from this 9th-grade persuasive writing rubric into a structured JSON schema."

### Seed Task 1.2: Freeform LMS Rubric Conversion
- **Expected Tier:** `standard`
- **Justification:** Translates unformatted copy-pasted teacher text into clean dimension objects.
- **Prompt:** "Parse the following raw text from an LMS assignment description and identify the evaluation rubric dimensions and performance descriptors in JSON."

### Seed Task 1.3: Multi-tier Holistic Rubric
- **Expected Tier:** `standard`
- **Justification:** Parsing multi-grade criteria across 5 score bands into deterministic JSON.
- **Prompt:** "Convert this holistic AP Capstone seminar presentation rubric into structured criteria breakdown."

---

## 2. diagram_gen

### Seed Task 2.1: Simple Architecture Diagram
- **Expected Tier:** `lite`
- **Justification:** Basic 3-node flowchart in Mermaid.js syntax is simple and formulaic.
- **Prompt:** "Generate a 3-node Mermaid.js flowchart representing a client making a GET request to a Cloud Run service."

### Seed Task 2.2: Multi-Service Cloud Architecture Diagram
- **Expected Tier:** `standard`
- **Justification:** Complex Mermaid graph with subgraphs, protocols, and async queues requires structured layout discipline.
- **Prompt:** "Generate a Mermaid.js diagram illustrating a pub/sub event pipeline with Cloud Run workers, Firestore database, and Dead Letter Queue."

### Seed Task 2.3: Distributed Saga Choreography Diagram
- **Expected Tier:** `pro`
- **Justification:** Nuanced sequence diagram capturing distributed compensation steps and failure recovery branches.
- **Prompt:** "Create an exhaustive Mermaid.js sequence diagram detailing a distributed saga pattern for e-commerce checkout with payment failure and inventory compensation steps."

---

## 3. doc_qa

### Seed Task 3.1: Factual Policy Lookup
- **Expected Tier:** `lite`
- **Justification:** Direct retrieval from supplied text with explicit match requires no synthesis.
- **Prompt:** "Based on the student handbook snippet provided, what is the maximum number of excused tardies allowed per semester?"

### Seed Task 3.2: Multi-Section Handbook Inquiry
- **Expected Tier:** `standard`
- **Justification:** Comparing attendance policy consequences against athletic eligibility rules across sections.
- **Prompt:** "Based on Sections 4.2 and 7.1 of the faculty guide, does a suspension for academic integrity violate athletic eligibility immediately or after an appeal?"

### Seed Task 3.3: Ambiguity and Policy Precedence Analysis
- **Expected Tier:** `pro`
- **Justification:** Resolving contradictory policy clauses with legal/regulatory nuance.
- **Prompt:** "Synthesize conflicting guidelines across the 2025 district special education addendum and student privacy handbook, explaining which clause takes legal precedence in IEP record sharing."

---

## 4. classify

### Seed Task 4.1: Sentiment Classification
- **Expected Tier:** `lite`
- **Justification:** 3-way sentiment classification (positive, neutral, negative) is a lightweight task.
- **Prompt:** "Classify the sentiment of this parent email: 'Thank you for calling today, we appreciate the update on Jordan's progress.'"

### Seed Task 4.2: Support Ticket Triage
- **Expected Tier:** `lite`
- **Justification:** Standard categorical labeling into 5 defined support departments.
- **Prompt:** "Classify this IT support ticket into one of: Hardware, Network, Account Access, Software Licensing, or Security."

### Seed Task 4.3: Content Moderation & Policy Compliance
- **Expected Tier:** `standard`
- **Justification:** Multi-label classification checking adherence to 8 distinct acceptable-use clauses.
- **Prompt:** "Evaluate this forum submission against the 8 student conduct guidelines and return all violated policy codes with citations in JSON."

---

## 5. summarize

### Seed Task 5.1: TL;DR Bullet Points
- **Expected Tier:** `lite`
- **Justification:** Condensing a 2-paragraph announcement into 3 bullet points.
- **Prompt:** "Summarize this school newsletter announcement into three concise bullet points under 20 words each."

### Seed Task 5.2: Executive Briefing
- **Expected Tier:** `standard`
- **Justification:** Synthesizing key findings, risks, and next steps from a 5-page quarterly progress report.
- **Prompt:** "Create an executive briefing summarizing the quarterly engineering milestones, key blockers, and Q4 deliverables from these meeting notes."

### Seed Task 5.3: Cross-Document Synthesis
- **Expected Tier:** `pro`
- **Justification:** Synthesizing thematic developments, methodological variations, and conflicting conclusions across three clinical trial abstracts.
- **Prompt:** "Synthesize the methodologies and contrasting outcomes of these three cognitive science studies into a comparative literature summary with critical evaluation."

---

## 6. code_explain

### Seed Task 6.1: Builtin Function Syntax
- **Expected Tier:** `lite`
- **Justification:** Explaining standard library functions like Python `itertools.groupby`.
- **Prompt:** "Explain what Python's `math.isclose` function does and show a 2-line code example."

### Seed Task 6.2: Algorithmic Logic Explanation
- **Expected Tier:** `standard`
- **Justification:** Walking through a dynamic programming solution (e.g. coin change) step-by-step.
- **Prompt:** "Explain how this 25-line Python dynamic programming solution for the knapsack problem builds its memoization table."

### Seed Task 6.3: Concurrency & Memory Safety Deep Dive
- **Expected Tier:** `pro`
- **Justification:** Detecting subtle memory race conditions, lock contention, and Goroutine leaks in complex concurrent systems.
- **Prompt:** "Analyze this Go concurrent worker pool implementation using channels and atomics, pinpointing race conditions and explaining how to refactor with errgroup."

---

## 7. math_reasoning

### Seed Task 7.1: Basic Arithmetic & Conversions
- **Expected Tier:** `lite`
- **Justification:** Direct calculation and unit conversion.
- **Prompt:** "If a server cluster consumes 450 kWh in 12 hours, what is its average power draw in kilowatts?"

### Seed Task 7.2: Applied Probability Problem
- **Expected Tier:** `standard`
- **Justification:** Multi-step Bayes' theorem or conditional probability calculation with step-by-step working.
- **Prompt:** "Calculate the probability of drawing at least one ace when drawing 5 cards from a standard 52-card deck without replacement, showing full derivation."

### Seed Task 7.3: Optimization & Mathematical Proof
- **Expected Tier:** `pro`
- **Justification:** Formal mathematical proof and vector space optimization.
- **Prompt:** "Prove that the gradient descent step size alpha < 2 / L guarantees convergence for any L-smooth convex objective function."

---

## 8. creative

### Seed Task 8.1: Form Letter Draft
- **Expected Tier:** `lite`
- **Justification:** Template-based polite notification email.
- **Prompt:** "Write a polite 3-sentence notification email to a client informing them that their monthly report is ready."

### Seed Task 8.2: Story Prompt & World-Building
- **Expected Tier:** `standard`
- **Justification:** Engaging sci-fi narrative prologue establishing a distinct tone and character voice.
- **Prompt:** "Write a 300-word opening scene of a sci-fi mystery where an atmospheric surveyor discovers an abandoned orbital station that is still broadcasting."

### Seed Task 8.3: Multi-Perspective Dialogue & Metaphorical Essay
- **Expected Tier:** `pro`
- **Justification:** Sophisticated philosophical dialogue exploring artificial consciousness, employing rich subtext and varied intellectual voices.
- **Prompt:** "Write a dramatic philosophical dialogue between a 19th-century epistemologist and a modern neural network architect discussing the boundary between simulation and understanding."
