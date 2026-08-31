import os

_here = os.path.dirname(os.path.abspath(__file__))
_WORKFLOW_DIR = os.path.join(_here, "workflows")

def _load(name: str) -> str:
    """Load a workflow prompt file safely.

    Returns the file contents, or a small fallback string if the file is missing
    or cannot be read. This prevents an import-time I/O error from crashing the
    whole application on launch.
    """
    path = os.path.join(_WORKFLOW_DIR, f"{name}.txt")
    if not os.path.isfile(path):
        return f"# MISSING: {name}.txt\nUse only provided chart data."
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as exc:
        # Log to stderr so the failure is visible, but keep the app alive.
        import sys
        print(f"WARNING: could not read prompt file {path}: {exc}", file=sys.stderr)
        return f"# UNREADABLE: {name}.txt ({type(exc).__name__})\nUse only provided chart data."

# Shared base instructions
COMMON_RULES = _load("common")

# Combine common rules + each specific workflow
WORKFLOWS = {
    "career":         COMMON_RULES + "\n\n" + _load("career"),
    "generic_career": COMMON_RULES + "\n\n" + _load("generic_career"),
    "luck":           COMMON_RULES + "\n\n" + _load("luck"),
    "wealth":         COMMON_RULES + "\n\n" + _load("wealth"),
    "marriage":       COMMON_RULES + "\n\n" + _load("marriage"),
    "relationships":  COMMON_RULES + "\n\n" + _load("relationships"),
    "health":         COMMON_RULES + "\n\n" + _load("health"),
    "children":       COMMON_RULES + "\n\n" + _load("children"),
    "foreign":        COMMON_RULES + "\n\n" + _load("foreign"),
    "legal":          COMMON_RULES + "\n\n" + _load("legal"),
    "general":        COMMON_RULES + "\n\n" + _load("general"),
}

def get_workflow_template(name: str) -> str:
    """Loads fresh workflow template from disk to ensure live updates without restart."""
    common = _load("common")
    specific = _load(name) if name in WORKFLOWS else _load("general")
    return common + "\n\n" + specific

def classify_workflow(text: str) -> str:
    import re
    t = text.lower()

    def has_match(keywords):
        return any(re.search(r'\b' + re.escape(k) + r'\b', t) for k in keywords)

    # 1. Luck, Destiny & Bhagya
    if has_match([
        "luck", "lucky", "fortune", "fortunate", "bhagya", "destiny", "9th house", "9th lord",
        "past life merit", "source of luck", "activate luck", "activate my luck", "how to activate luck",
        "is this lucky", "lucky for me", "lucky charm", "good luck", "bad luck"
    ]):
        return "luck"

    # 2. Career Direction, Vocation & Academic Majors
    if has_match([
        "career direction", "what field", "which field", "career path", "style of work",
        "work style", "level of authority", "type of environment", "work environment",
        "early career", "mid career", "middle career", "late career", "later career",
        "career phase", "ideal career", "suitable career", "which profession",
        "what career", "career field", "career choice", "generic career", "job vs business",
        "which college", "what college", "which university", "what university", "which major",
        "what major", "which degree", "what degree", "what to study", "which stream",
        "field of study", "academic direction", "which course"
    ]):
        return "generic_career"

    # 3. Career Timing, Jobs, Interviews, Promotions & Exams
    if has_match([
        "career", "careers", "job", "jobs", "profession", "professions", "professional",
        "business", "businesses", "company", "firm", "promotion", "promotions", "promote",
        "promoted", "work", "workplace", "working", "office", "transfer", "transfers",
        "boss", "colleague", "interview", "interviews", "hired", "hiring", "job offer", "offer letter",
        "unemployed", "unemployment", "resignation", "resign", "exam", "exams", "examination",
        "examinations", "exam result", "exam results", "test results", "test score", "clear exam",
        "pass exam", "entrance exam", "upsc", "gmat", "gre", "sat", "cat", "jee", "neet",
        "admission", "admissions", "selection", "interview result"
    ]):
        return "career"

    # 4. Wealth, Finances, Investments & Purchasing Assets
    if has_match([
        "wealth", "wealthy", "money", "finance", "finances", "financial", "financially",
        "income", "incomes", "salary", "salaries", "property", "properties", "house", "houses",
        "home", "flat", "real estate", "land", "plot", "debt", "debts", "loan", "loans",
        "savings", "saving", "invest", "invests", "investing", "investment", "investments",
        "rich", "richer", "richest", "assets", "asset", "net worth", "networth", "capital",
        "cash flow", "cashflow", "funds", "fund", "expenses", "expense", "expenditure",
        "expenditures", "loss", "losses", "profit", "profits", "gains", "gain",
        "earn", "earning", "earnings", "crypto", "stock", "stocks", "shares", "trading",
        "stock market", "mutual fund", "mutual funds", "buy land", "buy house", "buy property",
        "buying land", "buying a house", "buying property", "buy a car", "buy vehicle", "buy this",
        "buying this", "purchase", "purchasing", "gold", "silver"
    ]):
        return "wealth"

    # 5. Marriage, Spouse & Long-Term Matrimony
    if has_match([
        "marriage", "marriages", "marry", "marrying", "spouse", "wife", "wives", "husband",
        "husbands", "wedding", "weddings", "married", "matrimony", "matrimonial", "bride",
        "groom", "divorce", "divorced", "second marriage", "engaged", "engagement", "fiance", "fiancee",
        "marriage proposal", "rishta", "arranged marriage", "in-laws", "inlaws", "marital"
    ]):
        return "marriage"

    # 6. Romance, Dating, Chemistry, Breakups & Love Proposals
    if has_match([
        "love", "affair", "relationship", "relationships", "partner", "partners", "girlfriend",
        "boyfriend", "breakup", "breakups", "separation", "dating", "date", "dates", "crush", "ex",
        "propose", "proposing", "proposal", "confess", "feelings", "texting", "attracted", "attraction",
        "patch up", "patchup", "heartbreak"
    ]):
        return "relationships"

    # 7. Health, Vitality, Recovery & Family Wellness
    if has_match([
        "health", "illness", "illnesses", "disease", "diseases", "surgery", "surgeries",
        "hospital", "hospitals", "hospitalization", "hospitalisation", "hospitalized", "hospitalised",
        "mental", "recovery", "doctor", "doctors", "cancer", "operation", "operations", "sick", "sickness",
        "unwell", "not well", "ailing", "anxiety", "depression", "stress", "medical", "treatment",
        "healing", "family health", "mother health", "father health", "parent health", "wellness"
    ]):
        return "health"

    # 8. Children, Progeny, Pregnancy & Family Expansion
    if has_match([
        "child", "children", "son", "sons", "daughter", "daughters", "pregnancy", "pregnancies",
        "fertility", "baby", "babies", "kid", "kids", "progeny", "conceive", "conception",
        "pregnant", "adopt", "adoption", "ivf"
    ]):
        return "children"

    # 9. Foreign Travel, Relocation & Visas
    if has_match([
        "foreign", "abroad", "visa", "visas", "travel", "travelling", "settlement", "relocate",
        "relocating", "relocation", "overseas", "immigration", "green card", "citizenship",
        "permanent resident", "pr", "abroad study", "study abroad", "flight", "passport"
    ]):
        return "foreign"

    # 10. Legal Matters, Disputes & Conflict Resolution
    if has_match([
        "legal", "court", "courts", "case", "cases", "litigation", "lawyer", "lawyers",
        "judge", "police", "police case", "fir", "crime", "dispute", "disputes", "crisis", "jail", "bail",
        "accident", "accidents", "lawsuit", "allegation", "allegations", "enemy", "enemies", "rival"
    ]):
        return "legal"

    return "general"
