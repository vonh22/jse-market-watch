import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, Tuple, Optional, List

class JSEScraper:
    """Class to handle JSE web scraping operations"""
    
    def __init__(self, url: str):
        self.url = url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def fetch_tables(self) -> Optional[Dict[str, pd.DataFrame]]:
        """Fetch and parse tables from JSE website"""
        try:
            response = requests.get(self.url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.find_all('table')
            
            if len(tables) < 5:
                st.error("Could not find all required tables on the page")
                return None
            
            return {
                "Table 1": pd.read_html(str(tables[0]))[0],
                "Table 3": self._clean_table(pd.read_html(str(tables[2]))[0]),
                "Table 5": self._clean_table(pd.read_html(str(tables[4]))[0])
            }
            
        except Exception as e:
            st.error(f"An error occurred while fetching data: {str(e)}")
            return None

    @staticmethod
    def _clean_table(df: pd.DataFrame) -> pd.DataFrame:
        """Remove unnamed columns from DataFrame"""
        return df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]

class MarketAnalyzer:
    """Class to handle market data analysis"""
    
    @staticmethod
    def get_top_movers(df: pd.DataFrame, symbol_col: str, pct_change_col: str, n: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Calculate top gainers and decliners"""
        df_copy = df.copy()
        
        # Convert percentage change to numeric
        if df_copy[pct_change_col].dtype == object:
            df_copy[pct_change_col] = df_copy[pct_change_col].apply(
                lambda x: pd.to_numeric(str(x).replace('%', ''), errors='coerce')
            )
        else:
            df_copy[pct_change_col] = pd.to_numeric(df_copy[pct_change_col], errors='coerce')
        
        gainers = df_copy.nlargest(n, pct_change_col)[[symbol_col, pct_change_col]]
        decliners = df_copy.nsmallest(n, pct_change_col)[[symbol_col, pct_change_col]]
        
        return gainers, decliners

    @staticmethod
    def combine_tables(tables: Dict[str, pd.DataFrame], table_keys: List[str] = ["Table 3", "Table 5"]) -> pd.DataFrame:
        """Combine multiple tables into one DataFrame"""
        return pd.concat([tables[key] for key in table_keys], ignore_index=True)

class StreamlitUI:
    """Class to handle Streamlit UI components and layout"""
    
    def __init__(self):
        self.initialize_session_state()
        self.scraper = JSEScraper("https://www.jamstockex.com/trading/trade-quotes/weekly-quotes/")
        self.analyzer = MarketAnalyzer()
        # Set page config
        st.set_page_config(
            page_title="JSE Market Watch",
            page_icon="📈",
            layout="wide"
        )

    @staticmethod
    def initialize_session_state():
        """Initialize Streamlit session state variables"""
        if 'last_refresh' not in st.session_state:
            st.session_state['last_refresh'] = None
        if 'tables' not in st.session_state:
            st.session_state['tables'] = None
        if 'top_n' not in st.session_state:
            st.session_state['top_n'] = 5

    def display_header(self):
        """Display page header and controls"""
        # Title section with custom styling
        st.markdown("""
        <h1 style='text-align: center; color: #1E88E5; padding: 1rem;'>
            📊 JSE Market Watch
        </h1>
        """, unsafe_allow_html=True)
        
        # Control panel in a container
        with st.container():
            st.markdown("""
            <style>
            div[data-testid="stExpander"] div[role="button"] p {
                font-size: 1.1rem;
                font-weight: 600;
            }
            </style>
            """, unsafe_allow_html=True)
            
            with st.expander("📋 CONTROL PANEL", expanded=True):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    refresh_clicked = st.button(
                        "🔄 Refresh Data",
                        use_container_width=True,
                    )
                    if refresh_clicked:
                        st.session_state['last_refresh'] = datetime.now()
                with col2:
                    st.number_input(
                        "📊 Top Movers Count",
                        min_value=1,
                        max_value=20,
                        value=st.session_state['top_n'],
                        key='number_input_key',
                        on_change=self.on_top_n_change
                    )
                with col3:
                    if st.session_state['last_refresh']:
                        st.markdown(f"**Last Update:**  \n{st.session_state['last_refresh'].strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        st.markdown("**Last Update:**  \nNo data loaded")

        return refresh_clicked

    def display_movers(self, gainers: pd.DataFrame, decliners: pd.DataFrame, table_name: str):
        """Display top movers in a formatted layout"""
        st.markdown(f"#### {table_name}")
        
        col1, col2 = st.columns(2)
        with col1:
            self.display_movers_table(gainers, "Gainers", "↗️")
        with col2:
            self.display_movers_table(decliners, "Decliners", "↘️")

    def display_movers_table(self, df: pd.DataFrame, title: str, icon: str):
        """Display a formatted table of movers"""
        st.markdown(f"**{icon} Top {len(df)} {title}**")
        
        # Create a styled table
        table_data = []
        for _, row in df.iterrows():
            symbol, change = row.iloc[0], row.iloc[1]
            sign = '+' if title == "Gainers" else ''
            table_data.append([symbol, f"{sign}{change:.2f}%"])
        
        df_display = pd.DataFrame(table_data, columns=["Symbol", "Change"])
        st.dataframe(df_display, hide_index=True, use_container_width=True)

    def display_market_summary(self, tables: Dict[str, pd.DataFrame]):
        """Display market summary section"""
        with st.container():
            st.markdown("""
                <h3 style='color: #1E88E5; padding: 1rem 0;'>
                    📈 Market Summary
                </h3>
            """, unsafe_allow_html=True)
            
            try:
                # Overall market analysis
                combined_df = self.analyzer.combine_tables(tables)
                gainers_overall, decliners_overall = self.analyzer.get_top_movers(
                    combined_df, "Symbol", "Week Change (%)", st.session_state['top_n']
                )
                
                tabs = st.tabs(["Overall Market", "Ordinary Shares", "Preference Shares"])
                
                with tabs[0]:
                    self.display_movers(gainers_overall, decliners_overall, "Overall Market")
                
                with tabs[1]:
                    gainers3, decliners3 = self.analyzer.get_top_movers(
                        tables["Table 3"], "Symbol", "Week Change (%)", st.session_state['top_n']
                    )
                    self.display_movers(gainers3, decliners3, "ORDINARY SHARES")
                
                with tabs[2]:
                    gainers5, decliners5 = self.analyzer.get_top_movers(
                        tables["Table 5"], "Symbol", "Week Change (%)", st.session_state['top_n']
                    )
                    self.display_movers(gainers5, decliners5, "PREFERENCE SHARES")
                
            except Exception as e:
                st.error(f"Error in market summary: {str(e)}")

    def display_market_data(self, tables: Dict[str, pd.DataFrame]):
        """Display market data section"""
        st.markdown("""
            <h3 style='color: #1E88E5; padding: 1rem 0;'>
                📊 Market Data
            </h3>
        """, unsafe_allow_html=True)
        
        table_names = {
            "Table 1": "INDICES",
            "Table 3": "ORDINARY SHARES",
            "Table 5": "PREFERENCE SHARES"
        }
        
        tabs = st.tabs(list(table_names.values()))
        
        for (table_key, table_name), tab in zip(table_names.items(), tabs):
            with tab:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.dataframe(tables[table_key], use_container_width=True)
                with col2:
                    st.download_button(
                        label=f"📥 Download {table_name}",
                        data=tables[table_key].to_csv(index=False),
                        file_name=f"jse_{table_name.lower().replace(' ', '_')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

    @staticmethod
    def on_top_n_change():
        """Handle changes to the top movers count"""
        st.session_state['top_n'] = st.session_state.number_input_key

    def run(self):
        """Main application logic"""
        refresh_clicked = self.display_header()
        
        if refresh_clicked:
            with st.spinner("📊 Fetching latest market data..."):
                tables = self.scraper.fetch_tables()
                st.session_state['tables'] = tables
                
                if tables:
                    self.display_market_summary(tables)
                    self.display_market_data(tables)
                    
        elif st.session_state['tables'] is not None:
            self.display_market_summary(st.session_state['tables'])
            self.display_market_data(st.session_state['tables'])
        else:
            st.info("👆 Click 'Refresh Data' to load the latest market data")

def main():
    app = StreamlitUI()
    app.run()

if __name__ == "__main__":
    main()