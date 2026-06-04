#!/usr/bin/env python3
"""
신호 생성기 템플릿 (100점 시스템)
- DB의 실제 기술적 지표 활용
- 임계값: BUY≥20, SELL≤10 (실제 데이터에 맞춤)
"""
import sqlite3
import json
from datetime import datetime

class SignalGenerator:
    def __init__(self, db_path):
        self.db_path = db_path
        # ✅ 권장: 낮은 임계값 (실제 데이터 반영)
        self.buy_threshold = 20   # BUY 임계값
        self.sell_threshold = 10  # SELL 임계값
        
        # 100점 가중치 (합계 1.0)
        self.weights = {
            'trend': 0.45,      # 추세 45점
            'momentum': 0.30,   # 모멘텀 30점
            'macd': 0.20,        # MACD 20점
            'volume': 0.10,      # 거래량 10점
            'volatility': 0.10,   # 변동성 10점
            'price_change': 0.10   # 가격변화 10점
        }
    
    def get_latest_indicators(self, stock_code):
        """최신 기술적 지표 조회 (connection 항상 닫기)"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 최신 날짜 조회
            cursor.execute('''
            SELECT date FROM daily_prices 
            WHERE stock_code = ? 
            ORDER BY date DESC LIMIT 1
            ''', (stock_code,))
            latest_date = cursor.fetchone()
            if not latest_date:
                return None
            
            # 기술적 지표 조회
            cursor.execute('''
            SELECT indicator_type, value 
            FROM technical_indicators 
            WHERE stock_code = ? AND date = ?
            ''', (stock_code, latest_date[0]))
            
            indicators = {}
            for row in cursor.fetchall():
                key = row[0].lower()
                indicators[key] = row[1]
            
            return indicators
            
        except Exception as e:
            print(f"❌ 지표 조회 실패: {e}")
            return None
        finally:
            if conn:
                conn.close()  # ✅ 무조건 닫기
    
    def calculate_score(self, indicators):
        """100점 평가 (실제 지표 사용)"""
        if not indicators:
            return 0, {}
        
        score = 0
        details = {}
        
        # 1. 추세 (45점)
        ma5 = indicators.get('ma5', 0)
        ma20 = indicators.get('ma20', 0)
        ma60 = indicators.get('ma60', 0)
        
        trend_score = 0
        if ma5 > ma20 > ma60:
            trend_score = 45
        elif ma5 > ma20:
            trend_score = 30
        elif ma5 < ma20 < ma60:
            trend_score = 0
        else:
            trend_score = 15
        
        score += trend_score * self.weights['trend']
        details['trend'] = trend_score
        
        # 2. 모멘텀 (30점)
        rsi = indicators.get('rsi', 50)
        momentum_score = 30 if 50 <= rsi <= 70 else 15
        score += momentum_score * self.weights['momentum']
        details['momentum'] = momentum_score
        
        # 3. MACD (20점)
        macd_hist = indicators.get('macd_hist', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_score = 20 if macd_hist > 0 and macd_hist > macd_signal else 15 if macd_hist > 0 else 5
        score += macd_score * self.weights['macd']
        details['macd'] = macd_score
        
        # 4-6. 나머지 (10점씩)
        for key in ['volume', 'volatility', 'price_change']:
            score += 10 * self.weights[key]
            details[key] = 10
        
        return round(score), details

# 사용 예시
if __name__ == "__main__":
    gen = SignalGenerator('/home/june/trading_workspace/trading.db')
    indicators = gen.get_latest_indicators("005930")
    if indicators:
        score, details = gen.calculate_score(indicators)
        print(f"점수: {score}, 세부: {details}")