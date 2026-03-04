"""Entity-type-specific blocklists for filtering GLiNER false positives
and controlling consistency-scan propagation.

Two distinct blocklist layers:

1.  **GLiNER filter** -- ``is_blocked(text, label)``
    Blocks single-word entities that exactly match a per-type blocklist,
    UNLESS the word is a known real name (from the reference name list)
    and the label is PERSON_NAME.
    Multi-word entities are blocked when every token is in the combined
    filler + type-specific blocklist, or the full phrase is in the blocklist.
    Matching is case-insensitive.

2.  **Consistency-scan guard** -- ``NOT_A_PROPER_NAME``
    Broader set of words that should never be propagated as standalone
    name tokens across the document.
"""

from __future__ import annotations

# =====================================================================
# Known real names (reference allowlist from data/names.txt)
# =====================================================================

KNOWN_SHORT_NAMES: frozenset[str] = frozenset({
    "Ab", "Al", "Au", "Bo", "Cy", "Di", "Ed", "Em", "Ev", "Ey", "Ih", "Ix",
    "Jo", "Lu", "Mo", "Oz", "Pi", "Ro", "Sy", "Ty", "Uz", "Vi",
    "Abe", "Abt", "Ace", "Ada", "Alf", "Ali", "Alt", "Amy", "Ana", "Ann",
    "Ari", "Art", "Ash", "Ast", "Ava", "Awa", "Awe", "Axt",
    "Bea", "Ben", "Bix", "Bly", "Bob", "Box", "Bye",
    "Cal", "Cam", "Cas", "Cat", "Coe", "Cox", "Coy",
    "Dan", "Daw", "Dax", "Day", "Dee", "Del", "Dex", "Dix", "Doe", "Don",
    "Dot", "Dow", "Dre",
    "Eby", "Eck", "Eik", "Ela", "Eli", "Ely", "Ema", "Enz", "Epp", "Erb",
    "Eve", "Ewa", "Ewy", "Exl",
    "Fay", "Fee", "Fey", "Fia", "Fin", "Fix", "Flo", "Fox", "Fry",
    "Gau", "Gay", "Gee", "Gia", "Gil", "Gut", "Guy",
    "Hal", "Hau", "Hax", "Hay", "Hoe", "Hug",
    "Ian", "Ida", "Iff", "Igg", "Ike", "Ina", "Ira", "Isa", "Iva", "Ivy",
    "Jan", "Jax", "Jay", "Jed", "Jem", "Jim", "Joe", "Jon", "Joy", "Jux",
    "Kai", "Kau", "Kay", "Ken", "Key", "Kia", "Kim", "Kip", "Kit", "Kux", "Kya",
    "Lau", "Lea", "Lee", "Leo", "Lex", "Lia", "Liv", "Liz", "Lou", "Luc", "Lux",
    "Mac", "Mae", "Mai", "Mau", "Max", "May", "Meg", "Mel", "Mia", "Mut",
    "Ned", "Neu", "Ney", "Nia", "Noa", "Noe", "Nye",
    "Obi", "Ole", "Ora", "Ori", "Orr", "Ost", "Ott",
    "Pam", "Pat", "Peg", "Pen", "Per", "Pia", "Pil", "Pip", "Pit", "Poe", "Pux", "Pye",
    "Rad", "Rae", "Rax", "Ray", "Reh", "Rex", "Rey", "Ria", "Rob", "Roe", "Ron",
    "Row", "Roy", "Rue", "Ruf", "Rye",
    "Sal", "Sam", "See", "Six", "Sky", "Sly", "Sol", "Sue", "Syd",
    "Tad", "Taj", "Ted", "Teo", "Tia", "Til", "Tim", "Tom", "Toy", "Tye",
    "Udo", "Uhl", "Ulf", "Uli", "Ulm", "Una", "Urs", "Uta", "Ute", "Utz", "Uwe",
    "Val", "Van", "Vey", "Vic", "Voe",
    "Way", "Wes", "Wye", "Wyn",
    "Zac", "Zed", "Zeh", "Zoe",
})

_KNOWN_NAMES_LOWER: frozenset[str] = frozenset(n.lower() for n in KNOWN_SHORT_NAMES)

# =====================================================================
# Layer 1 -- GLiNER false-positive filter
# =====================================================================

_GERMAN_PRONOUNS: frozenset[str] = frozenset({
    "Ich", "ich", "Du", "du", "Er", "er", "Sie", "sie", "Es", "es",
    "Wir", "wir", "Ihr", "ihr", "Ihn", "ihn", "Ihm", "ihm",
    "Mich", "mich", "Mir", "mir", "Dich", "dich", "Dir", "dir",
    "Uns", "uns", "Euch", "euch", "Sich", "sich",
    "Man", "man", "Mein", "mein", "Dein", "dein", "Sein", "sein",
})

_GERMAN_ARTICLES: frozenset[str] = frozenset({
    "Der", "der", "Die", "die", "Das", "das",
    "Den", "den", "Dem", "dem", "Des", "des",
    "Ein", "ein", "Eine", "eine", "Einem", "einem",
    "Einen", "einen", "Einer", "einer", "Eines", "eines",
    "The", "the", "A", "a", "An", "an",
})

_TITLES_AND_SALUTATIONS: frozenset[str] = frozenset({
    "Herr", "Frau", "Sehr", "Geehrter", "geehrter", "Geehrte", "geehrte",
    "Lieber", "lieber", "Liebe", "liebe", "Liebes", "liebes",
    "Verehrter", "verehrter", "Verehrte", "verehrte",
    "Dr", "Prof", "Mr", "Mrs", "Ms",
})

_GREETINGS: frozenset[str] = frozenset({
    "Hey", "Hallo", "Hi", "Guten", "Gute", "Guter", "Morgen",
    "Servus", "Moin", "Ciao", "Tschüss", "Bye",
})

_CONJUNCTIONS_AND_PREPOSITIONS: frozenset[str] = frozenset({
    "and", "or", "of", "the", "in", "for", "to", "from", "with", "by",
    "on", "at", "as", "is", "are", "was", "were", "be", "been", "being",
    "und", "oder", "von", "für", "mit", "bei", "auf", "an", "zu",
    "nach", "über", "unter", "durch", "zwischen", "seit", "ab", "bis",
})

_FILLER_WORDS: frozenset[str] = (
    _GERMAN_PRONOUNS | _GERMAN_ARTICLES | _TITLES_AND_SALUTATIONS
    | _GREETINGS | _CONJUNCTIONS_AND_PREPOSITIONS
)

# ---------------------------------------------------------------------------
# Job titles, role names, and organisational terms (EN + DE)
# ---------------------------------------------------------------------------

_JOB_TITLES_EN: frozenset[str] = frozenset({
    "CEO", "CTO", "CFO", "COO", "CIO", "CISO", "CSO", "CMO",
    "DPO", "LISO", "CPO",
    "Director", "Manager", "Officer", "Owner", "Lead", "Head",
    "Chief", "Senior", "Junior", "Principal", "Associate",
    "President", "Chairman", "Secretary", "Treasurer",
    "Coordinator", "Specialist", "Analyst", "Architect",
    "Administrator", "Consultant", "Advisor", "Auditor",
    "Engineer", "Developer", "Designer", "Researcher",
    "Managing", "Executive", "General", "Deputy", "Assistant",
    "Employee", "Employees", "employees",
    "Supervisor", "Supervisors", "supervisors",
    "Contractor", "Contractors",
    "Representative", "Representatives",
    "Stakeholder", "Stakeholders",
})

_JOB_TITLES_DE: frozenset[str] = frozenset({
    "Leiter", "Leiterin", "Leitung",
    "Beauftragter", "Beauftragte", "Beauftragten",
    "Verantwortlicher", "Verantwortliche", "Verantwortlichen",
    "Mitarbeiter", "Mitarbeiterin", "Mitarbeitern", "Mitarbeiterinnen",
    "Vertreter", "Vertreterin", "Vertreterung",
    "Geschäftsführer", "Geschäftsführerin",
    "Vorstand", "Vorständin", "Vorstandsmitglied",
    "Berater", "Beraterin",
    "Prüfer", "Prüferin",
    "Risikoeigner", "Risikoverantwortlicher",
    "Applikationsmanager", "Assetverantwortlicher", "Assetverantwortliche",
    "Assetverantwortlichen", "Schwachstellenverantwortliche",
    "Schwachstellenverantwortlicher", "Schwachstellenverantwortlichen",
    "Prozessverantwortlicher", "Informationssicherheitsmanager",
    "Informationssicherheitsbeauftragter",
    "Konzerngesellschaft", "Konzerngesellschaften",
})

# ---------------------------------------------------------------------------
# Common English/German words that GLiNER misclassifies as names
# ---------------------------------------------------------------------------

_COMMON_WORDS_EN: frozenset[str] = frozenset({
    "Application", "Information", "Security", "Digital", "Product",
    "Group", "Cloud", "Risk", "Service", "Services",
    "System", "Systems", "Management", "Process", "Project",
    "Network", "Software", "Hardware", "Data", "Code",
    "Source", "Platform", "Infrastructure", "Operations",
    "Compliance", "Governance", "Policy", "Guideline",
    "Framework", "Standard", "Control", "Controls",
    "Assessment", "Monitoring", "Reporting", "Alerting",
    "Treatment", "Response", "Recovery", "Prevention",
    "Event", "Incident", "Vulnerability", "Threat",
    "Chapter", "Section", "Table", "Figure", "Annex",
    "Version", "Document", "Scope",
    "Internal", "External", "Local", "Global", "National",
    "Patch", "Update", "Release", "Lifecycle",
    "Notification", "Classification", "Distribution",
    "Requirement", "Requirements", "Regulation",
    "Circle", "Committee", "Board", "Team",
    "Common", "Scoring", "Introduction", "Overview",
    "Appendix", "Summary", "Conclusion", "Background",
    "Purpose", "Objective", "Definition", "Definitions",
    "Reference", "References", "Implementation", "Configuration",
    "Architecture", "Integration", "Testing", "Deployment",
    "Maintenance", "Documentation", "Communication",
    "Findings", "Results", "Analysis", "Evaluation",
})

_COMMON_WORDS_DE: frozenset[str] = frozenset({
    "Konzern", "Konzerns", "Gesellschaft", "Unternehmen",
    "Abteilung", "Bereich", "Gremium", "Steuerkreis",
    "Regelwerk", "Regelwerksmanagement",
    "Schwachstelle", "Schwachstellen", "Risiko", "Risiken",
    "Sicherheit", "Informationssicherheit",
    "Prozess", "Verfahren", "Maßnahme", "Maßnahmen",
    "Kontrolle", "Bewertung", "Behandlung", "Eskalation",
    "Schadenspotentials", "Schadenshöhe", "Schadenspotential",
    "Datum", "Monat", "Jahr", "Quartal",
    "Freigabe", "Erstellung", "Anpassung", "Prüfung",
    "Umsetzung", "Einhaltung", "Anforderung", "Anforderungen",
    "Kapitel", "Abschnitt", "Tabelle", "Abbildung", "Anhang", "Anlage",
    "Überblick", "Einleitung", "Zweck", "Anwendungsbereich",
    "Identifikation", "Klassifikation", "Benachrichtigung",
    "Wirtschaftsprüfung", "Erkenntnisse", "Plattform",
    "Ergebnisse", "Zusammenfassung", "Hintergrund",
    "Dokumentation", "Kommunikation", "Konfiguration",
    "Architektur", "Implementierung", "Bereitstellung",
    "Wartung", "Integration", "Auswertung",
    "Änderungshistorie", "Abkürzungsverzeichnis",
    "Protokollierung", "Überwachung", "Benachrichtigungen",
    "Risikobehandlung", "Schwachstellenmanagement",
    "Versionierung", "Klassifizierung",
})

# ---------------------------------------------------------------------------
# Per-type blocklists
# ---------------------------------------------------------------------------

PERSON_NAME_BLOCKED: frozenset[str] = frozenset(
    _FILLER_WORDS
    | _JOB_TITLES_EN
    | _JOB_TITLES_DE
    | _COMMON_WORDS_EN
    | _COMMON_WORDS_DE
    | {
        "Name", "Vorname", "Nachname", "Titel", "Anrede",
        "Herren", "Damen", "Personen", "Person",
        "Kontoinhaber", "Versicherungsnehmer", "Inhaber",
        "Bitte", "Danke", "Grüße", "Gruß",
        "Managers", "managers",
    }
)

PHYSICAL_ADDRESS_BLOCKED: frozenset[str] = frozenset({
    "Wohnung", "Haus", "Zimmer", "Raum", "Büro", "Gebäude",
    "Schule", "Kirche", "Laden", "Geschäft", "Etage", "Stock",
    "Eingang", "Ausgang", "Keller", "Dachboden", "Garage",
    "Office", "Building", "Floor", "Room",
})

BANK_NAME_BLOCKED: frozenset[str] = frozenset({
    "Bank", "Sparkasse", "Kredit", "Konto",
})

FINANCIAL_VALUE_BLOCKED: frozenset[str] = frozenset({
    "Betrag", "Beitrag", "Summe", "Gebühr", "Kosten",
    "jährlich", "monatlich", "fälligen", "fällig",
    "Schadenspotentials", "Schadenshöhe", "Schadenspotential",
    "billion", "million", "thousand", "Milliarde", "Million", "Tausend",
})

COMPANY_NAME_BLOCKED: frozenset[str] = frozenset({
    "Group", "Digital", "Cloud", "Security",
    "Services", "Solutions", "Systems",
    "Gruppe", "Dienste",
    "SAP", "Oracle", "Microsoft", "Google", "Amazon", "IBM",
    "DORA", "GDPR", "NIS2", "ISO",
})

DATE_OF_BIRTH_BLOCKED: frozenset[str] = frozenset({
    "Datum", "Monat", "Jahr", "Date", "Month", "Year",
    "Quartal", "Quarter",
})

INTERNAL_PROJECT_CODE_BLOCKED: frozenset[str] = frozenset({
    "Source Code", "Code", "Quellcode", "Sourcecode", "Source",
})

BLOCKLISTS: dict[str, frozenset[str]] = {
    "PERSON_NAME": PERSON_NAME_BLOCKED,
    "PHYSICAL_ADDRESS": PHYSICAL_ADDRESS_BLOCKED,
    "BANK_NAME": BANK_NAME_BLOCKED,
    "FINANCIAL_VALUE": FINANCIAL_VALUE_BLOCKED,
    "COMPANY_NAME": COMPANY_NAME_BLOCKED,
    "DATE_OF_BIRTH": DATE_OF_BIRTH_BLOCKED,
    "INTERNAL_PROJECT_CODE": INTERNAL_PROJECT_CODE_BLOCKED,
}

# Pre-compute lowercased versions for case-insensitive matching
_BLOCKLISTS_LOWER: dict[str, frozenset[str]] = {
    label: frozenset(w.lower() for w in bl)
    for label, bl in BLOCKLISTS.items()
}
_FILLER_LOWER: frozenset[str] = frozenset(w.lower() for w in _FILLER_WORDS)


def _is_numeric_token(word: str) -> bool:
    """Return True for pure numbers and decimal/dot-separated numbers."""
    cleaned = word.replace(".", "").replace(",", "").replace("-", "")
    return cleaned.isdigit()


def is_blocked(text: str, normalized_label: str) -> bool:
    """Return True if *text* is a known false positive for *normalized_label*.

    Matching is case-insensitive. Single-word entities are checked against
    the per-type blocklist, but known real names from the reference list
    are never blocked when detected as PERSON_NAME.

    Multi-word entities are blocked when:
    - The full phrase (case-insensitive) is in the blocklist, OR
    - Every individual token is in the combined filler + type blocklist.
    """
    stripped = text.strip()
    lower = stripped.lower()
    words = stripped.split()

    if len(words) == 1:
        if normalized_label == "PERSON_NAME" and lower in _KNOWN_NAMES_LOWER:
            return False
        bl_lower = _BLOCKLISTS_LOWER.get(normalized_label)
        return lower in bl_lower if bl_lower else False

    # Full-phrase check first (handles "Source Code" etc.)
    bl_lower = _BLOCKLISTS_LOWER.get(normalized_label)
    if bl_lower and lower in bl_lower:
        return True

    # Word-by-word check: every token must be a filler, numeric, or in the type blocklist
    combined = _FILLER_LOWER | (bl_lower or frozenset())
    return all(w.lower() in combined or _is_numeric_token(w) for w in words)


# =====================================================================
# Layer 2 -- Consistency-scan proper-name guard
# =====================================================================

_TECH_AND_ORG_TERMS: frozenset[str] = frozenset({
    "Deutsche", "Berliner", "Hamburger", "Münchner", "Stuttgarter",
    "Kreditbank", "Volksbank", "Raiffeisenbank",
    "Berlin", "Hamburg", "München", "Frankfurt", "Stuttgart",
    "Köln", "Düsseldorf", "Fellbach", "Hannover", "Dresden",
    "AWS", "SAP", "CERT", "DORA", "VW", "PAG", "GmbH", "AG",
    "ISMS", "ISVM", "ISRM", "CVSS", "CVE", "GDPR", "SAST", "DAST",
    "SaaS", "IaaS", "PaaS", "API", "FTP", "HTTP", "HTTPS",
    "PDiG", "PDCN", "PDDE", "PDES", "PDHR", "PDIL", "PDUS",
    "InfoSec", "ToGe", "KoGe", "AktG",
    "Zahlung", "Buchung", "Vertrag", "Versicherung",
    "Ende", "Anfang", "Teil", "Seite",
    "Version", "Datum", "Intern", "Extern",
    "Online", "Tarif", "Standard", "Premium",
    "Findings", "Advisory", "Dashboard",
    "Identification", "Assessment", "Treatment",
    "Monitoring", "Reporting", "Alerting",
    "Line", "Review", "Check",
    "Aktiengesellschaft", "Tochtergesellschaft",
    "Oracle", "Microsoft", "Google", "Amazon", "IBM",
})

NOT_A_PROPER_NAME: frozenset[str] = frozenset(
    PERSON_NAME_BLOCKED
    | PHYSICAL_ADDRESS_BLOCKED
    | BANK_NAME_BLOCKED
    | COMPANY_NAME_BLOCKED
    | _TECH_AND_ORG_TERMS
    | _COMMON_WORDS_EN
    | _COMMON_WORDS_DE
)
