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
    "career":        COMMON_RULES + "\n\n" + _load("career"),
    "wealth":        COMMON_RULES + "\n\n" + _load("wealth"),
    "marriage":      COMMON_RULES + "\n\n" + _load("marriage"),
    "relationships": COMMON_RULES + "\n\n" + _load("relationships"),
    "health":        COMMON_RULES + "\n\n" + _load("health"),
    "children":      COMMON_RULES + "\n\n" + _load("children"),
    "foreign":       COMMON_RULES + "\n\n" + _load("foreign"),
    "legal":         COMMON_RULES + "\n\n" + _load("legal"),
    "general":       COMMON_RULES + "\n\n" + _load("general"),
}

def classify_workflow(text: str) -> str:
    t = text.lower()

    if any(k in t for k in ["career","job","profession","business","promotion","work","office","transfer","career direction"]):
        return "career"
    if any(k in t for k in ["wealth","money","finance","income","salary","property","debt","loan","savings","invest","financial"]):
        return "wealth"
    if any(k in t for k in ["marriage","spouse","wife","husband","wedding","married","matrimony","bride","groom","divorce","second marriage","engaged","engagement","fiance"]):
        return "marriage"
    if any(k in t for k in ["love","affair","relationship","partner","girlfriend","boyfriend","breakup","separation","dating","crush"]):
        return "relationships"
    if any(k in t for k in ["health","illness","disease","surgery","hospital","mental","recovery","doctor","cancer","operation","sick","anxiety","depression","stress"]):
        return "health"
    if any(k in t for k in ["child","children","son","daughter","pregnancy","fertility","baby","kid","progeny","conceive","pregnant","adopt","ivf"]):
        return "children"
    if any(k in t for k in ["foreign","abroad","visa","travel","settlement","relocate","overseas","pr","immigration","green card","citizenship","permanent resident"]):
        return "foreign"
    if any(k in t for k in ["legal","court","case","litigation","lawyer","judge","police","fir","crime","dispute","crisis","jail","bail","accident"]):
        return "legal"

    return "general"
