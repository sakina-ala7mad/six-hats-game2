"""
Theme handling.

Streamlit's built-in dark/light mode does not automatically recolor custom
HTML we inject, which is exactly the "white text on white background" bug
called out in the design notes. This module defines two explicit palettes
and injects them as CSS variables, so every custom element (hat buttons,
face avatars, cards) always has a text color guaranteed to contrast with
its background, in both modes.
"""
import streamlit as st

LIGHT = {
    "bg": "#F7F8FC",
    "card_bg": "rgba(255,255,255,0.75)",
    "text": "#1B1F27",
    "text_muted": "#4B5160",
    "accent": "#457B9D",
    "border": "rgba(27,31,39,0.08)",
}

DARK = {
    "bg": "#12131A",
    "card_bg": "rgba(255,255,255,0.06)",
    "text": "#F2F3F7",
    "text_muted": "#B7BBC9",
    "accent": "#7EC8E3",
    "border": "rgba(255,255,255,0.10)",
}


def inject_theme(mode: str):
    """mode is 'light' or 'dark'. Call once near the top of every page render."""
    p = LIGHT if mode == "light" else DARK
    st.markdown(
        f"""
        <style>
        :root {{
            --bg: {p['bg']};
            --card-bg: {p['card_bg']};
            --text: {p['text']};
            --text-muted: {p['text_muted']};
            --accent: {p['accent']};
            --border: {p['border']};
        }}

        .stApp {{
            background: var(--bg);
        }}

        /* force every bit of custom-rendered text to the theme color,
           so it never collides with the background (no white-on-white,
           no black-on-black) */
        .six-hats-text, .six-hats-text * ,
        .sh-card, .sh-card * ,
        .sh-title, .sh-subtitle, .sh-badge, .sh-muted {{
            color: var(--text) !important;
        }}
        .sh-muted {{ color: var(--text-muted) !important; }}

        .sh-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 18px 20px;
            margin-bottom: 14px;
            backdrop-filter: blur(6px);
            box-shadow: 0 6px 24px rgba(0,0,0,0.08);
        }}

        .sh-title {{
            font-size: 1.4rem;
            font-weight: 800;
            margin-bottom: 4px;
        }}
        .sh-subtitle {{
            font-size: 0.95rem;
            opacity: 0.85;
        }}
        .sh-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 999px;
            background: var(--accent);
            color: white !important;
            font-size: 0.75rem;
            font-weight: 700;
        }}

        div.stButton > button {{
            border-radius: 16px !important;
            border: 1px solid var(--border) !important;
            padding: 10px 16px !important;
            font-weight: 700 !important;
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }}
        div.stButton > button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        }}

        .sh-face-wrap {{
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 92px;
        }}
        .sh-face-name {{
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text) !important;
            margin-top: 4px;
            max-width: 88px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            text-align: center;
        }}

        .sh-timer {{
            font-size: 2rem;
            font-weight: 900;
            color: var(--accent) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def card(html_inner: str):
    st.markdown(f"<div class='sh-card six-hats-text'>{html_inner}</div>", unsafe_allow_html=True)
