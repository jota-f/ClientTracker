"""
ClientTracker - In-House Sales Conversion & Predictive Propensity Model Training Pipeline
========================================================================================

Dataset Benchmark: Online Retail II (UCI Machine Learning Repository)
Objective: Train a high-throughput, low-latency XGBoost classifier to predict customer 
           conversion probability, sales retention, and churn propensity based on 
           extended RFM+ features and sales velocity.

Architecture:
  - Feature Engineering: RFM+ (Recency, Frequency, Monetary Value, Products per Order, 
                         Sales Velocity, Geographic Distribution).
  - Target: Binary Conversion (Repeat purchases / multi-invoice lifetime conversion).
  - Algorithm: Extreme Gradient Boosting (XGBClassifier) with Logistic Objective.
  - Serialization: Joblib artifact for sub-millisecond local inference.
"""

import os
import argparse
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb
import joblib

DATASET_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/00502/online_retail_II.xlsx"
MODEL_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_OUTPUT_FILE = os.path.join(MODEL_OUTPUT_DIR, "conversion_model.pkl")


def load_and_preprocess_data(dataset_path: str = None) -> pd.DataFrame:
    """
    Downloads or reads the UCI Online Retail II dataset, cleans invalid transactions,
    and formats Customer IDs consistently.
    """
    source = dataset_path if dataset_path else DATASET_URL
    print(f"[*] Loading raw dataset from: {source}...")
    
    if source.endswith(".xlsx"):
        raw_df = pd.read_excel(source, sheet_name=['Year 2009-2010', 'Year 2010-2011'])
        df = pd.concat([raw_df['Year 2009-2010'], raw_df['Year 2010-2011']], ignore_index=True)
    else:
        df = pd.read_csv(source)

    print(f"[*] Raw records loaded: {len(df):,}")

    # Data Hygiene: Positive quantity and price only
    df = df[(df['Quantity'] > 0) & (df['Price'] > 0)].copy()
    df.dropna(subset=['Customer ID'], inplace=True)

    # Consistent Customer ID as normalized string
    df['Customer ID'] = (
        df['Customer ID']
        .astype(str)
        .str.split('.', n=1).str[0]
        .str.strip()
    )

    return df


def engineer_rfm_plus_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs extended RFM+ features including:
      - Recency (days since latest transaction)
      - Frequency (distinct invoice count)
      - Monetary Value (total revenue generated)
      - Products per Purchase (average units per basket)
      - Sales Velocity (days span divided by frequency)
      - Geographic One-Hot Encoding
      - Target Variable: Multiple-purchase conversion (1 if unique invoices > 1 else 0)
    """
    print("[*] Running RFM+ feature engineering pipeline...")
    now = datetime.now()

    # Define binary conversion target
    df['conversao'] = (
        df.groupby('Customer ID')['Invoice']
        .transform(lambda x: 1 if x.nunique() > 1 else 0)
    )

    # Calculate baseline RFM
    rfm = df.groupby('Customer ID').agg({
        'InvoiceDate': lambda x: (now - x.max()).days,
        'Invoice': 'nunique',
        'Price': lambda x: (x * df.loc[x.index, 'Quantity']).sum()
    }).reset_index()

    rfm.columns = ['Customer ID', 'Recencia', 'Frequencia', 'Valor']

    # Products per purchase
    produtos_por_compra = df.groupby(['Customer ID', 'Invoice'])['Quantity'].sum().reset_index()
    avg_products = produtos_por_compra.groupby('Customer ID')['Quantity'].mean().reset_index()
    avg_products.columns = ['Customer ID', 'Produtos_Compra']
    rfm = rfm.merge(avg_products, on='Customer ID', how='left')

    # Sales velocity (days between first and last purchase / frequency)
    tempo_compra = df.groupby('Customer ID')['InvoiceDate'].agg(['min', 'max'])
    tempo_compra['sales_velocity'] = (
        (tempo_compra['max'] - tempo_compra['min']).dt.days
        / rfm.set_index('Customer ID')['Frequencia'].replace(0, 1)
    ).values
    rfm['sales_velocity'] = tempo_compra['sales_velocity'].values

    # Geographic encoding (Country)
    df['Country'] = df['Country'].fillna('Unknown')
    pais = (
        df[['Customer ID', 'Country']]
        .drop_duplicates('Customer ID')
        .pipe(lambda d: pd.get_dummies(d, columns=['Country'], prefix="Country"))
    )

    # Final merged dataset
    final_df = (
        rfm.merge(pais, on='Customer ID', how='left')
        .merge(
            df[['Customer ID', 'conversao']].drop_duplicates(),
            on='Customer ID',
            how='inner'
        )
        .dropna(subset=['Recencia', 'Frequencia', 'Valor'])
    )

    print(f"[+] Processed {len(final_df):,} unique client profiles.")
    print(f"[+] Base conversion rate: {final_df['conversao'].mean():.2%}")
    return final_df


def train_and_export_model(df: pd.DataFrame, output_path: str = MODEL_OUTPUT_FILE):
    """
    Trains the XGBoost classifier, evaluates performance (AUC & Classification Report),
    and serializes the production artifact with metadata.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    X = df.drop(['Customer ID', 'conversao'], axis=1)
    y = df['conversao']

    feature_names = list(X.columns)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("[*] Training XGBoost Classifier...")
    model = xgb.XGBClassifier(
        objective='binary:logistic',
        eval_metric='auc',
        max_depth=5,
        learning_rate=0.1,
        n_estimators=150,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )

    model.fit(X_train, y_train)

    # Evaluation
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)
    auc = roc_auc_score(y_test, y_pred_proba)

    print("\n" + "=" * 50)
    print("MODEL EVALUATION BENCHMARK")
    print("=" * 50)
    print(f"ROC-AUC Score: {auc:.4f}\n")
    print(classification_report(y_test, y_pred))
    print("=" * 50)

    # Save artifact with feature registry
    payload = {
        "model": model,
        "features": feature_names,
        "metrics": {"auc": auc},
        "trained_at": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

    joblib.dump(payload, output_path)
    print(f"\n[+] Production model successfully serialized to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ClientTracker Sales Conversion Model")
    parser.add_argument("--data", type=str, default=None, help="Local path to dataset file (optional)")
    parser.add_argument("--output", type=str, default=MODEL_OUTPUT_FILE, help="Output path for .pkl artifact")
    args = parser.parse_args()

    processed_data = load_and_preprocess_data(args.data)
    feature_df = engineer_rfm_plus_features(processed_data)
    train_and_export_model(feature_df, args.output)
