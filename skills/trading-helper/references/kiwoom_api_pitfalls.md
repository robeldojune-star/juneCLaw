# 키움 API 함정 모음 (2026-05-28 발견!)

## ⚠️ Critical Findings

### 1. API URLs vary by endpoint!
```python
# ❌ Wrong: Using same URL for all APIs
url = f"{base_url}/api/dostk/stkinfo"  # ❌ 1504 error for ka10081!

# ✅ Correct: Different URLs for different APIs
# ka10030, ka10031: /api/dostk/rkinfo
# ka10081 (주식일봉차트조회): /api/dostk/chart  ← ⚠️ Different!
# kt00004 (계좌평가현황): /api/dostk/acnt
```

### 2. Parameter names vary by API!
```python
# ❌ Wrong: Using same params for all APIs
body = {"stk_cd": "005930", "base_dt": "20260217"}  # Only works for ka10081!

# ✅ Correct: Different params per API
# ka10030 (당일거래량상위): mrkt_tp, sort_tp, mang_stk_incls, crd_tp, trde_qty_tp, prc_tp, trde_prica_tp, mrkt_open_tp, stex_tp
# ka10031 (전일거래량상위): mrkt_tp, qry_tp, rank_strt, rank_end, stex_tp
# ka10081 (주식일봉차트조회): stk_cd, base_dt, upd_stkpc_tp
# kt00004 (계좌평가현황): accno, pwd, qry_tp
```

### 3. Response data keys vary by API!
```python
# ❌ Wrong: Using same key for all APIs
data = response.json()['data']  # ❌ KeyError!

# ✅ Correct: Different keys per API
# ka10030: 'tdy_trde_qty_upper'
# ka10031: 'pred_trde_qty_upper'
# ka10081: 'stk_dt_pole_chart_qry'
```

### 4. Supabase Auth requires BOTH headers!
```python
# ❌ Wrong: Only one header
headers = {"apikey": supabase_key}  # ❌ 401 error!

# ✅ Correct: Both headers required
headers = {
    "apikey": supabase_key,          # ✅ Required!
    "Authorization": f"Bearer {supabase_key}"  # ✅ Required!
}
```

### 5. Rate Limiting (키움 API)
```python
# Always wait 2 seconds between requests!
import time
time.sleep(2)  # ✅ Required!

# Handle 429 errors
if response.status_code == 429:
    time.sleep(10)  # Wait 10 seconds on rate limit
```

## 📊 API Quick Reference

| API ID | Function | URL | Key Parameters | Response Key |
|---------|----------|-----|-----------------|--------------|
| ka10030 | 당일거래량상위 | /api/dostk/rkinfo | mrkt_tp, sort_tp, ... (9 params!) | tdy_trde_qty_upper |
| ka10031 | 전일거래량상위 | /api/dostk/rkinfo | mrkt_tp, qry_tp, rank_strt, rank_end | pred_trde_qty_upper |
| ka10081 | 주식일봉차트조회 | /api/dostk/chart | stk_cd, base_dt, upd_stkpc_tp | stk_dt_pole_chart_qry |
| kt00004 | 계좌평가현황 | /api/dostk/acnt | accno, pwd, qry_tp | (check response) |

## 💡 Lessons Learned

1. **Always check Excel file** (`키움_REST_API_문서.xlsx`) for exact API specs
2. **Don't assume** all APIs use same URL/params/response keys
3. **Test with small data** first (e.g., 5 stocks) before scaling to 50
4. **Supabase needs both headers** - this caused 401 errors multiple times
5. **Rate limiting is real** - always add time.sleep(2) between requests