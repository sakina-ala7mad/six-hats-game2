"""
Cute round face avatars wearing colored hats, used in the team lobby /
active-round screen. States:
  - "off"       : slot not joined yet -> dark gray, dimmed
  - "waiting"   : joined, hat not revealed yet -> gray face, gray hat
  - "revealed"  : hat color revealed, round in progress -> full color, neutral face
  - "submitted" : player has submitted -> full color, smiling face
"""

GRAY = "#8A8F98"
GRAY_DIM = "#3A3D44"


def face_svg(hat_hex: str, state: str, size: int = 68) -> str:
    if state == "off":
        hat_color = GRAY_DIM
        face_color = "#5B5F68"
        mouth = "line"
        opacity = "0.55"
    elif state == "waiting":
        hat_color = GRAY
        face_color = "#F2D9B8"
        mouth = "line"
        opacity = "1"
    elif state == "submitted":
        hat_color = hat_hex
        face_color = "#F2D9B8"
        mouth = "smile"
        opacity = "1"
    else:  # revealed
        hat_color = hat_hex
        face_color = "#F2D9B8"
        mouth = "neutral"
        opacity = "1"

    if mouth == "smile":
        mouth_path = 'M 24 42 Q 34 52 44 42'
    elif mouth == "line":
        mouth_path = 'M 26 42 Q 34 44 42 42'
    else:
        mouth_path = 'M 26 43 Q 34 46 42 43'

    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 68 68" style="opacity:{opacity}">
      <circle cx="34" cy="38" r="22" fill="{face_color}" />
      <circle cx="26" cy="35" r="3" fill="#2B2B2B" />
      <circle cx="42" cy="35" r="3" fill="#2B2B2B" />
      <path d="{mouth_path}" stroke="#2B2B2B" stroke-width="2.5" fill="none" stroke-linecap="round"/>
      <path d="M 12 24 Q 34 -4 56 24 Q 56 14 34 12 Q 12 14 12 24 Z" fill="{hat_color}" stroke="rgba(0,0,0,0.15)" stroke-width="1"/>
      <rect x="10" y="22" width="48" height="6" rx="3" fill="{hat_color}" />
    </svg>
    """


def face_block_html(name: str, hat_hex: str, state: str) -> str:
    svg = face_svg(hat_hex, state)
    display_name = name if state != "off" else "&mdash;"
    return f"""
    <div class="sh-face-wrap">
      {svg}
      <div class="sh-face-name">{display_name}</div>
    </div>
    """
