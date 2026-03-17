"""
Amazon Products Dataset → Product Demand Forecasting Data Generator
--------------------------------------------------------------------
Converts Kaggle Amazon Products dataset into time-series demand data.

Dataset: https://www.kaggle.com/datasets/lokeshparab/amazon-products-dataset

Flow:
  1. Load Amazon products CSV
  2. Select top N products (by ratings/popularity)
  3. Create synthetic stores
  4. Generate 24 months of weekly demand per Store+Product
  5. Output: Ready for ML pipeline

Usage:
  python amazon_data_generator.py [path_to_amazon_csv] [num_products] [num_stores]
  python amazon_data_generator.py amazon.csv 20 5
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import re

def clean_price(price_str):
    """Convert price string like '₹1,299' to float."""
    if pd.isna(price_str):
        return None
    price_str = str(price_str)
    cleaned = re.sub(r'[^\d.]', '', price_str)
    try:
        return float(cleaned) if cleaned else None
    except:
        return None

def clean_ratings(rating_str):
    """Convert rating string to float."""
    if pd.isna(rating_str):
        return 3.0
    try:
        return float(str(rating_str).split()[0])
    except:
        return 3.0

def clean_num_ratings(num_str):
    """Convert '1,234' to int."""
    if pd.isna(num_str):
        return 0
    cleaned = re.sub(r'[^\d]', '', str(num_str))
    try:
        return int(cleaned) if cleaned else 0
    except:
        return 0

def load_amazon_products(csv_path, num_products=20):
    """Load and clean Amazon products dataset."""
    print(f"Loading Amazon products from: {csv_path}")
    
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            break
        except:
            continue
    
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    col_map = {
        'product_name': 'name',
        'product_id': 'product_id',
        'category': 'main_category',
        'rating': 'ratings',
        'rating_count': 'no_of_ratings',
        'discounted_price': 'discount_price',
        'price': 'actual_price',
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    
    if 'actual_price' in df.columns:
        df['price'] = df['actual_price'].apply(clean_price)
    elif 'discount_price' in df.columns:
        df['price'] = df['discount_price'].apply(clean_price)
    else:
        df['price'] = 500
    
    if 'ratings' in df.columns:
        df['rating'] = df['ratings'].apply(clean_ratings)
    else:
        df['rating'] = 3.5
    
    if 'no_of_ratings' in df.columns:
        df['num_ratings'] = df['no_of_ratings'].apply(clean_num_ratings)
    else:
        df['num_ratings'] = 100
    
    df['price'] = df['price'].fillna(df['price'].median() if df['price'].notna().any() else 500)
    df['rating'] = df['rating'].fillna(3.5)
    df['num_ratings'] = df['num_ratings'].fillna(100)
    
    if 'main_category' in df.columns:
        df['category'] = df['main_category'].fillna('General')
    elif 'sub_category' in df.columns:
        df['category'] = df['sub_category'].fillna('General')
    else:
        df['category'] = 'General'
    
    df['popularity'] = df['num_ratings'] * df['rating']
    df = df.nlargest(num_products, 'popularity')
    df = df.reset_index(drop=True)
    df['Product'] = df.index + 1
    
    print(f"Selected {len(df)} products")
    print(f"Categories: {df['category'].nunique()}")
    print(f"Price range: {df['price'].min():.0f} - {df['price'].max():.0f}")
    
    return df[['Product', 'price', 'rating', 'num_ratings', 'category']]


def generate_demand_data(
    products_df,
    num_stores=5,
    start_year=2024,
    num_years=2,
    output_path="data/uploaded_data.csv"
):
    """
    Generate 24 months of weekly DEMAND data for Store+Product combinations.
    
    Demand (units) is influenced by:
    - Product popularity (rating * num_ratings)
    - Product price (inverse relationship - cheaper = more demand)
    - Seasonality (monthly patterns)
    - Store size (random multiplier)
    - Holiday effects
    - Random noise
    """
    np.random.seed(42)
    
    store_sizes = {i: 0.7 + np.random.random() * 0.6 for i in range(1, num_stores + 1)}
    
    seasonal = {
        1: 0.80, 2: 0.85, 3: 0.90, 4: 0.95, 5: 1.00, 6: 1.05,
        7: 1.10, 8: 1.05, 9: 0.95, 10: 1.10, 11: 1.30, 12: 1.50,
    }
    
    holiday_weeks = {
        6: 1.1, 21: 1.15, 27: 1.25, 35: 1.1, 47: 1.4, 48: 1.3, 51: 1.5, 52: 1.2,
    }
    
    rows = []
    
    for year in range(start_year, start_year + num_years):
        start_date = datetime(year, 1, 1)
        days_until_friday = (4 - start_date.weekday()) % 7
        current_date = start_date + timedelta(days=days_until_friday)
        
        week_num = 0
        while current_date.year == year:
            week_num += 1
            month = current_date.month
            
            is_holiday = 1 if week_num in holiday_weeks else 0
            holiday_mult = holiday_weeks.get(week_num, 1.0)
            
            year_offset = year - start_year
            month_offset = (month - 1) / 12
            
            temperature = {1: 35, 2: 38, 3: 50, 4: 60, 5: 70, 6: 80,
                          7: 85, 8: 83, 9: 75, 10: 60, 11: 45, 12: 35}[month]
            temperature += np.random.uniform(-8, 8)
            
            fuel_price = 3.20 + year_offset * 0.10 + month_offset * 0.05 + np.random.uniform(-0.15, 0.15)
            cpi = 230 + year_offset * 4 + month_offset * 0.5 + np.random.uniform(-1.5, 1.5)
            unemployment = 5.0 + np.random.uniform(-1.0, 1.0)
            
            for store in range(1, num_stores + 1):
                store_mult = store_sizes[store]
                
                for _, product in products_df.iterrows():
                    product_id = product['Product']
                    price = product['price']
                    rating = product['rating']
                    num_ratings = product['num_ratings']
                    
                    # Base demand from popularity (units, not dollars)
                    popularity_score = (rating / 5.0) * np.log1p(num_ratings)
                    
                    # Price effect (cheaper = more demand)
                    price_effect = 1.0 / (1.0 + price / 500)
                    
                    # Base weekly demand in UNITS
                    base_demand = 50 * popularity_score * price_effect
                    
                    # Apply multipliers
                    demand = base_demand * store_mult * seasonal[month] * holiday_mult
                    
                    # Add noise (+/- 20%)
                    demand *= np.random.uniform(0.80, 1.20)
                    
                    # Ensure positive integer-like demand
                    demand = max(1, round(demand))
                    
                    rows.append({
                        "Store": store,
                        "Product": product_id,
                        "Date": current_date.strftime("%d-%m-%Y"),
                        "Demand": demand,
                        "Holiday_Flag": is_holiday,
                        "Temperature": round(temperature, 1),
                        "Fuel_Price": round(fuel_price, 2),
                        "CPI": round(cpi, 1),
                        "Unemployment": round(unemployment, 1),
                    })
            
            current_date += timedelta(days=7)
    
    df = pd.DataFrame(rows)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
    print("\n" + "=" * 60)
    print("PRODUCT DEMAND DATA GENERATED FROM AMAZON PRODUCTS")
    print("=" * 60)
    print(f"Output: {output_path}")
    print(f"Total rows: {len(df):,}")
    print(f"Stores: {df['Store'].nunique()}")
    print(f"Products: {df['Product'].nunique()}")
    print(f"Date range: {df['Date'].min().date()} to {df['Date'].max().date()}")
    print(f"\nYear breakdown:")
    for year in sorted(df["Date"].dt.year.unique()):
        year_df = df[df["Date"].dt.year == year]
        print(f"  {year}: {len(year_df):,} rows")
    print(f"\nDemand range: {df['Demand'].min():,} - {df['Demand'].max():,} units")
    print(f"Mean weekly demand: {df['Demand'].mean():,.0f} units")
    print("=" * 60)
    
    return df


def save_product_mapping(products_df, output_path="data/product_mapping.csv"):
    """Save product ID to details mapping for reference."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    products_df.to_csv(output_path, index=False)
    print(f"Product mapping saved: {output_path}")


def generate_from_amazon(
    amazon_csv_path,
    num_products=20,
    num_stores=5,
    output_path="data/uploaded_data.csv"
):
    """Main function: Load Amazon data and generate demand dataset."""
    products = load_amazon_products(amazon_csv_path, num_products)
    save_product_mapping(products)
    return generate_demand_data(products, num_stores, output_path=output_path)


def generate_sample_without_amazon(
    num_products=20,
    num_stores=5,
    output_path="data/uploaded_data.csv"
):
    """Generate sample data without Amazon CSV (synthetic products)."""
    print("Generating synthetic product catalog...")
    
    np.random.seed(42)
    
    categories = ['Electronics', 'Home', 'Fashion', 'Books', 'Sports']
    
    products = []
    for i in range(1, num_products + 1):
        products.append({
            'Product': i,
            'price': np.random.uniform(100, 5000),
            'rating': np.random.uniform(3.0, 5.0),
            'num_ratings': int(np.random.uniform(50, 10000)),
            'category': np.random.choice(categories),
        })
    
    products_df = pd.DataFrame(products)
    save_product_mapping(products_df)
    return generate_demand_data(products_df, num_stores, output_path=output_path)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        amazon_csv = sys.argv[1]
        num_products = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        num_stores = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        
        if os.path.exists(amazon_csv):
            generate_from_amazon(amazon_csv, num_products, num_stores)
        else:
            print(f"File not found: {amazon_csv}")
            print("Generating synthetic data instead...")
            generate_sample_without_amazon(num_products, num_stores)
    else:
        print("Usage: python amazon_data_generator.py <amazon.csv> [num_products] [num_stores]")
        print("\nNo Amazon CSV provided. Generating synthetic data...")
        generate_sample_without_amazon(20, 5)
