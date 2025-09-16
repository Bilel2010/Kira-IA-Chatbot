# app/flows/engine.py
# -*- coding: utf-8 -*-
"""
Moteur de flow JSON (prompt / question / action / terminal)

Points clés :
- Templating léger : variables {{ var }} + ternaires {{ cond ? A : B }}
- Localisation native : message_fr / message_en, label_fr / label_en
- Effects reliés au code : set / incr / call (pricing.estimate, generation.title, generation.description, media.upload_url)
- Boucle de feedback : exécuter les effects aussi dans les états 'question' après avoir sauvegardé la réponse
- Ternaires robustes : supporte `var == 'x'`, `var != 'x'`, `var` (truthy), `!var` / `not var`

Ce moteur est prévu pour fonctionner avec le flow `publish_voitures.json` partagé.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, List

from app.services.generation import (
    generate_title,
    generate_description,
    rewrite_text,  # prêt si un call "generation.rewrite" est ajouté côté flow
)

FLOW_FILE = os.path.join(os.path.dirname(__file__), "publish_voitures.json")

# ---------------------------------------------------------------------------
# Templating minimal
# ---------------------------------------------------------------------------

# {{ variable }}
_var_pat = re.compile(r"{{\s*([a-zA-Z0-9_\.]+)\s*}}")

# {{ condition ? A : B }}
# (on évaluera la condition nous-mêmes ; A et B peuvent contenir d'autres expressions)
_ternary_pat = re.compile(r"{{\s*(.+?)\s*\?\s*(.+?)\s*:\s*(.+?)\s*}}", re.DOTALL)

def _lookup(ctx: Dict[str, Any], path: str) -> Any:
    """Accès simple par 'a.b.c' dans le dictionnaire ctx."""
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur

def _eval_ternary_condition(expr: str, ctx: Dict[str, Any]) -> bool:
    """
    Évalue la condition des ternaires avec 4 formes supportées :
      1)  foo == 'bar'
      2)  foo != 'bar'
      3)  foo           (truthy si présent et non vide / non nul)
      4)  !foo / not foo
    """
    expr = (expr or "").strip()

    # 1) égalité / inégalité : foo == 'bar' | foo != 'bar'
    m = re.match(r"^\s*([a-zA-Z0-9_\.]+)\s*([=!]=)\s*'([^']*)'\s*$", expr)
    if m:
        left_name, op, right_val = m.group(1), m.group(2), m.group(3)
        left = _lookup(ctx, left_name)
        if op == "==":
            return str(left) == right_val
        else:
            return str(left) != right_val

    # 2) négation : !foo  ou  not foo
    m = re.match(r"^\s*(!|not\s+)?\s*([a-zA-Z0-9_\.]+)\s*$", expr)
    if m:
        neg, name = m.group(1), m.group(2)
        val = _lookup(ctx, name)
        truthy = bool(val) and str(val).lower() not in {"", "0", "false", "none", "null"}
        return not truthy if neg else truthy

    # Par défaut : False si on ne reconnaît pas la forme
    return False

def _render_value(text: str, ctx: Dict[str, Any]) -> str:
    """
    Rend les ternaires puis les variables (2 passes).
    - Les branches A/B peuvent elles-mêmes contenir des ternaires/variables (récursif).
    - Si le résultat final est encadré entièrement par des quotes, on les retire.
    """
    if not isinstance(text, str):
        return str(text)

    # --- Pass 1 : ternaires ---
    def ternary_sub(match: re.Match) -> str:
        cond_raw, a_raw, b_raw = match.group(1), match.group(2), match.group(3)
        cond_eval = _eval_ternary_condition(cond_raw, ctx)
        chosen = a_raw if cond_eval else b_raw
        # ⚠️ On re-rend récursivement la branche choisie (elle peut contenir {{}}, etc.)
        s = _render_value(chosen, ctx)
        # Si la branche est entièrement entre quotes, on dépouille (ex: 'texte')
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
            s = s[1:-1]
        return s

    # Remplacement itératif des ternaires (il peut y en avoir plusieurs / imbriquées)
    prev = None
    out = text
    # Pour éviter les boucles infinies, on fait un nombre raisonnable d'itérations
    for _ in range(10):
        new_out = _ternary_pat.sub(ternary_sub, out)
        if new_out == out:
            break
        out = new_out

    # --- Pass 2 : variables ---
    def var_sub(m: re.Match) -> str:
        v = _lookup(ctx, m.group(1))
        return "" if v is None else str(v)

    out = _var_pat.sub(var_sub, out)

    # Dépouiller des quotes globales éventuelles
    if len(out) >= 2 and out[0] == out[-1] and out[0] in ("'", '"'):
        out = out[1:-1]

    return out

# ---------------------------------------------------------------------------
# Chargement du flow
# ---------------------------------------------------------------------------

def load_flow() -> Dict[str, Any]:
    """Charge le JSON de flow."""
    with open(FLOW_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Helpers : langue, options, localisation des champs
# ---------------------------------------------------------------------------

_YES = {"yes", "y", "oui", "o"}
_NO = {"no", "n", "non"}

_LANG_FR = {"fr", "français", "francais", "french", "france"}
_LANG_EN = {"en", "eng", "english", "anglais"}

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _canon_lang(s: str) -> Optional[str]:
    v = _norm(s)
    if v in _LANG_FR or v == "français" or v == "francais":
        return "Français"
    if v in _LANG_EN or v == "english":
        return "English"
    return None

def _canon_yes_no(s: str, locale: str) -> Optional[str]:
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
    """Retourne les options localisées pour un état 'prompt'."""
    if locale == "English" and "options_en" in state:
        return state["options_en"]
    if locale != "English" and "options_fr" in state:
        return state["options_fr"]
    return state.get("options")

def _localized_value(state: Dict[str, Any], key: str, locale: str) -> Optional[str]:
    """
    Récupère une valeur localisée :
      - message_en / message_fr  (fallback sur message)
      - label_en   / label_fr    (fallback sur label)
    """
    if locale == "English":
        if f"{key}_en" in state:
            return state[f"{key}_en"]
        if key in state:
            return state[key]
        if f"{key}_fr" in state:
            return state[f"{key}_fr"]
    else:
        if f"{key}_fr" in state:
            return state[f"{key}_fr"]
        if key in state:
            return state[key]
        if f"{key}_en" in state:
            return state[f"{key}_en"]
    return None

def _canon_choice(user_choice: Optional[str], options: Optional[List[str]], locale: str) -> Optional[str]:
    """
    Ramène l'input utilisateur à une option canonique (oui/non/langue)
    sinon match insensible à la casse.
    """
    if user_choice is None:
        return None
    txt = _norm(user_choice)
    if not options:
        lang = _canon_lang(txt)
        if lang:
            return lang
        yn = _canon_yes_no(txt, locale or "Français")
        if yn:
            return yn
        return user_choice
    low_map = {_norm(o): o for o in (options or [])}
    if txt in low_map:
        return low_map[txt]
    yn = _canon_yes_no(txt, locale or "Français")
    if yn and yn in (options or []):
        return yn
    return None

# ---------------------------------------------------------------------------
# Effects (set / incr / call)
# ---------------------------------------------------------------------------

def _apply_set(ctx: Dict[str, Any], payload: Dict[str, Any]):
    """Effect: set → pose des variables dans le contexte (avec templating)."""
    for k, v in payload.items():
        if isinstance(v, str):
            v = _render_value(v, ctx)
        ctx[k] = v

def _apply_incr(ctx: Dict[str, Any], key: str):
    """Effect: incr → incrémente un compteur simple."""
    ctx[key] = int(ctx.get(key, 0)) + 1

def _apply_call(ctx: Dict[str, Any], call: str, with_feedback: Optional[str] = None):
    """
    Effect: call → connecte le flow JSON aux fonctions Python (services).
    - pricing.estimate        (stub)
    - generation.title        (avec feedback optionnel)
    - generation.description  (avec feedback optionnel)
    - media.upload_url        (stub)
    """
    try:
        if call == "pricing.estimate":
            ctx["price_suggested"] = max(1000, int(ctx.get("price_user") or 0)) or 15000
            ctx["pricing_confidence"] = 0.72

        elif call == "generation.title":
            feedback = ctx.get(with_feedback) if with_feedback else ""
            try:
                title = generate_title(ctx, feedback=feedback or "")
            except Exception as e:
                ctx.setdefault("errors", []).append(f"generation.title error: {type(e).__name__}: {e}")
                title = ""

            if not title:
                # Fallback déterministe
                marque = ctx.get("marque", "")
                modele = ctx.get("modele", "")
                year = ctx.get("annee", "")
                title = " ".join([str(x) for x in [marque, modele, year] if x]).strip() or "Annonce véhicule"
            ctx["generated_title"] = title

        elif call == "generation.description":
            feedback = ctx.get(with_feedback) if with_feedback else ""
            try:
                desc = generate_description(ctx, feedback=feedback or "")
            except Exception as e:
                ctx.setdefault("errors", []).append(f"generation.description error: {type(e).__name__}: {e}")
                desc = ""

            if not desc:
                # Fallback déterministe
                base = (
                    f"{ctx.get('marque','')} {ctx.get('modele','')} {ctx.get('annee','')}, "
                    f"{ctx.get('kilometrage','')} km, {ctx.get('carburant','')}, "
                    f"boîte {ctx.get('boite','')}, couleur {ctx.get('couleur','')}."
                ).strip()
                if feedback:
                    base += f" Ajustements: {feedback}"
                desc = base or "Annonce véhicule."
            ctx["generated_description"] = desc

        elif call == "media.upload_url":
            ctx["upload_url"] = "https://example.com/upload/mock"

    except Exception as e:
        ctx.setdefault("errors", []).append(f"call:{call} -> {type(e).__name__}: {e}")

def apply_effects(ctx: Dict[str, Any], effects: Optional[list]):
    """Applique la liste d'effets d'un état."""
    if not effects:
        return
    for eff in effects:
        if "set" in eff:
            _apply_set(ctx, eff["set"])
        if "incr" in eff:
            _apply_incr(ctx, eff["incr"])
        if "call" in eff:
            _apply_call(ctx, eff["call"], eff.get("with_feedback"))

# ---------------------------------------------------------------------------
# Validation simple
# ---------------------------------------------------------------------------

def _validate(state: Dict[str, Any], value: str) -> bool:
    """Validation basique selon la config de l'état."""
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

# ---------------------------------------------------------------------------
# Engine API
# ---------------------------------------------------------------------------

def ensure_flow_session(sess: Dict[str, Any], flow: Dict[str, Any]):
    """Initialise la session de flow si nécessaire."""
    sess.setdefault("flow", {})
    sess["flow"]["id"] = flow["flow_id"]
    sess["flow"].setdefault("vars", {})
    sess["flow"].setdefault("counters", {})
    sess["flow"].setdefault("current", flow["entry"])

def start_flow(flow: Dict[str, Any], sess: Dict[str, Any]) -> Dict[str, Any]:
    """Reset et démarre le flow à l'état d'entrée."""
    sess["flow"] = {"id": flow["flow_id"], "vars": {}, "counters": {}, "current": flow["entry"]}
    first_state = flow["states"][flow["entry"]]
    return render_state(first_state, sess["flow"]["vars"])

def get_current_state(flow: Dict[str, Any], sess: Dict[str, Any]) -> Dict[str, Any]:
    """Retourne l'état courant."""
    states = flow["states"]
    cur = sess["flow"].get("current")
    if not cur:
        cur = flow["entry"]
        sess["flow"]["current"] = cur
    return states[cur]

def next_for_prompt(flow, sess, user_choice: Optional[str]) -> Dict[str, Any]:
    """Gestion d'un état 'prompt' (boutons Oui/Non/langue...)."""
    states = flow["states"]
    cur = get_current_state(flow, sess)
    locale = sess["flow"]["vars"].get("locale") or "Français"
    loc_options = _localized_prompt_options(cur, locale)

    # Normalise la langue si c'est le tout premier choix
    if user_choice is not None and cur is states[flow["entry"]]:
        canon = _canon_lang(user_choice)
        if canon:
            user_choice = canon

    # Exécute les effets (peuvent dépendre de {{user_choice}})
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
        return render_state(cur, sess["flow"]["vars"])

    sess["flow"]["current"] = nxt
    return render_state(states[nxt], sess["flow"]["vars"])

def next_for_question(flow, sess, answer_text: str) -> Dict[str, Any]:
    """Gestion d'un état 'question' (saisie attributs)."""
    states = flow["states"]
    cur_key = sess["flow"]["current"]
    cur = states[cur_key]
    attr = cur["attribute"]

    # 1) Validation
    if not _validate(cur, answer_text):
        nxt = cur.get("on_invalid") or cur_key
        sess["flow"]["current"] = nxt
        return render_state(states[nxt], sess["flow"]["vars"])

    # 2) Mapping EN->FR si enum et locale EN (via enum_map_en)
    locale = sess["flow"]["vars"].get("locale") or "Français"
    val = answer_text
    if cur.get("input", {}).get("type") == "enum" and locale == "English":
        m = cur["input"].get("enum_map_en") or {}
        key = (answer_text or "").strip().lower()
        if key in m:
            val = m[key]

    # 3) Sauvegarder la réponse
    sess["flow"]["vars"][attr] = val

    # 4) ⚠️ Exécuter les effects de l'état question (ex: generation.* avec with_feedback)
    apply_effects(sess["flow"]["vars"], cur.get("effects"))

    # 5) Transition
    nxt = cur.get("on_valid") or cur_key
    sess["flow"]["current"] = nxt
    return render_state(states[nxt], sess["flow"]["vars"])

def next_for_action(flow, sess) -> Dict[str, Any]:
    """Gestion d'un état 'action' (appel pricing/generation/etc.)."""
    states = flow["states"]
    cur = get_current_state(flow, sess)
    apply_effects(sess["flow"]["vars"], cur.get("effects"))
    nxt = cur.get("on_complete")
    if not nxt:
        return render_state(cur, sess["flow"]["vars"])
    sess["flow"]["current"] = nxt
    return render_state(states[nxt], sess["flow"]["vars"])

def check_guards(cur: Dict[str, Any], sess: Dict[str, Any]) -> Optional[str]:
    """Garde-fous (ex: limite d'itérations feedback)."""
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
    Prépare la réponse API pour l'état courant :
    - message/label localisés (message_fr/message_en, label_fr/label_en) avec fallback
    - templating double passe (ternaires + variables)
    - options : prompt → localisées ; question enum → options (FR/EN)
    """
    locale = vars_ctx.get("locale") or "Français"
    rendered: Dict[str, Any] = {"type": state["type"]}

    # Message (localisé)
    msg_tpl = _localized_value(state, "message", locale)
    if msg_tpl is not None:
        msg = _render_value(msg_tpl, vars_ctx)
        # Double passe utile si la 1re passe produit de nouvelles expressions
        msg = _render_value(msg, vars_ctx)
        rendered["message"] = msg

    # Label (localisé)
    lab_tpl = _localized_value(state, "label", locale)
    if lab_tpl is not None:
        lab = _render_value(lab_tpl, vars_ctx)
        lab = _render_value(lab, vars_ctx)
        rendered["label"] = lab

    # Options (prompt)
    if state["type"] == "prompt":
        loc_opts = _localized_prompt_options(state, locale)
        if loc_opts is not None:
            rendered["options"] = loc_opts

    # Attributs & options (question enum)
    if state["type"] == "question":
        rendered["attribute"] = state["attribute"]
        if state.get("input", {}).get("type") == "enum":
            if locale == "English" and "options_en" in state["input"]:
                rendered["options"] = state["input"]["options_en"]
            else:
                rendered["options"] = state["input"].get("options", [])

    return rendered

def step(flow: Dict[str, Any], sess: Dict[str, Any], user_input: Optional[str]) -> Dict[str, Any]:
    """
    Boucle principale du moteur (appelée à chaque /flow/reply).
    - Récupère l'état courant
    - Applique garde-fous
    - Délègue selon le type d'état
    """
    ensure_flow_session(sess, flow)
    states = flow["states"]

    cur = get_current_state(flow, sess)

    # Guards éventuels (ex: limite feedback)
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
        nxt = cur.get("on_complete")
        if nxt:
            sess["flow"]["current"] = nxt
            return render_state(states[nxt], sess["flow"]["vars"])
        return render_state(cur, sess["flow"]["vars"])
    elif stype == "terminal":
        return render_state(cur, sess["flow"]["vars"])
    else:
        return {"type": "error", "message": f"Unknown state type: {stype}"}









