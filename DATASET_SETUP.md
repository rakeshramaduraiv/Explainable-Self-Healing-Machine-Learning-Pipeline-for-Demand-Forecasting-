# Dataset Setup

Due to GitHub file size limits, the retail_sales.csv file (186MB) is not included in this repository.

## To run the system:

1. **Download the retail sales dataset** from Kaggle or your data source
2. **Place it as `backend/retail_sales.csv`**
3. **Run the pipeline:**
   ```bash
   cd backend
   python main.py
   ```

## Alternative: Use your own dataset

The system accepts any CSV with these columns:
- `Date` (DD-MM-YYYY format)
- `Product` (product identifier)  
- `Demand` (target variable - units demanded)
- Optional: `Store`, `Price`, `Promo`, etc.

## System Features

✅ **Full Dataset Training** - Uses ALL data without sampling  
✅ **Self-Healing** - Automatic drift detection and model fine-tuning  
✅ **70+ Engineered Features** - Dynamic feature generation  
✅ **Real-time Dashboard** - React frontend with live monitoring  
✅ **Production Ready** - FastAPI backend with comprehensive logging  

The system processes 652K+ rows with 50 stores × 50 products across 5 years of data.