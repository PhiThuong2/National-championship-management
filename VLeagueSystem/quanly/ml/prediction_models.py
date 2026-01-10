"""
ML Prediction Models for V-League Match Result Prediction
Implements Poisson Regression and Random Forest models
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import  PoissonRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os
from django.conf import settings
from scipy.stats import poisson

from quanly.ml.feature_engineering import build_match_features, build_training_dataset


class PoissonRegressionPredictor:
    """
    Sử dụng Poisson Regression để dự đoán số bàn thắng của mỗi đội
    Phù hợp cho dự đoán tỷ số chính xác
    """
    
    def __init__(self):
        self.home_model = None  # Model dự đoán bàn thắng đội nhà
        self.away_model = None  # Model dự đoán bàn thắng đội khách
        self.feature_columns = []
        self.is_trained = False
        
    def _get_feature_columns(self, df):
        """Lấy danh sách feature columns (loại bỏ labels)"""
        exclude_cols = ['home_score', 'away_score', 'result']
        return [col for col in df.columns if col not in exclude_cols]
    
    def train(self, training_data, test_size=0.2, random_state=42):
        """
Training the Poisson Regression model
        
        Args:
            training_data: pandas DataFrame from build_training_dataset()
            test_size: Tỷ lệ test set
            random_state: Random seed
        
        Returns:
            dict: Training metrics
        """
        if len(training_data) < 10:
            raise ValueError("Không đủ dữ liệu để training! Cần ít nhất 10 trận.")
        
        self.feature_columns = self._get_feature_columns(training_data)
        X = training_data[self.feature_columns]
        y_home = training_data['home_score']
        y_away = training_data['away_score']
        
        # Split data
        X_train, X_test, y_home_train, y_home_test, y_away_train, y_away_test = train_test_split(
            X, y_home, y_away, test_size=test_size, random_state=random_state
        )
        
        # Train Poisson models directly
        self.home_model = PoissonRegressor(max_iter=1000, alpha=0.1)
        self.home_model.fit(X_train, y_home_train)
        
        self.away_model = PoissonRegressor(max_iter=1000, alpha=0.1)
        self.away_model.fit(X_train, y_away_train)
        
        # Evaluate
        home_pred = self.home_model.predict(X_test)
        away_pred = self.away_model.predict(X_test)
        
        # Calculate accuracy (rounded predictions)
        home_accuracy = accuracy_score(y_home_test, np.round(home_pred))
        away_accuracy = accuracy_score(y_away_test, np.round(away_pred))
        
        self.is_trained = True
        
        return {
            'home_accuracy': home_accuracy,
            'away_accuracy': away_accuracy,
            'overall_accuracy': (home_accuracy + away_accuracy) / 2,
            'training_samples': len(X_train),
            'test_samples': len(X_test)
        }
    
    def predict_score(self, home_team, away_team, match_date, season):
        """
        Dự đoán tỷ số cho một trận đấu
        
        Returns:
            dict: {
                'home_score': int,
                'away_score': int,
                'home_lambda': float (expected goals),
                'away_lambda': float
            }
        """
        if not self.is_trained:
            raise ValueError("Model chưa được training!")
        
        features = build_match_features(home_team, away_team, match_date, season)
        features_df = pd.DataFrame([features])
        
        # Đảm bảo có đủ columns
        for col in self.feature_columns:
            if col not in features_df.columns:
                features_df[col] = 0
        
        features_df = features_df[self.feature_columns]
        
        # Predict expected goals (lambda)
        home_lambda = self.home_model.predict(features_df)[0]
        away_lambda = self.away_model.predict(features_df)[0]
        
        # Round to get predicted score
        home_score = int(round(home_lambda))
        away_score = int(round(away_lambda))
        
        return {
            'home_score': home_score,
            'away_score': away_score,
            'home_lambda': float(home_lambda),
            'away_lambda': float(away_lambda)
        }
    
    def calculate_probabilities(self, home_lambda, away_lambda, max_goals=6):
        """
        Tính xác suất các kết quả dựa trên Poisson distribution
        
        Returns:
            dict: {'win': float, 'draw': float, 'loss': float}
        """
        prob_win = 0.0
        prob_draw = 0.0
        prob_loss = 0.0
        
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                prob = poisson.pmf(home_goals, home_lambda) * poisson.pmf(away_goals, away_lambda)
                
                if home_goals > away_goals:
                    prob_win += prob
                elif home_goals == away_goals:
                    prob_draw += prob
                else:
                    prob_loss += prob
        
        # Normalize to ensure sum = 1
        total = prob_win + prob_draw + prob_loss
        if total > 0:
            prob_win /= total
            prob_draw /= total
            prob_loss /= total
        
        return {
            'win': prob_win,
            'draw': prob_draw,
            'loss': prob_loss
        }
    
    def save_model(self, filepath=None):
        """Lưu model vào file"""
        if not self.is_trained:
            raise ValueError("Model chưa được training!")
        
        if filepath is None:
            model_dir = os.path.join(settings.MEDIA_ROOT, 'ml_models')
            os.makedirs(model_dir, exist_ok=True)
            filepath = os.path.join(model_dir, 'poisson_predictor.pkl')
        
        model_data = {
            'home_model': self.home_model,
            'away_model': self.away_model,
            'feature_columns': self. feature_columns,
            'is_trained': self.is_trained
        }
        
        joblib.dump(model_data, filepath)
        return filepath
    
    def load_model(self, filepath=None):
        """Load model từ file"""
        if filepath is None:
            filepath = os.path.join(settings.MEDIA_ROOT, 'ml_models', 'poisson_predictor.pkl')
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        model_data = joblib.load(filepath)
        self.home_model = model_data['home_model']
        self.away_model = model_data['away_model']
        self.feature_columns = model_data['feature_columns']
        self.is_trained = model_data['is_trained']


class RandomForestResultPredictor:
    """
    Sử dụng Random Forest để dự đoán kết quả (Thắng/Hòa/Thua)
    Trả về xác suất cho mỗi outcome
    """
    
    def __init__(self, n_estimators=100):
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=10,
            random_state=42,
            class_weight='balanced'  # Handle imbalanced data
        )
        self.feature_columns = []
        self.is_trained = False
    
    def _get_feature_columns(self, df):
        """Lấy danh sách feature columns"""
        exclude_cols = ['home_score', 'away_score', 'result']
        return [col for col in df.columns if col not in exclude_cols]
    
    def train(self, training_data, test_size=0.2, random_state=42):
        """
        Train Random Forest classifier
        
        Returns:
            dict: Training metrics including accuracy and classification report
        """
        if len(training_data) < 10:
            raise ValueError("Không đủ dữ liệu để training!")
        
        self.feature_columns = self._get_feature_columns(training_data)
        X = training_data[self.feature_columns]
        y = training_data['result']  # 1=Win, 0=Draw, -1=Loss
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )
        
        # Train
        self.model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        # Get classification report
        report = classification_report(
            y_test, y_pred,
            labels=[1, 0, -1],
            target_names=['Home Win', 'Draw', 'Away Win'],
            output_dict=True
        )
        
        self.is_trained = True
        
        return {
            'accuracy': accuracy,
            'classification_report': report,
            'feature_importance': dict(zip(self.feature_columns, self.model.feature_importances_)),
            'training_samples': len(X_train),
            'test_samples': len(X_test)
        }
    
    def predict_result(self, home_team, away_team, match_date, season):
        """
        Dự đoán kết quả và xác suất
        
        Returns:
            dict: {
                'predicted_result': int (1=Win, 0=Draw, -1=Loss),
                'probabilities': {'win': float, 'draw': float, 'loss': float}
            }
        """
        if not self.is_trained:
            raise ValueError("Model chưa được training!")
        
        features = build_match_features(home_team, away_team, match_date, season)
        features_df = pd.DataFrame([features])
        
        # Ensure all feature columns exist
        for col in self.feature_columns:
            if col not in features_df.columns:
                features_df[col] = 0
        
        features_df = features_df[self.feature_columns]
        
        # Predict
        result = self.model.predict(features_df)[0]
        probabilities = self.model.predict_proba(features_df)[0]
        
        # Map probabilities to labels
        # Classes are sorted: [-1, 0, 1]
        classes = self.model.classes_
        prob_dict = dict(zip(classes, probabilities))
        
        return {
            'predicted_result': int(result),
            'probabilities': {
                'win': prob_dict.get(1, 0.0),
                'draw': prob_dict.get(0, 0.0),
                'loss': prob_dict.get(-1, 0.0)
            }
        }
    
    def get_feature_importance(self):
        """Trả về feature importance"""
        if not self.is_trained:
            return {}
        
        importance = dict(zip(self.feature_columns, self.model.feature_importances_))
        # Sort by importance
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
    
    def save_model(self, filepath=None):
        """Lưu model"""
        if not self.is_trained:
            raise ValueError("Model chưa được training!")
        
        if filepath is None:
            model_dir = os.path.join(settings.MEDIA_ROOT, 'ml_models')
            os.makedirs(model_dir, exist_ok=True)
            filepath = os.path.join(model_dir, 'random_forest_predictor.pkl')
        
        model_data = {
            'model': self.model,
            'feature_columns': self.feature_columns,
            'is_trained': self.is_trained
        }
        
        joblib.dump(model_data, filepath)
        return filepath
    
    def load_model(self, filepath=None):
        """Load model"""
        if filepath is None:
            filepath = os.path.join(settings.MEDIA_ROOT, 'ml_models', 'random_forest_predictor.pkl')
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        model_data = joblib.load(filepath)
        self.model = model_data['model']
        self.feature_columns = model_data['feature_columns']
        self.is_trained = model_data['is_trained']


class EnsemblePredictor:
    """
    Kết hợp cả 2 models để đưa ra prediction tốt nhất
    """
    
    def __init__(self):
        self.poisson_model = PoissonRegressionPredictor()
        self.rf_model = RandomForestResultPredictor()
        self. model_version = "v1.0"
    
    def train(self, training_data):
        """Train cả 2 models"""
        print("Training Poisson Regression model...")
        poisson_metrics = self.poisson_model.train(training_data)
        
        print("Training Random Forest model...")
        rf_metrics = self.rf_model.train(training_data)
        
        return {
            'poisson_metrics': poisson_metrics,
            'rf_metrics': rf_metrics
        }
    
    def predict(self, home_team, away_team, match_date, season):
        """
        Dự đoán toàn diện cho một trận đấu
        
        Returns:
            dict: {
                'predicted_home_score': int,
                'predicted_away_score': int,
                'win_probability': float,
                'draw_probability': float,
                'loss_probability': float,
                'confidence_score': float
            }
        """
        # Get predictions from Poisson model
        poisson_pred = self.poisson_model.predict_score(
            home_team, away_team, match_date, season
        )
        
        poisson_probs = self.poisson_model.calculate_probabilities(
            poisson_pred['home_lambda'],
            poisson_pred['away_lambda']
        )
        
        # Get predictions from Random Forest
        rf_pred = self.rf_model.predict_result(
            home_team, away_team, match_date, season
        )
        
        # Ensemble probabilities (average)
        win_prob = (poisson_probs['win'] + rf_pred['probabilities']['win']) / 2
        draw_prob = (poisson_probs['draw'] + rf_pred['probabilities']['draw']) / 2
        loss_prob = (poisson_probs['loss'] + rf_pred['probabilities']['loss']) / 2
        
        # --- HEURISTIC: ĐIỀU CHỈNH THEO BXH (YÊU CẦU BẮT BUỘC) ---
        # Lấy Ranking hiện tại
        features = build_match_features(home_team, away_team, match_date, season)
        home_rank = features.get('home_rank', 14)
        away_rank = features.get('away_rank', 14)
        rank_diff = features.get('rank_diff', 0) # Home - Away
        
        # Rule 1: Top 1 vs Top 10+ (Chênh lệch cực lớn)
        if home_rank == 1 and away_rank >= 10:
            win_prob = max(win_prob, 0.90)
            loss_prob = min(loss_prob, 0.05)
            draw_prob = min(draw_prob, 0.05)
        elif away_rank == 1 and home_rank >= 10:
            loss_prob = max(loss_prob, 0.90)
            win_prob = min(win_prob, 0.05)
            draw_prob = min(draw_prob, 0.05)
            
        # Rule 2: Chênh lệch thứ hạng đáng kể (> 5 bậc)
        elif rank_diff <= -5: # Home rank nhỏ hơn (tốt hơn) nhiều (VD: 3 vs 9 -> -6)
            win_prob += 0.2
            loss_prob -= 0.1
            draw_prob -= 0.1
        elif rank_diff >= 5: # Home rank lớn hơn (tệ hơn) nhiều (VD: 9 vs 3 -> 6)
            loss_prob += 0.2
            win_prob -= 0.1
            draw_prob -= 0.1
            
        # Normalize (Đảm bảo tổng = 1)
        win_prob = max(0.01, win_prob)
        draw_prob = max(0.01, draw_prob)
        loss_prob = max(0.01, loss_prob)
        total = win_prob + draw_prob + loss_prob
        win_prob /= total
        draw_prob /= total
        loss_prob /= total

        # Confidence score (based on max probability)
        confidence = max(win_prob, draw_prob, loss_prob)
        
        # --- LOGIC ĐIỀU CHỈNH TỈ SỐ CHO KHỚP VỚI XÁC SUẤT ---
        # (Tránh trường hợp xác suất THUA cao nhất nhưng dự đoán tỉ số là 1-1)
        
        probs = {'win': win_prob, 'draw': draw_prob, 'loss': loss_prob}
        likely_outcome = max(probs, key=probs.get)
        
        home_score = poisson_pred['home_score']
        away_score = poisson_pred['away_score']
        
        if likely_outcome == 'win' and home_score <= away_score:
            # Nếu dự đoán THẮNG nhưng tỉ số lại hòa hoặc thua -> Tăng bàn thắng chủ nhà
            home_score = away_score + 1
            
        elif likely_outcome == 'loss' and home_score >= away_score:
            # Nếu dự đoán THUA nhưng tỉ số lại hòa hoặc thắng -> Tăng bàn thắng đội khách
            away_score = home_score + 1
            
        elif likely_outcome == 'draw' and home_score != away_score:
            # Nếu dự đoán HÒA nhưng tỉ số lại chênh lệch -> Lấy trung bình làm tròn
            avg_score = round((home_score + away_score) / 2)
            home_score = int(avg_score)
            away_score = int(avg_score)

        return {
            'predicted_home_score': home_score,
            'predicted_away_score': away_score,
            'win_probability': win_prob,
            'draw_probability': draw_prob,
            'loss_probability': loss_prob,
            'confidence_score': confidence,
            'model_version': self.model_version
        }
    
    def save_models(self):
        """Lưu cả 2 models"""
        poisson_path = self.poisson_model.save_model()
        rf_path = self.rf_model.save_model()
        return {'poisson': poisson_path, 'rf': rf_path}
    
    def load_models(self):
        """Load cả 2 models"""
        self.poisson_model.load_model()
        self.rf_model.load_model()
