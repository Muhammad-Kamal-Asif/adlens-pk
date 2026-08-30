import pickle
import pandas as pd
from pathlib import Path
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder, MinMaxScaler

class AdFeatureBuilder:
    def __init__(self):
        # 1. TF-IDF vectorizer (max_features=500, ngram_range=(1,2))
        self.tfidf = TfidfVectorizer(max_features=500, ngram_range=(1, 2), stop_words='english')
        self.industry_le = LabelEncoder()
        self.cta_le = LabelEncoder()
        self.len_scaler = MinMaxScaler()
        
    def fit(self, df: pd.DataFrame):
        df = df.copy()
        
        # Fit tfidf on ad_copy
        df['ad_copy'] = df['ad_copy'].fillna("").astype(str)
        self.tfidf.fit(df['ad_copy'])
        
        # Fit label encoders (add 'unknown' to handle unseen data during transform safely)
        df['industry'] = df['industry'].fillna("unknown").astype(str)
        self.industry_le.fit(df['industry'].tolist() + ["unknown"])
        
        df['cta_type'] = df['cta_type'].fillna("unknown").astype(str)
        self.cta_le.fit(df['cta_type'].tolist() + ["unknown"])
        
        # Fit length scaler
        char_lens = df['ad_copy'].apply(len).values.reshape(-1, 1)
        self.len_scaler.fit(char_lens)
        
        return self
        
    def _safe_transform_le(self, le, series):
        classes = set(le.classes_)
        safe_series = series.apply(lambda x: x if x in classes else "unknown")
        return le.transform(safe_series)
        
    def transform(self, df: pd.DataFrame):
        df = df.copy()
        
        # 2. Extract TF-IDF features
        df['ad_copy'] = df['ad_copy'].fillna("").astype(str)
        tfidf_features = self.tfidf.transform(df['ad_copy'])
        
        # industry label encoded
        df['industry'] = df['industry'].fillna("unknown").astype(str)
        ind_features = self._safe_transform_le(self.industry_le, df['industry']).reshape(-1, 1)
        
        # cta_type label encoded
        df['cta_type'] = df['cta_type'].fillna("unknown").astype(str)
        cta_features = self._safe_transform_le(self.cta_le, df['cta_type']).reshape(-1, 1)
        
        # has_cod as 0/1, has_price as 0/1
        has_cod = df['has_cod'].fillna(False).astype(int).values.reshape(-1, 1)
        has_price = df['has_price'].fillna(False).astype(int).values.reshape(-1, 1)
        
        # ad_copy character length normalized 0-1
        char_lens = df['ad_copy'].apply(len).values.reshape(-1, 1)
        len_features = self.len_scaler.transform(char_lens)
        
        # Combine all horizontally into a scipy sparse matrix
        features = hstack([
            tfidf_features,
            csr_matrix(ind_features),
            csr_matrix(cta_features),
            csr_matrix(has_cod),
            csr_matrix(has_price),
            csr_matrix(len_features)
        ])
        
        return features
        
    def fit_transform(self, df: pd.DataFrame):
        # 3. combines both
        self.fit(df)
        return self.transform(df)
        
    def save(self, path: str):
        # 4. pickle serialization
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'wb') as f:
            pickle.dump(self, f)
            
    @classmethod
    def load(cls, path: str):
        with open(path, 'rb') as f:
            return pickle.load(f)
