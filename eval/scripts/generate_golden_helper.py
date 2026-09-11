#!/usr/bin/env python3
"""Generate eval/golden/golden_set.jsonl from the hand-authored prompt bank below.

Every item is written out by hand: no templated padding, no "(Variation N)" suffixes.
Prompts that need source material (a rubric, a handbook excerpt, code, a passage)
carry it inline so the gateway and the judge see a self-contained task. Items with a
crisp expected answer also carry a `reference` for the judge.

Allocation per category (lite / standard / pro) is chosen to keep the validator's
40 / 35 / 25 tier split and at least 30 items per category:

    rubric_parse    12 / 18 /  8  = 38
    diagram_gen     15 / 15 /  8  = 38
    doc_qa          18 / 12 /  8  = 38
    classify        22 / 12 /  4  = 38
    summarize       17 / 13 /  7  = 37
    code_explain    11 / 14 / 12  = 37
    math_reasoning  14 / 13 / 10  = 37
    creative        11 /  8 / 18  = 37
                   120 /105 / 75  = 300

Run from the repo root:  python3 eval/scripts/generate_golden_helper.py
"""

import json
import os
import sys
from typing import Dict, List, Optional, Tuple

Item = Tuple[str, str, Optional[str]]  # (prompt, rubric, reference)

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
TIERS = ["lite", "standard", "pro"]

ALLOCATIONS: Dict[str, Dict[str, int]] = {
    "rubric_parse": {"lite": 12, "standard": 18, "pro": 8},
    "diagram_gen": {"lite": 15, "standard": 15, "pro": 8},
    "doc_qa": {"lite": 18, "standard": 12, "pro": 8},
    "classify": {"lite": 22, "standard": 12, "pro": 4},
    "summarize": {"lite": 17, "standard": 13, "pro": 7},
    "code_explain": {"lite": 11, "standard": 14, "pro": 12},
    "math_reasoning": {"lite": 14, "standard": 13, "pro": 10},
    "creative": {"lite": 11, "standard": 8, "pro": 18},
}


def _i(prompt: str, rubric: str, reference: Optional[str] = None) -> Item:
    return (prompt.strip(), rubric.strip(), reference.strip() if reference else None)


# ---------------------------------------------------------------------------
# rubric_parse
# ---------------------------------------------------------------------------

RUBRIC_PARSE_LITE: List[Item] = [
    _i("Rubric: 'Persuasive Essay Rubric (Total: 20 points). Thesis 5 pts, Evidence 5 pts, Organization 5 pts, Conventions 5 pts.' List the criteria names and the total points.",
       "Must list Thesis, Evidence, Organization, and Conventions and state that the total is 20 points.",
       "Criteria: Thesis, Evidence, Organization, Conventions. Total: 20 points."),
    _i("Rubric excerpt: 'Performance levels: Beginning (1), Developing (2), Proficient (3), Exemplary (4).' How many performance levels are defined, and what is the top level called?",
       "Must answer four levels and name Exemplary as the top level.",
       "Four levels; the top level is Exemplary."),
    _i("From this rubric line, what percentage is grammar worth? 'Content 40%, Organization 30%, Grammar and Mechanics 20%, Citations 10%.'",
       "Must answer 20%.", "20%"),
    _i("Rubric: 'Lab Report. Hypothesis (2 pts), Method (3 pts), Data Tables (3 pts), Analysis (4 pts), Conclusion (3 pts).' Which criterion is worth the most points?",
       "Must identify Analysis at 4 points.", "Analysis (4 points)"),
    _i("Rubric table header: '| Criterion | Excellent | Good | Needs Work |'. List the column headers in order as a numbered list.",
       "Must list exactly Criterion, Excellent, Good, Needs Work in that order.",
       "1. Criterion 2. Excellent 3. Good 4. Needs Work"),
    _i("Convert this rubric into a two-column Markdown table with columns Criterion and Points: 'Presentation 10, Visual Aids 5, Q&A 5.'",
       "Must produce a valid Markdown table with a header row and three data rows with the correct point values."),
    _i("Rubric: 'Reading Response. Summary 3 pts, Personal Connection 3 pts, Text Evidence 4 pts.' What is the maximum total score?",
       "Must answer 10.", "10"),
    _i("Rubric: 'Speech. Eye Contact, Volume, Pacing, and Content are each scored 1 to 5.' What is the maximum total score, and how many criteria are there?",
       "Must answer 20 points across four criteria.", "Four criteria; maximum 20 points."),
    _i("Rubric row: 'Homework Completion. 4: all problems attempted. 3: most problems attempted. 2: about half attempted. 1: few or none attempted.' What score does a student receive who attempted about half of the problems?",
       "Must answer 2.", "2"),
    _i("Rubric snippet: 'Criterion: Citations. Descriptor: Uses MLA format and cites at least three sources.' Rewrite the requirement as two yes/no checklist questions.",
       "Must produce two questions, one about MLA format and one about a minimum of three sources.",
       "Is MLA format used? Are at least three sources cited?"),
    _i("Rubric: 'Math Problem Set. Accuracy 60%, Work Shown 30%, Neatness 10%.' Return the weights as a JSON object keyed by criterion with numeric percentage values.",
       "Must return valid JSON with keys Accuracy, Work Shown, and Neatness mapped to 60, 30, and 10.",
       '{"Accuracy": 60, "Work Shown": 30, "Neatness": 10}'),
    _i("Rubric: 'Group Project. Collaboration (5 pts), Research (5 pts), Product (10 pts).' Which criterion counts for half of the total grade?",
       "Must answer Product, and may note that 10 of 20 points is half.", "Product"),
]

RUBRIC_PARSE_STANDARD: List[Item] = [
    _i("""Convert this rubric into JSON with an array of criteria, each having name, points, and a levels object mapping score to descriptor: 'Argumentative Essay. Claim (4: clear and arguable; 3: clear; 2: vague; 1: missing). Evidence (4: three or more cited sources; 3: two sources; 2: one source; 1: none). Organization (4: logical with transitions; 3: logical; 2: some order; 1: no order).'""",
       "Must return valid JSON with exactly three criteria, each with four levels (4 through 1) and descriptor text matching the source."),
    _i("""Parse this pasted LMS text into a structured rubric listing each dimension with its performance levels and point values: 'Students will be assessed on: (a) Understanding of concepts - excellent/good/fair/poor; (b) Application to real-world problems - excellent/good/fair/poor; (c) Communication clarity - excellent/good/fair/poor. Each dimension is worth 10 points, where poor = 4, fair = 6, good = 8, excellent = 10.'""",
       "Must list three dimensions, each with four levels and the point mapping 4/6/8/10, and state a maximum of 30 points."),
    _i("""Parse this AP History DBQ rubric into a JSON array of objects with criterion, points, and requirement: 'Thesis (1 pt): historically defensible claim. Contextualization (1 pt): situates the argument in broader historical context. Document evidence (2 pts): uses at least six documents to support the argument. Outside evidence (1 pt): one additional piece of specific evidence. Sourcing (1 pt): explains point of view, purpose, or audience for at least three documents. Complexity (1 pt): demonstrates a nuanced understanding.'""",
       "Must return valid JSON with six criteria, correct point values summing to 7, and the requirement text for each."),
    _i("""Convert this lab report rubric into a JSON object where each section has max_points and a list of required elements: 'Abstract (5): purpose, method, key result. Hypothesis (5): testable, references variables. Methodology (10): materials, procedure, controls. Results (15): tables, graphs with labeled axes, units. Discussion (15): interpretation, error sources, connection to hypothesis.'""",
       "Must return valid JSON with five sections, correct max points (5, 5, 10, 15, 15), and the required elements split into list items."),
    _i("""Extract the dimensions, performance indicators, and point ranges from this debate rubric into JSON with min and max fields: 'Argumentation (0-10): claims supported by evidence. Cross-examination (0-5): asks probing, relevant questions. Rebuttal (0-10): directly addresses opponent points. Delivery (0-5): clear and confident speaking.'""",
       "Must return JSON with four dimensions, min 0 and max 10/5/10/5 respectively, and the indicator text."),
    _i("""Parse this computer science project rubric into JSON with name, weight_percent, and description per criterion: 'Code Quality 30% - readable, idiomatic, no duplicated logic. Documentation 20% - README with setup and usage. Test Coverage 20% - unit tests for core logic, at least 80% line coverage. Functionality 30% - all listed features work end to end.'""",
       "Must return four criteria with weights 30/20/20/30 summing to 100 and descriptions preserved."),
    _i("""This rubric mixes points and percentages on a 100-point scale. Normalize every criterion to a percentage of the total: 'Quiz average 20 pts, Midterm 30%, Final project 40 pts, Participation 10%.'""",
       "Must report Quiz 20%, Midterm 30%, Final project 40%, Participation 10%, and note that they sum to 100%.",
       "Quiz average 20%, Midterm 30%, Final project 40%, Participation 10% (total 100%)."),
    _i("""Identify any inconsistency in this rubric and state what the total should be: 'Total 50 points. Introduction 10, Body 25, Conclusion 10, Works Cited 10.'""",
       "Must point out that the criteria sum to 55, not the stated 50, and identify the mismatch.",
       "The criteria sum to 55 points, but the rubric claims a 50-point total."),
    _i("""Rewrite this holistic rubric as an analytic rubric with three criteria (Content, Structure, Language) and four levels (4 to 1): 'Score 4: insightful ideas, well organized, precise language. 3: clear ideas, mostly organized, generally correct language. 2: basic ideas, weak organization, frequent errors. 1: unclear ideas, no organization, errors impede meaning.'""",
       "Must produce a 3 by 4 grid where each cell contains the matching descriptor fragment from the holistic version."),
    _i("""Extract only the Proficient-level descriptors from this rubric: 'Thesis - Exemplary: original and precise; Proficient: clear and arguable; Developing: present but vague. Evidence - Exemplary: multiple well-integrated sources; Proficient: relevant sources cited; Developing: few or unrelated sources. Style - Exemplary: distinctive voice; Proficient: appropriate tone; Developing: inconsistent tone.'""",
       "Must return exactly three descriptors: clear and arguable; relevant sources cited; appropriate tone.",
       "Thesis: clear and arguable. Evidence: relevant sources cited. Style: appropriate tone."),
    _i("""Convert this narrative rubric into a checklist of observable behaviors: 'A proficient collaborator shares work equally, listens without interrupting, gives specific feedback, and meets agreed deadlines.'""",
       "Must produce four checklist items, one per behavior, phrased as observable actions.",
       "Shares work equally. Listens without interrupting. Gives specific feedback. Meets agreed deadlines."),
    _i("""Map this 6-trait writing rubric to a total score and express each trait's weight as a percentage in JSON: traits Ideas, Organization, Voice, Word Choice, Sentence Fluency, and Conventions, each scored 1 to 5.""",
       "Must state a 30-point maximum and return JSON with six traits at roughly 16.67% each.",
       "Maximum 30 points; each trait is worth 5 points, or about 16.67%."),
    _i("""Compute the weighted grade from this rubric and these scores: 'Content 50%, Delivery 30%, Visuals 20%. Scores: Content 8/10, Delivery 6/10, Visuals 10/10.' Show the arithmetic.""",
       "Must compute 0.5*80 + 0.3*60 + 0.2*100 = 40 + 18 + 20 = 78% and show the steps.",
       "78%"),
    _i("""One criterion in this rubric has no level-2 descriptor. Identify it and propose a descriptor consistent with the pattern: 'Analysis - 4: evaluates evidence critically; 3: explains evidence; 2: (missing); 1: lists evidence without explanation. Clarity - 4: precise; 3: clear; 2: mostly clear; 1: unclear.'""",
       "Must identify Analysis level 2 as missing and propose something between explaining and merely listing, such as 'describes evidence with limited explanation'."),
    _i("""Parse this science fair rubric into JSON with criterion, max_points, and a boolean written_component: 'Question (5), Hypothesis (5), Procedure (10, written), Data (10, written), Conclusion (10, written), Display Board (10), Interview (10).'""",
       "Must return seven entries with correct points, written_component true for Procedure, Data, and Conclusion, and false otherwise."),
    _i("""Turn this rubric table, given as text, into JSON: 'Criterion | Weight | 3 | 2 | 1. Accuracy | 50% | all facts correct | one error | multiple errors. Depth | 30% | explains causes | describes events | lists events. Sources | 20% | 3+ cited | 1-2 cited | none.'""",
       "Must return three criteria with weights 50/30/20 and three level descriptors each, keyed by 3, 2, and 1."),
    _i("""Translate this rubric into student-friendly 'I can' statements, one per criterion: 'Claim: states a clear position. Reasons: gives two reasons. Evidence: supports each reason with a fact. Counterclaim: acknowledges an opposing view.'""",
       "Must produce four 'I can' statements that preserve the requirement in each criterion, including 'two reasons'.",
       "I can state a clear position. I can give two reasons. I can support each reason with a fact. I can acknowledge an opposing view."),
    _i("""Given this rubric, list which criteria a submission fails when it has a thesis, cites one source, and is 350 words: 'Thesis present (required). At least two sources (required). Length 400-600 words (required). Title page (optional).'""",
       "Must state the submission fails the sources requirement and the length requirement, passes thesis, and that the title page is optional.",
       "Fails: at least two sources; length 400-600 words. Passes: thesis. Title page is optional."),
]

RUBRIC_PARSE_PRO: List[Item] = [
    _i("""Two departments grade the same capstone. Engineering rubric: Technical Depth 50%, Testing 30%, Documentation 20%. Communications rubric: Clarity 40%, Audience Awareness 30%, Visual Design 30%. Design a single unified rubric with five performance levels that preserves each department's priorities, specify a rule for the case where engineering scores a project 5 and communications scores it 2, and justify the final weightings.""",
       "Must produce a unified matrix with five levels covering all six criteria, an explicit arbitration rule for divergent scores, and a written justification of the weights."),
    _i("""Audit this state writing rubric descriptor for ambiguity and potential bias, then rewrite it: 'Level 4: Uses sophisticated, academic vocabulary appropriate for an educated audience. Level 2: Uses simple or everyday language.' Explain how the original could disadvantage multilingual learners and propose observable, language-neutral criteria.""",
       "Must name the ambiguous terms (sophisticated, educated audience), explain the equity risk for multilingual learners, and provide a rewrite based on observable features such as precision or task-appropriate word choice."),
    _i("""Design a scoring model for this ABET-style outcome with calibration anchors: 'Outcome 3: An ability to communicate effectively with a range of audiences.' Provide four levels, a short exemplar for each level, and a procedure for resolving disagreement between two raters who differ by more than one level.""",
       "Must provide four levels with distinct exemplars and a concrete rater-adjudication procedure such as a third rater or calibration discussion."),
    _i("""Create a competency rubric that distinguishes senior engineer, staff engineer, and principal engineer across five axes: scope, technical judgment, influence, handling ambiguity, and mentorship. Every cell must contain an observable behavior, not an adjective.""",
       "Must produce a 5 by 3 grid where each cell describes observable behavior and the progression across levels is clear."),
    _i("""Construct a formal argument for why this rubric cannot produce reliable inter-rater agreement, then repair it: 'Creativity: 10 pts, awarded based on how creative the grader feels the work is. Effort: 10 pts, awarded based on apparent effort.'""",
       "Must argue that both criteria rely on unobservable grader impressions, and provide a repaired rubric with observable indicators for each."),
    _i("""Merge these three overlapping data-science project rubrics into one without double counting: A: Data Cleaning 20, Modeling 40, Reporting 40. B: Reproducibility 30, Modeling 30, Ethics 20, Reporting 20. C: Code Quality 50, Communication 50. Produce final weights summing to 100 and explain each merge decision.""",
       "Must produce weights that sum to 100, explicitly map overlapping criteria (Reporting/Communication, Code Quality/Reproducibility), and justify each decision."),
    _i("""Convert this rubric into a machine-gradable specification. For each criterion define the input artifact, an automated check, and what still requires human judgment: 'Unit tests present and passing. README explains setup. API is documented. Code follows PEP 8. Design decisions are justified.'""",
       "Must cover all five criteria, propose a realistic automated check for each, and identify which parts remain human-judged (for example, design justification)."),
    _i("""Analyze this rubric for construct validity against the stated learning objective and propose a revision: Objective: 'Students can evaluate the credibility of online sources.' Rubric: 'Uses five sources (5 pts). Sources cited in APA (5 pts). Paper is three pages (5 pts).'""",
       "Must explain that none of the criteria measure evaluation of credibility, and propose criteria that do, such as assessing author expertise, publication date, or bias."),
]

# ---------------------------------------------------------------------------
# diagram_gen
# ---------------------------------------------------------------------------

DIAGRAM_GEN_LITE: List[Item] = [
    _i("Generate a 3-node Mermaid.js flowchart showing a user logging in: User, Login Form, Dashboard.",
       "Must be a valid Mermaid flowchart with three nodes connected in order User -> Login Form -> Dashboard."),
    _i("Create a Mermaid.js sequence diagram of a simple client-server request and response.",
       "Must be a valid Mermaid sequenceDiagram with Client -> Server request and Server -> Client response."),
    _i("Generate a Mermaid flowchart showing a single IF/THEN decision gate with a yes branch and a no branch.",
       "Must be a valid Mermaid flowchart with a diamond decision node and two labeled branches."),
    _i("Create a 4-step Mermaid diagram of a git feature-branch workflow: branch from main, commit, open pull request, merge.",
       "Must be a valid Mermaid gitGraph or flowchart showing branch, commit, pull request, and merge."),
    _i("Generate a Mermaid flowchart with four sequential steps: Write, Review, Revise, Publish.",
       "Must be a valid Mermaid flowchart with the four steps connected in order."),
    _i("Create a Mermaid pie chart of a monthly budget: Rent 50%, Food 30%, Savings 20%.",
       "Must be a valid Mermaid pie chart with three slices and the correct values."),
    _i("Create a Mermaid sequence diagram of a student submitting homework to a teacher and receiving a grade.",
       "Must be a valid sequenceDiagram with Student and Teacher participants, a submission message, and a grade message back."),
    _i("Generate a Mermaid flowchart of a traffic light cycle: Green to Yellow to Red and back to Green.",
       "Must be a valid flowchart with three nodes forming a cycle."),
    _i("Create a Mermaid mindmap with the root 'Study Plan' and three children: Reading, Practice, Review.",
       "Must be a valid Mermaid mindmap with one root and exactly three child nodes."),
    _i("Generate a Mermaid flowchart of making a cup of tea: boil water, steep tea bag, add milk, serve.",
       "Must be a valid flowchart with the four steps in order."),
    _i("Create a Mermaid sequence diagram for a password reset: user requests a reset, server emails a link, user sets a new password.",
       "Must be a valid sequenceDiagram with User and Server and the three messages in order."),
    _i("Generate a Mermaid flowchart with a loop: Start, Check Inventory, if empty then Reorder and return to Check Inventory, otherwise Ship.",
       "Must be a valid flowchart with a decision node, a loop edge back to Check Inventory, and a Ship exit."),
    _i("Create a Mermaid stateDiagram for a light switch with the states Off and On and transitions between them.",
       "Must be a valid stateDiagram-v2 with two states and transitions in both directions."),
    _i("Generate a Mermaid flowchart with two parallel branches from 'Order Received', 'Charge Card' and 'Reserve Stock', both joining at 'Confirm Order'.",
       "Must be a valid flowchart with a fork into two branches that rejoin at a single node."),
    _i("Create a Mermaid timeline of a school day: 8am Homeroom, 9am Math, 11am Lunch, 1pm Science, 3pm Dismissal.",
       "Must be a valid Mermaid timeline with the five entries in chronological order."),
]

DIAGRAM_GEN_STANDARD: List[Item] = [
    _i("Generate a Mermaid.js diagram of a pub/sub event pipeline with a publisher, a topic, two Cloud Run worker subscribers, a Firestore database written by the workers, and a dead-letter queue for failed messages.",
       "Must be a valid Mermaid flowchart including publisher, topic, two workers, Firestore, and a dead-letter path from the workers."),
    _i("Generate a Mermaid.js architecture diagram of a FastAPI backend on Cloud Run that reads and writes Firestore and publishes to Pub/Sub, using a subgraph for each Google Cloud service.",
       "Must use subgraphs for Cloud Run, Firestore, and Pub/Sub with labeled edges for read/write and publish."),
    _i("Generate a Mermaid class diagram for an e-commerce shopping cart domain: Cart, CartItem, Product, and Order, with attributes and associations.",
       "Must be a valid classDiagram with the four classes, at least two attributes each, and associations such as Cart contains CartItem and CartItem references Product."),
    _i("Create a Mermaid ER diagram for a learning management system with Student, Course, Enrollment, Assignment, and Submission entities and their relationships.",
       "Must be a valid erDiagram with five entities and cardinalities where Enrollment links Student and Course and Submission links Student and Assignment."),
    _i("Create a Mermaid sequence diagram of the OAuth 2.0 authorization code flow with Browser, Client App, Authorization Server, and Resource Server, including the redirect, code exchange, and resource request.",
       "Must show the redirect to the authorization server, the code returned to the client, the token exchange, and the bearer-token resource request in order."),
    _i("Generate a Mermaid flowchart of a CI/CD pipeline: lint, unit tests, build image, push to registry, deploy to staging, manual approval, deploy to production, with a failure path from each check back to the developer.",
       "Must include all seven stages in order, a manual approval gate, and failure edges back to a developer node."),
    _i("Create a Mermaid stateDiagram for an order lifecycle with states Created, Paid, Packed, Shipped, Delivered, Cancelled, and Refunded, allowing cancellation only before shipping and refunds only after payment.",
       "Must be a valid stateDiagram-v2 with the seven states and transitions that respect both constraints."),
    _i("Generate a Mermaid diagram of a three-tier web application: a load balancer, two application servers, a primary database, and a read replica, using a subgraph per tier and showing replication.",
       "Must have three subgraphs (web, app, data), two app servers behind the load balancer, and a replication edge from primary to replica."),
    _i("Create a Mermaid class diagram for a library system with Member, Book, Loan, and Librarian, including multiplicity on each association.",
       "Must be a valid classDiagram with the four classes and multiplicities such as Member 1 to many Loan and Loan to exactly one Book."),
    _i("Generate a Mermaid sequence diagram of a cache-aside read: the app checks Redis, on a miss reads Postgres, then writes the value back to Redis with a TTL, with an alt block for hit and miss.",
       "Must use an alt block distinguishing hit and miss, show the Postgres read only on miss, and show the write-back with TTL."),
    _i("Create a Mermaid ER diagram for a clinic with Patient, Doctor, Appointment, Prescription, and Medication, with cardinalities.",
       "Must be a valid erDiagram where Appointment links Patient and Doctor and Prescription links Appointment and Medication with correct cardinalities."),
    _i("Generate a Mermaid flowchart for a student grade appeal process with three decision points, 'deadline met?', 'evidence provided?', and 'committee agrees?', each with a rejection outcome and a final 'grade changed' outcome.",
       "Must contain three diamond decisions in sequence, rejection edges from each, and a single success terminal."),
    _i("Create a Mermaid gantt chart for a six-week software project with phases Design (weeks 1-2), Build (weeks 2-4), Test (weeks 4-5), and Launch (week 6), with dates in 2026.",
       "Must be a valid Mermaid gantt with four tasks whose date ranges overlap as specified."),
    _i("Generate a Mermaid diagram of an event-driven microservice architecture with an API gateway, order service, inventory service, message broker, and notification service. Use solid arrows for synchronous calls and dotted arrows for asynchronous messages.",
       "Must include all five components and visibly distinguish sync from async edges using different arrow styles."),
    _i("Create a Mermaid sequence diagram of a WebSocket chat: a client connects, the server authenticates it, the client sends a message, the server broadcasts to two other clients, and the client disconnects.",
       "Must show connect, authenticate, send, broadcast to two other participants, and disconnect in order."),
]

DIAGRAM_GEN_PRO: List[Item] = [
    _i("Create an exhaustive Mermaid.js sequence diagram of a distributed saga for e-commerce checkout across Order, Payment, Inventory, and Shipping services, including a payment failure that triggers inventory compensation and an order cancellation.",
       "Must show the happy path across four services plus a failure branch with explicit compensating actions in reverse order."),
    _i("Create a Mermaid sequence diagram of Raft leader election and log replication, including a follower election timeout, a split vote with a term increment, the winning election, and replication of one log entry with commit acknowledgement.",
       "Must show timeout, RequestVote with terms, a split-vote retry, AppendEntries replication, and the commit index advancing."),
    _i("Generate a Mermaid diagram of a multi-region active-active deployment with global load balancing, a Kubernetes cluster per region, cross-region database replication with conflict resolution, and a failover path. Annotate edges with the consistency guarantee each provides.",
       "Must include at least two regions, replication with a named conflict-resolution strategy, a failover edge, and consistency annotations on edges."),
    _i("Create a Mermaid stateDiagram of the TCP connection lifecycle including the three-way handshake, ESTABLISHED, the four-way termination, TIME_WAIT, and the simultaneous-close path.",
       "Must include LISTEN, SYN_SENT, SYN_RECEIVED, ESTABLISHED, FIN_WAIT_1, FIN_WAIT_2, CLOSE_WAIT, CLOSING, LAST_ACK, TIME_WAIT, and CLOSED with correct transitions."),
    _i("Generate a Mermaid sequence diagram of a zero-downtime schema migration using the expand/contract pattern: add the new column, enable dual writes, backfill, verify, cut reads over, and drop the old column, with a rollback branch after verification fails.",
       "Must show each expand/contract stage in order and an alt branch where verification fails and dual writes are reverted."),
    _i("Design a Mermaid C4-style container diagram for an LLM routing gateway with a rate limiter, a semantic cache, a tier router, a cost ledger, three model tiers, and an evaluation harness. Annotate each container with its primary failure mode.",
       "Must include all seven containers, connections that reflect request flow, and a failure-mode note on every container."),
    _i("Create a Mermaid flowchart of a Kubernetes pod scheduling decision covering node affinity, taints and tolerations, resource requests, preemption, and the unschedulable outcome.",
       "Must model the filtering steps as decisions in a sensible order and include both a scheduled outcome and an unschedulable/pending outcome with preemption considered."),
    _i("Generate a Mermaid sequence diagram of a two-phase commit across a coordinator and three participants, showing the commit path and, in an alt block, a participant failing during the prepare phase with the resulting abort and timeouts.",
       "Must show prepare and commit phases for all three participants, and an alt branch where one participant fails to vote and the coordinator aborts."),
]

# ---------------------------------------------------------------------------
# doc_qa
# ---------------------------------------------------------------------------

DOC_QA_LITE: List[Item] = [
    _i("Handbook excerpt: 'Students may have up to three excused tardies per semester. A fourth tardy results in a lunch detention.' How many excused tardies are allowed per semester?",
       "Must answer three.", "Three"),
    _i("Handbook excerpt: 'Grade appeals must be submitted in writing within 10 school days of the grade being posted.' What is the deadline for filing a grade appeal?",
       "Must answer within 10 school days of the grade being posted.", "Within 10 school days of the grade being posted"),
    _i("Handbook excerpt: 'Laboratory sessions require closed-toe shoes, a lab coat, and safety goggles.' What must students wear during lab sessions?",
       "Must list closed-toe shoes, a lab coat, and safety goggles.", "Closed-toe shoes, a lab coat, and safety goggles"),
    _i("Handbook excerpt: 'Lost student IDs can be replaced at the Student Services desk for a $5 fee.' Where do students replace a lost ID, and what does it cost?",
       "Must answer the Student Services desk and $5.", "Student Services desk; $5"),
    _i("Handbook excerpt: 'The library is open 7:30 a.m. to 4:30 p.m. Monday through Thursday and closes at 3:00 p.m. on Fridays.' When does the library close on Friday?",
       "Must answer 3:00 p.m.", "3:00 p.m."),
    _i("Handbook excerpt: 'Cell phones must be silenced and stored in backpacks during instructional time.' Where should phones be kept during class?",
       "Must answer in backpacks, silenced.", "Silenced and stored in backpacks"),
    _i("Handbook excerpt: 'Parking permits cost $40 per year and are available to juniors and seniors only.' Can a sophomore buy a parking permit?",
       "Must answer no, permits are limited to juniors and seniors.", "No"),
    _i("Handbook excerpt: 'Makeup exams are offered only with a doctor's note or prior approval from the principal.' Name the two ways a student can qualify for a makeup exam.",
       "Must list a doctor's note and prior principal approval.", "A doctor's note, or prior approval from the principal"),
    _i("Handbook excerpt: 'Club meetings end no later than 5:00 p.m. unless a faculty advisor is present.' What is the latest a club can meet without an advisor present?",
       "Must answer 5:00 p.m.", "5:00 p.m."),
    _i("Handbook excerpt: 'Final grades are weighted: quarter 1 40%, quarter 2 40%, final exam 20%.' What percent of the final grade is the exam?",
       "Must answer 20%.", "20%"),
    _i("Handbook excerpt: 'Visitors must sign in at the front office and wear a visitor badge at all times.' What two things must visitors do?",
       "Must answer sign in at the front office and wear a visitor badge.", "Sign in at the front office and wear a visitor badge"),
    _i("Handbook excerpt: 'The dress code prohibits hats indoors except for religious head coverings.' Are religious head coverings allowed indoors?",
       "Must answer yes.", "Yes"),
    _i("Handbook excerpt: 'Bus passes are issued in September. Replacement passes cost $10.' What is the cost of a replacement bus pass?",
       "Must answer $10.", "$10"),
    _i("Handbook excerpt: 'The nurse's office is located in Room 112, next to the main gym.' What room is the nurse's office in?",
       "Must answer Room 112.", "Room 112"),
    _i("Handbook excerpt: 'Students must maintain a 2.0 GPA to participate in athletics.' What is the minimum GPA required for athletics?",
       "Must answer 2.0.", "2.0"),
    _i("Handbook excerpt: 'Report cards are mailed home one week after each quarter ends.' When are report cards mailed?",
       "Must answer one week after each quarter ends.", "One week after each quarter ends"),
    _i("Handbook excerpt: 'Lockers are assigned in homeroom and may not be shared.' Can two students share a locker?",
       "Must answer no.", "No"),
    _i("Handbook excerpt: 'Early dismissal requires a signed note from a parent or guardian delivered to the attendance office before first period.' Where and by when must the note be delivered?",
       "Must answer the attendance office, before first period.", "To the attendance office before first period"),
]

DOC_QA_STANDARD: List[Item] = [
    _i("""Section 4.2: 'A suspension for an academic integrity violation lasts three school days.' Section 7.1: 'Students serving a suspension are ineligible for athletic competition for the duration of the suspension and the following two competition dates.' A student is suspended Monday through Wednesday under 4.2 and has games Wednesday, Friday, and the next Tuesday. Which of those games can the student play, and why?""",
       "Must conclude the student misses all three games: Wednesday during the suspension, then Friday and Tuesday as the two following competition dates, citing both sections.",
       "None of the three. Wednesday falls within the suspension; Friday and Tuesday are the two competition dates that follow it."),
    _i("""Attendance policy: 'Unexcused absences result in a zero for any work missed. Excused absences allow makeup work within five school days.' Extra credit policy: 'Extra credit is available only to students with no unexcused absences in the quarter.' A student had one unexcused absence in September and an excused absence in October. Can they earn extra credit this quarter, and can they make up the October work?""",
       "Must answer no extra credit because of the September unexcused absence, and yes to makeup work for October within five school days.",
       "No extra credit this quarter; yes, the October work can be made up within five school days."),
    _i("""Section 2: 'Late homework loses 10% per school day late, up to a maximum of 50%.' Section 5: 'Work due during an excused absence is due the day the student returns without penalty.' A student is excused Monday and Tuesday, returns Wednesday, and submits Monday's homework on Thursday. What penalty applies?""",
       "Must reason that the work was due Wednesday on return and is one day late, so 10%.",
       "10% (one school day late; the due date moved to Wednesday)."),
    _i("""Excerpt A: 'Honor roll requires all letter grades of B or higher.' Excerpt B: 'Pass/fail courses are excluded from GPA and honor roll calculations.' A student earned A, A, B, B and a Pass in physical education. Does the student qualify for honor roll?""",
       "Must answer yes, because the Pass is excluded and every letter grade is B or higher.", "Yes"),
    _i("""Faculty handbook: 'First academic dishonesty offense: zero on the assignment and parent notification. Second offense: referral to the dean and disciplinary probation. Third offense: recommendation for expulsion. Offense counts reset only at graduation.' A student was caught once last year and twice this year. Describe the consequence of the most recent incident.""",
       "Must identify the most recent incident as the third offense and state the recommendation for expulsion, noting that counts carry across years.",
       "It is the third offense, so the consequence is a recommendation for expulsion."),
    _i("""Chapter 4 course substitution petitions require: a syllabus review by the department chair, a minimum grade of C in the original course, the advisor's signature, and submission by the fourth week of the semester. A student earned a C- in the original course and submits in week 3 with the advisor's signature. Does the petition qualify? Explain.""",
       "Must answer no because a C- is below the minimum grade of C, while noting the other requirements were met.",
       "No. A C- is below the required minimum grade of C."),
    _i("""Field trip policy: 'Permission slips are due five school days before the trip. Students with outstanding fees may not attend. A chaperone ratio of one adult per ten students is required.' A class of 34 students has two chaperones, and one student owes a library fine. What must change before the trip can proceed?""",
       "Must state that at least four chaperones are needed for 34 students and the student with the fine must clear it or stay behind.",
       "Add chaperones to reach at least four for 34 students, and the student with the outstanding fine must pay it or not attend."),
    _i("""Technology policy: 'Personal laptops are permitted in class with teacher approval.' Assessment policy: 'No personal electronic devices may be used during quizzes, tests, or exams.' Can a student use a personal laptop during a quiz with the teacher's approval? State which policy governs and why.""",
       "Must answer no, because the assessment policy is the more specific rule and governs during quizzes.",
       "No. The assessment policy specifically governs quizzes and prohibits personal devices."),
    _i("""Grading policy: 'One retake is allowed per unit test. The higher score counts. Retakes must be completed within two weeks of the original test.' A student scored 70, retook the test three weeks later, and scored 90. Which score counts, and why?""",
       "Must answer 70 because the retake was outside the two-week window.", "70. The retake was taken after the two-week deadline."),
    _i("""Scholarship rules: 'Renewal requires a 3.2 GPA and 12 completed credits each semester. One probationary semester is allowed; a second consecutive shortfall ends the scholarship.' A student earned a 3.0 GPA with 12 credits in fall and a 3.3 GPA with 12 credits in spring. What is the student's status after each semester?""",
       "Must answer probation after fall and restored good standing after spring.",
       "After fall: probation. After spring: good standing restored."),
    _i("""Attendance policy: 'More than nine absences in a semester course results in loss of credit. Up to two college visits per semester do not count as absences.' A senior has 11 absences, three of which were college visits. Do they lose credit?""",
       "Must compute 11 minus 2 exempt visits equals 9, which is not more than nine, so credit is retained.",
       "No. Only two visits are exempt, leaving nine absences, which does not exceed the limit."),
    _i("""The parent portal FAQ says 'grades are updated weekly.' The course syllabus says 'assignments are graded within five school days of submission.' A quiz taken on Monday is still unposted the following Monday, seven school days later. Which document's promise, if any, has been broken?""",
       "Must conclude the syllabus promise (five school days) is broken, and that the weekly update promise is also broken or at best borderline, with reasoning.",
       "The syllabus promise is broken (seven school days exceeds five). The weekly update promise is also unmet if no update occurred within the week."),
]

DOC_QA_PRO: List[Item] = [
    _i("""2025 special education addendum: 'IEP progress data may be shared with contracted tutoring vendors to support services.' Student privacy handbook: 'Student records may not be released to third parties without written parental consent, except to school officials with a legitimate educational interest.' A tutoring vendor requests IEP data for a student. Explain which clause governs, what conditions the school-official exception under FERPA requires for a contractor, and what the district should do before sharing.""",
       "Must explain that the handbook and FERPA control, that a contractor can qualify as a school official only under direct control with a legitimate educational interest and a written agreement, and recommend a data-sharing agreement or parental consent before release."),
    _i("""Handbook: 'Lockers are school property and may be searched at any time.' Student rights addendum: 'Searches of student belongings require reasonable suspicion.' Reconcile these in light of the reasonable-suspicion standard for school searches, explain when each applies, and draft a single replacement clause.""",
       "Must distinguish locker (school property) from personal belongings inside it, apply the reasonable-suspicion standard, and produce one clause that covers both cases."),
    _i("""Policy A: 'Bullying investigations must conclude within 10 school days.' Policy B: 'Complaints involving sex-based harassment follow the Title IX grievance process, which takes precedence over other timelines.' A complaint alleges both bullying and sex-based harassment. Describe the procedure, identify the conflicts, and state which timeline governs and why.""",
       "Must identify the Title IX process as governing due to federal requirements, explain how the bullying policy still applies to non-Title IX conduct, and describe a coordinated procedure."),
    _i("""Three excerpts on AI use. Course syllabus: 'AI tools are prohibited for all written work.' District policy: 'AI tools are permitted with disclosure.' Department guidance: 'AI is permitted for brainstorming only.' A student used AI to brainstorm an essay. Determine which rule controls for this course, explain the hierarchy, and draft a consistent three-level policy statement.""",
       "Must recognize the district policy sets the outer bound, that a course syllabus may be stricter within that bound, and conclude the syllabus prohibition controls, then provide a coherent hierarchy."),
    _i("""Handbook: 'All medication must be administered by the school nurse.' Athletic policy: 'Athletes may self-carry inhalers with a physician's note.' State law: 'Schools must permit students to self-carry and self-administer inhalers and epinephrine auto-injectors with written physician authorization.' Resolve the conflict and rewrite the handbook clause so it complies.""",
       "Must state that state law overrides both policies, identify the handbook clause as non-compliant, and produce a rewritten clause permitting self-carry with physician authorization."),
    _i("""Attendance policy: 'Remote-learning days count as present.' Athletics eligibility policy: 'Athletes must attend school in person on the day of a competition.' A student attends remotely under a documented medical accommodation and wants to compete. Analyze the conflict under disability-accommodation principles and recommend a decision with reasoning.""",
       "Must weigh the in-person requirement against the accommodation, note the risk of discriminating on the basis of disability, and recommend allowing participation or an individualized review with justification."),
    _i("""District grading policy: 'No grade below 50% may be recorded.' Teacher syllabus: 'Missing work is recorded as a zero.' Explain which governs, compute the average for a student with scores 90, 90, and a missing assignment under each rule, and summarize the pedagogical argument for each side.""",
       "Must state the district policy governs, compute 60 under zeros and 76.7 under the 50% floor, and fairly present both arguments.",
       "District policy governs. Averages: 60 with a zero; about 76.7 with a 50% floor."),
    _i("""IT policy: 'Email is deleted after one year.' Records policy: 'Disciplinary records are retained for five years.' A disciplinary decision was communicated only by email and never filed elsewhere. Identify the compliance gap, explain the risk if the decision is challenged in year three, and propose a procedure that closes the gap.""",
       "Must identify that the record will be destroyed before the retention period ends, describe the evidentiary risk, and propose a filing or export step at decision time."),
]

# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------

CLASSIFY_LITE: List[Item] = [
    _i("Classify the sentiment of this parent email as positive, neutral, or negative: 'Thank you for calling today, we appreciate the update on Jordan's progress.'",
       "Must answer positive.", "Positive"),
    _i("Classify the sentiment of this parent email as positive, neutral, or negative: 'This is the third time the bus has been late this week and nobody has told us why.'",
       "Must answer negative.", "Negative"),
    _i("Classify the sentiment of this parent email as positive, neutral, or negative: 'Please confirm whether the field trip is on the 14th or the 15th.'",
       "Must answer neutral.", "Neutral"),
    _i("Classify the sentiment of this parent email as positive, neutral, or negative: 'Maya came home excited about the science fair for the first time all year.'",
       "Must answer positive.", "Positive"),
    _i("Classify the sentiment of this parent email as positive, neutral, or negative: 'I am disappointed that the grade was changed without anyone contacting us.'",
       "Must answer negative.", "Negative"),
    _i("Classify the sentiment of this parent email as positive, neutral, or negative: 'Attached is the signed permission form for next week.'",
       "Must answer neutral.", "Neutral"),
    _i("Classify this IT support ticket into exactly one of: Hardware, Network, Account Access, Software Licensing, Security. Ticket: 'My laptop screen flickers and then goes black when I open the lid.'",
       "Must answer Hardware.", "Hardware"),
    _i("Classify this IT support ticket into exactly one of: Hardware, Network, Account Access, Software Licensing, Security. Ticket: 'I can't reach any internal sites from the second-floor conference room, but my phone works on cellular.'",
       "Must answer Network.", "Network"),
    _i("Classify this IT support ticket into exactly one of: Hardware, Network, Account Access, Software Licensing, Security. Ticket: 'I've been locked out after too many password attempts and need to get back in before my 2pm meeting.'",
       "Must answer Account Access.", "Account Access"),
    _i("Classify this IT support ticket into exactly one of: Hardware, Network, Account Access, Software Licensing, Security. Ticket: 'Adobe says our team's license expired and won't let me open files.'",
       "Must answer Software Licensing.", "Software Licensing"),
    _i("Classify this IT support ticket into exactly one of: Hardware, Network, Account Access, Software Licensing, Security. Ticket: 'I clicked a link in an email that looked like it came from HR and now I'm worried it was phishing.'",
       "Must answer Security.", "Security"),
    _i("Classify this IT support ticket into exactly one of: Hardware, Network, Account Access, Software Licensing, Security. Ticket: 'The projector in room 204 shows no signal even with a new cable.'",
       "Must answer Hardware.", "Hardware"),
    _i("Classify this headline into one of: Sports, Politics, Technology, Health. Headline: 'City council approves new zoning rules after six-hour debate.'",
       "Must answer Politics.", "Politics"),
    _i("Classify this headline into one of: Sports, Politics, Technology, Health. Headline: 'Local hospital reports drop in flu cases after vaccination drive.'",
       "Must answer Health.", "Health"),
    _i("Classify this headline into one of: Sports, Politics, Technology, Health. Headline: 'Chipmaker unveils processor with on-device language model support.'",
       "Must answer Technology.", "Technology"),
    _i("Classify this headline into one of: Sports, Politics, Technology, Health. Headline: 'Underdogs clinch the regional title in overtime.'",
       "Must answer Sports.", "Sports"),
    _i("Is this message spam or not spam? 'Congratulations! You have been selected for a free cruise. Click here within 24 hours to claim.'",
       "Must answer spam.", "Spam"),
    _i("Is this message spam or not spam? 'Hi Sam, the reading list for next term is attached. Let me know if the link doesn't work.'",
       "Must answer not spam.", "Not spam"),
    _i("Is this message spam or not spam? 'URGENT: your account will be suspended unless you verify your password at the link below.'",
       "Must answer spam.", "Spam"),
    _i("Rate the urgency of this message as low, medium, or high: 'The main water line in the science wing is leaking onto the electrical panel.'",
       "Must answer high.", "High"),
    _i("Rate the urgency of this message as low, medium, or high: 'When you get a chance, could you share last year's field day schedule?'",
       "Must answer low.", "Low"),
    _i("Rate the urgency of this message as low, medium, or high: 'The substitute for tomorrow's first period cancelled; we need coverage by the end of today.'",
       "Must answer medium or high, with high acceptable given the same-day deadline; must not answer low.", "Medium to high"),
]

CLASSIFY_STANDARD: List[Item] = [
    _i("""Evaluate this forum post against the student conduct guidelines and return JSON with an array of violated codes and a one-line reason for each. Guidelines: C1 no personal attacks; C2 no sharing others' private information; C3 no plagiarism; C4 stay on topic; C5 no commercial promotion; C6 no profanity; C7 cite sources for factual claims; C8 no impersonation. Post: 'Everyone should skip Mr. Lee's class, he's an idiot. Also his home address is 42 Elm St if you want to complain in person. Buy my notes at notes4u.example for $10!'""",
       "Must return valid JSON listing C1, C2, and C5 with reasons, and must not list C3, C6, C7, or C8.",
       '{"violations": [{"code": "C1", "reason": "personal attack on the teacher"}, {"code": "C2", "reason": "shares a home address"}, {"code": "C5", "reason": "advertises notes for sale"}]}'),
    _i("""Classify each ticket with a department (Hardware, Network, Account Access, Software Licensing, Security) and a priority (P1 to P3, where P1 is outage-level) as a JSON array. Tickets: 1 'Entire east wing lost Wi-Fi during exams.' 2 'Need a second monitor for my desk.' 3 'Ransomware warning popped up on the front office PC.' 4 'My MFA app was on my old phone.' 5 'Our design software says the seat count is exceeded.'""",
       "Must return five objects with sensible departments (Network, Hardware, Security, Account Access, Software Licensing) and priorities where 1 and 3 are P1, 2 is P3, and 4 and 5 are P2 or P3."),
    _i("""Assign all applicable topic tags from this list to the abstract, as a JSON array: [machine learning, education, privacy, healthcare, policy, hardware]. Abstract: 'We study how classroom recommendation systems that personalize reading assignments affect student outcomes, and we examine the data protection obligations that arise when minors' reading histories are stored by vendors.'""",
       "Must return machine learning, education, and privacy; policy is acceptable; must not include healthcare or hardware.",
       '["machine learning", "education", "privacy"]'),
    _i("""Classify the intent of each chatbot message as one of: check_balance, transfer, report_fraud, update_contact, general_question, unclear. Return JSON with intent and a confidence from 0 to 1. Messages: 'How much do I have?' 'Move 200 to savings.' 'Someone bought a TV with my card.' 'I moved, new address is on file?' 'What are your hours?' 'The thing from before.'""",
       "Must map the six messages to check_balance, transfer, report_fraud, update_contact, general_question, and unclear respectively, with a low confidence on the last."),
    _i("""Classify each email as action_required or fyi and give a one-line justification. Emails: 1 'Reminder: the roof inspection is Tuesday, no action needed.' 2 'Please approve the attached purchase order by Friday.' 3 'FYI, the vendor renamed their product.' 4 'Your signature is missing on page 3 of the contract.'""",
       "Must mark 2 and 4 as action_required and 1 and 3 as fyi with justifications.",
       "1 fyi; 2 action_required; 3 fyi; 4 action_required"),
    _i("""Classify each code review comment as nit, bug, design, or question. Comments: 1 'Trailing whitespace here.' 2 'This will divide by zero when the list is empty.' 3 'Should this live in the service layer instead of the controller?' 4 'Why did we pick a linked list here?' 5 'Rename i to index for clarity.'""",
       "Must classify 1 nit, 2 bug, 3 design, 4 question, 5 nit.",
       "1 nit; 2 bug; 3 design; 4 question; 5 nit"),
    _i("""Sort each student request into one accommodation category: extended_time, assistive_technology, environment, format, scheduling, other. Requests: 'I need 50% extra time on tests.' 'Can I use a screen reader?' 'I need a quiet room away from the class.' 'Please provide handouts in large print.' 'I can only test in the morning because of medication.'""",
       "Must map the five requests to extended_time, assistive_technology, environment, format, and scheduling respectively.",
       "extended_time; assistive_technology; environment; format; scheduling"),
    _i("""For each review, identify which aspects are mentioned (shipping, quality, price, support) and the sentiment for each aspect, as JSON. Reviews: 1 'Arrived two days early, but the stitching is already coming apart.' 2 'Pricey, though support replaced it the same day without fuss.' 3 'Exactly as described and a fair price.'""",
       "Must return per-review aspect lists: 1 shipping positive and quality negative; 2 price negative and support positive; 3 quality positive and price positive."),
    _i("""Assign a Bloom's taxonomy level (remember, understand, apply, analyze, evaluate, create) to each question. Questions: 1 'List the three branches of government.' 2 'Explain why the branches are separated.' 3 'Use the checks-and-balances model to predict what happens if a veto is overridden.' 4 'Compare the powers of the two legislative chambers.' 5 'Judge whether the current balance of power is effective, with evidence.' 6 'Design a fourth branch and justify its powers.'""",
       "Must assign remember, understand, apply, analyze, evaluate, create in order.",
       "1 remember; 2 understand; 3 apply; 4 analyze; 5 evaluate; 6 create"),
    _i("""Classify each transaction into a budget category using these rules: Groceries = supermarkets; Dining = restaurants and cafes; Transport = fuel, transit, rideshare; Utilities = power, water, internet; Other = anything else. Transactions: 'SHELL 4412 $48.10', 'TRADER JOES $92.33', 'COMCAST $79.99', 'UBER TRIP $14.20', 'BLUE BOTTLE COFFEE $6.50', 'AMAZON MKTPLACE $23.99'.""",
       "Must classify Transport, Groceries, Utilities, Transport, Dining, Other in order.",
       "Transport; Groceries; Utilities; Transport; Dining; Other"),
    _i("""Label each statement as fact, opinion, or prediction and give a one-line reason. Statements: 1 'The school opened in 1962.' 2 'The new schedule is better for students.' 3 'Enrollment will fall next year.' 4 'Water boils at 100 degrees Celsius at sea level.' 5 'Most parents will prefer the later start time.'""",
       "Must label 1 fact, 2 opinion, 3 prediction, 4 fact, 5 prediction (opinion acceptable for 5 if justified).",
       "1 fact; 2 opinion; 3 prediction; 4 fact; 5 prediction"),
    _i("""Assign a severity to each bug report using these definitions: S1 data loss or outage; S2 major feature broken with no workaround; S3 feature broken with a workaround; S4 cosmetic. Reports: 1 'Saving a draft deletes the previous draft.' 2 'Export to PDF fails, but print-to-PDF works.' 3 'The login button is misaligned on mobile.' 4 'Search returns nothing for any query since this morning.'""",
       "Must assign S1, S3, S4, S2 in order.",
       "1 S1; 2 S3; 3 S4; 4 S2"),
]

CLASSIFY_PRO: List[Item] = [
    _i("""Moderate these five posts under a policy that prohibits harassment and hate speech but explicitly permits satire, quoting for the purpose of criticism, and in-group reclaimed language. For each post, decide allow or remove, name the policy clause, and explain the borderline reasoning. Posts: 1 A user quotes a slur from a news article to condemn it. 2 A parody account exaggerates a politician's speech patterns. 3 A user tells another user to 'go back where you came from.' 4 A member of a group uses a reclaimed term about themselves in a joke. 5 A user posts the same critical comment about a coworker on every one of their photos.""",
       "Must allow 1, 2, and 4 with the relevant exception named, remove 3 as hate speech, remove 5 as harassment based on the pattern, and explain each judgment."),
    _i("""Classify each contract clause by type (indemnification, limitation of liability, termination, confidentiality, governing law) and flag any clause whose wording supports two conflicting readings, explaining both. Clauses: 1 'Either party may terminate on 30 days notice; termination for cause is immediate.' 2 'Vendor shall hold Customer harmless from third-party claims arising from Vendor's negligence.' 3 'In no event shall either party's liability exceed fees paid, except for breaches of Section 5.' 4 'Each party shall keep the other's information confidential for three years after disclosure or termination.' 5 'This agreement is governed by the laws of the State of Delaware.'""",
       "Must classify all five correctly, and identify at least clause 4's ambiguity (three years from disclosure versus from termination) and ideally clause 3's dependence on what Section 5 contains."),
    _i("""Here are ten messy support tickets. Propose a taxonomy of no more than six categories that covers them without an 'other' bucket, classify each ticket, and justify why each category is necessary. Tickets: 'refund never arrived', 'app crashes on launch', 'how do I change my email', 'charged twice', 'dark mode request', 'password reset link expired', 'can't upload photos over 10MB', 'want to cancel subscription', 'export to CSV would be great', 'login loops back to the login page'.""",
       "Must propose a coherent taxonomy (for example billing, account access, bugs, feature requests, subscription, usage help), classify all ten, and justify each category."),
    _i("""Determine the true sentiment (positive, negative, or mixed) of each review, detecting sarcasm where present, and explain the cues. Reviews: 1 'Great, another update that moved every button. Love relearning the app every month.' 2 'Honestly expected junk at this price, but it has survived a year of daily use.' 3 'The camera is stunning. The battery, less so. I keep it anyway.' 4 'Five stars for the box. The product inside did not survive shipping.'""",
       "Must identify 1 as negative sarcasm, 2 as positive despite the negative opening, 3 as mixed leaning positive, and 4 as negative with ironic praise, citing the textual cues."),
]

# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------

SUMMARIZE_LITE: List[Item] = [
    _i("Summarize this announcement in three bullet points under 20 words each: 'The spring book fair runs March 3 to 7 in the library. Volunteers are needed for the afternoon shifts. All proceeds fund new graphic novels for the middle school collection.'",
       "Must produce exactly three bullets covering the dates and location, the volunteer request, and the use of proceeds, each under 20 words."),
    _i("Summarize in one sentence: 'Due to the forecast of freezing rain, all after-school activities on Thursday are cancelled. Regular classes will run as scheduled. Buses will depart at the normal time.'",
       "Must state that after-school activities are cancelled Thursday because of freezing rain while classes and buses run normally, in one sentence."),
    _i("Give a two-sentence summary: 'The cafeteria will switch to a new vendor on October 1. Menus will include more vegetarian options and prices will stay the same. Students with allergies should update their forms with the nurse by September 25.'",
       "Must mention the vendor change on October 1 with unchanged prices and the September 25 allergy-form deadline in two sentences."),
    _i("Summarize this paragraph in three bullets: 'Tryouts for the robotics team are next Tuesday and Wednesday after school in Room 118. No experience is required, but students should bring a laptop if they have one. Team members meet twice a week and compete in two regional events each spring.'",
       "Must cover the tryout days and room, the no-experience/laptop note, and the meeting and competition schedule."),
    _i("Reduce this to a single headline of at most ten words: 'After three years of fundraising, the school has installed solar panels on the gym roof that will cover about 40 percent of the building's electricity use.'",
       "Must produce one headline of ten words or fewer that conveys solar panels installed and the electricity savings."),
    _i("Summarize in one sentence for a text message: 'Picture day has been moved from Monday to Friday of the same week because the photographer had a scheduling conflict. Order forms are still due Monday.'",
       "Must convey the move to Friday and that order forms are still due Monday in a single short sentence."),
    _i("Write a two-bullet summary: 'The library's late fee policy has ended. Books are still due after three weeks, and accounts with more than five overdue items will be blocked from new checkouts until items are returned.'",
       "Must state that late fees are gone and that more than five overdue items blocks checkouts."),
    _i("Summarize this in one sentence: 'Our new attendance app sends a text to parents within 15 minutes of an unexcused absence. Parents can reply directly to the text to provide an excuse, which goes to the attendance office.'",
       "Must mention the 15-minute text and the reply-to-excuse feature in one sentence."),
    _i("Give a three-bullet TL;DR: 'The senior parking lot will be repaved during spring break. Seniors should park in the east lot that week. Parking permits remain valid, and the lot reopens the Monday after break.'",
       "Must include repaving during spring break, using the east lot, and reopening the Monday after break."),
    _i("Summarize in under 25 words: 'Yearbook orders close Friday at midnight. This year's book is 30 pages longer than last year's and includes a section on the new arts wing.'",
       "Must give the Friday midnight deadline and note the longer book with the arts wing section, under 25 words."),
    _i("Condense to one sentence: 'The PTA meeting on the 12th will cover the budget for the spring carnival, a proposal to start school 20 minutes later, and elections for next year's officers.'",
       "Must mention the date and all three agenda items in one sentence."),
    _i("Summarize this weather notice in two bullets: 'Because of the heat advisory, outdoor recess is moved indoors for the rest of the week. Physical education classes will meet in the gym. Water bottles are encouraged.'",
       "Must convey indoor recess and PE for the rest of the week due to heat, and the water bottle suggestion."),
    _i("Write a one-sentence summary: 'The lost and found will be donated to charity on the last day of each month. Items can be claimed from the front office during school hours before then.'",
       "Must state the monthly donation and where to claim items beforehand."),
    _i("Summarize in three bullets: 'Course selection for next year opens February 1 in the student portal. Counselors will visit homerooms during the first week of February. Selections lock on February 28.'",
       "Must cover the February 1 opening, counselor visits, and the February 28 lock date."),
    _i("Give a one-line summary suitable for a calendar entry: 'The chess club's regional tournament is Saturday, April 18, at Lincoln High. Buses leave at 7:15 a.m. and return around 5 p.m.'",
       "Must include the date, location, and departure and return times on one line."),
    _i("Summarize in two sentences: 'Starting in January, students may bring their own devices for classroom use. Devices must be registered with IT and connect only to the student network. Phones are still not permitted during instructional time.'",
       "Must convey the January BYOD start with registration and network rules, and that phones remain prohibited in class."),
    _i("Reduce this to three bullets under 15 words each: 'The winter concert is December 15 at 7 p.m. in the auditorium. Doors open at 6:30 p.m. Admission is free, but donations to the music program are welcome.'",
       "Must include date and time, doors opening at 6:30, and free admission with optional donations, each under 15 words."),
]

SUMMARIZE_STANDARD: List[Item] = [
    _i("""Write an executive briefing with three headings (Milestones, Blockers, Next Quarter) from these engineering meeting notes: 'Shipped the new grading export and the parent-portal redesign. Mobile app login rewrite slipped two weeks because the auth vendor changed their SDK. Data warehouse migration is 60% done; the remaining tables depend on the finance team's sign-off, which has been pending for three weeks. Q4 plan: finish the migration, launch mobile login, start the accessibility audit. Hiring: two backend roles still open.'""",
       "Must produce the three headings, list both shipped items, name the SDK change and the finance sign-off as blockers, and list the three Q4 items."),
    _i("""Summarize this incident report into a five-line postmortem summary covering impact, cause, detection, fix, and prevention: 'On May 3 from 09:10 to 10:45 the grade portal returned errors for about 30% of requests. A deploy at 09:05 introduced a database connection pool size of 5 instead of 50 due to a typo in the config. Alerts fired at 09:20 on error rate. The config was corrected and redeployed at 10:40. We will add a config validation step and a canary deploy.'""",
       "Must have five labeled lines with the correct time window and error share, the pool-size typo as the cause, the 09:20 alert, the 10:40 fix, and the two prevention items."),
    _i("""Condense these customer interview notes into the top three recurring themes with one supporting quote each: 'P1: I never know when grades are posted, I refresh constantly. P2: The app logs me out every day, which is annoying. P3: Would love a notification when a grade changes. P4: Logging in on my phone takes four steps. P5: Assignments are easy to find, no complaints there. P6: I want an alert when something is graded. P7: Every morning I have to sign in again.'""",
       "Must identify grade notifications, repeated logouts/sign-in friction, and mobile login difficulty as themes, each with a matching quote."),
    _i("""Summarize this policy memo for a parent newsletter in under 120 words, keeping every date: 'Beginning January 6, the school day will start at 8:20 instead of 8:00 and end at 3:10 instead of 2:50. Bus routes will shift by 20 minutes. Before-school care will open at 7:00 as before. The change follows the district's sleep study and a parent survey completed in October. A review will occur in May.'""",
       "Must keep January 6, the new start and end times, the 20-minute bus shift, 7:00 before-care, the October survey, and the May review, within 120 words."),
    _i("""Write a plain-language abstract of at most 100 words for a general audience: 'We evaluated a peer-tutoring program across 14 middle schools over two years. Students who received tutoring at least twice a week improved reading scores by 0.31 standard deviations relative to matched controls, with larger effects for students starting below grade level. Effects were not significant for students tutored once a week or less. Program cost was about $400 per student per year.'""",
       "Must convey the two-year, 14-school study, the improvement for twice-weekly tutoring, larger gains for below-grade students, no effect for less frequent tutoring, and the cost, in plain language within 100 words."),
    _i("""Summarize the following release notes as a changelog with sections Added, Changed, Fixed: 'This release introduces dark mode and CSV export. The settings page has been reorganized into tabs. Notification emails now use the new template. Fixed a crash when opening an empty gradebook. Fixed timezone display for users west of UTC-8. Removed the legacy print view.'""",
       "Must place dark mode and CSV export under Added, settings tabs and the email template under Changed, both crashes/bugs under Fixed, and handle the removal (Removed section or under Changed)."),
    _i("""Turn these meeting minutes into a decision log listing each decision, its owner, and its due date: 'Agreed to move the science fair to April 22, Ms. Ortiz to notify parents by March 30. Decided to cap projects at two students each; Mr. Kim updates the rules page by March 15. Deferred the question of prizes to the April meeting. Ms. Chen will get three quotes for display boards before March 20.'""",
       "Must list three decisions with owners and dates, mark prizes as deferred, and include the display board quotes action."),
    _i("""Summarize this product review thread into a balanced two-paragraph summary, one paragraph of praise and one of complaints, with rough counts: 'R1: battery lasts two days, love it. R2: screen scratches easily. R3: fast charging is great. R4: scratched within a week. R5: battery is excellent. R6: case is slippery. R7: two-day battery confirmed. R8: screen protector is a must.'""",
       "Must report battery life and fast charging as praise (about four mentions) and screen scratching plus the slippery case as complaints (about four mentions) in two paragraphs."),
    _i("""Write a 60 to 80 word summary of this grant report section for a board slide: 'With the $50,000 STEM grant we purchased 30 laptops and a 3D printer, trained 12 teachers over the summer, and launched two elective courses in the fall. Enrollment in the electives was 84 students, 41% of them girls, up from 28% in prior STEM electives. Remaining funds of $6,200 will cover printer materials through June.'""",
       "Must include the grant amount, purchases, teacher training, two electives with 84 students, the 41% versus 28% figure, and remaining funds, in 60 to 80 words."),
    _i("""Summarize the argument of this op-ed excerpt in three sentences without adding your own opinion: 'Homework in elementary school has little measurable effect on achievement, yet it consumes family evenings and widens gaps between students with and without support at home. Schools should replace nightly worksheets with reading time and optional enrichment. Teachers would regain planning time, and families would regain their evenings.'""",
       "Must neutrally capture the claim of little effect, the equity and family-time costs, and the proposed replacement, in three sentences."),
    _i("""Create a one-paragraph summary for a superintendent of this transportation study: 'Average bus ride time is 38 minutes, with 12% of students riding over an hour. Consolidating four low-ridership routes would save $210,000 per year but add 6 minutes to rides for 300 students. Adding one route in the north district would cut hour-plus rides by half at a cost of $95,000. The committee recommends both changes for a net saving of $115,000.'""",
       "Must state the current ride times, both proposals with their costs and effects, and the net $115,000 recommendation."),
    _i("""Summarize the key points of this syllabus section as a five-item student checklist: 'Assignments are due at 11:59 p.m. on the stated date. Late work is accepted for three days at a 10% per day penalty. One assignment may be dropped. Collaboration is allowed on homework but not on quizzes. All code must be submitted through the course repository, not email.'""",
       "Must produce five checklist items covering the deadline time, the late policy, the dropped assignment, the collaboration rule, and repository submission."),
    _i("""Condense this security advisory into a three-sentence notice for non-technical staff: 'A vulnerability in the document viewer allows a crafted PDF to execute code when previewed. Version 4.2.1 fixes it. Until updated, staff should not preview PDFs from unknown senders; opening them in the standalone reader is unaffected. IT will push the update by Wednesday.'""",
       "Must say what to avoid (previewing PDFs from unknown senders), what is safe (standalone reader), and when the fix arrives (Wednesday), in three sentences."),
]

SUMMARIZE_PRO: List[Item] = [
    _i("""Synthesize these three study abstracts into a comparative literature summary that identifies methodological differences, reconciles the conflicting conclusions, and states what a reader should believe. A: 'A randomized trial of 400 students found retrieval practice improved delayed recall by 22% over rereading.' B: 'An observational study of 3,000 students found no relationship between self-reported quizzing frequency and course grades.' C: 'A lab study of 60 adults found retrieval practice improved recall only when feedback was provided.'""",
       "Must contrast randomized versus observational versus lab designs, note self-report and outcome-measure differences, use C's feedback moderator to reconcile A and B, and give a calibrated conclusion."),
    _i("""Produce a critical synthesis of these three positions on class size, noting where the evidence conflicts and what would resolve it: 1 'A statewide experiment reducing K-3 classes from 22 to 15 raised test scores by 0.2 SD, with lasting effects.' 2 'A cross-national comparison finds no correlation between class size and achievement after controlling for income.' 3 'A cost analysis argues the same money spent on teacher coaching yields larger gains.'""",
       "Must distinguish causal experimental evidence from cross-national correlation, address confounding, treat the cost argument as a separate question, and propose what evidence would settle the disagreement."),
    _i("""Write a one-page brief that reconciles these three quarterly reports from different departments into a single narrative, flagging every place the numbers disagree: Finance: 'Enrollment revenue up 4% on 2% enrollment growth.' Admissions: 'Enrollment grew 3.5%, the strongest in five years.' Operations: 'Classroom utilization fell 3% as enrollment was flat.' Explain plausible reasons for each discrepancy and what data would resolve them.""",
       "Must identify the three conflicting enrollment figures, propose reasons such as different counting dates or definitions, and specify the reconciling data."),
    _i("""Synthesize these three abstracts on AI tutoring into a summary for a school board, including effect sizes, limitations, and a recommendation: A: 'AI tutor use for 8 weeks improved algebra scores by 0.15 SD in a randomized trial of 1,200 students; effects concentrated among students with prior scores in the bottom quartile.' B: 'Teachers reported that AI tutor use reduced homework help requests by 30% but increased instances of copied answers.' C: 'A survey found 45% of students used the tutor fewer than twice.'""",
       "Must report the effect size and its concentration, integrate the copying and low-usage caveats, and give a recommendation that accounts for both benefits and risks."),
    _i("""Compare these three descriptions of the same historical event, identify factual disagreements and differences in framing, and write a neutral synthesized account: 1 'The 1968 strike was led by students demanding curriculum reform and ended after three weeks with most demands met.' 2 'The 1968 walkout, organized largely by parents, lasted nearly a month and achieved only a promise to review the curriculum.' 3 'A brief 1968 protest by a few hundred students prompted the board to form a committee.'""",
       "Must list disagreements on leadership, duration, scale, and outcome, note the framing differences, and produce a hedged neutral account that reflects the uncertainty."),
    _i("""Distill these three conflicting expert reviews of a software architecture into a decision memo: Reviewer 1: 'The event-driven design scales well but makes debugging hard; approve with a tracing requirement.' Reviewer 2: 'The design over-engineers a problem that a single service would solve for years; reject.' Reviewer 3: 'Approve if the team commits to a two-service split now with events added later.' Recommend a path and explain how it addresses each reviewer's concern.""",
       "Must fairly summarize all three positions, recommend a specific path, and explicitly map how the recommendation answers each reviewer."),
    _i("""Synthesize these three data points into an analysis of whether a reading intervention worked, addressing the apparent contradiction: 'Average reading scores rose 8 points in intervention schools and 7 points in comparison schools.' 'Among students who attended at least 80% of sessions, scores rose 15 points.' 'Attendance averaged 55%, and low attenders were disproportionately students with the lowest baseline scores.'""",
       "Must explain that the small overall difference and the large effect among high attenders reflect selection (higher attenders differed at baseline), and conclude cautiously about effectiveness with suggested next steps."),
]

# ---------------------------------------------------------------------------
# code_explain
# ---------------------------------------------------------------------------

CODE_EXPLAIN_LITE: List[Item] = [
    _i("Explain what Python's math.isclose function does and show a two-line code example.",
       "Must explain approximate float comparison with a tolerance and give a correct example."),
    _i("What does Python's itertools.groupby do, and why must the input be sorted by the key first? Give a short example.",
       "Must explain that groupby groups consecutive elements with the same key, that unsorted input yields multiple groups for the same key, and include an example."),
    _i("Explain what the maxsplit argument does in Python's str.split, with an example.",
       "Must explain that maxsplit limits the number of splits and show the resulting list."),
    _i("What does Python's dict.get(key, default) return when the key is missing, and how does that differ from dict[key]?",
       "Must state that get returns the default (None by default) while indexing raises KeyError.",
       "get returns the default value instead of raising; dict[key] raises KeyError for a missing key."),
    _i("Explain what enumerate does in Python and show how to start counting at 1.",
       "Must explain that enumerate yields index-value pairs and show enumerate(items, start=1) or equivalent."),
    _i("What does the JavaScript Array.prototype.map method return, and how is it different from forEach?",
       "Must state that map returns a new array of transformed values while forEach returns undefined."),
    _i("Explain what the SQL clause 'LIMIT 10 OFFSET 20' does.",
       "Must explain that it skips the first 20 rows and returns the next 10.", "Skips 20 rows, then returns up to 10 rows."),
    _i("What does 'git stash' do, and how do you get the stashed changes back?",
       "Must explain that stash saves uncommitted changes and cleans the working tree, and that git stash pop or apply restores them."),
    _i("Explain what Python's zip does when the input iterables have different lengths.",
       "Must state that zip stops at the shortest iterable, and may mention strict=True or itertools.zip_longest."),
    _i("What does the Python slice items[::-1] return?",
       "Must state it returns a reversed copy of the sequence.", "A reversed copy of the sequence."),
    _i("Explain what 'chmod +x script.sh' does on Linux.",
       "Must explain that it adds the execute permission so the script can be run directly."),
]

CODE_EXPLAIN_STANDARD: List[Item] = [
    _i("""Explain how this dynamic programming solution builds its table and why the inner loop runs backwards:
def knapsack(weights, values, capacity):
    dp = [0] * (capacity + 1)
    for w, v in zip(weights, values):
        for c in range(capacity, w - 1, -1):
            dp[c] = max(dp[c], dp[c - w] + v)
    return dp[capacity]""",
       "Must explain that dp[c] holds the best value for capacity c, that each item updates the table once, and that iterating c downward prevents reusing the same item twice (0/1 knapsack)."),
    _i("""Walk through this React hook and explain the role of the cleanup function:
function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}""",
       "Must explain that a timer is set on each value change and the cleanup cancels the pending timer so only the last value within the delay is committed, and that cleanup also runs on unmount."),
    _i("""Explain what this function does and its time complexity:
def search(a, target):
    lo, hi = 0, len(a) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if a[mid] == target:
            return mid
        if a[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1""",
       "Must identify binary search on a sorted array, explain the halving, and state O(log n) time.",
       "Binary search; O(log n)."),
    _i("""Explain how this LRU cache works and why OrderedDict is used:
from collections import OrderedDict
class LRU:
    def __init__(self, n):
        self.n, self.d = n, OrderedDict()
    def get(self, k):
        if k not in self.d:
            return None
        self.d.move_to_end(k)
        return self.d[k]
    def put(self, k, v):
        self.d[k] = v
        self.d.move_to_end(k)
        if len(self.d) > self.n:
            self.d.popitem(last=False)""",
       "Must explain that insertion order tracks recency, move_to_end marks recent use, and popitem(last=False) evicts the least recently used entry."),
    _i("""Explain what this decorator does and what functools.wraps is for:
import functools, time
def timed(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        t = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            print(f"{fn.__name__} took {time.perf_counter() - t:.3f}s")
    return inner""",
       "Must explain the wrapper measures elapsed time even on exceptions via finally, and that wraps preserves the original function's name and docstring."),
    _i("""Explain the difference between these two SQL queries and when their results differ:
SELECT s.name, g.score FROM students s JOIN grades g ON g.student_id = s.id;
SELECT s.name, g.score FROM students s LEFT JOIN grades g ON g.student_id = s.id;""",
       "Must explain that the inner join drops students without grades while the left join keeps them with NULL scores."),
    _i("""Explain what this generator does and why it uses less memory than building a list:
def chunks(iterable, size):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch""",
       "Must explain lazy batching into lists of the given size, the final partial batch, and that only one batch is held in memory at a time."),
    _i("""Explain what this regular expression matches and give one string that matches and one that does not:
^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$""",
       "Must describe it as a basic email pattern (local part, @, domain, dot, TLD of two or more letters) with a valid and an invalid example."),
    _i("""Explain the order in which these lines print and why:
import asyncio
async def work(name, delay):
    await asyncio.sleep(delay)
    print(name)
async def main():
    await asyncio.gather(work("a", 0.2), work("b", 0.1), work("c", 0.0))
asyncio.run(main())""",
       "Must state the output order c, b, a and explain that gather runs the coroutines concurrently so they finish in order of delay.",
       "c, b, a"),
    _i("""Explain what this Go code does and what the WaitGroup is for:
var wg sync.WaitGroup
results := make(chan int, len(jobs))
for _, j := range jobs {
    wg.Add(1)
    go func(j int) {
        defer wg.Done()
        results <- j * j
    }(j)
}
wg.Wait()
close(results)""",
       "Must explain that each job is squared in its own goroutine, the buffered channel collects results, and WaitGroup blocks until all goroutines finish before the channel is closed."),
    _i("""Explain what this Bash script does line by line:
#!/usr/bin/env bash
set -euo pipefail
for f in "$@"; do
  [[ -f "$f" ]] || { echo "skip $f" >&2; continue; }
  gzip -k "$f"
done""",
       "Must explain set -euo pipefail, iterating over arguments, skipping non-files with a message to stderr, and gzip -k keeping the original file."),
    _i("""Explain why this Python code prints the same number three times and how to fix it:
funcs = [lambda: i for i in range(3)]
print([f() for f in funcs])""",
       "Must explain late binding of the closure variable i, that it prints [2, 2, 2], and show a fix such as a default argument lambda i=i: i.",
       "[2, 2, 2]; fix with lambda i=i: i"),
    _i("""Explain what this TypeScript type does and give an example:
type Optionalize<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;""",
       "Must explain that it makes the listed keys optional while keeping the others required, with a concrete example type."),
    _i("""Explain the memoization in this function and its effect on time complexity:
from functools import lru_cache
@lru_cache(maxsize=None)
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)""",
       "Must explain that cached results turn exponential recursion into linear time with O(n) calls, and mention the recursion depth limit for large n."),
]

CODE_EXPLAIN_PRO: List[Item] = [
    _i("""Analyze this Go worker pool for race conditions and goroutine leaks, then show a corrected version using errgroup:
func process(items []Item) error {
    var firstErr error
    ch := make(chan Item)
    for i := 0; i < 4; i++ {
        go func() {
            for it := range ch {
                if err := handle(it); err != nil {
                    firstErr = err
                    return
                }
            }
        }()
    }
    for _, it := range items {
        ch <- it
    }
    close(ch)
    return firstErr
}""",
       "Must identify the unsynchronized write to firstErr (data race), the send blocking forever once workers exit early (leak/deadlock), the missing wait for workers, and provide an errgroup-based fix with context cancellation."),
    _i("""Review this Rust code for undefined behavior and explain the alignment and aliasing rules it violates:
fn as_u32(bytes: &[u8]) -> u32 {
    unsafe { *(bytes.as_ptr() as *const u32) }
}
fn split_mut(v: &mut Vec<u32>) -> (&mut u32, &mut u32) {
    let p = v.as_mut_ptr();
    unsafe { (&mut *p, &mut *p.add(0)) }
}""",
       "Must identify the unaligned and possibly out-of-bounds read in as_u32 (needs read_unaligned and a length check), and the two aliasing mutable references to the same element in split_mut, explaining Rust's aliasing rules."),
    _i("""Explain why this Python asyncio code can deadlock and how to fix it:
lock = asyncio.Lock()
async def outer():
    async with lock:
        await inner()
async def inner():
    async with lock:
        return 1""",
       "Must explain that asyncio.Lock is not reentrant so inner blocks forever waiting on the lock held by outer, and propose restructuring or passing ownership rather than re-acquiring."),
    _i("""Explain why this Java double-checked locking is broken without volatile and what the memory model guarantees with it:
class Config {
    private static Config instance;
    static Config get() {
        if (instance == null) {
            synchronized (Config.class) {
                if (instance == null) instance = new Config();
            }
        }
        return instance;
    }
}""",
       "Must explain instruction reordering allowing a reference to a partially constructed object to be published, and that volatile establishes a happens-before edge making the pattern correct."),
    _i("""Find the memory safety bug in this C code and explain the consequence:
char *greet(const char *name) {
    char buf[32];
    snprintf(buf, sizeof buf, "hello %s", name);
    return buf;
}
int main(void) {
    char *g = greet("world");
    puts(g);
}""",
       "Must identify returning a pointer to a stack buffer (dangling pointer, use after scope) and explain the undefined behavior, suggesting heap allocation or caller-provided buffer."),
    _i("""Explain how this Node.js code starves the event loop and how to restructure it:
app.get('/report', (req, res) => {
  const rows = loadAllRows();
  let out = '';
  for (const r of rows) out += render(r);
  res.send(out);
});""",
       "Must explain synchronous CPU-bound work blocking all other requests, and propose chunking with setImmediate, streaming, or moving to a worker thread."),
    _i("""Explain the isolation anomaly in this sequence and which isolation level prevents it: Transaction A reads balance = 100. Transaction B reads balance = 100, writes balance = 150, commits. Transaction A writes balance = 100 - 30 = 70, commits.""",
       "Must identify a lost update, explain that read committed permits it, and state that repeatable read with row locking, serializable, or select for update prevents it."),
    _i("""Identify the deadlock in this code and explain the lock-ordering fix:
def transfer(a, b, amount):
    with a.lock:
        with b.lock:
            a.balance -= amount
            b.balance += amount
# Thread 1: transfer(acct1, acct2, 10)
# Thread 2: transfer(acct2, acct1, 5)""",
       "Must explain the circular wait when the two threads acquire the locks in opposite order and propose a global ordering (for example by account id) or a single lock."),
    _i("""Explain how Linux eBPF programs are made safe to run in the kernel: describe the verifier's role, what it rejects, and why maps are the mechanism for communicating with user space.""",
       "Must describe static verification of bounded loops, memory access checks, and helper restrictions, and explain maps as the shared data structure between kernel and user space."),
    _i("""This retry logic causes duplicate charges. Explain why and redesign it around idempotency:
def charge(card, amount):
    for attempt in range(3):
        try:
            return gateway.charge(card, amount)
        except TimeoutError:
            continue
    raise RuntimeError("failed")""",
       "Must explain that a timeout does not mean the charge failed, so retries can charge again, and propose an idempotency key passed to the gateway with the same key on each retry."),
    _i("""Explain the ABA problem in this lock-free stack pop and how a tagged pointer or hazard pointer addresses it:
Node* pop() {
    Node* head = top.load();
    while (head && !top.compare_exchange_weak(head, head->next)) {}
    return head;
}""",
       "Must explain that head can be freed and reallocated between the load and the CAS so the CAS succeeds with a stale next pointer, and explain tagged pointers or hazard pointers as mitigations."),
    _i("""Explain why this Python code leaks memory under a long-running process and how to fix it:
_cache = {}
def handler(request):
    key = (request.user_id, request.body)
    if key not in _cache:
        _cache[key] = compute(request)
    return _cache[key]""",
       "Must explain the unbounded module-level dictionary keyed on request bodies, and propose a bounded LRU, TTL, or keying on a hash with size limits."),
]

# ---------------------------------------------------------------------------
# math_reasoning
# ---------------------------------------------------------------------------

MATH_REASONING_LITE: List[Item] = [
    _i("If a server cluster consumes 450 kWh over 12 hours, what is its average power draw in kilowatts?",
       "Must answer 37.5 kW.", "37.5 kW"),
    _i("Convert 72 degrees Fahrenheit to Celsius, rounded to one decimal place.",
       "Must answer about 22.2 C and may show (72 - 32) * 5/9.", "22.2 C"),
    _i("Calculate the compound interest earned on $1,000 at 5% annual interest for 2 years, compounded annually.",
       "Must answer $102.50 in interest (final amount $1,102.50).", "$102.50"),
    _i("A class of 28 students has 16 girls. What percentage of the class are boys?",
       "Must answer about 42.9%.", "42.9%"),
    _i("What is 15% of 240?", "Must answer 36.", "36"),
    _i("A recipe for 4 people uses 300 g of rice. How much rice is needed for 10 people?",
       "Must answer 750 g.", "750 g"),
    _i("A car travels 180 miles in 3 hours. At the same speed, how long does it take to travel 300 miles?",
       "Must answer 5 hours.", "5 hours"),
    _i("What is the area of a rectangle 7.5 m by 4 m?", "Must answer 30 square meters.", "30 m^2"),
    _i("Find the mean of the numbers 12, 15, 9, 20, and 14.", "Must answer 14.", "14"),
    _i("A store marks a $80 jacket down by 25%. What is the sale price?", "Must answer $60.", "$60"),
    _i("Convert 2.5 hours into minutes.", "Must answer 150 minutes.", "150 minutes"),
    _i("Solve for x: 3x + 7 = 22.", "Must answer x = 5.", "x = 5"),
    _i("A tank holds 500 liters and drains at 20 liters per minute. How long until it is empty?", "Must answer 25 minutes.", "25 minutes"),
    _i("What is the perimeter of a square with side length 9 cm?", "Must answer 36 cm.", "36 cm"),
]

MATH_REASONING_STANDARD: List[Item] = [
    _i("Calculate the probability of drawing at least one ace when drawing 5 cards from a standard 52-card deck without replacement. Show the full derivation.",
       "Must use the complement: 1 - C(48,5)/C(52,5), which is about 0.341, with the steps shown.", "About 0.341"),
    _i("A test for a disease has 95% sensitivity and 90% specificity. The disease affects 2% of the population. If a person tests positive, what is the probability they have the disease? Show your work with Bayes' theorem.",
       "Must compute 0.019 / (0.019 + 0.098) which is about 16.2%, showing prior, true positive, and false positive terms.", "About 16.2%"),
    _i("Solve the system: 2x + 3y = 12 and x - y = 1. Show each step.",
       "Must find x = 3, y = 2 with steps.", "x = 3, y = 2"),
    _i("A loan of $10,000 at 6% annual interest is repaid in equal monthly payments over 3 years. Compute the monthly payment using the amortization formula and show the steps.",
       "Must apply P = L * r / (1 - (1 + r)^-n) with r = 0.005 and n = 36, giving about $304.22.", "About $304.22"),
    _i("Two dice are rolled. What is the probability that the sum is 7 or that at least one die shows a 6? Show the inclusion-exclusion steps.",
       "Must compute 6/36 + 11/36 - 2/36 = 15/36 = 5/12 with reasoning.", "5/12"),
    _i("The population of a town grows 3% per year. Starting at 20,000, how many years until it exceeds 30,000? Show the logarithm calculation.",
       "Must solve 1.03^t > 1.5, t > ln(1.5)/ln(1.03), which is about 13.7, so 14 years.", "14 years"),
    _i("Find the derivative of f(x) = x^2 * e^(3x) and simplify.",
       "Must apply the product rule to get e^(3x) * (2x + 3x^2) or equivalent.", "e^(3x)(3x^2 + 2x)"),
    _i("A rectangle's length is 3 more than twice its width, and its perimeter is 48. Find the dimensions and show the setup.",
       "Must set up 2(w + 2w + 3) = 48, find w = 7 and length 17.", "Width 7, length 17"),
    _i("Compute the expected value of a game where you win $10 with probability 0.2, win $2 with probability 0.5, and lose $5 otherwise. Is it worth playing?",
       "Must compute 2 + 1 - 1.5 = $1.50 and conclude positive expected value.", "$1.50 expected gain"),
    _i("How many distinct arrangements are there of the letters in the word BALLOON? Show the formula.",
       "Must compute 7! / (2! * 2!) = 1260.", "1260"),
    _i("A projectile is launched upward at 20 m/s. Using g = 9.8 m/s^2, find the maximum height and the total time in the air. Show the equations used.",
       "Must find height about 20.4 m and total time about 4.08 s using v^2 = 2gh and t = 2v/g.", "About 20.4 m; about 4.08 s"),
    _i("The mean of a sample of 50 scores is 72 with a standard deviation of 8. Compute a 95% confidence interval for the population mean using z = 1.96, and interpret it.",
       "Must compute 72 +/- 1.96 * 8 / sqrt(50), about (69.8, 74.2), with a correct interpretation.", "About (69.8, 74.2)"),
    _i("Evaluate the integral of (2x + 1)/(x^2 + x + 1) dx and explain the substitution.",
       "Must recognize the numerator as the derivative of the denominator and give ln|x^2 + x + 1| + C.", "ln(x^2 + x + 1) + C"),
]

MATH_REASONING_PRO: List[Item] = [
    _i("Prove that gradient descent with step size alpha < 2/L converges for any L-smooth convex function, and state what is guaranteed about the objective value.",
       "Must use the descent lemma f(y) <= f(x) + grad f(x).(y - x) + (L/2)||y - x||^2 to show monotone decrease for alpha < 2/L, and state the O(1/k) rate for alpha <= 1/L or equivalent."),
    _i("Formulate and prove the Cauchy-Schwarz inequality for a real inner product space, stating the exact condition for equality.",
       "Must construct the quadratic in t from ||u - t v||^2 >= 0, use the discriminant, and show equality holds iff u and v are linearly dependent."),
    _i("Derive the Black-Scholes partial differential equation for a European call using Ito's lemma and a delta-hedged riskless portfolio.",
       "Must apply Ito's lemma to V(S, t), form the portfolio V - (dV/dS) S, eliminate the dW term, equate the return to r, and arrive at V_t + (1/2) sigma^2 S^2 V_SS + r S V_S - r V = 0."),
    _i("Prove that the square root of 2 is irrational, then explain why the same argument shows sqrt(p) is irrational for any prime p.",
       "Must give the standard contradiction argument via parity or prime factorization and generalize it correctly using Euclid's lemma."),
    _i("Show that the sum of the first n odd numbers equals n^2, first by induction and then with a direct combinatorial or geometric argument.",
       "Must give a complete induction proof with base case and inductive step, plus a valid second argument."),
    _i("Prove that every bounded monotone sequence of real numbers converges, and state which property of the reals the proof relies on.",
       "Must use the least upper bound property, show the supremum is the limit via an epsilon argument, and name completeness."),
    _i("Let A be a real symmetric n by n matrix. Prove that its eigenvalues are real and that eigenvectors for distinct eigenvalues are orthogonal.",
       "Must use the conjugate transpose argument for realness and the symmetry of the inner product for orthogonality."),
    _i("Derive the maximum likelihood estimator for the rate parameter of an exponential distribution from n i.i.d. samples, and show the estimator is biased while 1/estimator is unbiased for the mean.",
       "Must derive lambda_hat = n / sum(x_i), show E[lambda_hat] != lambda (for example via the gamma distribution of the sum), and note the sample mean is unbiased for 1/lambda."),
    _i("Prove that the number of primes is infinite, then explain why the argument does not show that the product of the first n primes plus one is itself prime.",
       "Must give Euclid's argument correctly and address the common misconception with a counterexample such as 2*3*5*7*11*13 + 1 = 30031 = 59 * 509."),
    _i("Formulate the optimization problem of fitting a line by least squares, derive the normal equations, and state the condition under which the solution is unique.",
       "Must set up minimizing ||Xb - y||^2, derive X^T X b = X^T y, and state uniqueness requires X to have full column rank."),
]

# ---------------------------------------------------------------------------
# creative
# ---------------------------------------------------------------------------

CREATIVE_LITE: List[Item] = [
    _i("Write a polite three-sentence email to a client informing them their monthly report is ready and attached.",
       "Must be exactly three sentences, polite, and state that the report is ready and attached."),
    _i("Write a warm two-sentence thank-you note to a colleague for covering your shift.",
       "Must be two sentences, express thanks, and mention the shift."),
    _i("Suggest five distinct names for a community coffee shop next to a university library.",
       "Must list five distinct names that fit the library or campus setting."),
    _i("Draft a short out-of-office auto-reply for a one-week vacation, including a return date and an emergency contact placeholder.",
       "Must include a return date, a placeholder emergency contact, and a professional tone."),
    _i("Write a four-line rhyming birthday message for a coworker who loves hiking.",
       "Must be four lines, rhyme, and reference hiking."),
    _i("Write a one-sentence tagline for a reusable water bottle brand.",
       "Must be a single memorable sentence relevant to reusable water bottles."),
    _i("Write a friendly two-sentence reminder to parents that the permission slip is due Friday.",
       "Must be two sentences, friendly, and mention the Friday deadline."),
    _i("Write a three-sentence product description for a lightweight folding umbrella.",
       "Must be three sentences and describe the umbrella's lightness and portability."),
    _i("Write a short LinkedIn headline (under 15 words) for a data analyst who specializes in education.",
       "Must be under 15 words and mention data analysis and education."),
    _i("Compose a two-sentence apology to a customer whose order arrived late, offering a discount code placeholder.",
       "Must be two sentences, apologize for lateness, and include a discount code placeholder."),
    _i("Write a haiku about a quiet library on a rainy afternoon.",
       "Must follow the 5-7-5 syllable pattern and reference the library and rain."),
]

CREATIVE_STANDARD: List[Item] = [
    _i("Write a 300-word opening scene of a science fiction mystery in which an atmospheric surveyor discovers an abandoned orbital station that is still broadcasting.",
       "Must be about 300 words, establish the surveyor and the station, include the broadcast, and end on an unresolved hook."),
    _i("Write a 250-word monologue for a lighthouse keeper on the night the light is automated and they are no longer needed.",
       "Must be about 250 words, stay in first person, and convey the keeper's mixed feelings about obsolescence."),
    _i("Write a 200-word bedtime story for a six-year-old about a snail who is late for everything but arrives exactly when needed.",
       "Must be about 200 words, age-appropriate, and deliver the payoff of arriving at the right moment."),
    _i("Write a persuasive Kickstarter pitch of about 250 words for an ergonomic modular keyboard for programmers, including the problem, the key feature, and a call to action.",
       "Must be about 250 words and include the problem, a specific mechanical or modular feature, and a call to action."),
    _i("Write a 300-word scene in which two strangers stuck in an elevator discover they applied for the same job.",
       "Must be about 300 words, feature dialogue between two distinct voices, and resolve or heighten the tension."),
    _i("Write a 200-word museum placard for a fictional 12th-century astrolabe, in the voice of a curator.",
       "Must be about 200 words, sound like a curator, and describe the object's origin, use, and significance."),
    _i("Write a 250-word letter from a retiring teacher to next year's incoming class of first-year teachers.",
       "Must be about 250 words, warm and specific, and offer at least two concrete pieces of advice."),
    _i("Write a 300-word flash fiction piece told entirely through a group chat between three roommates planning a surprise party that goes wrong.",
       "Must be about 300 words, formatted as chat messages, with three distinct voices and a comedic turn."),
]

CREATIVE_PRO: List[Item] = [
    _i("Write a dramatic philosophical dialogue of about 600 words between a 19th-century epistemologist and a modern neural network architect on the boundary between simulation and understanding. Each character must concede one point.",
       "Must be about 600 words, present two distinct intellectual voices, engage the simulation-versus-understanding question substantively, and include a concession from each."),
    _i("Compose a multi-layered dialogue of about 600 words between Spinoza and Alan Turing debating free will, determinism, and computational substrates, in which each speaker uses the other's framework against him.",
       "Must reflect Spinoza's necessitarianism and Turing's computational views accurately, and show each using the other's framework."),
    _i("Write a literary short story of about 700 words about a deep-sea cartographer who encounters bioluminescent structures that do not obey Euclidean geometry. Use precise sensory detail and avoid explaining the phenomenon.",
       "Must be about 700 words, maintain a literary register, render the geometry through sensory detail, and leave the phenomenon unexplained."),
    _i("Write a sonnet in strict Shakespearean form (three quatrains and a couplet, iambic pentameter, ABAB CDCD EFEF GG) about a machine learning to forget.",
       "Must have 14 lines with the correct rhyme scheme, mostly iambic pentameter, and a volta or turn in the couplet."),
    _i("Write a 500-word piece of nature writing about a single tide pool over one hour, with a structure that mirrors the tide receding and returning.",
       "Must be about 500 words, focused on one tide pool, and have a structure that visibly mirrors the tidal movement."),
    _i("Write a villanelle about insomnia that follows the form exactly: 19 lines, five tercets and a quatrain, two refrains, ABA rhyme scheme.",
       "Must have 19 lines, two correctly placed refrains, and an ABA rhyme scheme throughout."),
    _i("Write a 600-word short story told in second person, present tense, in which the reader is a translator who realizes mid-negotiation that one side is lying.",
       "Must sustain second-person present tense, maintain tension around the lie, and resolve the translator's dilemma in about 600 words."),
    _i("Write a metaphorical essay of about 500 words that explains technical debt to a non-technical reader using a single extended metaphor that is not a financial one.",
       "Must be about 500 words, use one sustained non-financial metaphor, and accurately convey what technical debt is and why it accrues."),
    _i("Write a 600-word dialogue between a grief counselor and an AI that has been trained on a deceased person's messages, in which the counselor is the one who becomes unsettled.",
       "Must be about 600 words, give both speakers credible voices, and shift the emotional weight to the counselor by the end."),
    _i("Write a prose poem of about 300 words in the voice of a river being dammed, without using the words water, flow, or stop.",
       "Must be about 300 words, in the river's voice, and must not contain the words water, flow, or stop."),
    _i("Write a satirical 500-word op-ed from the year 2090 arguing that people should return to typing on keyboards, in the style of a nostalgia column.",
       "Must be about 500 words, sustain a satirical nostalgic tone, and build a coherent argument."),
    _i("Write a 600-word scene in which three generations of a family argue over a recipe, where the argument is really about something else that is never named.",
       "Must be about 600 words, feature three distinct generational voices, and convey the unnamed subtext through the recipe argument."),
    _i("Write a ghazal of at least seven couplets on the theme of exile, with a consistent radif and a signature couplet naming the poet.",
       "Must have at least seven autonomous couplets, a repeated radif at the end of each second line, and a final signature couplet."),
    _i("Write a 500-word story in which every paragraph is exactly one sentence long, about an astronaut's last hour before re-entry.",
       "Must be about 500 words with each paragraph a single sentence, and sustain narrative momentum."),
    _i("Write a 600-word Socratic dialogue between a physician and an algorithm-ethicist about whether a triage model should be allowed to consider age, ending without a settled answer.",
       "Must be about 600 words, present real arguments on both sides, and end genuinely unresolved."),
    _i("Write a piece of about 400 words describing a city from the point of view of its oldest bridge, structured as a series of dated entries spanning 150 years.",
       "Must be about 400 words, use dated entries spanning about 150 years, and keep the bridge's perspective consistent."),
    _i("Write a 500-word short story that is a single continuous sentence, about a courier delivering a letter that is addressed to themselves.",
       "Must be one grammatical sentence of about 500 words that remains readable and completes the story."),
    _i("Write a dramatic monologue of about 500 words for a retired chess grandmaster addressing the engine that ended their career, in blank verse.",
       "Must be about 500 words of mostly unrhymed iambic pentameter, in a consistent voice, addressing the engine directly."),
]

BANK: Dict[str, Dict[str, List[Item]]] = {
    "rubric_parse": {"lite": RUBRIC_PARSE_LITE, "standard": RUBRIC_PARSE_STANDARD, "pro": RUBRIC_PARSE_PRO},
    "diagram_gen": {"lite": DIAGRAM_GEN_LITE, "standard": DIAGRAM_GEN_STANDARD, "pro": DIAGRAM_GEN_PRO},
    "doc_qa": {"lite": DOC_QA_LITE, "standard": DOC_QA_STANDARD, "pro": DOC_QA_PRO},
    "classify": {"lite": CLASSIFY_LITE, "standard": CLASSIFY_STANDARD, "pro": CLASSIFY_PRO},
    "summarize": {"lite": SUMMARIZE_LITE, "standard": SUMMARIZE_STANDARD, "pro": SUMMARIZE_PRO},
    "code_explain": {"lite": CODE_EXPLAIN_LITE, "standard": CODE_EXPLAIN_STANDARD, "pro": CODE_EXPLAIN_PRO},
    "math_reasoning": {"lite": MATH_REASONING_LITE, "standard": MATH_REASONING_STANDARD, "pro": MATH_REASONING_PRO},
    "creative": {"lite": CREATIVE_LITE, "standard": CREATIVE_STANDARD, "pro": CREATIVE_PRO},
}


def build_items() -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    seen_prompts = set()
    next_id = 1
    for cat in CATEGORIES:
        for tier in TIERS:
            bank = BANK[cat][tier]
            expected = ALLOCATIONS[cat][tier]
            if len(bank) != expected:
                raise SystemExit(f"{cat}/{tier}: bank has {len(bank)} items, allocation expects {expected}")
            for prompt, rubric, reference in bank:
                if prompt in seen_prompts:
                    raise SystemExit(f"Duplicate prompt in {cat}/{tier}: {prompt[:60]}...")
                seen_prompts.add(prompt)
                entries.append({
                    "id": f"g_{next_id:04d}",
                    "category": cat,
                    "expected_tier": tier,
                    "prompt": prompt,
                    "system": None,
                    "json_schema": None,
                    "reference": reference,
                    "rubric": rubric,
                    "reviewed": True,
                    "source": f"seed:{cat}_{tier}",
                })
                next_id += 1
    return entries


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "eval/golden/golden_set.jsonl"
    entries = build_items()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for item in entries:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    by_tier = {t: sum(1 for e in entries if e["expected_tier"] == t) for t in TIERS}
    print(f"Wrote {len(entries)} items to {out_path}: {by_tier}")


if __name__ == "__main__":
    main()
