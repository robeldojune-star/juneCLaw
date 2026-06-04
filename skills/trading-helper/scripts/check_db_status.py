#!/usr/bin/env python3
"""
DB 상태 확인 스크립트 (재실행 가능)
- 8개 테이블 현황
- 기술적 지표 샘플
- BUY/SELL/HOLD 신호 개수
"""
import sqlite3
import sys

DB_PATH = '/home/june/trading_workspace/trading.db'

def check_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("=" * 50)
        print("📊 DB 상태 확인")
        print("=" * 50)
        
        # 1. 테이블 목록
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\n📋 테이블 개수: {len(tables)}개")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"  - {table[0]:25}: {count:>5}건")
        
        # 2. technical_indicators 샘플
        print(f"\n📈 technical_indicators 샘플 (상위 5개):")
        cursor.execute('''
        SELECT stock_code, date, indicator_type, value 
        FROM technical_indicators 
        ORDER BY stock_code, date
        LIMIT 5
        ''')
        for row in cursor.fetchall():
            print(f"  {row[0]} | {row[1]} | {row[2]:10} | {row[3]:.2f}")
        
        # 3. 지표 타입별 개수
        print(f"\n📊 지표 타입별 개수:")
        cursor.execute('''
        SELECT indicator_type, COUNT(*) 
        FROM technical_indicators 
        GROUP BY indicator_type
        ''')
        for row in cursor.fetchall():
            print(f"  {row[0]:10}: {row[1]:>4}개")
        
        # 4. trading_signals 신호 개수
        print(f"\n📉 매매 신호 현황:")
        cursor.execute('''
        SELECT signal_type, COUNT(*) 
        FROM trading_signals 
        GROUP BY signal_type
        ''')
        signals = cursor.fetchall()
        for sig in signals:
            print(f"  {sig[0]:5}: {sig[1]:>3}개")
        
        # 5. positions 보유 종목
        print(f"\n💼 현재 보유 종목:")
        cursor.execute('''
        SELECT stock_code, quantity, avg_price, current_price
        FROM positions
        ''')
        positions = cursor.fetchall()
        if positions:
            for pos in positions:
                print(f"  {pos[0]} | 수량: {pos[1]}주 | 평단가: {pos[2]:,.0f}원 | 현재가: {pos[3]:,.0f}원")
        else:
            print("  ⚪ 보유 종목 없음")
        
        # 6. orders 주문 내역
        print(f"\n📝 주문 내역:")
        cursor.execute('''
        SELECT COUNT(*) FROM orders
        ''')
        order_count = cursor.fetchone()[0]
        print(f"  총 {order_count}건")
        
        conn.close()
        print("\n" + "=" * 50)
        print("✅ DB 상태 확인 완료")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_db()
