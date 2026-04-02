"""
Authentication utilities for the IALA Policy Toolkit.
Password gate applied to all pages via check_auth().
"""
import streamlit as st

_PASSWORD = "AHOY"


def check_auth():
    """Check authentication. Shows login form and stops execution if not authenticated."""
    if not st.session_state.get("authenticated", False):
        _show_login()
        st.stop()


def logout():
    """Log the user out and reload."""
    st.session_state.authenticated = False
    st.rerun()


def _show_login():
    """Display the password login form."""
    st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: none; }
        .login-header {
            text-align: center;
            padding: 40px 0 20px 0;
        }
        .login-header h1 {
            color: #1f4e79;
            font-size: 2rem;
            margin-bottom: 0.25rem;
        }
        .login-header p {
            color: #555;
            font-size: 0.95rem;
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.6, 1])
    with col2:
        # Pirate mascot on the login page
        st.markdown("""
        <div style="text-align:center; margin-bottom: 8px;">
          <svg xmlns="http://www.w3.org/2000/svg" width="90" height="110" viewBox="0 0 140 180">
            <ellipse cx="70" cy="52" rx="40" ry="8" fill="#1a1a1a"/>
            <polygon points="38,52 50,10 90,10 102,52" fill="#1a1a1a"/>
            <rect x="38" y="46" width="64" height="8" fill="#c8a000"/>
            <ellipse cx="70" cy="28" rx="11" ry="10" fill="#f0f0f0"/>
            <circle cx="66" cy="26" r="2.5" fill="#1a1a1a"/>
            <circle cx="74" cy="26" r="2.5" fill="#1a1a1a"/>
            <path d="M64,32 Q70,36 76,32" stroke="#1a1a1a" stroke-width="1.5" fill="none"/>
            <line x1="58" y1="38" x2="82" y2="38" stroke="#f0f0f0" stroke-width="2.5" stroke-linecap="round"/>
            <ellipse cx="70" cy="78" rx="28" ry="26" fill="#f5c89a"/>
            <line x1="44" y1="72" x2="98" y2="72" stroke="#1a1a1a" stroke-width="3"/>
            <ellipse cx="56" cy="72" rx="10" ry="8" fill="#1a1a1a"/>
            <circle cx="84" cy="72" r="5" fill="white"/>
            <circle cx="84" cy="72" r="3" fill="#3a7bbf"/>
            <path d="M55,90 Q70,102 85,90" stroke="#1a1a1a" stroke-width="2.5" fill="white"/>
            <rect x="63" y="90" width="6" height="5" fill="white" stroke="#1a1a1a" stroke-width="0.5"/>
            <rect x="71" y="90" width="6" height="5" fill="white" stroke="#1a1a1a" stroke-width="0.5"/>
          </svg>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div class='login-header'>", unsafe_allow_html=True)
        st.markdown("## 🏴‍☠️ IALA Policy Toolkit")
        st.markdown("*Impact Analysis Lord Admiralty*")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""
        <div style="text-align:center; background:#f0f7ff; border-radius:8px; padding:10px; margin-bottom:12px; font-size:0.85rem; color:#1f4e79;">
        ⚓ A <strong>Vibecoding Club</strong> project — a fun way to explore AI-assisted policy analysis!
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password to board the ship",
            label_visibility="collapsed",
        )

        login_clicked = st.button("⚓ All Aboard!", use_container_width=True, type="primary")

        if login_clicked:
            if password.upper() == _PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Wrong password, landlubber! Try again. 🏴‍☠️")

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("For access, contact: admiral@iala.ahoy | 1800-AHOY-IALA")
