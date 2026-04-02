import streamlit as st

def apply_custom_css():
    """Apply custom CSS for mobile optimization."""
    st.markdown("""
        <style>
        /* Reduce main container padding for mobile */
        @media (max-width: 768px) {
            .block-container {
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-top: 2rem !important;
                padding-bottom: 1rem !important;
            }
            
            /* Make metrics look better on small screens */
            [data-testid="stMetricValue"] {
                font-size: 1.5rem !important;
            }
            
            /* Adjust chart container margins */
            .js-plotly-plot {
                margin-left: -10px !important;
                margin-right: -10px !important;
            }
            
            /* Improve expander readability */
            .streamlit-expanderHeader {
                font-size: 1rem !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)
