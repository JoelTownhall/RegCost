"""
Pirate mascot SVG components for the IALA Policy Toolkit.
- render_pirate(): friendly pirate for policy/data pages
- render_pirate_robot(): friendly pirate robot for AI chat pages
"""
import streamlit as st


_PIRATE_SVG = """
<div style="text-align:center; padding: 8px 0;">
  <svg xmlns="http://www.w3.org/2000/svg" width="140" height="180" viewBox="0 0 140 180">
    <!-- Hat brim -->
    <ellipse cx="70" cy="52" rx="40" ry="8" fill="#1a1a1a"/>
    <!-- Hat body -->
    <polygon points="38,52 50,10 90,10 102,52" fill="#1a1a1a"/>
    <!-- Hat band -->
    <rect x="38" y="46" width="64" height="8" fill="#c8a000"/>
    <!-- Skull on hat -->
    <ellipse cx="70" cy="28" rx="11" ry="10" fill="#f0f0f0"/>
    <circle cx="66" cy="26" r="2.5" fill="#1a1a1a"/>
    <circle cx="74" cy="26" r="2.5" fill="#1a1a1a"/>
    <path d="M64,32 Q70,36 76,32" stroke="#1a1a1a" stroke-width="1.5" fill="none"/>
    <!-- Crossbones -->
    <line x1="58" y1="38" x2="82" y2="38" stroke="#f0f0f0" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="60" y1="40" x2="62" y2="36" stroke="#f0f0f0" stroke-width="2" stroke-linecap="round"/>
    <line x1="80" y1="40" x2="78" y2="36" stroke="#f0f0f0" stroke-width="2" stroke-linecap="round"/>
    <!-- Head -->
    <ellipse cx="70" cy="78" rx="28" ry="26" fill="#f5c89a"/>
    <!-- Eye patch strap -->
    <line x1="44" y1="72" x2="98" y2="72" stroke="#1a1a1a" stroke-width="3"/>
    <!-- Eye patch -->
    <ellipse cx="56" cy="72" rx="10" ry="8" fill="#1a1a1a"/>
    <!-- Right eye -->
    <circle cx="84" cy="72" r="5" fill="white"/>
    <circle cx="84" cy="72" r="3" fill="#3a7bbf"/>
    <circle cx="85" cy="71" r="1" fill="white"/>
    <!-- Big grin -->
    <path d="M55,90 Q70,102 85,90" stroke="#1a1a1a" stroke-width="2.5" fill="white"/>
    <!-- Teeth -->
    <rect x="63" y="90" width="6" height="5" fill="white" stroke="#1a1a1a" stroke-width="0.5"/>
    <rect x="71" y="90" width="6" height="5" fill="white" stroke="#1a1a1a" stroke-width="0.5"/>
    <!-- Ear -->
    <ellipse cx="98" cy="78" rx="5" ry="7" fill="#f5c89a"/>
    <!-- Beard -->
    <path d="M48,94 Q55,115 70,118 Q85,115 92,94" fill="#4a3000" opacity="0.7"/>
    <!-- Body -->
    <rect x="45" y="104" width="50" height="55" rx="8" fill="#c0392b"/>
    <!-- Shirt stripe -->
    <rect x="45" y="118" width="50" height="6" fill="#922b21"/>
    <rect x="45" y="132" width="50" height="6" fill="#922b21"/>
    <!-- Left arm with scroll -->
    <rect x="22" y="104" width="14" height="38" rx="7" fill="#f5c89a" transform="rotate(-10, 29, 123)"/>
    <!-- Scroll -->
    <rect x="10" y="132" width="22" height="16" rx="3" fill="#f5e6c0" stroke="#8B7355" stroke-width="1.5"/>
    <line x1="14" y1="137" x2="28" y2="137" stroke="#8B7355" stroke-width="1"/>
    <line x1="14" y1="141" x2="28" y2="141" stroke="#8B7355" stroke-width="1"/>
    <line x1="14" y1="145" x2="24" y2="145" stroke="#8B7355" stroke-width="1"/>
    <!-- Right arm (hook) -->
    <rect x="104" y="104" width="14" height="35" rx="7" fill="#f5c89a" transform="rotate(10, 111, 121)"/>
    <!-- Hook -->
    <path d="M116,134 Q128,134 128,145 Q128,155 118,155" stroke="#aaa" stroke-width="4" fill="none" stroke-linecap="round"/>
    <!-- Belt -->
    <rect x="45" y="148" width="50" height="8" fill="#4a3000"/>
    <rect x="63" y="146" width="14" height="12" rx="2" fill="#c8a000"/>
  </svg>
  <div style="font-size:0.75rem; color:#666; margin-top:4px;">⚓ Cap'n Policy</div>
</div>
"""

_PIRATE_ROBOT_SVG = """
<div style="text-align:center; padding: 8px 0;">
  <svg xmlns="http://www.w3.org/2000/svg" width="140" height="185" viewBox="0 0 140 185">
    <!-- Pirate hat brim -->
    <ellipse cx="70" cy="32" rx="38" ry="7" fill="#1a1a1a"/>
    <!-- Hat body -->
    <polygon points="38,32 50,3 90,3 102,32" fill="#1a1a1a"/>
    <!-- Hat band -->
    <rect x="38" y="27" width="64" height="7" fill="#c8a000"/>
    <!-- Skull on hat -->
    <ellipse cx="70" cy="14" rx="9" ry="8" fill="#e0e0e0"/>
    <circle cx="66.5" cy="13" r="2" fill="#1a1a1a"/>
    <circle cx="73.5" cy="13" r="2" fill="#1a1a1a"/>
    <path d="M64,17 Q70,20 76,17" stroke="#1a1a1a" stroke-width="1.2" fill="none"/>
    <!-- Crossbones -->
    <line x1="60" y1="22" x2="80" y2="22" stroke="#e0e0e0" stroke-width="2" stroke-linecap="round"/>
    <!-- Antenna -->
    <line x1="70" y1="39" x2="70" y2="50" stroke="#888" stroke-width="2.5"/>
    <circle cx="70" cy="50" r="4" fill="#ff5555"/>
    <!-- Robot head -->
    <rect x="38" y="54" width="64" height="58" rx="10" fill="#5a8fa8"/>
    <!-- Head highlight -->
    <rect x="38" y="54" width="64" height="12" rx="10" fill="#6aa8c2" opacity="0.5"/>
    <!-- Screen face area -->
    <rect x="44" y="62" width="52" height="42" rx="6" fill="#1a2e3d"/>
    <!-- Left glowing eye -->
    <circle cx="60" cy="80" r="9" fill="#003355"/>
    <circle cx="60" cy="80" r="6" fill="#00aaff"/>
    <circle cx="60" cy="80" r="3" fill="#aaddff"/>
    <circle cx="62" cy="78" r="1.5" fill="white"/>
    <!-- Right glowing eye -->
    <circle cx="80" cy="80" r="9" fill="#003355"/>
    <circle cx="80" cy="80" r="6" fill="#00aaff"/>
    <circle cx="80" cy="80" r="3" fill="#aaddff"/>
    <circle cx="82" cy="78" r="1.5" fill="white"/>
    <!-- Friendly robot smile -->
    <path d="M53,96 Q70,108 87,96" stroke="#00aaff" stroke-width="3" fill="none" stroke-linecap="round"/>
    <!-- Smile dots -->
    <circle cx="57" cy="99" r="2" fill="#00aaff"/>
    <circle cx="83" cy="99" r="2" fill="#00aaff"/>
    <!-- Ear bolts -->
    <rect x="31" y="68" width="8" height="14" rx="4" fill="#4a7a90"/>
    <rect x="101" y="68" width="8" height="14" rx="4" fill="#4a7a90"/>
    <!-- Body -->
    <rect x="38" y="116" width="64" height="55" rx="8" fill="#4a7a90"/>
    <!-- Chest panel -->
    <rect x="48" y="124" width="44" height="30" rx="5" fill="#1a2e3d"/>
    <!-- AI label -->
    <text x="70" y="144" text-anchor="middle" font-family="monospace" font-size="14" font-weight="bold" fill="#00aaff">AI</text>
    <!-- Chest lights -->
    <circle cx="54" cy="130" r="3" fill="#ff5555"/>
    <circle cx="54" cy="140" r="3" fill="#55ff55"/>
    <circle cx="86" cy="130" r="3" fill="#ffaa00"/>
    <circle cx="86" cy="140" r="3" fill="#5555ff"/>
    <!-- Left arm -->
    <rect x="22" y="116" width="14" height="40" rx="7" fill="#4a7a90"/>
    <!-- Left hand gear -->
    <circle cx="29" cy="158" r="6" fill="#5a8fa8" stroke="#aaa" stroke-width="1.5"/>
    <line x1="29" y1="152" x2="29" y2="164" stroke="#aaa" stroke-width="1.5"/>
    <line x1="23" y1="158" x2="35" y2="158" stroke="#aaa" stroke-width="1.5"/>
    <!-- Right arm -->
    <rect x="104" y="116" width="14" height="40" rx="7" fill="#4a7a90"/>
    <!-- Right hand -->
    <rect x="100" y="156" width="22" height="10" rx="5" fill="#5a8fa8"/>
  </svg>
  <div style="font-size:0.75rem; color:#666; margin-top:4px;">🤖 Admiral Bot</div>
</div>
"""


def render_pirate(location: str = "sidebar"):
    """Render the friendly pirate mascot (for policy/data pages)."""
    if location == "sidebar":
        with st.sidebar:
            st.markdown(_PIRATE_SVG, unsafe_allow_html=True)
    else:
        st.markdown(_PIRATE_SVG, unsafe_allow_html=True)


def render_pirate_robot(location: str = "sidebar"):
    """Render the friendly pirate robot mascot (for AI chat pages)."""
    if location == "sidebar":
        with st.sidebar:
            st.markdown(_PIRATE_ROBOT_SVG, unsafe_allow_html=True)
    else:
        st.markdown(_PIRATE_ROBOT_SVG, unsafe_allow_html=True)
