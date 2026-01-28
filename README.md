# CEX Transfer Reconciliation Tool

Automated reconciliation of internal CEX transfer tools against the complete transfers ledger to identify missing or unrecorded transactions.

---

## 🎯 Business Problem

**Challenge:** Multiple transfer sources (CEX tools, Fireblocks, direct CEX, manual) create reconciliation complexity.

**Risk:** Transfers initiated via internal CEX tools may not appear in the ledger, causing:
- Accounting discrepancies
- Missing audit trails
- Untracked fund movements
- Compliance issues

**Solution:** Automated daily reconciliation identifies missing transfers immediately, prioritized by risk level.

---

## 📊 What It Does

### Input Files

**1. CEX Transfer Tools CSV** (`cex_transfer_tools.csv`)
- Source: Internal API transfer tool
- Contains: 100 transfers initiated via CEX tools
- Fields: timestamp, asset, quantity, usd_amount, from_account, to_account, status, user

**2. All Transfers History CSV** (`all_transfers_history.csv`)
- Source: Complete ledger (all sources)
- Contains: 200 total transfers (CEX tools + Fireblocks + direct CEX + manual)
- Fields: All above + from_address, to_address, from_team, to_team, source

### Output

**Excel Report** (`transfer_reconciliation_YYYY-MM-DD-HHMM.xlsx`)

**3 Sheets:**

1. **Missing Transfers** - CEX transfers not in ledger (requires action)
2. **CEX Tools Data** - All internal transfers with match status
3. **All Transfers History** - Complete ledger for reference

---

## 🚨 Risk Assessment

The tool automatically categorizes missing transfers:

### HIGH Risk (Immediate Action Required)
- Status: Completed
- Amount: >$10,000
- Age: >3 days old
- **Action:** Investigate immediately, may indicate system failure

### MEDIUM Risk (Review Within 24h)
- Status: Completed, >$1,000 OR >7 days old
- **Action:** Investigate within 1 business day

### LOW Risk (Monitor)
- Status: Failed or Pending
- Recent transfers (<3 days)
- **Action:** Normal processing delays, monitor

---

## 📈 Sample Results

```
RECONCILIATION RESULTS
Total CEX Transfers: 100
Matched in Ledger: 80
Missing from Ledger: 20
Match Rate: 80.0%
Total Missing USD Value: $1,831,202.36

Risk Breakdown:
  HIGH risk: 14 transfers
  MEDIUM risk: 5 transfers
  LOW risk: 1 transfer
```

---

## 🚀 Installation & Usage

### Prerequisites

```bash
pip install pandas openpyxl
```

### Running the Tool

```bash
python transfer_reconciliation.py
```

### Configuration

Edit `transfer_reconciliation.py` line 435:

```python
CEX_FILE = "cex_transfer_tools.csv"
LEDGER_FILE = "all_transfers_history.csv"
```

---

## 📋 Matching Logic

Transfers are matched using composite key:

```
timestamp (rounded to minute) + 
asset + 
quantity + 
from_account + 
to_account
```

**Why timestamp to minute?** Allows for slight timing differences between systems.

---

## 📊 Excel Report Details

### Sheet 1: Missing Transfers

**Columns:**
- All original fields from CEX tools
- `days_since_transfer` - How old the transfer is
- `risk_level` - HIGH / MEDIUM / LOW (color-coded)

**Formatting:**
- 🔴 RED = HIGH risk
- 🟡 YELLOW = MEDIUM risk  
- 🟢 GREEN = LOW risk
- Sorted by timestamp (newest first)
- Frozen header row

### Sheet 2: CEX Tools Data

**Additional column:**
- `in_ledger` - TRUE/FALSE indicating if found in ledger

### Sheet 3: All Transfers History

**Shows:**
- All 200 ledger entries
- Includes transfers from all sources:
  - `cex_tools` (80 records)
  - `fireblocks` (92 records)
  - `cex_direct` (17 records)
  - `manual` (11 records)

---

## 🔧 Customization

### Adjust Risk Criteria

Edit `_assess_risk()` method (line ~150):

```python
def _assess_risk(self, row):
    # HIGH: Completed, >$10K, >3 days old
    if row['usd_amount'] > 10000 and row['days_since_transfer'] > 3:
        return 'HIGH'
    
    # Customize thresholds here
    if row['usd_amount'] > 5000 or row['days_since_transfer'] > 5:
        return 'MEDIUM'
```

### Change Matching Logic

Edit `create_match_key()` method (line ~85):

```python
# Add status to matching criteria
match_key = (
    df_temp['timestamp_minute'].astype(str) + '|' +
    df_temp['asset'].astype(str) + '|' +
    df_temp['quantity'].astype(str) + '|' +
    df_temp['from_account'].astype(str) + '|' +
    df_temp['to_account'].astype(str) + '|' +
    df_temp['status'].astype(str)  # Add this line
)
```

### Add Email Alerts

Add after generating report:

```python
def send_alert_email(missing_count, high_risk_count):
    import smtplib
    from email.message import EmailMessage
    
    if high_risk_count > 0:
        msg = EmailMessage()
        msg['Subject'] = f'[URGENT] {high_risk_count} High-Risk Missing Transfers'
        msg['From'] = 'reconciliation@company.com'
        msg['To'] = 'treasury@company.com'
        msg.set_content(f'{missing_count} transfers missing, {high_risk_count} HIGH RISK')
        
        with smtplib.SMTP('smtp.company.com') as smtp:
            smtp.send_message(msg)

# Call after reconciliation
send_alert_email(stats['missing_transfers'], stats['high_risk_count'])
```

---

## 📅 Recommended Schedule

Run **daily** at end of business day:

```bash
# Windows Task Scheduler (5:30 PM daily)
schtasks /create /tn "Transfer Reconciliation" /tr "python C:\path\to\transfer_reconciliation.py" /sc daily /st 17:30

# Linux cron (5:30 PM daily)
30 17 * * * /usr/bin/python3 /path/to/transfer_reconciliation.py
```

---

## 🎓 Technical Highlights

**Skills Demonstrated:**
- ✅ Data reconciliation algorithms
- ✅ Multi-source data integration
- ✅ Risk scoring and prioritization
- ✅ Pandas data manipulation
- ✅ Excel report automation with formatting
- ✅ Production logging and error handling
- ✅ Cryptocurrency operations knowledge

---

## 📊 Mock Data Breakdown

### CEX Transfer Tools (100 records)

**Account Types:**
- Sub-account to sub-account: 70%
- Exchange to sub-account: 20%
- Sub-account to exchange: 10%

**Status:**
- Completed: 95%
- Pending: 3%
- Failed: 2%

**Exchanges:** Binance, Kraken, Kucoin

### All Transfers History (200 records)

**Sources:**
- Fireblocks: 92 records (46%)
- CEX Tools: 80 records (40%)
- Direct CEX: 17 records (8.5%)
- Manual: 11 records (5.5%)

**Missing:** 20 CEX tool transfers (20%) intentionally omitted

---

## 🐛 Troubleshooting

### "File not found" error
- Ensure CSV files are in same directory as script
- Check file names match exactly

### Wrong number of missing transfers
- Verify timestamp formats are consistent
- Check if quantity precision matches (decimals)

### All transfers showing as missing
- Verify matching logic in `create_match_key()`
- Check timestamp rounding (minute vs second)

---

## 📈 Real-World Usage

### Daily Workflow

1. **8:00 AM** - Export CEX tools transfers (yesterday)
2. **8:30 AM** - Export all transfers history (yesterday)
3. **9:00 AM** - Run reconciliation script
4. **9:05 AM** - Review Missing Transfers sheet
5. **9:30 AM** - Investigate HIGH risk transfers
6. **EOD** - Close out reconciliation items

### Escalation Path

- **HIGH risk** → Immediate investigation by treasury team
- **MEDIUM risk** → Review within 24 hours
- **LOW risk** → Monitor, resolve within 3 days

---

## 🎯 Key Metrics to Track

Monitor these KPIs:
- **Match Rate** (target: >95%)
- **High-Risk Count** (target: 0)
- **Average Resolution Time** (target: <24h for HIGH)
- **Total Missing USD** (track trends over time)

---

## 📝 Sample Output Files

**Included in this package:**

1. `cex_transfer_tools.csv` - Mock CEX tools data (100 records)
2. `all_transfers_history.csv` - Mock ledger data (200 records)
3. `transfer_reconciliation.py` - Main reconciliation script
4. `transfer_reconciliation_2026-01-28-0713.xlsx` - Sample output report

---
