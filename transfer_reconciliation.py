"""
CEX Transfer Reconciliation Tool
=================================
Reconciles CEX Transfer Tools data against All Transfers History ledger.

Input:
- cex_transfer_tools.csv (internal API transfers)
- all_transfers_history.csv (complete ledger)

Output:
- transfer_reconciliation_YYYY-MM-DD-HHMM.xlsx with 3 sheets:
  1. Missing Transfers - CEX tools transfers not found in ledger
  2. CEX Tools Data - All CEX tools transfers
  3. All Transfers History - Complete ledger
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('transfer_reconciliation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Fix console encoding for Windows
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass


class TransferReconciliation:
    """Reconcile CEX transfers against ledger."""
    
    def __init__(self, cex_file, ledger_file):
        """
        Initialize reconciliation.
        
        Args:
            cex_file (str): Path to CEX Transfer Tools CSV
            ledger_file (str): Path to All Transfers History CSV
        """
        self.cex_file = Path(cex_file)
        self.ledger_file = Path(ledger_file)
        self.df_cex = None
        self.df_ledger = None
        self.df_missing = None
        self.stats = {}
        
    def load_data(self):
        """Load both CSV files."""
        logging.info("=" * 80)
        logging.info("Loading data files...")
        
        try:
            # Load CEX tools data
            self.df_cex = pd.read_csv(self.cex_file)
            logging.info(f"[OK] Loaded CEX Transfer Tools: {len(self.df_cex)} records")
            
            # Load ledger data
            self.df_ledger = pd.read_csv(self.ledger_file)
            logging.info(f"[OK] Loaded All Transfers History: {len(self.df_ledger)} records")
            
            # Convert timestamps to datetime for comparison
            self.df_cex['timestamp'] = pd.to_datetime(self.df_cex['timestamp'])
            self.df_ledger['timestamp'] = pd.to_datetime(self.df_ledger['timestamp'])
            
            return True
            
        except Exception as e:
            logging.error(f"Error loading data: {e}")
            return False
    
    def create_match_key(self, df):
        """
        Create composite key for matching transfers.
        
        Match criteria: timestamp + asset + quantity + from_account + to_account
        
        Args:
            df (pd.DataFrame): DataFrame to create keys for
            
        Returns:
            pd.Series: Match keys
        """
        # Round timestamp to minute (to handle slight timing differences)
        df_temp = df.copy()
        df_temp['timestamp_minute'] = df_temp['timestamp'].dt.floor('T')
        
        # Create composite key
        match_key = (
            df_temp['timestamp_minute'].astype(str) + '|' +
            df_temp['asset'].astype(str) + '|' +
            df_temp['quantity'].astype(str) + '|' +
            df_temp['from_account'].astype(str) + '|' +
            df_temp['to_account'].astype(str)
        )
        
        return match_key
    
    def find_missing_transfers(self):
        """Identify CEX transfers not in ledger."""
        logging.info("=" * 80)
        logging.info("Reconciling transfers...")
        
        # Create match keys
        cex_keys = self.create_match_key(self.df_cex)
        ledger_keys = self.create_match_key(self.df_ledger)
        
        # Find missing transfers (in CEX but not in ledger)
        missing_mask = ~cex_keys.isin(ledger_keys)
        self.df_missing = self.df_cex[missing_mask].copy()
        
        # Add analysis columns
        self.df_missing['days_since_transfer'] = (
            datetime.now() - self.df_missing['timestamp']
        ).dt.days
        
        self.df_missing['risk_level'] = self.df_missing.apply(self._assess_risk, axis=1)
        
        # Sort by timestamp (most recent first)
        self.df_missing = self.df_missing.sort_values('timestamp', ascending=False)
        
        # Calculate statistics
        self.stats = {
            'total_cex_transfers': len(self.df_cex),
            'total_ledger_entries': len(self.df_ledger),
            'matched_transfers': len(self.df_cex) - len(self.df_missing),
            'missing_transfers': len(self.df_missing),
            'match_rate': round((len(self.df_cex) - len(self.df_missing)) / len(self.df_cex) * 100, 2),
            'total_missing_usd': round(self.df_missing['usd_amount'].sum(), 2),
            'missing_by_status': self.df_missing['status'].value_counts().to_dict(),
            'missing_by_asset': self.df_missing['asset'].value_counts().to_dict(),
            'high_risk_count': len(self.df_missing[self.df_missing['risk_level'] == 'HIGH']),
            'medium_risk_count': len(self.df_missing[self.df_missing['risk_level'] == 'MEDIUM']),
            'low_risk_count': len(self.df_missing[self.df_missing['risk_level'] == 'LOW'])
        }
        
        # Log results
        logging.info("=" * 80)
        logging.info("RECONCILIATION RESULTS")
        logging.info(f"Total CEX Transfers: {self.stats['total_cex_transfers']}")
        logging.info(f"Matched in Ledger: {self.stats['matched_transfers']}")
        logging.info(f"Missing from Ledger: {self.stats['missing_transfers']}")
        logging.info(f"Match Rate: {self.stats['match_rate']}%")
        logging.info(f"Total Missing USD Value: ${self.stats['total_missing_usd']:,.2f}")
        
        if self.stats['missing_transfers'] > 0:
            logging.warning(f"\nRisk Breakdown:")
            logging.warning(f"  HIGH risk: {self.stats['high_risk_count']} transfers")
            logging.warning(f"  MEDIUM risk: {self.stats['medium_risk_count']} transfers")
            logging.warning(f"  LOW risk: {self.stats['low_risk_count']} transfers")
            
            logging.warning(f"\nMissing by Status:")
            for status, count in self.stats['missing_by_status'].items():
                logging.warning(f"  {status}: {count}")
        
        logging.info("=" * 80)
        
        return self.df_missing
    
    def _assess_risk(self, row):
        """
        Assess risk level of missing transfer.
        
        Criteria:
        - HIGH: Completed, >$10K, >3 days old
        - MEDIUM: Completed, >$1K OR >7 days old
        - LOW: Failed, pending, or recent
        """
        if row['status'] == 'failed':
            return 'LOW'
        
        if row['status'] == 'pending':
            if row['days_since_transfer'] > 1:
                return 'MEDIUM'
            return 'LOW'
        
        # Completed transfers
        if row['usd_amount'] > 10000 and row['days_since_transfer'] > 3:
            return 'HIGH'
        
        if row['usd_amount'] > 1000 or row['days_since_transfer'] > 7:
            return 'MEDIUM'
        
        return 'LOW'
    
    def generate_report(self, output_file=None):
        """
        Generate Excel report with 3 sheets.
        
        Args:
            output_file (str): Custom output filename (optional)
            
        Returns:
            str: Path to saved file
        """
        if output_file is None:
            datetime_str = datetime.now().strftime('%Y-%m-%d-%H%M')
            output_file = f"transfer_reconciliation_{datetime_str}.xlsx"
        
        output_path = Path(output_file)
        
        try:
            logging.info(f"Generating Excel report: {output_file}")
            
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                
                # Sheet 1: Missing Transfers
                df_missing_export = self.df_missing.copy()
                df_missing_export['timestamp'] = df_missing_export['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                df_missing_export.to_excel(writer, sheet_name='Missing Transfers', index=False)
                
                # Sheet 2: CEX Tools Data
                df_cex_export = self.df_cex.copy()
                df_cex_export['timestamp'] = df_cex_export['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                # Add matched indicator
                cex_keys = self.create_match_key(self.df_cex)
                ledger_keys = self.create_match_key(self.df_ledger)
                df_cex_export['in_ledger'] = cex_keys.isin(ledger_keys)
                df_cex_export.to_excel(writer, sheet_name='CEX Tools Data', index=False)
                
                # Sheet 3: All Transfers History
                df_ledger_export = self.df_ledger.copy()
                df_ledger_export['timestamp'] = df_ledger_export['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                df_ledger_export.to_excel(writer, sheet_name='All Transfers History', index=False)
                
                # Format sheets
                self._format_excel_sheets(writer)
            
            logging.info(f"[OK] Report saved: {output_file}")
            
            # Generate summary
            self._print_summary()
            
            return str(output_path)
            
        except Exception as e:
            logging.error(f"Error generating report: {e}")
            return None
    
    def _format_excel_sheets(self, writer):
        """Apply formatting to Excel sheets."""
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        
        # Format each sheet
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            
            # Format header row
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            
            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center')
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Special formatting for Missing Transfers sheet
            if sheet_name == 'Missing Transfers':
                # Color code risk levels
                for row in range(2, worksheet.max_row + 1):
                    risk_cell = None
                    # Find risk_level column
                    for col in range(1, worksheet.max_column + 1):
                        if worksheet.cell(1, col).value == 'risk_level':
                            risk_cell = worksheet.cell(row, col)
                            break
                    
                    if risk_cell and risk_cell.value:
                        if risk_cell.value == 'HIGH':
                            risk_cell.fill = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
                            risk_cell.font = Font(bold=True, color="FFFFFF")
                        elif risk_cell.value == 'MEDIUM':
                            risk_cell.fill = PatternFill(start_color="FFD93D", end_color="FFD93D", fill_type="solid")
                        elif risk_cell.value == 'LOW':
                            risk_cell.fill = PatternFill(start_color="6BCB77", end_color="6BCB77", fill_type="solid")
            
            # Freeze header row
            worksheet.freeze_panes = 'A2'
    
    def _print_summary(self):
        """Print executive summary."""
        print("\n" + "=" * 80)
        print("EXECUTIVE SUMMARY")
        print("=" * 80)
        
        if self.stats['missing_transfers'] == 0:
            print("\n[OK] All CEX transfers are recorded in the ledger!")
            print(f"Total transfers verified: {self.stats['total_cex_transfers']}")
        else:
            print(f"\n[!] ATTENTION REQUIRED")
            print(f"\nMissing Transfers: {self.stats['missing_transfers']} out of {self.stats['total_cex_transfers']}")
            print(f"Match Rate: {self.stats['match_rate']}%")
            print(f"Total Missing Value: ${self.stats['total_missing_usd']:,.2f}")
            
            print(f"\nRisk Assessment:")
            print(f"  [!] HIGH Priority: {self.stats['high_risk_count']} transfers")
            print(f"  [!] MEDIUM Priority: {self.stats['medium_risk_count']} transfers")
            print(f"  [ ] LOW Priority: {self.stats['low_risk_count']} transfers")
            
            if self.stats['high_risk_count'] > 0:
                print(f"\n[!] IMMEDIATE ACTION REQUIRED for {self.stats['high_risk_count']} high-risk transfers")
                print("    Review 'Missing Transfers' sheet for details")
        
        print("\n" + "=" * 80)
        print(f"Detailed report saved with 3 sheets:")
        print("  1. Missing Transfers - Requires investigation")
        print("  2. CEX Tools Data - All internal transfers")
        print("  3. All Transfers History - Complete ledger")
        print("=" * 80 + "\n")


def run_reconciliation(cex_file, ledger_file, output_file=None):
    """
    Execute transfer reconciliation.
    
    Args:
        cex_file (str): Path to CEX Transfer Tools CSV
        ledger_file (str): Path to All Transfers History CSV
        output_file (str): Custom output filename (optional)
        
    Returns:
        bool: Success status
    """
    try:
        reconciler = TransferReconciliation(cex_file, ledger_file)
        
        # Load data
        if not reconciler.load_data():
            return False
        
        # Find missing transfers
        reconciler.find_missing_transfers()
        
        # Generate report
        report_path = reconciler.generate_report(output_file)
        
        if report_path:
            logging.info(f"SUCCESS: Reconciliation completed. Report: {report_path}")
            return True
        
        return False
        
    except Exception as e:
        logging.error(f"CRITICAL ERROR: {e}")
        return False


if __name__ == "__main__":
    # Configuration
    CEX_FILE = "cex_transfer_tools.csv"
    LEDGER_FILE = "all_transfers_history.csv"
    
    # Run reconciliation
    run_reconciliation(CEX_FILE, LEDGER_FILE)
