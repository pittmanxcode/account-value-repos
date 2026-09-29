#!/usr/bin/env python3
"""Crunchyroll x Factory value model.

Assigns every verbatim responsibility bullet to a normalized cluster, maps each
posting to a US occupation and seniority (BLS May 2025 wage data via O*NET),
allocates 1,920 role-hours per posting across clusters, and computes
conservative/base/upside saved hours under the normal-setup and bespoke
deployment boundaries defined in methodology/rubric.md.

Inputs:  data/processed/jobs.csv, data/processed/responsibilities.csv
Outputs: data/processed/responsibilities_normalized.csv
         data/processed/scored_responsibilities.csv
         data/processed/role_summary.csv
         data/processed/cluster_ranking.csv
"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"

ANNUAL_HOURS = 1920          # 40 h x 48 weeks, editable assumption
LOADED_FACTOR = 1.30         # fully loaded cost view
ADOPTION = {"conservative": 0.50, "base": 0.75, "upside": 0.90}

# --------------------------------------------------------------------------
# 1. Normalized responsibility taxonomy
#    fit_normal / fit_bespoke: 0-100 Factory fit per methodology/rubric.md
#    addressable: share of cluster hours an agent could own end-to-end
#    tred: net time reduction on addressable time (conservative, base, upside)
# --------------------------------------------------------------------------
C = [
    dict(key="tax_sox", label="Tax, SOX & Audit Compliance",
         pat=r"\btax\b|sox|\baudits?\b|compliance testing|control (design|testing|owner)|internal controls?|regulator|filing|vat|gst|e-?invoic",
         fit_n=55, fit_b=75, bespoke="Read-only ERP/tax-engine connectors plus a regulated-output review harness",
         addr=0.45, tred=(0.18, 0.28, 0.40),
         basis="Per filing cycle (monthly/quarterly, annualized)", time_src="O*NET 13-2011 work activity structure",
         conf="Medium",
         rationale="Drafting workpapers, legislation monitoring and control documentation are digitizable, but filings, sign-off and professional judgment stay human.",
         workflow="Droid drafts workpapers, monitors regulation changes, prepares control matrices; human reviewer approves filings",
         checkpoint="Licensed professional approves every filing and control conclusion"),

    dict(key="security_eng", label="Security & Identity Engineering",
         pat=r"secur|vulnerab|threat|appsec|owasp|pentest|penetration|\biam\b|\bsso\b|identity (platform|governance|engineer)|encryption|zer(o| )day|fraud detection",
         fit_n=70, fit_b=82, bespoke="Security tooling APIs (SIEM, SAST/DAST, IdP) via MCP servers with least-privilege scopes",
         addr=0.60, tred=(0.18, 0.30, 0.42),
         basis="Continuous (per-sprint activity, annualized)", time_src="O*NET 15-1212 work activities",
         conf="Medium",
         rationale="Code-level security work, vuln triage and tooling automation fit Factory well; pen-testing decisions and sign-off remain human.",
         workflow="Droid triages findings, drafts remediations, automates scans; security engineer approves changes",
         checkpoint="Security engineer approves all remediations and policy exceptions"),

    dict(key="ml_eng", label="ML & AI Engineering",
         pat=r"machine learning|mlops|\bmodel\b|llm|gen ?.?ai|recommendation|\bfraud\b|ai runtime|data science platform|experiment track",
         fit_n=82, fit_b=90, bespoke="MLflow/feature-store APIs and model-registry MCP integration",
         addr=0.70, tred=(0.22, 0.35, 0.50),
         basis="Continuous (per-model lifecycle, annualized)", time_src="O*NET 15-2051 work activities",
         conf="Medium",
         rationale="Pipeline code, experiment tracking, evaluation harnesses and model promotion automation are core Factory strengths; problem framing stays human.",
         workflow="Droid builds pipelines/evals, tracks experiments, prepares promotion; human data scientist reviews",
         checkpoint="Data scientist approves model promotion and evaluation thresholds"),

    dict(key="deal_admin", label="Contracts, Rights & Royalty Administration",
         pat=r"contract|deal terms|agreement|\brights\b|licen[cs]|royalt|approval workflow|approvals? process|tracking (deal|system)",
         fit_n=75, fit_b=85, bespoke="CLM (contract lifecycle) system connector with redline-and-review workflow",
         addr=0.60, tred=(0.25, 0.38, 0.52),
         basis="Per contract/deal event, annualized", time_src="O*NET 13-1111 work activities",
         conf="Medium",
         rationale="Deal abstraction, term tracking, obligation checklists and royalty-system setup are highly digitizable; negotiation and execution are not.",
         workflow="Droid extracts terms, maintains trackers, drafts checklists; business-affairs staff approve",
         checkpoint="Deal owner approves abstracts and outbound commitments"),

    dict(key="sourcing", label="Procurement & Strategic Sourcing",
         pat=r"sourcing|procure|\bvendor\b|supplier (selection|management)|\brfp\b|\brfx\b|negotiat|purchase order",
         fit_n=45, fit_b=65, bespoke="S2P (source-to-pay) platform connector for intake and supplier data",
         addr=0.35, tred=(0.15, 0.25, 0.35),
         basis="Per sourcing event/quarter, annualized", time_src="O*NET 11-3061 work activities",
         conf="Low-Medium",
         rationale="Market scans, RFP logistics and spend analysis automate well; negotiation and relationship leverage stay human.",
         workflow="Droid assembles market scans, manages RFP logistics, models spend; category manager negotiates",
         checkpoint="Category manager leads negotiations and awards"),

    dict(key="localization", label="Localization & Creative Adaptation",
         pat=r"translat|subtitl|localiz|script (edit|adapt)|japanese and english|language version|dub",
         fit_n=60, fit_b=80, bespoke="TMS (translation management) connector plus terminology/style-guide fine-tune",
         addr=0.50, tred=(0.20, 0.32, 0.45),
         basis="Per title/episode volume, annualized", time_src="O*NET 27-3043 work activities",
         conf="Medium",
         rationale="First-pass translation and script prep accelerate strongly; nuance, comedy timing and final creative QA stay human for brand quality.",
         workflow="Droid produces first-pass adaptations with glossary; editor performs creative QA",
         checkpoint="Editorial lead approves language quality"),

    dict(key="crm_ops", label="CRM & Lifecycle Marketing Operations",
         pat=r"\bcrm\b|braze|email (campaign|program)|push notification|segmentation|lifecycle|customer journey|martech|marketing automation|a/?b test|subject line|send-?time",
         fit_n=78, fit_b=88, bespoke="ESP/CDP (Braze-class) connector with approval-gated send workflow",
         addr=0.70, tred=(0.25, 0.40, 0.55),
         basis="Per campaign cycle, annualized", time_src="O*NET 11-2021 work activities",
         conf="Medium-High",
         rationale="Segment building, template QA, journey logic and reporting are agent-friendly; brand voice approval and sends stay gated.",
         workflow="Droid builds segments/journeys, drafts copy variants, assembles reports; marketer approves sends",
         checkpoint="Marketing manager approves audience and creative before send"),

    dict(key="accounting_tx", label="Accounting Operations (AP, Reconciliations)",
         pat=r"invoice|accounts payable|reconcil|journal|ledger|payment|aging|purchase (order|sub)?|expense",
         fit_n=78, fit_b=88, bespoke="ERP (NetSuite/SAP-class) connector with maker-checker payment controls",
         addr=0.70, tred=(0.30, 0.45, 0.60),
         basis="Per accounting period (monthly, annualized)", time_src="O*NET 43-3031 work activities",
         conf="Medium-High",
         rationale="Invoice matching, aging analysis, documentation chase and reconciliation prep are classic automation targets; payment release stays human.",
         workflow="Droid codes invoices, prepares reconciliations, chases exceptions; accountant approves entries",
         checkpoint="Accountant approves journal entries and payments"),

    dict(key="fin_modeling", label="Financial Analysis & Modeling",
         pat=r"financial (model|analysis|planning|forecast|report)|fp&a|\bbudget\b|p&l|m&a|investment (analysis|opportunit)|pricing analysis|variance|board (meeting|pack)",
         fit_n=85, fit_b=90, bespoke="FP&A platform / ERP data MCP connector for refreshable models",
         addr=0.70, tred=(0.25, 0.38, 0.52),
         basis="Per reporting cycle (monthly/quarterly, annualized)", time_src="O*NET 13-2051 work activities",
         conf="Medium-High",
         rationale="Model construction, scenario building, variance narratives and deck production are core Droid strengths; interpretation and recommendations get human review.",
         workflow="Droid builds/updates models, drafts variance commentary and decks; analyst reviews outputs",
         checkpoint="Finance lead validates assumptions and outputs"),

    dict(key="analytics_bi", label="Analytics, Reporting & Dashboards",
         pat=r"analy(tics|ze|sis)|report(ing)?|dashboard|tableau|looker|\bkpi\b|metric|insight|forecast|voice of the customer|\bvoc\b|csat|\bnps\b|survey",
         fit_n=90, fit_b=94, bespoke="Warehouse/BI MCP connector for governed query execution",
         addr=0.80, tred=(0.30, 0.45, 0.60),
         basis="Per reporting cycle/ad-hoc request, annualized", time_src="O*NET 13-1161 work activities",
         conf="High",
         rationale="SQL/BI development, metric definition, executive-ready visualization and written analysis are among the strongest agent workflows.",
         workflow="Droid writes queries, builds dashboards, drafts insight memos; analyst validates numbers",
         checkpoint="Analyst validates data lineage and conclusions"),

    dict(key="data_eng", label="Data Engineering & Pipelines",
         pat=r"data pipeline|\betl\b|\belt\b|data (engineer|ingest|warehouse|quality)|\bdbt\b|airflow|dataset|telemetry into",
         fit_n=88, fit_b=93, bespoke="Orchestration/warehouse deployment credentials with change review",
         addr=0.80, tred=(0.28, 0.42, 0.58),
         basis="Continuous (per-sprint activity, annualized)", time_src="O*NET 15-1252 work activities",
         conf="High",
         rationale="Pipeline development, data-quality checks and orchestration code are core Droid work, verified by tests and review.",
         workflow="Droid develops pipelines/tests in repo, raises reviewed PRs; engineer merges",
         checkpoint="Engineer reviews and merges pipeline changes"),

    dict(key="sw_dev", label="Software Development & Code Review",
         pat=r"\bcode\b|coding|\bapi\b|backend|back.?end|front.?end|full.?stack|software|debug|refactor|pull request|code review|feature|android|ios\b|swift|kotlin|playback|media delivery|entitlement|sdk|architect",
         fit_n=90, fit_b=95, bespoke="Not required beyond standard repo/CI access",
         addr=0.75, tred=(0.25, 0.40, 0.55),
         basis="Continuous (per-sprint activity, annualized)", time_src="pandev-metrics 2026 IDE telemetry (3.2h code + 1.8h debug/day)",
         conf="High",
         rationale="Droid's core competency: implementation, debugging, refactoring and code review with human review through PRs.",
         workflow="Droid implements in repo with tests, opens PRs; engineer reviews and merges",
         checkpoint="Engineer reviews and merges every change"),

    dict(key="qa_testing", label="Test Automation & QA",
         pat=r"\btest|qa\b|quality assurance|sdet|regression|test pyramid|defect|\bbug\b|automation framework",
         fit_n=92, fit_b=95, bespoke="Device farm / emulator grid access for mobile test execution",
         addr=0.85, tred=(0.30, 0.45, 0.60),
         basis="Continuous (per-sprint activity, annualized)", time_src="pandev-metrics 2026 debugging telemetry",
         conf="High",
         rationale="Test authoring, maintenance, and flake triage are highly automatable with verifiable outputs.",
         workflow="Droid authors/maintains test suites and reproduces failures; engineer reviews coverage",
         checkpoint="Engineer reviews coverage and release go/no-go"),

    dict(key="cicd_devops", label="CI/CD & DevOps Automation",
         pat=r"ci/?cd|build (pipeline|process|and deployment)|deployment|deploy\b|infrastructure as code|terraform|kubernetes|docker|devops|release process|rollout",
         fit_n=88, fit_b=92, bespoke="Cluster/registry credentials scoped via sandbox policy",
         addr=0.85, tred=(0.30, 0.45, 0.60),
         basis="Continuous (per-release cadence, annualized)", time_src="O*NET 15-1252 work activities",
         conf="High",
         rationale="Pipeline-as-code, environment automation and release tooling are scriptable end-to-end with human gates on production.",
         workflow="Droid maintains pipelines/IaC, automates release tasks; engineer approves production deploys",
         checkpoint="Engineer approves production deployments"),

    dict(key="sre_incident", label="Reliability, Incident Response & Capacity",
         pat=r"incident|on.?call|post.?mortem|root cause|availability|reliability|\bslo\b|\bsla\b|disaster recovery|business continuity|capacity planning|toil|production issue|escalation|outage|degrad",
         fit_n=75, fit_b=85, bespoke="Read-only observability stack (metrics/logs/traces) MCP integration",
         addr=0.60, tred=(0.20, 0.32, 0.45),
         basis="Continuous (on-call rotation and per-incident, annualized)", time_src="O*NET 15-1244 work activities",
         conf="Medium",
         rationale="Postmortem drafting, alert review, runbook automation and capacity analysis fit Factory; incident command and production access stay human.",
         workflow="Droid drafts postmortems/runbooks, triages alerts, automates toil; SRE commands incidents",
         checkpoint="SRE leads incident command and approves remediation"),

    dict(key="observability", label="Monitoring & Observability Engineering",
         pat=r"monitor|observab|alert(ing)?\b|telemetry|drift|degradation|anomaly detection|signal",
         fit_n=85, fit_b=90, bespoke="Observability platform API connector",
         addr=0.80, tred=(0.25, 0.40, 0.55),
         basis="Continuous (per-service, annualized)", time_src="O*NET 15-1244 work activities",
         conf="High",
         rationale="Instrumentation code, alert-rule authoring and signal pipelines are code-first and verifiable.",
         workflow="Droid instruments services and authors alert rules; engineer reviews thresholds",
         checkpoint="Engineer reviews alert rules and thresholds"),

    dict(key="database", label="Database Engineering & Operations",
         pat=r"database|\bsql\b|query (optimization|performance)|schema|\bdba\b|data model|migration",
         fit_n=80, fit_b=88, bespoke="Controlled DB access via change-management integration",
         addr=0.70, tred=(0.22, 0.35, 0.50),
         basis="Continuous (per-change/per-quarter maintenance, annualized)", time_src="O*NET 15-1243 work activities",
         conf="Medium-High",
         rationale="Schema design, query tuning and migration scripting are strong Droid work; production data changes stay gated.",
         workflow="Droid designs schemas, tunes queries, scripts migrations with tests; engineer approves changes",
         checkpoint="Engineer approves production data changes"),

    dict(key="cloud_infra", label="Cloud & Infrastructure Engineering",
         pat=r"\bcloud\b|infrastructure|\bnetwork(ing)?\b|\baws\b|\bgcp\b|\bazure\b|scaling|server|compute|storage",
         fit_n=80, fit_b=88, bespoke="Cloud account access scoped through permission rules and sandboxing",
         addr=0.70, tred=(0.22, 0.35, 0.50),
         basis="Continuous (per-sprint activity, annualized)", time_src="O*NET 15-1243 work activities",
         conf="Medium-High",
         rationale="IaC, network policy as code and cost/performance analysis suit Droid; production operations stay human-gated.",
         workflow="Droid authors IaC and analysis; engineer reviews and applies",
         checkpoint="Engineer approves infrastructure changes"),

    dict(key="content_ops", label="Content Operations & Metadata",
         pat=r"metadata|content (deliver|operat|supply)|distribution|delivery validation|asset (management|validation|qc)|ingest( of)? content|\bqc\b|launch readiness|delivery operations",
         fit_n=80, fit_b=88, bespoke="Internal delivery/metadata platform API connectors",
         addr=0.70, tred=(0.28, 0.42, 0.58),
         basis="Per title/delivery volume, annualized", time_src="O*NET 13-1111 work activities",
         conf="Medium-High",
         rationale="Metadata QA, delivery validation, issue tracking and partner notification are structured, verifiable workflows.",
         workflow="Droid validates deliveries, syncs metadata, triages issues; ops specialist approves exceptions",
         checkpoint="Ops specialist approves exceptions and partner comms"),

    dict(key="prod_coord", label="Production & Vendor Coordination",
         pat=r"producer|production (schedule|coordinat|management)|coordinat(e|ion) (with|of)|third.?party (studio|production)|vendor (management|relation)|shoot|production company|associate producer",
         fit_n=55, fit_b=70, bespoke="Project-management platform connector with vendor-facing artifacts",
         addr=0.40, tred=(0.15, 0.25, 0.35),
         basis="Per production milestone, annualized", time_src="O*NET 27-2012 work activities",
         conf="Low-Medium",
         rationale="Schedule tracking, deliverable checklists and status packs automate; studio relationships and creative supervision do not.",
         workflow="Droid maintains schedules, trackers and status packs; producer manages relationships",
         checkpoint="Producer approves external comms and creative decisions"),

    dict(key="cx_ops", label="CX Operations & Support Analytics",
         pat=r"customer (support|service|experience) (metric|performance|operation)|ticket|contact center|case management|salesforce|knowledge (base|article)|csat|\bnps\b|service level|support agent|quality (review|score)|escalat|fan (inquiry|complaint)|self.?service",
         fit_n=85, fit_b=90, bespoke="Helpdesk (Zendesk/Salesforce-class) connector with human-gated replies",
         addr=0.70, tred=(0.28, 0.42, 0.58),
         basis="Per ticket volume/shift, annualized", time_src="O*NET 43-4051 work activities",
         conf="High",
         rationale="Ticket analytics, macro/KB authoring, QA scoring and routing logic are strong agent workflows; live sensitive conversations stay human.",
         workflow="Droid analyzes tickets, authors KB/macros, scores QA; CX lead approves customer-facing content",
         checkpoint="CX lead approves customer-facing content"),

    dict(key="training", label="Training, Enablement & Documentation",
         pat=r"training|instructional design|onboarding (material|program)|\bsop\b|documentation for|enable(ment)?|curriculum|elearning|course|playbook|wiki",
         fit_n=85, fit_b=90, bespoke="LMS authoring connector",
         addr=0.75, tred=(0.30, 0.45, 0.60),
         basis="Per program/course cycle, annualized", time_src="O*NET 13-1151 work activities",
         conf="High",
         rationale="Curriculum drafts, SOPs, scripts and assessments are classic generation tasks verified by SME review.",
         workflow="Droid drafts curricula, SOPs and assessments from SME input; designer reviews",
         checkpoint="SME/designer reviews before publication"),

    dict(key="pm_program", label="Program & Project Management",
         pat=r"program manage|project manage|roadmap|\bagile\b|scrum|sprint|backlog|ceremonies|\buat\b|stakeholder (sync|update|align|manage)|timeline|workstream|raisd?|status (report|update)",
         fit_n=72, fit_b=82, bespoke="Work-management platform (Jira/Asana-class) connector",
         addr=0.50, tred=(0.20, 0.32, 0.45),
         basis="Per program cadence (weekly ceremonies, annualized)", time_src="O*NET 13-1082 work activities",
         conf="Medium",
         rationale="Status automation, RAID logs, dependency tracking and documentation lift PMs; leadership alignment and negotiation stay human.",
         workflow="Droid automates status, risks, dependencies and reporting; PM drives alignment",
         checkpoint="PM validates status accuracy and drives decisions"),

    dict(key="strategy_exec", label="Strategy, Market & Competitive Analysis",
         pat=r"strateg|market (research|trend|sizing)|competitor|business case|executive (presentation|ready)|board|opportunity assessment|annual (plan|operating)|operating rhythm|\bokr\b|objective",
         fit_n=70, fit_b=80, bespoke="Paid data-source connectors (market intelligence)",
         addr=0.55, tred=(0.20, 0.32, 0.45),
         basis="Per planning cycle (quarterly/annual, annualized)", time_src="O*NET 13-1111 work activities",
         conf="Medium",
         rationale="Research synthesis, market scans and deck production accelerate; strategic judgment and exec relationships stay human.",
         workflow="Droid researches, synthesizes and drafts analyses/decks; strategist refines positioning",
         checkpoint="Strategy lead validates recommendations"),

    dict(key="partnership", label="Partnership & Relationship Management",
         pat=r"partner(ship)? (manager|relationship|performance|review|meeting)|account (manage|owner)|distributor relation|licensee relation|\bqbr\b",
         fit_n=40, fit_b=60, bespoke="CRM partnership workspace connector",
         addr=0.30, tred=(0.12, 0.20, 0.30),
         basis="Per partner review cycle, annualized", time_src="O*NET 11-2021 work activities",
         conf="Low",
         rationale="Prep material and performance reporting automate; the relationship itself is human-owned.",
         workflow="Droid prepares QBR packs and performance analyses; manager leads the relationship",
         checkpoint="Partnership owner leads all partner interactions"),

    dict(key="legal_affairs", label="Legal, Business Affairs & Content Protection",
         pat=r"\blegal\b|draft|negotiat|counsel|piracy|copyright|takedown|enforcement|litigation|intellectual property|\bip\b protection|licensing agreement|merchandise licensing",
         fit_n=35, fit_b=55, bespoke="CLM + anti-piracy platform connectors for evidence packs",
         addr=0.30, tred=(0.12, 0.20, 0.30),
         basis="Per matter/agreement, annualized", time_src="O*NET 23-1011 work activities",
         conf="Low-Medium",
         rationale="Research, first drafts and evidence gathering assist counsel; legal judgment, privilege and negotiation are human obligations.",
         workflow="Droid researches, drafts first passes, compiles evidence; counsel reviews and owns output",
         checkpoint="Counsel reviews everything; nothing is filed or sent without approval"),

    dict(key="people_hr", label="People, Talent & Internal Communication",
         pat=r"hiring|interview|people (strategy|operation|partner)|coach|mentor|performance (review|management)|team build|culture|human resources|\bhr\b|one.?on.?one|feedback|internal communication|town hall|engagement survey|grow(th)? of (the )?team",
         fit_n=40, fit_b=55, bespoke="HRIS + comms platform connectors",
         addr=0.35, tred=(0.15, 0.25, 0.35),
         basis="Per HR cycle (quarterly/annual, annualized)", time_src="O*NET 11-3121 work activities",
         conf="Low-Medium",
         rationale="Comms drafts, survey analysis and process documentation help; trust-building, coaching and judgment calls are human.",
         workflow="Droid drafts comms, analyzes surveys, documents processes; people lead reviews",
         checkpoint="People lead approves anything employee-facing"),

    dict(key="creative_design", label="Creative & Product Design",
         pat=r"design (direction|guideline|system|of )|creative (direction|concept|execution)|art direction|illustrat|\bbrand\b (design|guideline)|product design|prototype|figure design|\bdesigner\b",
         fit_n=35, fit_b=60, bespoke="Design-tool (Figma-class) connector for iteration loops",
         addr=0.30, tred=(0.12, 0.20, 0.30),
         basis="Per design cycle/project, annualized", time_src="O*NET 27-1024 work activities",
         conf="Low",
         rationale="Explorations, production variants and spec docs accelerate; taste-led brand decisions stay with the designer.",
         workflow="Droid produces explorations, variants and spec documentation; designer curates and decides",
         checkpoint="Designer makes all final creative decisions"),

    dict(key="workplace", label="Workplace & Facilities",
         pat=r"workplace|facilit|office (space|event|experience)|visitor|amenities|reception|on.?site event",
         fit_n=20, fit_b=40, bespoke="Facilities/IoT system connectors",
         addr=0.10, tred=(0.05, 0.10, 0.15),
         basis="Continuous on-site operations, annualized", time_src="O*NET 11-3013 work activities",
         conf="Low",
         rationale="Overwhelmingly physical and in-person work; only scheduling and vendor paperwork are digitizable.",
         workflow="Droid assists with scheduling, vendor paperwork and signage drafts only",
         checkpoint="Workplace manager owns all physical execution"),

    dict(key="supply_physical", label="Physical Supply Chain & Manufacturing",
         pat=r"manufactur|factory|logistic|shipment|freight|tooling|packaging|warehouse|\bsku\b|goods|product (sample|development for physical)|inventory management for physical|collectible production",
         fit_n=25, fit_b=45, bespoke="ERP/supply-chain platform connectors for planning data",
         addr=0.20, tred=(0.08, 0.15, 0.22),
         basis="Per production run/season, annualized", time_src="O*NET 11-3061 work activities",
         conf="Low",
         rationale="Planning spreadsheets and spec docs digitize; factory floors, samples and logistics do not.",
         workflow="Droid maintains planning models, specs and trackers; manager owns physical execution",
         checkpoint="Supply chain manager owns vendor and factory execution"),

    dict(key="other_generalist", label="Cross-Functional Collaboration & Generalist Duties",
         pat=r".*",
         fit_n=50, fit_b=65, bespoke="Case-by-case; assessed individually",
         addr=0.40, tred=(0.20, 0.32, 0.45),
         basis="Mixed cadence, annualized", time_src="O*NET general work activities",
         conf="Low",
         rationale="Catch-all for collaboration, culture and unclassified duties; average automatability with human coordination.",
         workflow="Assessed individually per bullet",
         checkpoint="Reviewing manager defines approval path"),
]

NOISE_PAT = re.compile(
    r"^(in the role of|we are (considering|seeking|looking)|founded by fans|join (our|us)|"
    r".*(you will report to|report to the)|equal opportunity|eoe\b|crunchyroll is (an|the)|"
    r".*\bour benefits\b|total rewards|applicants for)", re.I)

# --------------------------------------------------------------------------
# 2. Role -> occupation/seniority mapping (US-equivalent pay basis)
# --------------------------------------------------------------------------
LEVELS = {"entry": 0.80, "mid": 0.90, "senior": 1.10, "lead": 1.25,
          "staff": 1.50, "manager": 1.35, "director": 1.60, "exec": 2.00}

OCC_LABELS = {
    "11-1021.00": "General and Operations Managers",
    "11-2021.00": "Marketing Managers",
    "11-3013.00": "Facilities Managers",
    "11-3021.00": "Computer and Information Systems Managers",
    "11-3031.00": "Financial Managers",
    "11-3061.00": "Purchasing Managers",
    "11-3121.00": "Human Resources Managers",
    "13-1082.00": "Project Management Specialists",
    "13-1111.00": "Management Analysts",
    "13-1151.00": "Training and Development Specialists",
    "13-1161.00": "Market Research Analysts",
    "13-2011.00": "Accountants and Auditors",
    "13-2051.00": "Financial and Investment Analysts",
    "15-1212.00": "Information Security Analysts",
    "15-1243.00": "Database Architects and Engineers",
    "15-1244.00": "Network and Computer Systems Administrators",
    "15-1252.00": "Software Developers",
    "15-2051.00": "Data Scientists",
    "23-1011.00": "Lawyers",
    "27-1011.00": "Art Directors",
    "27-1024.00": "Graphic Designers",
    "27-2012.00": "Producers and Directors",
    "27-3031.00": "Public Relations Specialists",
    "27-3043.00": "Editors",
    "43-3031.00": "Bookkeeping and Accounting Clerks",
    "43-4051.00": "Customer Service Representatives",
    "43-6014.00": "Secretaries and Administrative Assistants",
}

# BLS May 2025 median annual wages, national (via O*NET, harvested into
# data/raw/onet_wages_2025.txt; 15-1252 read directly).
OCC_WAGE = {}
for line in (ROOT / "data" / "raw" / "onet_wages_2025.txt").read_text().splitlines():
    m = re.match(r"([\d.-]+) :: .*?([\d,]+) annual", line)
    if m:
        OCC_WAGE[m.group(1)] = int(m.group(2).replace(",", ""))
OCC_WAGE["15-1252.00"] = 135980  # harvested in initial probe

TITLE_MAP = {
    "シニア・プロデューサー、アニメコープロダクション": ("27-2012.00", "senior"),
    "Senior Producer, Anime Co-Production": ("27-2012.00", "senior"),
    "Accounting Director - Mexico": ("11-3031.00", "director"),
    "Accounts Payable Analyst": ("43-3031.00", "mid"),
    "Associate Approvals Manager": ("13-1111.00", "mid"),
    "Business Affairs Associate I": ("13-1111.00", "entry"),
    "Corporate Strategy Senior Analyst": ("13-1111.00", "senior"),
    "Creative Executive": ("27-1011.00", "exec"),
    "CX Operations Analyst": ("13-1161.00", "mid"),
    "Data Engineer III": ("15-1252.00", "senior"),
    "Deal Management Analyst": ("13-2051.00", "mid"),
    "Deal Management Senior Analyst": ("13-2051.00", "senior"),
    "Delivery Operations Coordinator": ("43-6014.00", "mid"),
    "Designer - Collectibles": ("27-1024.00", "mid"),
    "Director, AI Enablement": ("11-3021.00", "director"),
    "Director, People Strategy & Partnership": ("11-3121.00", "director"),
    "Director, Product Security": ("15-1212.00", "director"),
    "General Manager, Latin America (LATAM)": ("11-1021.00", "exec"),
    "GTM Programs, Senior Manager - UCANZ - Membership Value (Contract)": ("11-2021.00", "manager"),
    "Internal Communications Senior Manager": ("27-3031.00", "manager"),
    "Lead Finance Data Analyst": ("15-2051.00", "lead"),
    "Lead Financial Business Analyst": ("13-2051.00", "lead"),
    "Manager, GTM - UCANZ (Contract)": ("11-2021.00", "manager"),
    "Metadata Manager": ("13-1111.00", "manager"),
    "Paid Social Senior Manager": ("11-2021.00", "manager"),
    "Principal Engineer, Engineering Practices": ("15-1252.00", "staff"),
    "Principal Technical Program Manager, Enterprise Technology": ("13-1082.00", "staff"),
    "Salesforce Technical Administrator": ("15-1244.00", "mid"),
    "Security Analyst": ("15-1212.00", "mid"),
    "Senior AI Engineer": ("15-1252.00", "senior"),
    "Senior CX Analytics Manager": ("13-1161.00", "manager"),
    "Senior CX Insights Manager, LATAM": ("13-1161.00", "manager"),
    "Senior Database Engineer": ("15-1243.00", "senior"),
    "Senior Database Operations Engineer": ("15-1243.00", "senior"),
    "Senior Database Reliability Engineer": ("15-1243.00", "senior"),
    "Senior Engineer, Insights & Reliability Engineering": ("15-1252.00", "senior"),
    "Senior Identity Engineer": ("15-1212.00", "senior"),
    "Senior Instructional Designer, Customer Experience": ("13-1151.00", "senior"),
    "Senior IT Engineer, SaaS Applications": ("15-1244.00", "senior"),
    "Senior Machine Learning Engineer, Fraud Detection": ("15-2051.00", "senior"),
    "Senior Manager, CRM Marketing, APAC": ("11-2021.00", "manager"),
    "Senior Manager, CRM Marketing, Europe": ("11-2021.00", "manager"),
    "Senior Manager, Global Partnerships": ("11-2021.00", "manager"),
    "Senior MLOps Engineer": ("15-1252.00", "senior"),
    "Senior Program Manager": ("13-1082.00", "senior"),
    "Senior Program Manager - Customer Experience": ("13-1082.00", "senior"),
    "Senior Security Engineer": ("15-1212.00", "senior"),
    "Senior Site Reliability Engineer": ("15-1252.00", "senior"),
    "Senior Software Engineer - Android, Partner Engineering": ("15-1252.00", "senior"),
    "Senior Software Engineer, Apple": ("15-1252.00", "senior"),
    "Senior Software Engineer -Backend/Full Stack": ("15-1252.00", "senior"),
    "Senior Software Engineer, EDGE Discovery": ("15-1252.00", "senior"),
    "Senior Software Engineer, Infrastructure Engineering": ("15-1252.00", "senior"),
    "Senior SOX Analyst": ("13-2011.00", "senior"),
    "Senior Specialist, Distribution Operations": ("13-1111.00", "senior"),
    "Senior Strategic Sourcing Manager, Marketing": ("11-3061.00", "manager"),
    "Software Engineer": ("15-1252.00", "mid"),
    "Software Engineer I, Android": ("15-1252.00", "entry"),
    "Software Engineer II, Android": ("15-1252.00", "mid"),
    "Software Engineer II, Frontend": ("15-1252.00", "mid"),
    "Software Engineer III, Apple": ("15-1252.00", "senior"),
    "Software Engineer III, Media Delivery": ("15-1252.00", "senior"),
    "Software Engineer III, Playback Services": ("15-1252.00", "senior"),
    "Software Engineer III, Service Monetization": ("15-1252.00", "senior"),
    "Staff AI Engineer": ("15-1252.00", "staff"),
    "Staff Site Reliability Engineer": ("15-1252.00", "staff"),
    "Staff Software Engineer": ("15-1252.00", "staff"),
    "Staff Software Engineer, AI/ML": ("15-1252.00", "staff"),
    "Staff Software Engineer, Partner Engineering": ("15-1252.00", "staff"),
    "Strategic Sourcing Manager, Technology": ("11-3061.00", "manager"),
    "Supply Chain & Manufacturing Manager, Collectibles": ("11-3061.00", "manager"),
    "SVOD Strategy Senior Manager": ("13-1111.00", "manager"),
    "Tax Manager - LATAM": ("13-2011.00", "manager"),
    "Vice President, Content Protection & Anti-Piracy": ("23-1011.00", "exec"),
}

def classify(bullet: str):
    # Crude singularization so plural keywords (audits, vendors, dashboards)
    # still match \b-anchored patterns.
    sing = re.sub(r"(?<=[a-z])s\b", "", bullet.lower())
    for c in C:
        if re.search(c["pat"], bullet, re.I) or re.search(c["pat"], sing, re.I):
            return c["key"]
    return "other_generalist"

def main() -> int:
    jobs = list(csv.DictReader((P / "jobs.csv").open(encoding="utf-8")))
    resp = list(csv.DictReader((P / "responsibilities.csv").open(encoding="utf-8")))

    # Classify bullets; flag noise (kept in catalogue, excluded from hours).
    norm_rows = []
    by_job = defaultdict(lambda: defaultdict(int))  # job_id -> cluster -> bullets
    noise_count = 0
    for r in resp:
        bullet = r["verbatim_responsibility"]
        is_noise = bool(NOISE_PAT.search(bullet))
        if is_noise:
            noise_count += 1
            cluster = ""
        else:
            cluster = classify(bullet)
            by_job[r["job_id"]][cluster] += 1
        norm_rows.append({**r, "cluster": cluster, "is_noise": int(is_noise)})
    with (P / "responsibilities_normalized.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(norm_rows[0].keys()))
        w.writeheader()
        w.writerows(norm_rows)

    cmeta = {c["key"]: c for c in C}
    jmeta = {j["job_id"]: j for j in jobs}

    # Per job x cluster scoring.
    scored, role_rows = [], []
    for j in jobs:
        jid, title = j["job_id"], j["title"]
        # Japanese twin posting reuses its English twin's cluster distribution.
        if j["language"] == "ja":
            en = next((x for x in jobs if x["language"] != "ja"
                       and x["title"] == "Senior Producer, Anime Co-Production"), None)
            dist = dict(by_job[en["job_id"]]) if en else {}
        else:
            dist = dict(by_job[jid])
        total_b = sum(dist.values()) or 1
        soc, level = TITLE_MAP[title]
        occ_med = OCC_WAGE[soc]
        # Posted pay range (US postings) takes precedence; BLS estimate fallback.
        posted_mid = j.get("pay_mid_posted") or ""
        if posted_mid:
            base_pay = int(posted_mid)
            pay_source = "posted pay range (Crunchyroll)"
        else:
            base_pay = round(occ_med * LEVELS[level])
            pay_source = "BLS OEWS May 2025 median × seniority factor"
        hourly = round(base_pay / ANNUAL_HOURS, 2)

        tot = {"conservative": 0.0, "base": 0.0, "upside": 0.0}
        tot_hours = 0.0
        for cluster_key, n in sorted(dist.items(), key=lambda kv: -kv[1]):
            c = cmeta[cluster_key]
            hours = ANNUAL_HOURS * n / total_b
            tot_hours += hours
            row = {
                "job_id": jid, "title": title, "department": j["department"],
                "cluster": cluster_key, "cluster_label": c["label"],
                "bullet_count": n, "bullet_share": round(n / total_b, 4),
                "role_hours_annual": round(hours, 1),
                "fit_normal": c["fit_n"], "fit_bespoke": c["fit_b"],
                "bespoke_build": c["bespoke"],
                "addressable_share": c["addr"],
                "time_basis": c["basis"], "time_source": c["time_src"],
                "evidence_confidence": c["conf"],
                "hourly_usd_equiv": hourly,
            }
            for scen, (adoption, tred_i) in {
                "conservative": (ADOPTION["conservative"], 0),
                "base": (ADOPTION["base"], 1),
                "upside": (ADOPTION["upside"], 2),
            }.items():
                saved = hours * c["addr"] * c["tred"][tred_i] * adoption * (c["fit_n"] / 100)
                row[f"saved_hours_{scen}"] = round(saved, 1)
                row[f"saved_value_{scen}"] = round(saved * hourly, 0)
                tot[scen] += saved
            scored.append(row)

        assert abs(tot_hours - ANNUAL_HOURS) < 0.5, f"{title} hours {tot_hours}"
        role_rows.append({
            "job_id": jid, "title": title, "department": j["department"],
            "location": j["location"], "url": j["url"],
            "occupation_soc": soc, "occupation": OCC_LABELS[soc],
            "seniority": level, "us_equiv_base_pay": base_pay,
            "pay_source": pay_source,
            "posted_range": (f"${j['pay_min_posted']}-${j['pay_max_posted']}"
                             if j.get("pay_min_posted") else ""),
            "hourly_equiv": hourly,
            "loaded_hourly_equiv": round(hourly * LOADED_FACTOR, 2),
            "role_hours_annual": ANNUAL_HOURS,
            "saved_hours_conservative": round(tot["conservative"], 1),
            "saved_hours_base": round(tot["base"], 1),
            "saved_hours_upside": round(tot["upside"], 1),
            "saved_value_base": round(tot["base"] * hourly, 0),
            "pct_capacity_freed_base": round(100 * tot["base"] / ANNUAL_HOURS, 1),
        })

    for name, rows in [
        ("scored_responsibilities.csv", scored), ("role_summary.csv", role_rows)]:
        with (P / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # Cluster rollup across the portfolio.
    agg = defaultdict(lambda: {"hours": 0.0, "base": 0.0, "bullets": 0})
    for s in scored:
        a = agg[s["cluster"]]
        a["hours"] += s["role_hours_annual"]
        a["base"] += s["saved_hours_base"]
        a["bullets"] += s["bullet_count"]
    rank = []
    for key, a in agg.items():
        c = cmeta[key]
        rank.append({
            "cluster": key, "cluster_label": c["label"],
            "fit_normal": c["fit_n"], "fit_bespoke": c["fit_b"],
            "bespoke_build": c["bespoke"],
            "addressable_share": c["addr"],
            "time_basis": c["basis"], "time_source": c["time_src"],
            "evidence_confidence": c["conf"],
            "rationale": c["rationale"],
            "recommended_workflow": c["workflow"],
            "human_checkpoint": c["checkpoint"],
            "portfolio_hours": round(a["hours"], 1),
            "portfolio_saved_hours_base": round(a["base"], 1),
            "bullet_count": a["bullets"],
            "saved_hours_conservative": round(a["base"] * (ADOPTION["conservative"] / ADOPTION["base"]), 1) if False else "",
        })
    rank.sort(key=lambda r: -(r["fit_normal"] * 1000 + r["portfolio_saved_hours_base"]))
    with (P / "cluster_ranking.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rank[0].keys()))
        w.writeheader()
        w.writerows(rank)

    # Console reconciliation summary.
    print(f"bullets: {len(resp)} | noise excluded: {noise_count} | classified: {len(resp)-noise_count}")
    print(f"jobs: {len(jobs)} | scored job-cluster rows: {len(scored)}")
    tot_base = sum(r['saved_hours_base'] for r in role_rows)
    tot_hours = sum(r['role_hours_annual'] for r in role_rows)
    print(f"portfolio hours: {tot_hours:.0f} | saved base: {tot_base:.0f} "
          f"({100*tot_base/tot_hours:.1f}% of capacity)")
    for scen in ("conservative", "base", "upside"):
        t = sum(r[f'saved_hours_{scen}'] for r in role_rows)
        print(f"  {scen:12}: {t:8.0f} h  (${sum(r[f'saved_value_base'] for r in role_rows)*t/max(tot_base,1):,.0f} salary-equiv)")
    unmatched = {t for t in TITLE_MAP} - {j["title"] for j in jobs}
    if unmatched:
        print("WARNING unmapped titles:", unmatched)
    return 0

if __name__ == "__main__":
    sys.exit(main())
