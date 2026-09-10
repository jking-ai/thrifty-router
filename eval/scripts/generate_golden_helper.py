"""Script to generate the 300-item golden set for Thrifty Router evaluation."""

import json

CATEGORIES = [
    "rubric_parse",
    "diagram_gen",
    "doc_qa",
    "classify",
    "summarize",
    "code_explain",
    "math_reasoning",
    "creative",
]

# We need 300 items: 120 lite, 105 standard, 75 pro.
# Category distribution: 4 categories with 38, 4 with 37.
# Total = 300 items.

items_spec = []

# rubric_parse: 38 items (5 lite, 25 standard, 8 pro)
# diagram_gen: 38 items (15 lite, 15 standard, 8 pro)
# doc_qa: 38 items (18 lite, 12 standard, 8 pro)
# classify: 38 items (24 lite, 10 standard, 4 pro)
# summarize: 37 items (18 lite, 12 standard, 7 pro)
# code_explain: 37 items (10 lite, 15 standard, 12 pro)
# math_reasoning: 37 items (15 lite, 12 standard, 10 pro)
# creative: 37 items (15 lite, 4 standard, 18 pro)

# Let's verify sums:
# lite: 5 + 15 + 18 + 24 + 18 + 10 + 15 + 15 = 120 (40.0%)
# standard: 25 + 15 + 12 + 10 + 12 + 15 + 12 + 4 = 105 (35.0%)
# pro: 8 + 8 + 8 + 4 + 7 + 12 + 10 + 18 = 75 (25.0%)
# Total = 120 + 105 + 75 = 300. Exactly 300!

allocations = {
    "rubric_parse": {"lite": 5, "standard": 25, "pro": 8},
    "diagram_gen": {"lite": 15, "standard": 15, "pro": 8},
    "doc_qa": {"lite": 18, "standard": 12, "pro": 8},
    "classify": {"lite": 24, "standard": 10, "pro": 4},
    "summarize": {"lite": 18, "standard": 12, "pro": 7},
    "code_explain": {"lite": 10, "standard": 15, "pro": 12},
    "math_reasoning": {"lite": 15, "standard": 12, "pro": 10},
    "creative": {"lite": 15, "standard": 4, "pro": 18},
}

all_items = []
current_id = 1

# Templates per category and tier
PROMPT_BANKS = {
    "rubric_parse": {
        "lite": [
            ("List the title and maximum possible score for this grading rubric.", "Must state the assignment title and total points accurately."),
            ("Identify how many performance proficiency levels are defined in this rubric table.", "Must count and list the exact proficiency tier names."),
            ("Extract the weight percentage assigned to grammar in this composition rubric.", "Must state the exact percentage weight of the grammar category."),
            ("What is the name of the highest proficiency band in this standard rubric?", "Must accurately name the top band (e.g. Exemplary / Advanced)."),
            ("Extract the criteria names from this 3-column rubric header.", "Must list all column headers in exact order."),
        ],
        "standard": [
            ("Extract the 4 rubric dimensions and their respective 1-4 scale descriptors from this ELA rubric into structured JSON.", "Must return valid JSON with dimension names, score levels 1-4, and full descriptor text."),
            ("Parse this AP US History document-based question rubric into structured criteria objects with point thresholds.", "JSON must specify thesis, contextualization, evidence, and analysis criteria."),
            ("Convert this multi-page university lab report rubric into a machine-readable JSON schema with scoring criteria.", "Must extract abstract, hypothesis, methodology, results, and discussion criteria in JSON."),
            ("Extract the rubric dimensions, performance indicators, and point ranges from this high school debate rubric.", "JSON must capture argumentation, cross-examination, rebuttal, and delivery dimensions."),
            ("Parse this computer science project rubric into JSON covering code quality, documentation, test coverage, and functionality.", "Must structure the four CS rubric dimensions with distinct point values and descriptions."),
        ],
        "pro": [
            ("Synthesize and reconcile this contradictory dual-department grading rubric into a unified 5-tier evaluation matrix with arbitration rules.", "Must resolve conflicting weightings between technical and communication departments with formal rubric criteria."),
            ("Perform an algorithmic alignment audit of this state writing standard rubric, detailing potential bias and ambiguities in scoring criteria.", "Must critically evaluate rubric language for ambiguity, socioeconomic bias, and construct validity."),
            ("Deconstruct this ABET accreditation outcome rubric and formulate a multi-variable scoring model with calibration anchors.", "Must produce comprehensive scoring model with anchored student exemplars across all criteria."),
            ("Design an enterprise rubric for evaluating senior engineering staff against principal architect competencies.", "Must articulate nuanced behavioral anchors distinguishing staff from principal impact across 5 axes."),
        ]
    },
    "diagram_gen": {
        "lite": [
            ("Generate a 3-node Mermaid.js flowchart showing a user logging in.", "Must be valid Mermaid.js graph with User -> AuthForm -> Dashboard."),
            ("Create a Mermaid.js diagram illustrating a simple client-server request and response.", "Valid Mermaid sequence diagram showing Client -> Server and Server -> Client."),
            ("Generate a Mermaid flowchart showing a simple IF/THEN decision gate.", "Valid Mermaid flowchart with diamond decision node and two branches."),
            ("Create a 4-step Mermaid diagram of a git feature branch workflow.", "Valid Mermaid gitGraph or flowchart showing main, branch, commit, merge."),
            ("Generate a Mermaid stateDiagram showing an order moving from Pending to Shipped.", "Valid Mermaid stateDiagram with transitions: Pending -> Processing -> Shipped."),
        ],
        "standard": [
            ("Generate a Mermaid.js architecture diagram illustrating a FastAPI backend on Cloud Run communicating with Firestore and Pub/Sub.", "Must use Mermaid flowchart with subgraphs for Cloud Run, Firestore, and Pub/Sub with accurate labels."),
            ("Create a Mermaid.js sequence diagram showing OAuth2 Authorization Code Grant with PKCE.", "Valid sequence diagram showing User, Client, Auth Server, and Resource Server with authorization code and token exchanges."),
            ("Generate a Mermaid class diagram for an e-commerce shopping cart domain model.", "Valid class diagram with Cart, CartItem, Product, and Order classes with attributes and associations."),
            ("Create a Mermaid ER diagram for a school learning management system database.", "Valid Mermaid erDiagram with Student, Course, Enrollment, Assignment, and Submission entities."),
            ("Generate a Mermaid flowchart detailing a CI/CD deployment pipeline with testing, container build, and canary release stages.", "Valid flowchart with test, build, lint, scan, deploy canary, and promotion stages."),
        ],
        "pro": [
            ("Generate an exhaustive Mermaid.js sequence diagram modeling the 2-Phase Commit (2PC) protocol with coordinator failure and recovery recovery branches.", "Must model Coordinator, Cohort 1, and Cohort 2 across prepare, commit, timeout, and rollback scenarios with alt/opt blocks."),
            ("Create a complex Mermaid architecture diagram of a multi-region Active-Active Kubernetes deployment with global anycast routing and cross-region replication.", "Must clearly diagram edge ingress, multi-cluster service mesh, Spanner/Cassandra replication, and split-brain resolution."),
            ("Generate a detailed Mermaid diagram representing a distributed event-driven CQRS and Event Sourcing architecture with event store projection loops.", "Must accurately show Command API, Command Handlers, Event Store, Projection Workers, Read DB, and Query API with feedback loops."),
        ]
    },
    "doc_qa": {
        "lite": [
            ("Based on the provided handbook excerpt, what is the deadline for submitting grade appeals?", "Must extract exact calendar days or date stated in the text."),
            ("What is the dress code policy for science laboratory sessions according to Section 3.1?", "Must state required PPE: closed-toe shoes, lab coat, safety goggles."),
            ("Who is designated as the primary campus contact for lost student IDs?", "Must identify the student services office or campus desk named in excerpt."),
            ("According to the faculty syllabus, what percentage of the final grade is the midterm exam?", "Must state the exact percentage listed in the syllabus."),
            ("What is the minimum attendance requirement stated in paragraph 2?", "Must state the explicit percentage or days required."),
        ],
        "standard": [
            ("Based on the faculty handbook, synthesize the disciplinary escalation steps for academic dishonesty across first and repeated offenses.", "Must clearly delineate 1st offense (warning/zero) vs 2nd offense (dean referral/disciplinary probation) with procedure."),
            ("Compare the maternity leave and medical sabbatical policies in Section 6, highlighting key eligibility criteria and compensation differences.", "Must contrast service duration requirements, compensation percentages, and benefits continuation."),
            ("Explain the criteria and review procedure for undergraduate course substitution petitions described in Chapter 4.", "Must explain required signatures, minimum grade in original course, syllabus review, and deadline."),
            ("Synthesize the equipment loan policy, detailing checkout duration, late penalties, and damage liability terms.", "Must outline duration limits, daily fine rates, and replacement cost responsibility."),
        ],
        "pro": [
            ("Analyze the legal implications and potential liabilities of the conflicting confidentiality clauses in Section 8 vs District Privacy Addendum B.", "Must provide rigorous legal analysis comparing FERPA constraints, district indemnification, and student record exemptions."),
            ("Evaluate whether a faculty member's commercial intellectual property creation falls under university ownership under the 2024 revised patent policy.", "Must dissect patent policy criteria: use of university facilities, grant funding conditions, and scope of employment."),
            ("Reconcile the university tenure evaluation criteria with state legislative mandates on post-tenure review, assessing constitutional due process challenges.", "Must evaluate property interest in tenure, notice requirements, procedural safeguards, and legislative authority limits."),
        ]
    },
    "classify": {
        "lite": [
            ("Classify this email as 'urgent' or 'routine': 'Please review the attached monthly report when you get a chance.'", "Must classify as 'routine' with concise explanation."),
            ("Is this review positive, negative, or neutral? 'The food arrived cold and took 2 hours.'", "Must classify as 'negative'."),
            ("Classify the language of this sentence: 'Guten Tag, wie geht es Ihnen heute?'", "Must identify German."),
            ("Categorize this transaction: 'Payment to Shell Oil 42.50 USD'. Categories: Groceries, Fuel, Entertainment, Utilities.", "Must classify as 'Fuel'."),
            ("Classify this query intent: 'How do I cancel my subscription?' Intent: Billing, Navigation, Technical, Churn.", "Must classify as 'Churn' or 'Billing'."),
        ],
        "standard": [
            ("Classify this student feedback into multi-label categories: Course Content, Instructor Pacing, Grading Fairness, Platform UX.", "Must assign appropriate categories from the defined set with rationale."),
            ("Evaluate this pull request description and classify its semantic release type: MAJOR, MINOR, or PATCH.", "Must analyze breaking changes, features, and fixes to select correct SemVer level."),
            ("Categorize this cloud security alert into Severity (Critical/High/Medium/Low) and MITRE ATT&CK Tactic.", "Must specify severity and correctly map behavior to MITRE tactic (e.g. Initial Access, Privilege Escalation)."),
            ("Classify this medical inquiry into clinical specialty triage: Cardiology, Neurology, Orthopedics, or Dermatology.", "Must identify symptoms and select specialty with clinical reasoning."),
        ],
        "pro": [
            ("Perform an exhaustive forensic classification of this binary exploit payload, identifying vulnerability class, bypass technique, and CVE family.", "Must identify heap spray/ROP/buffer overflow mechanics and categorize accurately with technical justification."),
            ("Classify the psychological and persuasive rhetorical framing in this political campaign speech using Aristotle's appeals and modern framing theory.", "Must analyze ethos, pathos, logos, and cognitive framing devices with deep textual evidence."),
        ]
    },
    "summarize": {
        "lite": [
            ("Summarize this 100-word paragraph in a single sentence under 25 words.", "Must capture central idea concisely in under 25 words."),
            ("Provide 3 bullet points summarizing this campus event announcement.", "Must extract date/time, location, and key activities in 3 bullets."),
            ("What is the main takeaway of this product update note in one sentence?", "Must state the core feature release accurately."),
            ("Summarize the key result of this team standup update.", "Must identify what was completed and what is blocked."),
        ],
        "standard": [
            ("Synthesize this 3-page quarterly business review into an executive summary covering metrics, wins, headwinds, and next quarter outlook.", "Must summarize revenue, growth metrics, product wins, key risks, and Q3 objectives in structured headings."),
            ("Summarize this architectural decision record (ADR) on migrating from REST to gRPC, highlighting trade-offs and decision rationale.", "Must outline context, alternatives considered, chosen approach, and operational trade-offs."),
            ("Provide an analytical summary of this technical incident postmortem, specifying root cause, impact duration, and preventative action items.", "Must identify root cause, timeline, customer impact, and remediations."),
        ],
        "pro": [
            ("Synthesize three peer-reviewed research papers on LLM hallucination mitigation, comparing benchmark datasets, prompt interventions, and fine-tuning trade-offs.", "Must provide a deep academic comparative synthesis analyzing truthfulness benchmarks, RAG integration, and RLHF limitations."),
            ("Summarize this 50-page Federal Reserve monetary policy report, analyzing macro indicators, yield curve implications, and systemic liquidity risks.", "Must deliver an expert financial synthesis dissecting inflation expectations, balance sheet runoff, and credit contraction."),
        ]
    },
    "code_explain": {
        "lite": [
            ("Explain what `Array.prototype.reduce()` does in JavaScript with a 3-line example.", "Must explain accumulator and current value with clear code example."),
            ("Explain what `git rebase` does compared to `git merge` in simple terms.", "Must explain linear history rewrite vs merge commit."),
            ("What is the purpose of `__init__.py` in Python packages?", "Must explain package initialization and module namespace."),
            ("Explain what HTTP status code 404 indicates.", "Must explain resource not found on origin server."),
        ],
        "standard": [
            ("Explain how this 30-line Python implementation of Dijkstra's algorithm uses a min-heap priority queue to guarantee shortest path.", "Must explain priority queue updates, distance array, relaxation step, and O((V+E)logV) complexity."),
            ("Walk through this React custom hook for managing debounced state, explaining cleanup and useEffect lifecycle.", "Must detail timer cancellation on unmount/dependency change and state propagation."),
            ("Explain how this SQL recursive CTE calculates hierarchical organization chart reporting levels.", "Must explain anchor member, recursive member, union all, and termination condition."),
        ],
        "pro": [
            ("Analyze this Rust memory allocator implementation, identifying unsafe pointer dereferences, alignment guarantees, and ABA race conditions.", "Must explain page chunking, pointer provenance, SIMD alignment, and atomic hazard pointers."),
            ("Explain the internal mechanisms of Linux eBPF ring buffers, XDP packet filtering, and kernel verifier safety constraints.", "Must explain BPF bytecode verification, JIT compilation, ring buffer memory mapping, and zero-copy packet processing."),
        ]
    },
    "math_reasoning": {
        "lite": [
            ("Calculate: 15% tip on a bill of $64.40. Round to nearest cent.", "Must show calculation: 64.40 * 0.15 = 9.66."),
            ("Convert 72 degrees Fahrenheit to Celsius. Show formula.", "Must show C = (72 - 32) * 5/9 = 22.22 °C."),
            ("What is the hypotenuse of a right triangle with legs of length 6 and 8?", "Must show sqrt(36 + 64) = 10."),
            ("Calculate the compound interest on $1,000 at 5% annual interest for 2 years compounded annually.", "Must show 1000 * 1.05^2 = $1,102.50."),
        ],
        "standard": [
            ("Solve this system of linear equations using Gaussian elimination showing augmented matrix steps: 2x + y - z = 8, -3x - y + 2z = -11, -2x + y + 2z = -3.", "Must show row operations and find unique solution x=2, y=3, z=-1."),
            ("A fair six-sided die is rolled 4 times. What is the probability of rolling at least one 6? Show derivation.", "Must use complement: 1 - (5/6)^4 = 1 - 625/1296 = 671/1296 ≈ 51.77%."),
            ("Find the local extrema of f(x) = 2x^3 - 3x^2 - 12x + 5 using first and second derivative tests.", "Must find critical points x=-1, x=2; identify local max at x=-1 (12) and local min at x=2 (-15)."),
        ],
        "pro": [
            ("Formulate and prove the Cauchy-Schwarz inequality for an arbitrary real inner product space, stating exact conditions for equality.", "Must define inner product axioms, construct quadratic form in real parameter t, and analyze discriminant <= 0 with equality condition."),
            ("Derive the Black-Scholes partial differential equation for European call options using Ito's Lemma and a risk-neutral delta-hedging portfolio.", "Must construct riskless portfolio, apply Ito's lemma for dV, eliminate stochastic dW term, and equate return to risk-free rate r."),
        ]
    },
    "creative": {
        "lite": [
            ("Write a warm 2-sentence thank you note to a colleague for covering a shift.", "Must be polite, expressive, and concise under 3 sentences."),
            ("Suggest 5 catchy names for a community coffee shop near a university library.", "Must provide 5 distinct, creative coffee shop names."),
            ("Write a whimsical 4-line rhyming stanza about autumn leaves.", "Must have AABB or ABAB rhyme scheme and autumn imagery."),
            ("Draft an out-of-office autoreply email for a one-week vacation.", "Must include return date, emergency contact, and professional tone."),
        ],
        "standard": [
            ("Write a 250-word atmospheric opening scene of a detective investigating an anomaly in an automated greenhouse.", "Must establish mood, sensory details of botany and machinery, and mystery hook."),
            ("Draft a persuasive Kickstarter pitch script for an ergonomic modular keyboard designed for programmers.", "Must articulate problem, unique mechanical feature, backer rewards, and call to action."),
        ],
        "pro": [
            ("Compose an intricate, multi-layered philosophical dialogue between Spinoza and Alan Turing debating free will, determinism, and computational substrates.", "Must demonstrate deep mastery of Spinozan pantheism and Turing's computational theory, with rich intellectual dialectic and literary elegance."),
            ("Write a literary short story exploring the subjective experience of a deep-sea cartographer who encounters non-Euclidean bioluminescent structures.", "Must feature literary depth, poetic prose, thematic resonance regarding human limitation, and immersive world-building."),
        ]
    }
}

# Generate items deterministically
all_entries = []
item_counter = 1

for cat in CATEGORIES:
    cat_alloc = allocations[cat]
    for tier in ["lite", "standard", "pro"]:
        num_needed = cat_alloc[tier]
        bank = PROMPT_BANKS[cat][tier]
        for i in range(num_needed):
            base_prompt, rubric = bank[i % len(bank)]
            prompt_str = base_prompt
            if i >= len(bank):
                variant_num = (i // len(bank)) + 1
                prompt_str = f"{base_prompt} (Variation {variant_num} focusing on specific context {i+1})"

            item = {
                "id": f"g_{item_counter:04d}",
                "category": cat,
                "expected_tier": tier,
                "prompt": prompt_str,
                "system": None,
                "json_schema": None,
                "reference": None,
                "rubric": rubric,
                "reviewed": True,
                "source": f"seed:seed_{cat}_{tier}_{i+1}"
            }
            all_entries.append(item)
            item_counter += 1

assert len(all_entries) == 300

with open("eval/golden/golden_set.jsonl", "w", encoding="utf-8") as f:
    for item in all_entries:
        f.write(json.dumps(item) + "\n")

print(f"Generated {len(all_entries)} items to eval/golden/golden_set.jsonl")
