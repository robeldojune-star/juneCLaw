from pathlib import Path
import sys, json
sys.path.insert(0, '/home/june/trading')
import pandas as pd
import numpy as np
from core.supabase_rest import SupabaseRestClient

sb=SupabaseRestClient()
stocks=['005930','000660','035420','005380','068270']
all_rows=[]
for code in stocks:
    offset=0
    while True:
        rows=sb.get('intraday_prices', params={
            'select':'stock_code,timestamp,time_frame,source,open,high,low,close,volume',
            'stock_code':f'eq.{code}',
            'time_frame':'eq.1min',
            'source':'eq.kiwoom_ka10080_minute',
            'order':'timestamp.asc',
            'limit':'1000',
            'offset':str(offset),
        }, timeout=60)
        if not rows: break
        all_rows.extend(rows)
        if len(rows)<1000: break
        offset += len(rows)

df=pd.DataFrame(all_rows)
if df.empty:
    print(json.dumps({'error':'no rows'}, ensure_ascii=False)); raise SystemExit
for c in ['open','high','low','close','volume']:
    df[c]=pd.to_numeric(df[c], errors='coerce').abs()
df['timestamp']=pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert('Asia/Seoul')
df['day']=df['timestamp'].dt.date.astype(str)
df=df.sort_values(['stock_code','timestamp']).reset_index(drop=True)

FEE_BPS=23.0; SLIP_BPS=10.0
round_trip_cost_pct=2*(FEE_BPS+SLIP_BPS)/100.0

def add_indicators_one(g):
    g=g.copy().sort_values('timestamp')
    g['ma5']=g['close'].rolling(5).mean()
    g['ma20']=g['close'].rolling(20).mean()
    g['disparity20']=g['close']/g['ma20']*100
    tp=(g['high']+g['low']+g['close'])/3
    ma_tp=tp.rolling(20).mean()
    md=(tp-ma_tp).abs().rolling(20).mean()
    g['cci']=(tp-ma_tp)/(0.015*md)
    g['vol_ma20']=g['volume'].rolling(20).mean()
    delta=g['close'].diff(); up=delta.clip(lower=0); down=-delta.clip(upper=0)
    ma_up=up.ewm(com=13, adjust=False).mean(); ma_down=down.ewm(com=13, adjust=False).mean()
    rs=ma_up/ma_down
    g['rsi']=100-(100/(1+rs))
    return g

def add_indicators(g):
    return pd.concat([add_indicators_one(part) for _, part in g.groupby('stock_code', sort=False)], ignore_index=True)

def simulate(g, variant):
    g=add_indicators(g)
    trades=[]
    counters={'raw_entry_bars':0,'edge_entry_bars':0,'raw_exit_bars':0,'edge_exit_bars':0,'forced_open_positions':0}
    for (code, day), d in g.groupby(['stock_code','day'], sort=True):
        d=d.sort_values('timestamp').reset_index(drop=True)
        if len(d)<40: continue
        if variant=='disparity_cci_rsi_exit_100':
            entry=(d['disparity20']<=100) & (d['cci'].shift(1)<=-100) & (d['cci']>-100) & (d['volume']>=d['vol_ma20'])
            exit_sig=(d['rsi'].shift(1)>=70) & (d['rsi']<70)
        elif variant=='disparity_cci_rsi_exit_95':
            entry=(d['disparity20']<=95) & (d['cci'].shift(1)<=-100) & (d['cci']>-100) & (d['volume']>=d['vol_ma20'])
            exit_sig=(d['rsi'].shift(1)>=70) & (d['rsi']<70)
        elif variant=='rsi_cci_oversold_overbought':
            entry=(d['rsi']<30) & (d['cci']<-100) & (d['close']>d['ma5'])
            exit_sig=(d['rsi']>70) & (d['cci']>100) & (d['close']<d['ma5'])
        else:
            raise ValueError(variant)
        d['entry']=entry & (~entry.shift(1).fillna(False))
        d['exit']=exit_sig & (~exit_sig.shift(1).fillna(False))
        counters['raw_entry_bars'] += int(entry.fillna(False).sum())
        counters['edge_entry_bars'] += int(d['entry'].fillna(False).sum())
        counters['raw_exit_bars'] += int(exit_sig.fillna(False).sum())
        counters['edge_exit_bars'] += int(d['exit'].fillna(False).sum())
        in_pos=False; ep=None; et=None
        for _, row in d.iterrows():
            t=row['timestamp']
            if not in_pos and bool(row['entry']) and pd.notna(row['close']):
                in_pos=True; ep=float(row['close']); et=t
            elif in_pos:
                time_exit = t.strftime('%H:%M') >= '15:20'
                if bool(row['exit']) or time_exit:
                    xp=float(row['close'])
                    gross=(xp-ep)/ep*100
                    net=gross-round_trip_cost_pct
                    trades.append({'variant':variant,'stock_code':code,'day':day,'entry_time':str(et),'exit_time':str(t),'entry_price':ep,'exit_price':xp,'gross_return_pct':gross,'net_return_pct':net,'exit_reason':'signal_exit' if bool(row['exit']) else 'time_exit'})
                    in_pos=False; ep=None; et=None
        if in_pos:
            counters['forced_open_positions'] += 1
    return trades, counters

variants=['disparity_cci_rsi_exit_100','disparity_cci_rsi_exit_95','rsi_cci_oversold_overbought']
all_trades=[]; summary={}
for v in variants:
    tr,counters=simulate(df, v); all_trades += tr
    rets=[x['net_return_pct'] for x in tr]
    gross=[x['gross_return_pct'] for x in tr]
    wins=sum(1 for r in rets if r>0)
    losses=[r for r in rets if r<0]
    gains=[r for r in rets if r>0]
    summary[v]={
        'trades':len(tr),
        'win_rate':round(wins/len(tr)*100,4) if tr else None,
        'avg_gross_return_pct':round(float(np.mean(gross)),4) if tr else None,
        'avg_net_return_pct':round(float(np.mean(rets)),4) if tr else None,
        'median_net_return_pct':round(float(np.median(rets)),4) if tr else None,
        'profit_factor':round(sum(gains)/abs(sum(losses)),4) if losses and gains else None,
        'signal_counters':counters,
        'exit_reason_counts':pd.Series([x['exit_reason'] for x in tr]).value_counts().to_dict() if tr else {},
        'by_stock':pd.DataFrame(tr).groupby('stock_code')['net_return_pct'].agg(['count','mean']).round(4).to_dict('index') if tr else {},
    }

out={'dataset':{'rows':len(df),'stock_days':int(df.groupby(['stock_code','day']).ngroups),'stocks':stocks,'round_trip_cost_pct':round(round_trip_cost_pct,4),'date_min':str(df['timestamp'].min()),'date_max':str(df['timestamp'].max())},'summary':summary,'sample_trades':all_trades[:20]}
Path('/home/june/trading/reports/rsi_cci_current_backtest.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False, indent=2))
