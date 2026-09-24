"""
ClientTracker - In-House Fast Inference Engine
==============================================

Provides ultra-low-latency, zero-cost, privacy-first local inference for sales conversion 
and customer prioritization. Runs on-premise without dispatching any customer data externally.
"""

import os
import logging
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger("ClientTracker.ML")

DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "conversion_model.pkl")


class ConversionInferenceEngine:
    """
    In-memory inference engine for the local XGBoost RFM+ conversion model.
    Falls back gracefully to RFM-weighted heuristic scoring if artifact is not compiled yet.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.model = None
        self.expected_features = []
        self.is_loaded = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                import joblib
                data = joblib.load(self.model_path)
                if isinstance(data, dict) and "model" in data:
                    self.model = data["model"]
                    self.expected_features = data.get("features", [])
                else:
                    self.model = data
                self.is_loaded = True
                logger.info(f"Loaded local ML model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Could not load ML artifact from {self.model_path}: {e}. Operating in heuristic fallback.")
        else:
            logger.info(f"No local model found at {self.model_path}. Ready for heuristic inference or new model compilation.")

    def predict_propensity(
        self,
        recency_days: float,
        frequency_count: int,
        monetary_value: float,
        sales_velocity_days: float = 30.0,
        avg_products_per_order: float = 1.0,
        country: str = "Unknown"
    ) -> Dict[str, Any]:
        """
        Executes zero-latency local prediction.

        Returns:
            Dict containing:
              - conversion_probability (float 0.0 - 1.0)
              - propensity_tier ('High', 'Medium', 'Low')
              - churn_risk ('Low', 'Moderate', 'High')
              - inference_mode ('local_xgboost' | 'local_heuristic')
        """
        if self.is_loaded and self.model is not None:
            try:
                import pandas as pd
                # Build feature row matching model expectation
                row = {
                    "Recencia": [recency_days],
                    "Frequencia": [frequency_count],
                    "Valor": [monetary_value],
                    "Produtos_Compra": [avg_products_per_order],
                    "sales_velocity": [sales_velocity_days]
                }
                df_input = pd.DataFrame(row)

                # Align missing one-hot country columns
                for col in self.expected_features:
                    if col not in df_input.columns:
                        country_col = f"Country_{country}"
                        df_input[col] = 1 if col == country_col else 0

                # Select and order columns as expected
                if self.expected_features:
                    df_input = df_input.reindex(columns=self.expected_features, fill_value=0)

                proba = float(self.model.predict_proba(df_input)[0][1])
                mode = "local_xgboost"
            except Exception as ex:
                logger.error(f"Inference error with local model: {ex}. Falling back to heuristic.")
                proba = self._calculate_heuristic_probability(recency_days, frequency_count, monetary_value)
                mode = "local_heuristic"
        else:
            proba = self._calculate_heuristic_probability(recency_days, frequency_count, monetary_value)
            mode = "local_heuristic"

        # Tier assignment
        if proba >= 0.70:
            tier = "High"
            churn_risk = "Low"
        elif proba >= 0.40:
            tier = "Medium"
            churn_risk = "Moderate"
        else:
            tier = "Low"
            churn_risk = "High"

        return {
            "conversion_probability": round(proba, 4),
            "propensity_tier": tier,
            "churn_risk": churn_risk,
            "inference_mode": mode,
            "execution_target": "edge_local"
        }

    def _calculate_heuristic_probability(self, recency: float, freq: int, value: float) -> float:
        """Normalized heuristic fallback when model binary is not yet mounted."""
        r_score = max(0.0, 1.0 - (recency / 180.0))  # Decays over 6 months
        f_score = min(1.0, freq / 5.0)               # Caps at 5 orders
        v_score = min(1.0, value / 2000.0)           # Caps at normalized benchmark
        score = (r_score * 0.4) + (f_score * 0.35) + (v_score * 0.25)
        return min(max(score, 0.05), 0.98)


# Singleton instance for high-throughput reuse
inference_engine = ConversionInferenceEngine()
