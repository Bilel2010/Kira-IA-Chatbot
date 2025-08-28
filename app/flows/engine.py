# app/flows/engine.py
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, List

# === Intégration génération LLM (titre/description/réécriture) ===
# Ces fonctions doivent exister dans app/services/generation.py
from app.services.generation import (
    generate_title,
    generate_description,
    rewrite_text,
)

FLOW_FILE = os.path.join(os.path.dirname(__file__), "publish_voitures.json")

# ----------------- Mini moteur de templating -----------------
# Supporte:
#   - ternaires: {{ locale == 'English' ? 'Hello' : 'Bonjour' }}
#   - variables: {{ marque }}, {{kilometrage}}, etc.
_var_pat = re.compile(r"{{\s*([a-zA-Z0-9_\.]+)\s*}}")
_ternary_pat = re.compile(r"{{\s*(.+?)\s*\?\s*(.+?)\s*:\s*(.+?)\s*}}")


def _lookup(ctx: Dict[str, Any], path: str) -> Any:
    """Recherche récursive d’une variable dans le contexte (vars du flow)."""
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _render_value(value: str, ctx: Dict[str, Any]) -> str:
    """Rend une string contenant {{var}} et ternaires {{ cond ? 'A' : 'B' }}."""

    def ternary_sub(m):
        cond, a, b = m.group(1), m.group(2), m.group(3)
        cond_eval = False
        cm = re.match(r"^\s*([a-zA-Z0-9_\.]+)\s*==\s*'([^']*)'\s*$", cond)
        if cm:
            left = _lookup(ctx, cm.group(1))
            cond_eval = (str(left) == cm.group(2))
        chosen = a if cond_eval else b
        s = _render_value(chosen, ctx)
        # enlève d’éventuelles quotes englobantes
        if len(s) >= 2 and (s[0] == s[-1]) and s[0] in ("'", '"'):
            s = s[1:-1]
        return s

    # 1) Évalue les ternaires
    value = _ternary_pat.sub(ternary_sub, value)

    # 2) Remplace les {{vars}}
    def var_sub(m):
        v = _lookup(ctx, m.group(1))
        return str(v) if v is not None else ""

    out = _var_pat.sub(var_sub, value)

    # 3) Nettoyage final: quotes parasites
    if len(out) >= 2 and (out[0] == out[-1]) and out[0] in ("'", '"'):
        out = out[1:-1]
    return out


# ----------------- Chargement du flow -----------------
def load_flow() -> Dict[str, Any]:
    """Charge le JSON de flow (voitures)."""
    with open(FLOW_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ----------------- Helpers: langue, casse & options -----------------
_YES = {"yes", "y", "oui", "o"}
_NO = {"no", "n", "non"}

_LANG_FR = {"fr", "français", "francais", "french", "france"}
_LANG_EN = {"en", "eng", "english", "anglais"}


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _canon_lang(s: str) -> Optional[str]:
    """Normalise la langue en 'Français' ou 'English'."""
    v = _norm(s)
    if v in _LANG_FR:
        return "Français"
    if v in _LANG_EN:
        return "English"
    if v in {"français", "francais"}:
        return "Français"
    if v == "english":
        return "English"
    return None


def _canon_yes_no(s: str, locale: str) -> Optional[str]:
    """Normalise Yes/No ou Oui/Non selon la locale active (insensible à la casse)."""
    v = _norm(s)
    if v in _YES:
        return "Yes" if locale == "English" else "Oui"
    if v in _NO:
        return "No" if locale == "English" else "Non"
    if v in {"oui", "non"}:
        return v.capitalize()
    if v in {"yes", "no"}:
        return v.capitalize()
    return None


def _localized_prompt_options(state: Dict[str, Any], locale: str) -> Optional[List[str]]:
    """
    Pour les PROMPTS (assist_opt_in, recap, pricing...), on choisit les options
    localisées si disponibles: options_fr / options_en ; sinon "options".
    """
    if locale == "English" and "options_en" in state:
        return state["options_en"]
    if locale != "English" and "options_fr" in state:
        return state["options_fr"]
    return state.get("options")


def _canon_choice(
    user_choice: Optional[str], options: Optional[List[str]], locale: str
) -> Optional[str]:
    """
    Essaie de ramener l’input user à une option canonique (oui/non/langue),
    sinon, match insensible à la casse si options listées.
    """
    if user_choice is None:
        return None
    txt = _norm(user_choice)
    if not options:
        # cas q_locale / prompts sans options localisées
        lang = _canon_lang(txt)
        if lang:
            return lang
        yn = _canon_yes_no(txt, locale or "Français")
        if yn:
            return yn
        return user_choice  # laisse passer tel quel
    low_map = {_norm(o): o for o in options}
    if txt in low_map:
        return low_map[txt]
    yn = _canon_yes_no(txt, locale or "Français")
    if yn and yn in options:
        return yn
    return None


# ----------------- Effects -----------------
def _apply_set(ctx: Dict[str, Any], payload: Dict[str, Any]):
    """Effect: set de variables dans le contexte (avec templating rendu)."""
    for k, v in payload.items():
        if isinstance(v, str):
            v = _render_value(v, ctx)
        ctx[k] = v


def _apply_incr(ctx: Dict[str, Any], key: str):
    """Effect: incrément d’un compteur (ex: title_iters)."""
    ctx[key] = int(ctx.get(key, 0)) + 1


def _apply_call(ctx: Dict[str, Any], call: str, with_feedback: Optional[str] = None):
    """
    Effect: appels métiers.
    Supporte: pricing.estimate, generation.title, generation.description, media.upload_url.
    Intègre réellement la génération via app/services/generation.py.
    """
    try:
        if call == "pricing.estimate":
            # Stub simple : tu pourras brancher un vrai modèle plus tard
            ctx["price_suggested"] = max(1000, int(ctx.get("price_user") or 0)) or 15000
            ctx["pricing_confidence"] = 0.72

        elif call == "generation.title":
            feedback = ctx.get(with_feedback) if with_feedback else ""
            # Utilise ctx (locale + attributs déjà posés)
            title = generate_title(ctx, feedback=feedback or "")
            # fallback de sécurité
            if not title:
                marque = ctx.get("marque", "")
                modele = ctx.get("modele", "")
                year = ctx.get("annee", "")
                title = f"{marque} {modele} {year}".strip()
            ctx["generated_title"] = title

        elif call == "generation.description":
            feedback = ctx.get(with_feedback) if with_feedback else ""
            desc = generate_description(ctx, feedback=feedback or "")
            if not desc:
                # fallback sobre
                base = (
                    f"{ctx.get('marque','')} {ctx.get('modele','')} {ctx.get('annee','')}, "
                    f"{ctx.get('kilometrage','')} km, {ctx.get('carburant','')}, "
                    f"boîte {ctx.get('boite','')}, couleur {ctx.get('couleur','')}."
                )
                if feedback:
                    base += f" Ajustements: {feedback}"
                desc = base
            ctx["generated_description"] = desc

        elif call == "media.upload_url":
            ctx["upload_url"] = "https://example.com/upload/mock"

        # (Optionnel) un futur call "generation.rewrite" pourrait utiliser rewrite_text(ctx, current, feedback)

    except Exception as e:
        # En cas d’erreur LLM/SDK: ne bloque pas le flow
        ctx.setdefault("errors", []).append(f"call:{call} -> {type(e).__name__}: {e}")


def apply_effects(ctx: Dict[str, Any], effects: Optional[list]):
    """Applique enchaînement d’effets (set/incr/call)."""
    if not effects:
        return
    for eff in effects:
        if "set" in eff:
            _apply_set(ctx, eff["set"])
        if "incr" in eff:
            _apply_incr(ctx, eff["incr"])
        if "call" in eff:
            _apply_call(ctx, eff["call"], eff.get("with_feedback"))


# ----------------- Validation simple -----------------
def _validate(state: Dict[str, Any], value: str) -> bool:
    """Validation simple (required, int range, longueur min)."""
    v = state.get("validation") or {}
    if v.get("required") and not str(value).strip():
        return False
    if state.get("input", {}).get("type") == "int":
        if not str(value).strip().isdigit():
            return False
        iv = int(value)
        if "min" in v and iv < v["min"]:
            return False
        if "max" in v and iv > v["max"]:
            return False
    if v.get("min_len") and len(str(value)) < v["min_len"]:
        return False
    return True


# ----------------- Engine API -----------------
def ensure_flow_session(sess: Dict[str, Any], flow: Dict[str, Any]):
    """Initialise les champs essentiels de la session flow si manquants."""
    sess.setdefault("flow", {})
    sess["flow"]["id"] = flow["flow_id"]
    sess["flow"].setdefault("vars", {})
    sess["flow"].setdefault("counters", {})
    sess["flow"].setdefault("current", flow["entry"])


def start_flow(flow: Dict[str, Any], sess: Dict[str, Any]) -> Dict[str, Any]:
    """Démarre le flow depuis l’état d’entrée (reset propre)."""
    sess["flow"] = {
        "id": flow["flow_id"],
        "vars": {},
        "counters": {},
        "current": flow["entry"],
    }
    first_state = flow["states"][flow["entry"]]
    return render_state(first_state, sess["flow"]["vars"])


def get_current_state(flow: Dict[str, Any], sess: Dict[str, Any]) -> Dict[str, Any]:
    """Récupère l’état courant de la session (sinon entry)."""
    states = flow["states"]
    cur = sess["flow"].get("current")
    if not cur:
        cur = flow["entry"]
        sess["flow"]["current"] = cur
    return states[cur]


def next_for_prompt(flow, sess, user_choice: Optional[str]) -> Dict[str, Any]:
    """Gestion d’un prompt (Oui/Non/langue/etc.)."""
    states = flow["states"]
    cur = get_current_state(flow, sess)
    locale = sess["flow"]["vars"].get("locale") or "Français"

    loc_options = _localized_prompt_options(cur, locale)

    # Canoniser la langue si q_locale
    if user_choice is not None and cur is states[flow["entry"]]:
        canon = _canon_lang(user_choice)
        if canon:
            user_choice = canon

    # Injecter temporairement user_choice dans le contexte pour les effets ({{user_choice}})
    if user_choice is not None:
        sess["flow"]["vars"]["user_choice"] = user_choice
        apply_effects(sess["flow"]["vars"], cur.get("effects"))
        sess["flow"]["vars"].pop("user_choice", None)
    else:
        apply_effects(sess["flow"]["vars"], cur.get("effects"))

    # Transition
    nxt = None
    if user_choice is not None:
        selected = _canon_choice(user_choice, loc_options, locale)
        key = selected if selected is not None else user_choice
        if "on_reply" in cur:
            nxt = cur["on_reply"].get(key)

    if not nxt and "on_complete" in cur:
        nxt = cur["on_complete"]

    if not nxt:
        # choix invalide → rester sur place (le front réaffiche les options)
        return render_state(cur, sess["flow"]["vars"])

    sess["flow"]["current"] = nxt
    return render_state(states[nxt], sess["flow"]["vars"])


def next_for_question(flow, sess, answer_text: str) -> Dict[str, Any]:
    """Gestion d’une question attribut (input texte/enum/int)."""
    states = flow["states"]
    cur_key = sess["flow"]["current"]
    cur = states[cur_key]
    attr = cur["attribute"]

    # Validation
    if not _validate(cur, answer_text):
        nxt = cur.get("on_invalid") or cur_key
        sess["flow"]["current"] = nxt
        return render_state(states[nxt], sess["flow"]["vars"])

    # Mapping EN->FR si enum et locale EN
    locale = sess["flow"]["vars"].get("locale") or "Français"
    val = answer_text
    if cur.get("input", {}).get("type") == "enum" and locale == "English":
        m = cur["input"].get("enum_map_en") or {}
        key = (answer_text or "").strip().lower()
        if key in m:
            val = m[key]

    # Sauvegarder réponse
    sess["flow"]["vars"][attr] = val

    nxt = cur.get("on_valid") or cur_key
    sess["flow"]["current"] = nxt
    return render_state(states[nxt], sess["flow"]["vars"])


def next_for_action(flow, sess) -> Dict[str, Any]:
    """Gestion d’un état action (appel pricing/generation/etc.)."""
    states = flow["states"]
    cur = get_current_state(flow, sess)
    apply_effects(sess["flow"]["vars"], cur.get("effects"))
    nxt = cur.get("on_complete")
    if not nxt:
        return render_state(cur, sess["flow"]["vars"])
    sess["flow"]["current"] = nxt
    return render_state(states[nxt], sess["flow"]["vars"])


def check_guards(cur: Dict[str, Any], sess: Dict[str, Any]) -> Optional[str]:
    """Vérifie les gardes (sauts conditionnels selon compteurs)."""
    guards = cur.get("guards") or []
    for g in guards:
        if g.get("if_counter_exceeds"):
            key = g["if_counter_exceeds"]
            maxv = g["max"]
            if int(sess["flow"]["vars"].get(key, 0)) > int(maxv):
                return g["goto"]
    return None


def render_state(state: Dict[str, Any], vars_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prépare la réponse API pour un état donné.
    - message/label: double passe pour bien résoudre les ternaires imbriquées + {{vars}}
    - options: prompt → options localisées ; question enum → options (FR/EN)
    """
    locale = vars_ctx.get("locale") or "Français"
    rendered: Dict[str, Any] = {"type": state["type"]}

    if "message" in state:
        msg = _render_value(state["message"], vars_ctx)
        msg = _render_value(msg, vars_ctx)  # seconde passe si besoin
        rendered["message"] = msg

    if "label" in state:
        lab = _render_value(state["label"], vars_ctx)
        lab = _render_value(lab, vars_ctx)
        rendered["label"] = lab

    if state["type"] == "prompt":
        loc_opts = _localized_prompt_options(state, locale)
        if loc_opts is not None:
            rendered["options"] = loc_opts

    if state["type"] == "question":
        rendered["attribute"] = state["attribute"]
        if state.get("input", {}).get("type") == "enum":
            # options côté question (boutons)
            if locale == "English" and "options_en" in state["input"]:
                rendered["options"] = state["input"]["options_en"]
            else:
                rendered["options"] = state["input"].get("options", [])

    return rendered


def step(flow: Dict[str, Any], sess: Dict[str, Any], user_input: Optional[str]) -> Dict[str, Any]:
    """Boucle principale du moteur (appelée à chaque /flow/reply)."""
    ensure_flow_session(sess, flow)
    states = flow["states"]

    cur = get_current_state(flow, sess)

    # Guards éventuels (ex: limite d’itérations feedback)
    goto = check_guards(cur, sess)
    if goto:
        sess["flow"]["current"] = goto
        cur = states[goto]

    stype = cur["type"]
    if stype == "prompt":
        return next_for_prompt(flow, sess, user_input)
    elif stype == "question":
        if user_input is None:
            return render_state(cur, sess["flow"]["vars"])
        return next_for_question(flow, sess, user_input)
    elif stype == "action":
        return next_for_action(flow, sess)
    elif stype == "noop":
        # auto-advance pour éviter les blocages
        nxt = cur.get("on_complete")
        if nxt:
            sess["flow"]["current"] = nxt
            return render_state(states[nxt], sess["flow"]["vars"])
        return render_state(cur, sess["flow"]["vars"])
    elif stype == "terminal":
        return render_state(cur, sess["flow"]["vars"])
    else:
        return {"type": "error", "message": f"Unknown state type: {stype}"}





