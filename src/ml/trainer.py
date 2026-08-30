import time
import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score

from src.ml.data_loader import load_training_data
from src.ml.feature_builder import AdFeatureBuilder

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class AdSurvivalTrainer:
    def __init__(self):
        self.df = None
        self.target = None
        self.model = None
        self.feature_builder = None
        self.accuracy = 0.0
        self.f1_score = 0.0
        self.model_path = ""
        
    def load_and_prepare(self):
        logger.info("Loading training data via data_loader...")
        self.df = load_training_data()
        
        db_mask = self.df['source'] == 'database'
        db_count = db_mask.sum()
        
        logger.info(f"Found {db_count} DB records and {(~db_mask).sum()} Kaggle records")
        
        if db_count < 30:
            logger.warning(f"Only {db_count} DB records found. Using heuristic labeling for training signal.")
            
            def heuristic_label(row):
                ad_copy = str(row.get('ad_copy', '')).lower()
                has_cod = any(kw in ad_copy for kw in ['cash on delivery', 'cod', 'cashondelivery', 'payment on delivery'])
                has_price = bool(row.get('has_price', False)) or any(kw in ad_copy for kw in ['rs', 'rs.', 'pkr', 'price', '₨'])
                has_whatsapp = any(kw in ad_copy for kw in ['whatsapp', 'wa.me', 'whats app', '03', '+92'])
                return 1 if (has_cod or has_price or has_whatsapp) else 0
            
            self.target = self.df.apply(heuristic_label, axis=1)
        else:
            logger.info(f"Using {db_count} DB records with real days_active labels")
            self.target = (self.df['days_active'] >= 30).astype(int)
            self.target[~db_mask] = 0
        
        self.target.name = 'target'
        
        balance = self.target.value_counts().to_dict()
        logger.info(f"Class balance: {balance}")
        logger.info(f"Total records for training: {len(self.df)}")
        
    def train(self):
        db_mask = self.df['source'] == 'database'
        db_count = db_mask.sum()

        logger.info("Fitting feature builder on full corpus (DB + Kaggle) for vocabulary enrichment...")
        self.feature_builder = AdFeatureBuilder()
        self.feature_builder.fit(self.df)

        if db_count >= 30:
            logger.info(f"Training classifier on {db_count} DB records only (real labels).")
            db_df = self.df[db_mask]
            X = self.feature_builder.transform(db_df)
            y = self.target[db_mask].values
        else:
            logger.info(f"Training classifier on all {len(self.df)} rows (heuristic labels).")
            X = self.feature_builder.transform(self.df)
            y = self.target.values

        logger.info("Configuring GradientBoostingClassifier...")
        self.model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.1,
            random_state=42
        )

        if len(y) < 10:
            logger.warning(f"Only {len(y)} training samples. Skipping CV, fitting directly.")
            self.model.fit(X, y)
            self.accuracy = 0.0
            self.f1_score = 0.0
        elif len(np.unique(y)) < 2:
            logger.warning("Only 1 class in training data. Skipping CV.")
            self.model.fit(X, y)
            self.accuracy = 0.0
            self.f1_score = 0.0
        else:
            n_splits = min(5, min(np.bincount(y)))
            if n_splits < 2:
                n_splits = 2
            cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

            logger.info(f"Evaluating Accuracy & F1 Score ({n_splits}-fold CV)...")
            acc_scores = cross_val_score(self.model, X, y, cv=cv, scoring='accuracy', n_jobs=-1)
            self.accuracy = float(acc_scores.mean())

            f1_scores = cross_val_score(self.model, X, y, cv=cv, scoring='f1', n_jobs=-1)
            self.f1_score = float(f1_scores.mean())

            logger.info(f"CV Accuracy: {self.accuracy:.4f}")
            logger.info(f"CV F1 Score: {self.f1_score:.4f}")

            logger.info("Training final model on full dataset...")
            self.model.fit(X, y)
        
    def save_model(self):
        logger.info("Saving models...")
        models_dir = Path("src/ml/models")
        models_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = models_dir / f"gbc_model_{timestamp}.pkl"
        fb_path = models_dir / f"feature_builder_{timestamp}.pkl"
        
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
            
        self.feature_builder.save(str(fb_path))
        
        status_path = models_dir / "status.json"
        status = {}
        if status_path.exists():
            with open(status_path, 'r') as f:
                try:
                    status = json.load(f)
                except Exception:
                    pass
                    
        status.update({
            "records_used": len(self.df),
            "accuracy": self.accuracy,
            "f1_score": self.f1_score,
            "last_trained": datetime.now().isoformat(),
            "latest_model_path": str(model_path),
            "latest_fb_path": str(fb_path)
        })
        
        with open(status_path, 'w') as f:
            json.dump(status, f, indent=4)
            
        self.model_path = str(model_path)
        logger.info(f"Saved to {model_path}")
        
    def run(self):
        start_time = time.time()
        try:
            self.load_and_prepare()
            self.train()
            self.save_model()
            duration = time.time() - start_time
            return {
                "success": True,
                "accuracy": self.accuracy,
                "records_used": len(self.df),
                "model_path": self.model_path,
                "duration_seconds": duration
            }
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - start_time
            }

if __name__ == "__main__":
    trainer = AdSurvivalTrainer()
    result = trainer.run()
    print("Training Complete:")
    print(json.dumps(result, indent=2))
