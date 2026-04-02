"""
Authentication utilities for the OIA Policy Toolkit.
Password gate applied to all pages via check_auth().
"""
import streamlit as st

_PASSWORD = "OIA"


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
        st.markdown("<div class='login-header'>", unsafe_allow_html=True)
        st.markdown("## ⚖️ OIA Policy Toolkit")
        st.markdown("*Office of Impact Analysis — Department of the Prime Minister and Cabinet*")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password to access toolkit",
            label_visibility="collapsed",
        )

        login_clicked = st.button("Sign In", use_container_width=True, type="primary")

        if login_clicked:
            if password.upper() == _PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("For access, contact: helpdesk-OIA@pmc.gov.au | 02 6271 6270")
