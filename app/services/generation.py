# app/services/generation.py
# -*- coding: utf-8 -*-
"""
Génération IA (titre / description / rewrite) avec garde-fous :
- FR/EN strict selon ctx["locale"]
- Titre <= 20 mots (et cap de sécurité en caractères)
- Description <= 60 mots (un seul paragraphe)
- Interdit: ":" et formes "clé: valeur" dans les titres
- Boucle de feedback (plus court, ajouter couleur/année/km)
- Fallback déterministe si la sortie est vide/non conforme
"""

from __future__ import annotations

import re
from typing import Dict

from app.services.llm_service import get_client


# ===================== Constantes =====================

# Limites en MOTS (pas en caractères)
MAX_TITLE_WORDS = 20
MAX_DESC_WORDS = 60

# Cap de sécurité en caractères pour le titre (évite un titre très long même à 20 mots)
MAX_TITLE_CHARS = 90


# ===================== Prompts (renforcés) =====================

SYS_TITLE_FR = (
    "Tu rédiges des TITRES d'annonce automobile pour une marketplace.\n"
    "Réponds UNIQUEMENT en français (fr-FR).\n"
    f"Contraintes: ≤{MAX_TITLE_WORDS} mots, une seule ligne, ton neutre et crédible.\n"
    "Interdits: emojis, hashtags, URLs, téléphone/email, prix, superlatifs excessifs, TOUTES MAJUSCULES,\n"
    "           tout caractère ':' et toute forme 'clé: valeur' (ex: Marque:, Modèle:, Année:).\n"
    "N'écris QUE le titre final, sans guillemets, sans préfixe, sans étiquette, sans puces."
)

SYS_TITLE_EN = (
    "You write car listing TITLES for a marketplace.\n"
    "Respond ONLY in English.\n"
    f"Constraints: ≤{MAX_TITLE_WORDS} words, single line, neutral, credible.\n"
    "Forbidden: emojis, hashtags, URLs, phone/email, price, overhype, ALL CAPS,\n"
    "           any colon ':' and any 'key: value' form (e.g., Brand:, Model:, Year:).\n"
    "Output ONLY the final title, no quotes, no prefixes, no labels, no bullets."
)

SYS_DESC_FR = (
    "Tu rédiges des DESCRIPTIONS d'annonce automobile pour une marketplace.\n"
    "Réponds UNIQUEMENT en français.\n"
    f"Longueur: ≤{MAX_DESC_WORDS} mots (vise 45–60). Un seul paragraphe, clair et factuel, phrases courtes.\n"
    "Interdits: prix, coordonnées, URLs, emojis, TOUTES MAJUSCULES, promesses excessives, hors plateforme.\n"
    "N'invente pas: omets ce qui manque. Termine par un appel à l'action discret.\n"
    "Sors UNIQUEMENT le texte final (sans titres/étiquettes)."
)

SYS_DESC_EN = (
    "You write car listing DESCRIPTIONS for a marketplace.\n"
    "Respond ONLY in English.\n"
    f"Length: ≤{MAX_DESC_WORDS} words (aim 45–60). Single paragraph, clear and factual, short sentences.\n"
    "Forbidden: price, contacts, URLs, emojis, ALL CAPS, hype, off-platform.\n"
    "Never invent: omit missing data. End with a light call-to-action.\n"
    "Output ONLY the final text (no headings/labels)."
)

SYS_REWRITE_FR = (
    "Tu réécris un TEXTE d'annonce selon la consigne utilisateur.\n"
    "Réponds UNIQUEMENT en français.\n"
    f"Contraintes marketplace: titre ≤{MAX_TITLE_WORDS} mots, 1 ligne; description ≤{MAX_DESC_WORDS} mots, 1 paragraphe.\n"
    "Si la consigne demande un élément interdit (prix, emojis, contacts, promesses), ignore-le et reste conforme.\n"
    "Sors UNIQUEMENT le texte final, sans guillemets, sans titres, sans étiquettes."
)

SYS_REWRITE_EN = (
    "You rewrite a listing TEXT according to the user instructions.\n"
    "Respond ONLY in English.\n"
    f"Constraints: title ≤{MAX_TITLE_WORDS} words, single line; description ≤{MAX_DESC_WORDS} words, single paragraph.\n"
    "If feedback requests something disallowed (price, emojis, contacts, claims), ignore it and stay compliant.\n"
    "Output ONLY the final text, no quotes, no headings or labels."
)


# ===================== Construction des messages =====================

USR_COMMON = """
MODE = {mode}  # one of: title | description | rewrite

IMPORTANT: n'UTILISE PAS les données suivantes au format 'clé: valeur' et n'emploie AUCUN ':' dans le texte final.
Utilise-les uniquement pour guider l'écriture (ne copie rien tel quel).

DONNÉES (ne pas copier/verbatim) :
- marque = {marque}
- modele = {modele}
- annee = {annee}
- kilometrage = {kilometrage}
- carburant = {carburant}
- boite = {boite}
- couleur = {couleur}
- extra = {infos_supplementaires}

FEEDBACK (facultatif, à appliquer si présent):
{feedback}

TÂCHE:
- Si MODE=title: produire exactement un titre marketplace concis (≤{max_title_words} mots) dans la langue cible, en appliquant le FEEDBACK s'il existe.
- Si MODE=description: produire une description marketplace (≤{max_desc_words} mots, idéal 45–60) dans la langue cible, en appliquant le FEEDBACK s'il existe.
- Si MODE=rewrite: réécrire le texte fourni conformément au FEEDBACK.
Règles: ne jamais inclure prix, contacts, URL, emojis; omettre les infos manquantes; sortir UNIQUEMENT le texte final (pas de titres/étiquettes, pas de listes, pas de fences).
""".strip()


def _pick_system(locale: str, mode: str) -> str:
    loc = (locale or "Français").lower()
    m = (mode or "title").lower()
    if m == "title":
        return SYS_TITLE_EN if loc.startswith("en") else SYS_TITLE_FR
    if m == "description":
        return SYS_DESC_EN if loc.startswith("en") else SYS_DESC_FR
    return SYS_REWRITE_EN if loc.startswith("en") else SYS_REWRITE_FR


def _build_messages(locale: str, mode: str, ctx: dict, feedback: str = "", rewrite_text: str = ""):
    system_prompt = _pick_system(locale, mode)
    feedback_block = (feedback.strip() if feedback else "(none)")
    if mode == "rewrite" and rewrite_text:
        feedback_block = f"(rewrite target below)\n\nTEXT:\n{rewrite_text}"

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
        feedback=feedback_block,
        max_title_words=MAX_TITLE_WORDS,
        max_desc_words=MAX_DESC_WORDS,
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_payload},
    ]


# ===================== Post-traitements robustes =====================

# Supprimer d'éventuels en-têtes (Title:, Description:) et fences
HEAD_LABEL_RX = re.compile(r"(?im)^\s*(title|description|rewrite|titre|description)\s*:\s*")

# Détecter les formes "clé: valeur" interdites dans les titres
LABEL_IN_TITLE_RX = re.compile(
    r"\b(brand|model|year|mileage|fuel|gearbox|color|titre|marque|mod[eè]le|ann[eé]e|kilom[eé]trage|carburant|bo[iî]te|couleur)\b\s*:",
    re.I,
)

def _strip_headings(t: str) -> str:
    if not t:
        return ""
    t = HEAD_LABEL_RX.sub("", t)
    t = t.replace("```", " ")
    return t.strip()

def _clip_chars(txt: str, n: int = MAX_TITLE_CHARS) -> str:
    t = (txt or "").strip()
    if len(t) <= n:
        return t
    cut = t[:n]
    if " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut.strip()

def _clip_words(txt: str, max_words: int) -> str:
    t = (txt or "").strip()
    if not t:
        return ""
    words = re.findall(r"\S+", t, flags=re.UNICODE)
    if len(words) <= max_words:
        return " ".join(words)
    out = " ".join(words[:max_words]).rstrip(",;:").strip()
    return out

def _fmt_km(val) -> str:
    try:
        iv = int(str(val).strip())
    except Exception:
        return ""
    s = f"{iv:,}".replace(",", " ")
    return f"{s} km"

def _deterministic_title(ctx: Dict, locale: str) -> str:
    marque = (ctx.get("marque") or "").strip()
    modele = (ctx.get("modele") or "").strip()
    annee  = str(ctx.get("annee") or "").strip()
    km_str = _fmt_km(ctx.get("kilometrage"))
    parts = [p for p in [marque, modele, annee] if p]
    base = " ".join(parts).strip() or ("Vehicle listing" if (locale or "").lower().startswith("en") else "Annonce véhicule")
    if km_str:
        base = f"{base} • {km_str}"
    base = _clip_words(base, MAX_TITLE_WORDS)
    base = _clip_chars(base, MAX_TITLE_CHARS)
    return base

def _apply_feedback_to_title(title: str, ctx: Dict, feedback: str, locale: str) -> str:
    if not feedback:
        return title
    fb = feedback.lower()

    # Raccourcir si demandé
    if any(k in fb for k in ["plus court", "plus courte", "short", "shorter"]):
        title = _clip_words(title, max(8, MAX_TITLE_WORDS - 5))

    # Ajouter couleur si demandé
    if "couleur" in fb or "color" in fb:
        col = (ctx.get("couleur") or "").strip()
        if col and col.lower() not in title.lower():
            title = f"{title} {col}"

    # Ajouter année si demandé
    if "année" in fb or "annee" in fb or "year" in fb:
        an = str(ctx.get("annee") or "").strip()
        if an and an not in title:
            title = f"{title} {an}"

    # Ajouter kilométrage si demandé
    if "km" in fb or "kilométrage" in fb or "kilometrage" in fb or "mileage" in fb:
        km = _fmt_km(ctx.get("kilometrage"))
        if km and km.lower() not in title.lower():
            sep = " • " if " • " in title else " "
            title = f"{title}{sep}{km}"

    # Appliquer les limites
    title = _clip_words(title, MAX_TITLE_WORDS)
    title = _clip_chars(title, MAX_TITLE_CHARS)
    return title

def _sanitize_title(raw: str, ctx: Dict, locale: str, feedback: str) -> str:
    t = (raw or "").strip().replace("\n", " ").strip('"').strip("'")

    # Titre manquant -> fallback
    if not t:
        return _apply_feedback_to_title(_deterministic_title(ctx, locale), ctx, feedback, locale)

    # Interdictions: ":" ou "clé: valeur" -> fallback déterministe
    if ":" in t or LABEL_IN_TITLE_RX.search(t):
        t = _deterministic_title(ctx, locale)
    else:
        t = re.sub(r"\s+", " ", t).strip()

    # Limites (mots + chars)
    t = _clip_words(t, MAX_TITLE_WORDS)
    t = _clip_chars(t, MAX_TITLE_CHARS)

    # Si vide/bizarre -> fallback
    if not t or len(re.sub(r"[^\w]", "", t, flags=re.UNICODE)) < 2:
        t = _deterministic_title(ctx, locale)

    # Feedback
    t = _apply_feedback_to_title(t, ctx, feedback, locale)
    return t

def _postprocess_title(txt: str, ctx: Dict, locale: str, feedback: str) -> str:
    return _sanitize_title(txt, ctx, locale, feedback)


# Heuristique simple FR/EN (pour sécuriser la sortie vs locale)
_FR_HINTS = {" et ", " avec ", " km", " couleur", " année", " boîte", " en ", " état "}
_EN_HINTS = {" and ", " with ", " km", " color", " year", " gearbox", " in ", " condition "}

def _is_english(txt: str) -> bool:
    t = " " + (txt or "").lower() + " "
    en = sum(1 for w in _EN_HINTS if w in t)
    fr = sum(1 for w in _FR_HINTS if w in t)
    return en > fr + 1

def _deterministic_description(ctx: Dict, locale: str) -> str:
    fr = not str(locale).lower().startswith("en")
    marque = (ctx.get("marque") or "").strip()
    modele = (ctx.get("modele") or "").strip()
    annee  = str(ctx.get("annee") or "").strip()
    km     = _fmt_km(ctx.get("kilometrage"))
    carb   = (ctx.get("carburant") or "").strip()
    boite  = (ctx.get("boite") or "").strip()
    coul   = (ctx.get("couleur") or "").strip()
    extra  = (ctx.get("infos_supplementaires") or "").strip()

    if fr:
        parts = [s for s in [marque, modele, annee] if s]
        head = " ".join(parts).strip() or "Véhicule"
        sent = [f"{head} en bon état, prêt à rouler."]
        details = []
        if km:   details.append(f"Kilométrage {km}")
        if carb: details.append(f"Motorisation {carb}")
        if boite:details.append(f"Boîte {boite}")
        if coul: details.append(f"Couleur {coul}")
        if details:
            sent.append(" · ".join(details) + ".")
        if extra:
            e = extra if extra.endswith(".") else extra + "."
            sent.append(e)
        sent.append("Visite possible. Contactez-nous via la messagerie de la plateforme.")
        base = " ".join(sent)
    else:
        parts = [s for s in [marque, modele, annee] if s]
        head = " ".join(parts).strip() or "Vehicle"
        sent = [f"{head} in good condition, ready to drive."]
        details = []
        if km:   details.append(f"Mileage {km}")
        if carb: details.append(f"Fuel {carb}")
        if boite:details.append(f"Gearbox {boite}")
        if coul: details.append(f"Color {coul}")
        if details:
            sent.append(" · ".join(details) + ".")
        if extra:
            e = extra if extra.endswith(".") else extra + "."
            sent.append(e)
        sent.append("Viewing available. Message via the platform.")
        base = " ".join(sent)

    # Respecter la limite en mots
    base = _clip_words(base, MAX_DESC_WORDS)
    if base and base[-1] not in ".!?…":
        base += "."
    return base.strip()

def _postprocess_description(txt: str, ctx: Dict, locale: str, feedback: str) -> str:
    """
    Nettoyage description :
    - supprime headings (Title:, Description:)
    - force FR si locale FR et que le texte ressemble à de l'EN
    - 1 paragraphe, ≤ 60 mots, terminaison propre
    - feedback simple: raccourcir, ajouter couleur/année
    """
    t = (txt or "").strip().strip('"').strip("'")
    t = _strip_headings(t)
    t = re.sub(r"\s+", " ", t).strip()

    # FR strict si locale FR
    if not str(locale).lower().startswith("en") and _is_english(t):
        t = _deterministic_description(ctx, locale)

    # Limite maximale en mots
    t = _clip_words(t, MAX_DESC_WORDS)

    # Terminer proprement
    if t and t[-1] not in ".!?…":
        t += "."

    # Feedback
    fb = (feedback or "").lower()
    if fb:
        # plus courte
        if any(k in fb for k in ["plus court", "plus courte", "short", "shorter"]):
            t = _clip_words(t, max(35, MAX_DESC_WORDS - 10))
            if t and t[-1] not in ".!?…":
                t += "."
        # ajouter couleur
        if ("couleur" in fb or "color" in fb) and ctx.get("couleur"):
            if ctx["couleur"].lower() not in t.lower():
                t = t.rstrip(".") + (f". Couleur {ctx['couleur']}." if not str(locale).lower().startswith("en") else f". Color {ctx['couleur']}.")
                t = _clip_words(t, MAX_DESC_WORDS)
        # ajouter année
        if ("année" in fb or "annee" in fb or "year" in fb) and ctx.get("annee"):
            if str(ctx["annee"]) not in t:
                t = t.rstrip(".") + f" ({ctx['annee']})."
                t = _clip_words(t, MAX_DESC_WORDS)

    return t.strip()


# ===================== API publiques =====================

def generate_title(ctx: dict, feedback: str = "") -> str:
    client = get_client()
    locale = ctx.get("locale", "Français")
    msgs = _build_messages(locale, "title", ctx, feedback=feedback)
    out = client.chat(msgs)
    return _postprocess_title(out, ctx, locale, feedback)

def generate_description(ctx: dict, feedback: str = "") -> str:
    client = get_client()
    locale = ctx.get("locale", "Français")
    msgs = _build_messages(locale, "description", ctx, feedback=feedback)
    out = (client.chat(msgs) or "").strip()
    return _postprocess_description(out, ctx, locale, feedback)

def rewrite_text(ctx: dict, current_text: str, feedback: str) -> str:
    client = get_client()
    locale = ctx.get("locale", "Français")
    msgs = _build_messages(locale, "rewrite", ctx, feedback=feedback, rewrite_text=current_text)
    out = (client.chat(msgs) or "").strip()
    return _postprocess_description(out, ctx, locale, feedback)








