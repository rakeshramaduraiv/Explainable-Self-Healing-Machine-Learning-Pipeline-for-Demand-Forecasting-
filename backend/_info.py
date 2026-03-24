import pandas as pd
df = pd.read_csv('retail_sales.csv')
print('Columns:', df.columns.tolist())
print('Rows:', len(df))
print('item_id unique:', df['item_id'].nunique())
print('item_id values:', sorted(df['item_id'].unique())[:10], '...')
print('store_id unique:', df['store_id'].nunique())
print('store_id values:', sorted(df['store_id'].unique())[:5])
print('Date range:', df['date'].min(), '->', df['date'].max())
