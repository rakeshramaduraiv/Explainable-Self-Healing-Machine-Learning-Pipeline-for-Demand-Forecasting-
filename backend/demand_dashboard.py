import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from demand_analyzer import DemandAnalyzer
import os

def format_number(num):
    """Format large numbers with K/M suffixes"""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    return f"{num:.0f}"

def create_demand_insights():
    """Create the demand insights section for the dashboard"""
    
    st.header("📊 Demand Insights")
    
    # Check if data exists
    if not os.path.exists("data/uploaded_data.csv"):
        st.warning("⚠️ No data uploaded yet. Please upload a dataset first.")
        return
    
    try:
        # Initialize analyzer and load data
        analyzer = DemandAnalyzer()
        analyzer.load_data()
        metrics = analyzer.calculate_demand_metrics()
        
        # Display metrics cards
        st.subheader("📈 Key Demand Metrics")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                label="Average Weekly Demand",
                value=format_number(metrics["avg_weekly_demand"])
            )
        
        with col2:
            growth = metrics["demand_growth_rate"]
            st.metric(
                label="Growth Rate (MoM)",
                value=f"{growth:+.1f}%",
                delta=f"{growth:.1f}%"
            )
        
        with col3:
            st.metric(
                label="Peak Demand Month",
                value=metrics["peak_demand_month"]
            )
        
        with col4:
            st.metric(
                label="Lowest Demand Month", 
                value=metrics["lowest_demand_month"]
            )
        
        with col5:
            st.metric(
                label="Total Demand",
                value=format_number(metrics["total_demand"])
            )
        
        st.divider()
        
        # Visualizations
        st.subheader("📊 Demand Visualizations")
        
        # Row 1: Demand Trend and Monthly Demand
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Demand Trend Over Time**")
            trend_data = analyzer.get_demand_trend_data()
            
            fig_trend = px.line(
                trend_data, 
                x="Date", 
                y="Weekly_Sales",
                title="Weekly Sales Demand Trend"
            )
            fig_trend.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                xaxis=dict(gridcolor="#444"),
                yaxis=dict(gridcolor="#444")
            )
            fig_trend.update_traces(line_color="#1f77b4")
            st.plotly_chart(fig_trend, use_container_width=True)
        
        with col2:
            st.write("**Monthly Demand Aggregation**")
            monthly_data = analyzer.get_monthly_demand_data()
            
            fig_monthly = px.bar(
                monthly_data,
                x="Date",
                y="Weekly_Sales", 
                title="Total Monthly Demand"
            )
            fig_monthly.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                xaxis=dict(gridcolor="#444"),
                yaxis=dict(gridcolor="#444")
            )
            fig_monthly.update_traces(marker_color="#ff7f0e")
            st.plotly_chart(fig_monthly, use_container_width=True)
        
        # Row 2: Store-Level Analysis (if applicable)
        store_data = analyzer.get_store_demand_data()
        if not store_data.empty:
            st.write("**Store-Level Demand Analysis**")
            
            fig_store = px.bar(
                store_data,
                x="Store",
                y="Weekly_Sales",
                title="Total Demand by Store"
            )
            fig_store.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                xaxis=dict(gridcolor="#444"),
                yaxis=dict(gridcolor="#444")
            )
            fig_store.update_traces(marker_color="#2ca02c")
            st.plotly_chart(fig_store, use_container_width=True)
        
        # Summary insights
        st.subheader("🔍 Key Insights")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if metrics["demand_growth_rate"] > 5:
                st.success("📈 Strong positive demand growth detected")
            elif metrics["demand_growth_rate"] < -5:
                st.error("📉 Significant demand decline detected")
            else:
                st.info("📊 Stable demand pattern observed")
        
        with col2:
            total_weeks = len(analyzer.df)
            avg_weekly = metrics["avg_weekly_demand"]
            st.info(f"📅 Dataset spans {total_weeks} weeks with average weekly sales of {format_number(avg_weekly)}")
            
    except Exception as e:
        st.error(f"❌ Error analyzing demand data: {str(e)}")
        st.info("Please ensure your dataset contains the required columns: Date, Weekly_Sales")

if __name__ == "__main__":
    st.set_page_config(
        page_title="Demand Insights Dashboard",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    create_demand_insights()