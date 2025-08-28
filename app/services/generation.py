# app/services/generation.py
from app.services.llm_service import get_client

# ------------------ System Prompts ------------------

SYS_TITLE_FR = (
    "Tu es un assistant qui rédige des TITRES d’annonces auto pour une marketplace.\n"
    "Réponds UNIQUEMENT en français.\n"
    "Contraintes: ≤60 caractères, une seule ligne, ton neutre, crédible.\n"
    "Interdits: emojis, hashtags, URL, téléphone/email, prix, promesses ou superlatifs abusifs, TOUTES MAJUSCULES.\n"
    "Pas de mentions hors plateforme (livraison, financement, WhatsApp, etc.).\n"
    "Sors UNIQUEMENT le titre, sans guillemets."
)

SYS_TITLE_EN = (
    "You are an assistant writing car listing TITLES for a marketplace.\n"
    "Respond ONLY in English.\n"
    "Constraints: ≤60 characters, single line, neutral, credible.\n"
    "Forbidden: emojis, hashtags, URLs, phone/email, price, hype/superlatives, ALL CAPS.\n"
    "No off-platform mentions (delivery, financing, WhatsApp, etc.).\n"
    "Output ONLY the title, no quotes."
)

SYS_DESC_FR = (
    "Tu rédiges des DESCRIPTIONS d’annonces auto pour une marketplace.\n"
    "Réponds UNIQUEMENT en français.\n"
    "Longueur: 90–140 mots. Ton clair, neutre, factuel. Pas de promesses ni superlatifs excessifs.\n"
    "Interdits: prix, coordonnées, URL, emojis, TOUTES MAJUSCULES, hors plateforme.\n"
    "N’invente jamais: omets ce qui manque. Termine par un appel à l’action discret.\n"
    "Sors UNIQUEMENT le texte final, sans guillemets."
)

SYS_DESC_EN = (
    "You write car listing DESCRIPTIONS for a marketplace.\n"
    "Respond ONLY in English.\n"
    "Length: 90–140 words. Clear, neutral, factual tone. No promises/hype.\n"
    "Forbidden: price, contacts, URLs, emojis, ALL CAPS, off-platform.\n"
    "Never invent: omit missing data. End with a light call-to-action.\n"
    "Output ONLY the final text, no quotes."
)

SYS_REWRITE_FR = (
    "Tu réécris un TEXTE d’annonce selon la consigne utilisateur.\n"
    "Réponds UNIQUEMENT en français.\n"
    "Conserve les contraintes marketplace (si titre: ≤60 car., 1 ligne; si description: 90–140 mots).\n"
    "Si la consigne demande un élément interdit (prix, emojis, contacts, promesses), ignore-le et reste conforme.\n"
    "Sors UNIQUEMENT le texte final, sans guillemets."
)

SYS_REWRITE_EN = (
    "You rewrite a listing TEXT according to user feedback.\n"
    "Respond ONLY in English.\n"
    "Keep marketplace constraints (if title: ≤60 chars, 1 line; if description: 90–140 words).\n"
    "If feedback requests something disallowed (price, emojis, contacts, claims), ignore that and stay compliant.\n"
    "Output ONLY the final text, no quotes."
)

# ------------------ User Prompt ------------------

USR_COMMON = """
MODE: {mode}  # one of: title | description | rewrite

DATA:
- Brand: {marque}
- Model: {modele}
- Year: {annee}
- Mileage: {kilometrage}
- Fuel: {carburant}
- Gearbox: {boite}
- Color: {couleur}
- Extra: {infos_supplementaires}

FEEDBACK (optional):
{feedback}

INSTRUCTIONS:
- If MODE=title: produce one concise, credible marketplace title.
- If MODE=description: produce a 90–140 word marketplace description.
- If MODE=rewrite: rewrite the provided text according to FEEDBACK while preserving constraints.
- Never add price, contacts, URLs, emojis, or exaggerated claims.
- Omit missing data; never invent.
- Output ONLY the final text (no quotes).
"""

# ------------------ Helpers ------------------

def _pick_system(locale: str, mode: str) -> str:
    loc = (locale or "Français").lower()
    m = (mode or "title").lower()

    if m == "title":
        return SYS_TITLE_EN if loc.startswith("en") else SYS_TITLE_FR
    if m == "description":
        return SYS_DESC_EN if loc.startswith("en") else SYS_DESC_FR
    # rewrite
    return SYS_REWRITE_EN if loc.startswith("en") else SYS_REWRITE_FR

def _build_messages(locale: str, mode: str, ctx: dict, feedback: str = "", rewrite_text: str = ""):
    system_prompt = _pick_system(locale, mode)

    user_payload = USR_COMMON.format(
        mode=mode,
        marque=ctx.get("marque", "") or "",
        modele=ctx.get("modele", "") or "",
        annee=ctx.get("annee", "") or "",
        kilometrage=ctx.get("kilometrage", "") or "",
        carburant=ctx.get("carburant", "") or "",
        boite=ctx.get("boite", "") or "",
        couleur=ctx.get("couleur", "") or "",
        infos_supplementaires=ctx.get("infos_supplementaires", "") or "",
        feedback=(feedback.strip() if feedback else ("(none)" if mode != "rewrite" else f"(rewrite target below)\n\nTEXT:\n{rewrite_text}"))
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_payload.strip()},
    ]

def _postprocess_title(txt: str) -> str:
    t = (txt or "").strip().replace("\n", " ")
    if len(t) > 60:
        cut = t[:60]
        if " " in cut:
            cut = cut[:cut.rfind(" ")]
        t = cut
    return t

# ------------------ API Génération ------------------

def generate_title(ctx: dict, feedback: str = "") -> str:
    client = get_client()
    locale = ctx.get("locale", "Français")
    msgs = _build_messages(locale, "title", ctx, feedback=feedback)
    out = client.chat(msgs)
    return _postprocess_title(out)

def generate_description(ctx: dict, feedback: str = "") -> str:
    client = get_client()
    locale = ctx.get("locale", "Français")
    msgs = _build_messages(locale, "description", ctx, feedback=feedback)
    return (out := client.chat(msgs)).strip()

def rewrite_text(ctx: dict, current_text: str, feedback: str) -> str:
    client = get_client()
    locale = ctx.get("locale", "Français")
    msgs = _build_messages(locale, "rewrite", ctx, feedback=feedback, rewrite_text=current_text)
    return (out := client.chat(msgs)).strip()

