"""Recompute saved prediction metrics without training."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('predictions',type=Path); args=ap.parse_args()
    if not args.predictions.is_file(): ap.error('Prediction CSV missing. Restore authorized artifacts or run scripts/train_dkt.py.')
    sys.path.insert(0,str(ROOT/'kt_demo'))
    import pandas as pd
    from core import metrics
    df=pd.read_csv(args.predictions)
    if not {'event_id','label','probability'}.issubset(df): ap.error('Expected event_id,label,probability columns')
    if not df.event_id.is_unique or not df.label.isin([0,1]).all(): ap.error('Invalid labels or repeated event IDs')
    print(json.dumps(metrics(df),indent=2))
if __name__=='__main__': main()
